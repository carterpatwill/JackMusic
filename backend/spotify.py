"""Spotify Web API helpers for the data this app's access tier DOES return:
artist image and discography (album/single list with art + release dates).

Note: this tier does NOT return followers/popularity/genres (see CLAUDE.md),
and the albums endpoint rejects limit>20, so we cap it.

Token + artist fetch are shared with refresh.py.
"""

import base64
import os
import time

import requests

from . import usage

TOKEN_URL = "https://accounts.spotify.com/api/token"
ARTIST_URL = "https://api.spotify.com/v1/artists/{id}"
ALBUMS_URL = "https://api.spotify.com/v1/artists/{id}/albums"
TIMEOUT = 15
ALBUM_LIMIT = 10  # this tier 400s above 10
ALBUM_MAX_PAGES = 4  # paginate up to 40 releases

# Simple in-process token + response cache so we don't re-auth / re-fetch on
# every page click.
_token_cache = {"value": None, "expires": 0.0}
_ALBUMS_TTL = 24 * 3600  # releases change rarely; cached in the DB (db.cache_*)


class SpotifyError(RuntimeError):
    pass


def get_token():
    now = time.time()
    if _token_cache["value"] and _token_cache["expires"] > now + 30:
        return _token_cache["value"]
    cid = os.environ.get("SPOTIFY_CLIENT_ID")
    secret = os.environ.get("SPOTIFY_CLIENT_SECRET")
    if not cid or not secret:
        raise SpotifyError(
            "Missing SPOTIFY_CLIENT_ID / SPOTIFY_CLIENT_SECRET (see .env.example)"
        )
    auth = base64.b64encode(f"{cid}:{secret}".encode()).decode()
    resp = requests.post(
        TOKEN_URL,
        headers={"Authorization": f"Basic {auth}"},
        data={"grant_type": "client_credentials"},
        timeout=TIMEOUT,
    )
    resp.raise_for_status()
    data = resp.json()
    _token_cache["value"] = data["access_token"]
    _token_cache["expires"] = now + data.get("expires_in", 3600)
    return _token_cache["value"]


def _best_image(images, idx=0):
    """images is Spotify's list (largest first). idx 0 = largest."""
    if not images:
        return None
    return images[min(idx, len(images) - 1)]["url"]


def get_artist_image(token, spotify_id):
    resp = requests.get(
        ARTIST_URL.format(id=spotify_id),
        headers={"Authorization": f"Bearer {token}"},
        timeout=TIMEOUT,
    )
    resp.raise_for_status()
    data = resp.json()
    return {
        "name": data.get("name"),
        "image": _best_image(data.get("images")),
        "url": data.get("external_urls", {}).get("spotify"),
    }


def get_albums(token, spotify_id):
    """Return the artist's own releases (albums + singles, not features),
    deduped by title, newest first. Paginates because this tier caps limit=10."""
    headers = {"Authorization": f"Bearer {token}"}
    items = []
    for page in range(ALBUM_MAX_PAGES):
        resp = requests.get(
            ALBUMS_URL.format(id=spotify_id),
            params={
                "limit": ALBUM_LIMIT,
                "offset": page * ALBUM_LIMIT,
                "include_groups": "album,single",  # compilations cost extra pages
            },
            headers=headers,
            timeout=TIMEOUT,
        )
        resp.raise_for_status()
        batch = resp.json().get("items", [])
        items.extend(batch)
        if len(batch) < ALBUM_LIMIT:
            break  # last page

    seen = set()
    albums = []
    for a in items:
        if a.get("album_group") == "appears_on":
            continue
        key = (a.get("name") or "").strip().lower()
        if not key or key in seen:
            continue
        seen.add(key)
        albums.append(
            {
                "name": a.get("name"),
                "type": a.get("album_type"),
                "release_date": a.get("release_date"),
                "total_tracks": a.get("total_tracks"),
                "image": _best_image(a.get("images"), 1) or _best_image(a.get("images")),
                "url": a.get("external_urls", {}).get("spotify"),
            }
        )

    albums.sort(key=lambda x: x["release_date"] or "", reverse=True)
    return albums


def artist_detail(spotify_id):
    """Artist image + discography. Cached in the database for a day; if
    Spotify fails or is rate-limiting, the last good copy is returned."""
    from . import db

    key = f"spotify:artist:{spotify_id}"
    fresh = db.cache_get(key, max_age=_ALBUMS_TTL)
    if fresh:
        return fresh
    stale = db.cache_get(key)
    if not usage.live_apis() or usage.is_blocked("spotify"):
        if stale:
            return stale
        usage.require_live("Spotify")
        raise SpotifyError("Spotify is rate-limiting this app; try again later.")
    try:
        token = get_token()
        info = get_artist_image(token, spotify_id)
        payload = {
            "name": info["name"],
            "image": info["image"],
            "url": info["url"],
            "albums": get_albums(token, spotify_id),
        }
    except requests.HTTPError as e:
        resp = e.response
        if resp is not None and resp.status_code == 429:
            # Saved in the database so restarts wait it out too.
            wait = float(resp.headers.get("Retry-After") or 60)
            usage.block("spotify", min(wait, 24 * 3600))
        if stale:
            return stale
        raise
    db.cache_put(key, payload)
    return payload
