"""Data behind each profile's "Explore the Data" charts.

Three real sources, combined by GET /api/artist/{slug}/history:

1. YouTube upload history: every video on the artist's channel with its
   publish date and CURRENT view count. YouTube doesn't give past view
   counts, so this shows growth release by release, not day by day.
2. Spotify releases: singles/albums with release dates (spotify.py).
3. Our own snapshots: the channel's total views/subs each time the site
   refreshed. This is the true over-time line, and it grows week by week.

YouTube + Spotify responses are cached in-process for a few hours; quota
cost is ~1 unit per 50 videos.
"""

import os
import time

import requests

from . import db, instagram, refresh, spotify

YT = "https://www.googleapis.com/youtube/v3"
TIMEOUT = 15
MAX_VIDEOS = 300
_TTL = 6 * 3600
_cache = {}  # channel_id -> (expires_ts, videos)


class HistoryError(RuntimeError):
    pass


def _get(path, **params):
    params["key"] = os.environ["YOUTUBE_API_KEY"]
    r = requests.get(f"{YT}/{path}", params=params, timeout=TIMEOUT)
    r.raise_for_status()
    return r.json()


def youtube_videos(channel_id):
    """Every upload on the channel: id, title, published (ISO), views.
    Oldest first."""
    hit = _cache.get(channel_id)
    if hit and hit[0] > time.time():
        return hit[1]

    items = _get("channels", part="contentDetails", id=channel_id).get("items", [])
    if not items:
        return []
    uploads = items[0]["contentDetails"]["relatedPlaylists"]["uploads"]

    ids, token = [], None
    try:
        while len(ids) < MAX_VIDEOS:
            params = {"part": "contentDetails", "playlistId": uploads, "maxResults": 50}
            if token:
                params["pageToken"] = token
            page = _get("playlistItems", **params)
            ids += [it["contentDetails"]["videoId"] for it in page.get("items", [])]
            token = page.get("nextPageToken")
            if not token:
                break
    except requests.HTTPError as e:
        if e.response is None or e.response.status_code != 404:
            raise
    if not ids:
        # Auto-generated "Artist - Topic" channels hide their uploads list;
        # search finds their tracks instead (100 quota units, cached).
        ids = _search_channel(channel_id)

    videos = []
    for i in range(0, len(ids), 50):
        data = _get("videos", part="snippet,statistics", id=",".join(ids[i:i + 50]))
        for v in data.get("items", []):
            views = v.get("statistics", {}).get("viewCount")
            videos.append({
                "id": v["id"],
                "title": v["snippet"]["title"],
                "published": v["snippet"]["publishedAt"],
                "views": int(views) if views is not None else 0,
            })
    videos.sort(key=lambda v: v["published"])
    _cache[channel_id] = (time.time() + _TTL, videos)
    return videos


def _search_channel(channel_id, pages=2):
    ids, token = [], None
    for _ in range(pages):
        params = {"part": "id", "channelId": channel_id, "type": "video",
                  "maxResults": 50, "order": "date"}
        if token:
            params["pageToken"] = token
        page = _get("search", **params)
        ids += [it["id"]["videoId"] for it in page.get("items", [])]
        token = page.get("nextPageToken")
        if not token:
            break
    return ids


def _channel_id(artist):
    """Cached channel id, or resolve it from the artist's video URL once."""
    if artist["youtube_channel_id"]:
        return artist["youtube_channel_id"]
    cid = refresh.channel_id_from_url(os.environ["YOUTUBE_API_KEY"], artist["youtube_url"])
    if cid:
        db.set_channel_id(artist["id"], cid)
    return cid


def artist_history(slug):
    artist = db.get_artist(slug)
    if not artist:
        return None

    out = {
        "name": artist["name"],
        "youtube": {"available": False, "videos": [], "error": None},
        "releases": [],
        "releases_error": None,
        "snapshots": db.get_snapshots(artist["id"]),
    }

    if artist["youtube_url"] and os.environ.get("YOUTUBE_API_KEY"):
        try:
            cid = _channel_id(artist)
            if cid:
                out["youtube"] = {
                    "available": True,
                    "channel_url": f"https://www.youtube.com/channel/{cid}",
                    "videos": youtube_videos(cid),
                    "error": None,
                }
        except Exception as e:  # noqa: BLE001 - one bad source shouldn't sink the page
            out["youtube"]["error"] = type(e).__name__

    ig_user = instagram.username_from_url(artist["instagram_url"])
    out["instagram"] = {"available": False, "username": ig_user, "posts": [], "error": None}
    if ig_user and instagram.configured():
        try:
            p = instagram.profile(ig_user)
            out["instagram"].update(available=True, followers=p["followers"],
                                    media_count=p["media_count"], posts=p["posts"])
        except Exception as e:  # noqa: BLE001 - e.g. a personal (non-business) account
            out["instagram"]["error"] = str(e)[:200]

    if artist["spotify_id"]:
        try:
            albums = spotify.artist_detail(artist["spotify_id"])["albums"]
            out["releases"] = sorted(
                (
                    {"name": a["name"], "type": a["type"],
                     "date": a["release_date"], "url": a["url"]}
                    for a in albums if a.get("release_date")
                ),
                key=lambda a: a["date"],
            )
        except Exception as e:  # noqa: BLE001
            out["releases_error"] = type(e).__name__

    return out
