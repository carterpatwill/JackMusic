# Quigley Discovery

A weekly independent-music discovery site. Five artists per week, each with
**real, live stats** pulled from Spotify and YouTube. The trend badge ("+X%")
is a genuine week-over-week change computed from stored snapshots — not a
placeholder.

- **Front end:** plain HTML + CSS + vanilla JS (no build step)
- **Back end:** Python + FastAPI
- **Data:** SQLite (single file, auto-created)
- **Live stats:** Spotify Web API + YouTube Data API

## Quick start

```bash
# 1. Install dependencies (ideally in a virtualenv)
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 2. Add your API keys
cp .env.example .env         # then edit .env — see "API keys" below

# 3. Run
uvicorn backend.app:app --reload

# 4. Open http://127.0.0.1:8000
```

The site loads immediately with the current roster. Stats show "no data yet"
until you click **Refresh stats** (top of the Artists section), which fetches
live numbers. Trend percentages compare the latest refresh with one taken
about a week earlier, so they appear once you have refreshes at least 6 days
apart (refreshing more often is fine).

## API keys

Put these in `.env` (copied from `.env.example`):

| Key | Where to get it | Required? |
|-----|-----------------|-----------|
| `SPOTIFY_CLIENT_ID` / `SPOTIFY_CLIENT_SECRET` | https://developer.spotify.com/dashboard → create an app (Client Credentials; no redirect URI needed) | For Spotify stats |
| `YOUTUBE_API_KEY` | https://console.cloud.google.com → enable "YouTube Data API v3" → create an API key | Optional (skips YT if blank) |
| `ADMIN_TOKEN` | Any random string | Optional; only needed if deployed publicly |

Keys are used **only** server-side in `backend/refresh.py`. They are never sent
to the browser, so they stay private even though the site itself is static.

## Deploying (Render)

The repo is public, so it deploys on [Render](https://render.com) as a
**Web Service → Public Git Repository** (`https://github.com/carterpatwill/JackMusic`):

| Setting | Value |
|---|---|
| Runtime | Python 3 |
| Build command | `pip install -r requirements.txt` |
| Start command | `uvicorn backend.app:app --host 0.0.0.0 --port $PORT` |
| Environment | `SPOTIFY_CLIENT_ID`, `SPOTIFY_CLIENT_SECRET`, `YOUTUBE_API_KEY`, `ADMIN_TOKEN` (any random string) |

On start the server fetches fresh stats if the newest snapshot is older than
`STALE_AFTER_HOURS` (default 12), so a new deploy isn't empty. The
"Refresh stats" button only shows on localhost. Render's free disk is wiped on
each deploy, so the database (and trend history) starts over then.

## Publishing a new week

1. Edit `backend/seed.py` — update `CURRENT_WEEK`, `CURRENT_WEEK_LABEL`, and the
   `ARTISTS` list.
2. Publish it: `python -m backend.db --publish` (adds the new week and keeps
   every earlier week, which then appears on the archive page, `/archive.html`).
   `--reseed` still exists but wipes all weeks and their stats history.
3. Start the server and click **Refresh stats** twice (over the week) to build
   trend history.

## Project layout

```
backend/
  app.py       FastAPI app — serves the site + JSON API
  db.py        SQLite schema, seeding, trend-% query
  refresh.py   fetches Spotify/YouTube stats (holds the keys)
  seed.py      the artist roster (edit this each week)
frontend/
  index.html   the page
  styles.css   design tokens + styles (ported from the original mockup)
  app.js       fetches /api/artists and renders the cards
assets/        images + fonts (from the design)
data.db        SQLite, auto-created (gitignored)
```

## API

| Method | Route | Purpose |
|--------|-------|---------|
| GET  | `/api/artists?week=latest` | Current week's artists + stats + trend |
| GET  | `/api/weeks` | Available weeks (for an archive) |
| GET  | `/api/artist/{slug}/spotify` | Artist image + discography (art, dates) from Spotify |
| POST | `/api/refresh` | Fetch live stats, store a snapshot (admin-only) |
| POST | `/api/subscribe` | Store a newsletter email |

## What data each service offers

**[`DATA_SOURCES.md`](DATA_SOURCES.md)** — a plain-language rundown of exactly
what stats and content are available from YouTube and Spotify (and what's
blocked), plus free/paid options not yet connected. Start there to understand
what the site can and can't show.

See `CLAUDE.md` for architecture notes and conventions.
