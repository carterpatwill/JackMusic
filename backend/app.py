"""FastAPI app: serves the static front-end and a small JSON API.

Run:  uvicorn backend.app:app --reload   (or: python -m backend.app)

Endpoints
    GET  /                 -> the site (frontend/index.html)
    GET  /api/artists      -> current week's artists + real stats/trend
    GET  /api/weeks        -> list of available weeks (for the archive)
    POST /api/refresh      -> fetch live stats, store a snapshot (admin-only)
    POST /api/subscribe    -> store a newsletter email

The refresh endpoint is protected by ADMIN_TOKEN so random visitors can't
trigger API calls. Set it in .env; if unset, refresh is allowed from
localhost only (fine for local dev).
"""

import os

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:  # dotenv optional at runtime
    pass

from . import db, refresh, spotify

ROOT = os.path.dirname(os.path.dirname(__file__))
FRONTEND = os.path.join(ROOT, "frontend")
ASSETS = os.path.join(ROOT, "assets")

app = FastAPI(title="Quigley Discovery")

db.init_db()


@app.get("/")
def index():
    return FileResponse(os.path.join(FRONTEND, "index.html"))


@app.get("/api/artists")
def api_artists(week: str | None = None):
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


def _authorized(request: Request, token: str | None) -> bool:
    admin = os.environ.get("ADMIN_TOKEN")
    if admin:
        return token == admin
    # No token configured -> allow localhost only.
    client = request.client.host if request.client else ""
    return client in ("127.0.0.1", "::1", "localhost")


@app.post("/api/refresh")
def api_refresh(request: Request, x_admin_token: str | None = Header(default=None)):
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
    created = db.add_subscriber(email)
    return {"ok": True, "created": created}


# Static mounts (after routes so /api/* wins).
app.mount("/assets", StaticFiles(directory=ASSETS), name="assets")
app.mount("/", StaticFiles(directory=FRONTEND, html=True), name="frontend")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("backend.app:app", host="127.0.0.1", port=8000, reload=True)
