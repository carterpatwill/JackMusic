"""FastAPI app: serves the static front-end and a small JSON API.

Run:  uvicorn backend.app:app --reload   (or: python -m backend.app)

Endpoints
    GET  /                 -> the site (frontend/index.html)
    GET  /api/artists      -> current week's artists + real stats/trend
    GET  /api/weeks        -> list of available weeks (for the archive)
    POST /api/refresh      -> fetch live stats, store a snapshot (admin-only)
    POST /api/subscribe    -> add an email to the Kit newsletter list

The refresh endpoint is protected by ADMIN_TOKEN so random visitors can't
trigger API calls. Set it in .env; if unset, refresh is allowed from
localhost only (fine for local dev).
"""

import os
from typing import Optional

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:  # dotenv optional at runtime
    pass

from . import db, newsletter, refresh, spotify

ROOT = os.path.dirname(os.path.dirname(__file__))
FRONTEND = os.path.join(ROOT, "frontend")
ASSETS = os.path.join(ROOT, "assets")

app = FastAPI(title="Quigley Discovery")


@app.middleware("http")
async def revalidate_static(request: Request, call_next):
    """Make browsers re-check pages, scripts and styles on every load (they
    still get a fast 304 when nothing changed), so edits show up without a
    hard refresh."""
    response = await call_next(request)
    if not request.url.path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-cache"
    return response

db.init_db()

# How old the newest stats snapshot can be before the server fetches fresh
# ones when it starts. On a host that sleeps when idle (e.g. Render's free
# tier) every wake-up is a start, so stats stay current without a scheduler.
STALE_AFTER_HOURS = float(os.environ.get("STALE_AFTER_HOURS", "12"))


def _refresh_if_stale():
    from datetime import datetime, timedelta, timezone

    try:
        conn = db.connect()
        row = conn.execute(
            "SELECT MAX(s.captured_at) AS last FROM snapshots s "
            "JOIN artists a ON a.id = s.artist_id WHERE a.week_of = ?",
            (db.latest_week(),),
        ).fetchone()
        conn.close()
        last = row["last"] if row else None
        if last and datetime.now(timezone.utc) - datetime.fromisoformat(last) < timedelta(hours=STALE_AFTER_HOURS):
            return
        refresh.refresh_week()
        print("Startup refresh: stats snapshot taken.")
    except Exception as e:  # noqa: BLE001 - never block startup on a fetch problem
        print(f"Startup refresh skipped: {type(e).__name__}")


@app.on_event("startup")
def _startup_refresh():
    import threading

    # Run in the background so the site starts serving immediately.
    threading.Thread(target=_refresh_if_stale, daemon=True).start()


@app.get("/")
def index():
    return FileResponse(os.path.join(FRONTEND, "index.html"))


@app.get("/api/artists")
def api_artists(week: Optional[str] = None):
    week_of = None if (week in (None, "", "latest")) else week
    return {
        "week_of": week_of or db.latest_week(),
        "artists": db.get_artists_for_week(week_of),
    }


@app.get("/api/weeks")
def api_weeks():
    return {"weeks": db.get_weeks()}


@app.get("/api/artist/{slug}/spotify")
def api_artist_spotify(slug: str):
    """Artist image + discography (album/single list with art + release dates)
    pulled live from Spotify. Cached server-side for an hour."""
    spotify_id = db.get_spotify_id(slug)
    if not spotify_id:
        raise HTTPException(status_code=404, detail="Unknown artist.")
    try:
        return spotify.artist_detail(spotify_id)
    except spotify.SpotifyError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"Spotify fetch failed: {e}")


def _authorized(request: Request, token: Optional[str]) -> bool:
    admin = os.environ.get("ADMIN_TOKEN")
    if admin:
        return token == admin
    # No token configured -> allow localhost only.
    client = request.client.host if request.client else ""
    return client in ("127.0.0.1", "::1", "localhost")


@app.post("/api/refresh")
def api_refresh(request: Request, x_admin_token: Optional[str] = Header(default=None)):
    if not _authorized(request, x_admin_token):
        raise HTTPException(status_code=401, detail="Not authorized to refresh.")
    try:
        result = refresh.refresh_week()
    except refresh.RefreshError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"Fetch failed: {e}")
    return JSONResponse(result)


class SubscribeIn(BaseModel):
    email: str


@app.post("/api/subscribe")
def api_subscribe(payload: SubscribeIn):
    email = (payload.email or "").strip()
    if "@" not in email or "." not in email:
        raise HTTPException(status_code=400, detail="Please enter a valid email.")
    # Local copy first (a backup; Render's free disk is wiped on redeploy).
    created = db.add_subscriber(email)
    # Kit holds the real mailing list. Skipped if KIT_API_KEY isn't set.
    if newsletter.configured():
        try:
            newsletter.subscribe(email)
        except newsletter.NewsletterError as e:
            print(f"Kit signup failed: {e}")
            raise HTTPException(
                status_code=502,
                detail="Couldn't add you to the list right now. Please try again in a minute.",
            )
    return {"ok": True, "created": created}


# Static mounts (after routes so /api/* wins).
app.mount("/assets", StaticFiles(directory=ASSETS), name="assets")
app.mount("/", StaticFiles(directory=FRONTEND, html=True), name="frontend")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("backend.app:app", host="127.0.0.1", port=8000, reload=True)
