"""Fetch live stats from Spotify + YouTube and store a snapshot per artist.

This is the ONLY place the API keys are used. It runs server-side (locally),
never in the browser, so the Spotify secret is never exposed.

Run standalone:   python -m backend.refresh
Or it's called by POST /api/refresh in app.py (the UI "Refresh" button).

Keys come from the environment (.env):
    SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET, YOUTUBE_API_KEY
"""

import base64
import os
import re
from datetime import datetime, timezone

import requests

from . import db, instagram

SPOTIFY_TOKEN_URL = "https://accounts.spotify.com/api/token"
SPOTIFY_ARTIST_URL = "https://api.spotify.com/v1/artists/{id}"
YT_VIDEOS_URL = "https://www.googleapis.com/youtube/v3/videos"
YT_CHANNELS_URL = "https://www.googleapis.com/youtube/v3/channels"

TIMEOUT = 15


class RefreshError(RuntimeError):
    pass


# ---------------------------------------------------------------- Spotify ----
def _spotify_token():
    cid = os.environ.get("SPOTIFY_CLIENT_ID")
    secret = os.environ.get("SPOTIFY_CLIENT_SECRET")
    if not cid or not secret:
        raise RefreshError(
            "Missing SPOTIFY_CLIENT_ID / SPOTIFY_CLIENT_SECRET (see .env.example)"
        )
    auth = base64.b64encode(f"{cid}:{secret}".encode()).decode()
    resp = requests.post(
        SPOTIFY_TOKEN_URL,
        headers={"Authorization": f"Basic {auth}"},
        data={"grant_type": "client_credentials"},
        timeout=TIMEOUT,
    )
    resp.raise_for_status()
    return resp.json()["access_token"]


def _spotify_artist(token, spotify_id):
    resp = requests.get(
        SPOTIFY_ARTIST_URL.format(id=spotify_id),
        headers={"Authorization": f"Bearer {token}"},
        timeout=TIMEOUT,
    )
    resp.raise_for_status()
    data = resp.json()
    return {
        "followers": data.get("followers", {}).get("total"),
        "popularity": data.get("popularity"),
    }


# ---------------------------------------------------------------- YouTube ----
_VIDEO_ID_RE = re.compile(r"(?:youtu\.be/|v=|/embed/|/shorts/)([A-Za-z0-9_-]{11})")


def _extract_video_id(url):
    if not url:
        return None
    m = _VIDEO_ID_RE.search(url)
    return m.group(1) if m else None


_CHANNEL_ID_RE = re.compile(r"youtube\.com/channel/(UC[A-Za-z0-9_-]{22})")


def channel_id_from_url(api_key, url):
    """youtube_url in seed.py may be a channel URL (youtube.com/channel/UC...)
    or any video URL, in which case the video's channel is looked up."""
    m = _CHANNEL_ID_RE.search(url or "")
    if m:
        return m.group(1)
    vid = _extract_video_id(url)
    return _yt_channel_id_from_video(api_key, vid) if vid else None


def _yt_channel_id_from_video(api_key, video_id):
    resp = requests.get(
        YT_VIDEOS_URL,
        params={"part": "snippet", "id": video_id, "key": api_key},
        timeout=TIMEOUT,
    )
    resp.raise_for_status()
    items = resp.json().get("items", [])
    if not items:
        return None
    return items[0]["snippet"]["channelId"]


def _yt_channel_stats(api_key, channel_id):
    resp = requests.get(
        YT_CHANNELS_URL,
        params={"part": "statistics", "id": channel_id, "key": api_key},
        timeout=TIMEOUT,
    )
    resp.raise_for_status()
    items = resp.json().get("items", [])
    if not items:
        return {"subs": None, "views": None}
    s = items[0]["statistics"]
    subs = None if s.get("hiddenSubscriberCount") else s.get("subscriberCount")
    return {
        "subs": int(subs) if subs is not None else None,
        "views": int(s["viewCount"]) if "viewCount" in s else None,
    }


# ------------------------------------------------------------------- Main ----
def refresh_week(week_of=None):
    """Fetch stats for every artist in the week and insert a snapshot row each.
    Returns a per-artist summary dict for the API response."""
    week_of = week_of or db.latest_week()
    yt_key = os.environ.get("YOUTUBE_API_KEY")

    token = _spotify_token()
    now = datetime.now(timezone.utc).isoformat()

    conn = db.connect()
    rows = conn.execute(
        "SELECT * FROM artists WHERE week_of = ? ORDER BY sort_order",
        (week_of,),
    ).fetchall()

    results = []
    for ar in rows:
        entry = {"slug": ar["slug"], "name": ar["name"], "errors": []}

        # --- Spotify ---
        followers = popularity = None
        if ar["spotify_id"]:
            try:
                sp = _spotify_artist(token, ar["spotify_id"])
                followers, popularity = sp["followers"], sp["popularity"]
            except Exception as e:  # noqa: BLE001 - surface per-artist, keep going
                entry["errors"].append(f"spotify: {e}")

        # --- YouTube (resolve channel id once, then cache it) ---
        subs = views = None
        channel_id = ar["youtube_channel_id"]
        if yt_key and ar["youtube_url"]:
            try:
                if not channel_id:
                    channel_id = channel_id_from_url(yt_key, ar["youtube_url"])
                    if channel_id:
                        conn.execute(
                            "UPDATE artists SET youtube_channel_id = ? WHERE id = ?",
                            (channel_id, ar["id"]),
                        )
                if channel_id:
                    yt = _yt_channel_stats(yt_key, channel_id)
                    subs, views = yt["subs"], yt["views"]
            except Exception as e:  # noqa: BLE001
                entry["errors"].append(f"youtube: {e}")

        # --- Instagram (follower count via Business Discovery) ---
        ig_followers = None
        ig_user = instagram.username_from_url(ar["instagram_url"])
        if ig_user and instagram.configured():
            try:
                ig_followers = instagram.followers(ig_user)
            except Exception as e:  # noqa: BLE001
                entry["errors"].append(f"instagram: {e}")

        conn.execute(
            """INSERT INTO snapshots
                 (artist_id, captured_at, spotify_followers, spotify_popularity,
                  youtube_subs, youtube_views, instagram_followers)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (ar["id"], now, followers, popularity, subs, views, ig_followers),
        )
        entry.update(
            spotify_followers=followers,
            spotify_popularity=popularity,
            youtube_subs=subs,
            youtube_views=views,
            instagram_followers=ig_followers,
        )
        results.append(entry)

    conn.commit()
    conn.close()
    return {"week_of": week_of, "captured_at": now, "artists": results}


if __name__ == "__main__":
    from dotenv import load_dotenv

    load_dotenv()
    db.init_db()
    out = refresh_week()
    print(f"Snapshot taken at {out['captured_at']} for week {out['week_of']}:")
    for a in out["artists"]:
        line = (
            f"  {a['name']:<12} followers={a['spotify_followers']} "
            f"pop={a['spotify_popularity']} subs={a['youtube_subs']}"
        )
        if a["errors"]:
            line += f"  !! {'; '.join(a['errors'])}"
        print(line)
