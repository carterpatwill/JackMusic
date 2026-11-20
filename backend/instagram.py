"""Instagram data via Meta's Business Discovery API (free, official).

Our own Instagram Business/Creator account (linked to a Facebook Page) looks
up another Business/Creator account by username and gets its follower count
plus recent posts: date, likes, comments, and view counts for Reels.

Env:
    IG_USER_ID       - our Instagram business account id
    IG_ACCESS_TOKEN  - a Page access token (doesn't expire)
Both are produced once by:   python -m backend.instagram --setup
(which reads META_APP_ID, META_APP_SECRET and a short-lived IG_SETUP_TOKEN
from .env; see README "Instagram data").
"""

import os
import re
import time

import requests

GRAPH = "https://graph.facebook.com"
TIMEOUT = 20
_TTL = 12 * 3600  # Meta allows few calls per hour for new apps; cache generously
_cache = {}  # username -> (expires_ts, payload)
_blocked_until = [0.0]  # after an error (e.g. rate limit), pause calls briefly

POST_FIELDS = "timestamp,like_count,comments_count,view_count,media_type,media_product_type,permalink,caption"


class InstagramError(RuntimeError):
    pass


def configured():
    return bool(os.environ.get("IG_USER_ID") and os.environ.get("IG_ACCESS_TOKEN"))


def username_from_url(url):
    m = re.search(r"instagram\.com/([A-Za-z0-9_.]+)", url or "")
    return m.group(1) if m and m.group(1) not in ("p", "reel", "reels", "stories") else None


def _graph(path, **params):
    if time.time() < _blocked_until[0]:
        raise InstagramError("Paused after a recent Instagram API error; retrying shortly.")
    params["access_token"] = os.environ["IG_ACCESS_TOKEN"]
    r = requests.get(f"{GRAPH}/{path}", params=params, timeout=TIMEOUT)
    data = r.json() if r.content else {}
    if r.status_code >= 400 or "error" in data:
        err = data.get("error") or {}
        if err.get("code") in (4, 17, 32, 613):  # rate limits: back off 15 min
            _blocked_until[0] = time.time() + 15 * 60
        raise InstagramError(err.get("message") or f"HTTP {r.status_code}")
    return data


def profile(username, max_posts=100):
    """{'username', 'followers', 'media_count', 'posts': [...] oldest first}.
    Posts: timestamp, likes, comments, views (Reels only, else None), type, url."""
    hit = _cache.get(username)
    if hit and hit[0] > time.time():
        return hit[1]

    ig_user = os.environ["IG_USER_ID"]
    base = "business_discovery.username({u}){{followers_count,media_count,media{after}{{{f}}}}}"
    data = _graph(ig_user, fields=base.format(u=username, after="", f=POST_FIELDS))["business_discovery"]
    out = {
        "username": username,
        "followers": data.get("followers_count"),
        "media_count": data.get("media_count"),
        "posts": [],
    }
    media = data.get("media") or {}
    raw = list(media.get("data", []))
    seen = set()
    # Page through older posts (Business Discovery pages via .after(cursor)).
    while len(raw) < max_posts:
        after = ((media.get("paging") or {}).get("cursors") or {}).get("after")
        if not after or after in seen:
            break
        seen.add(after)
        page = _graph(ig_user, fields=base.format(u=username, after=f".after({after})", f=POST_FIELDS))
        media = page["business_discovery"].get("media") or {}
        batch = media.get("data", [])
        if not batch:
            break
        raw += batch

    uniq = {}
    for p in raw:
        uniq[p.get("permalink") or p.get("timestamp")] = p
    for p in uniq.values():
        caption = (p.get("caption") or "").strip().split("\n")[0]
        out["posts"].append({
            "timestamp": p.get("timestamp"),
            "likes": p.get("like_count"),
            "comments": p.get("comments_count"),
            "views": p.get("view_count"),
            "type": "reel" if p.get("media_product_type") == "REELS" else (p.get("media_type") or "").lower(),
            "url": p.get("permalink"),
            "caption": caption[:90],
        })
    out["posts"].sort(key=lambda p: p["timestamp"] or "")
    _cache[username] = (time.time() + _TTL, out)
    return out


def followers(username):
    """Just the follower count (used for weekly snapshots)."""
    ig_user = os.environ["IG_USER_ID"]
    data = _graph(ig_user, fields=f"business_discovery.username({username}){{followers_count}}")
    return data["business_discovery"].get("followers_count")


# ------------------------------------------------------------ one-time setup --
def _setup():
    """Exchange a short-lived Graph API Explorer token for a permanent Page
    token, find the linked Instagram account, and write both to .env."""
    from dotenv import load_dotenv

    env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env")
    load_dotenv(env_path)
    app_id, secret, short = (os.environ.get(k, "").strip() for k in ("META_APP_ID", "META_APP_SECRET", "IG_SETUP_TOKEN"))
    if not (app_id and secret and short):
        raise SystemExit("Add META_APP_ID, META_APP_SECRET and IG_SETUP_TOKEN to .env first.")

    def get(path, **params):
        r = requests.get(f"{GRAPH}/{path}", params=params, timeout=TIMEOUT)
        d = r.json()
        if "error" in d:
            raise SystemExit(f"Meta said: {d['error'].get('message')}")
        return d

    long_user = get("oauth/access_token", grant_type="fb_exchange_token", client_id=app_id,
                    client_secret=secret, fb_exchange_token=short)["access_token"]
    pages = get("me/accounts", fields="name,access_token,instagram_business_account{id,username}",
                access_token=long_user).get("data", [])
    linked = [p for p in pages if p.get("instagram_business_account")]
    if not linked:
        names = ", ".join(p.get("name", "?") for p in pages) or "none"
        raise SystemExit(f"No Facebook Page with a linked Instagram business account was found (pages: {names}).")
    page = linked[0]
    ig = page["instagram_business_account"]

    lines = open(env_path).read().splitlines() if os.path.exists(env_path) else []
    lines = [l for l in lines if not l.startswith(("IG_USER_ID=", "IG_ACCESS_TOKEN=", "IG_SETUP_TOKEN="))]
    lines += [f"IG_USER_ID={ig['id']}", f"IG_ACCESS_TOKEN={page['access_token']}"]
    open(env_path, "w").write("\n".join(lines) + "\n")
    print(f"Connected Instagram @{ig.get('username')} (via Facebook Page '{page['name']}').")
    print("Saved IG_USER_ID and IG_ACCESS_TOKEN to .env (the short-lived setup token was removed).")


if __name__ == "__main__":
    import sys

    if "--setup" in sys.argv:
        _setup()
    else:
        from dotenv import load_dotenv

        load_dotenv()
        for u in sys.argv[1:] or ["_____arze_____"]:
            p = profile(u)
            print(u, p["followers"], "followers,", len(p["posts"]), "posts")
