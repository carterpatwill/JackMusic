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
live numbers. The *first* refresh sets a baseline; the trend percentages
appear from the *second* refresh onward (you need two points to measure change).

## API keys

Put these in `.env` (copied from `.env.example`):

| Key | Where to get it | Required? |
|-----|-----------------|-----------|
| `SPOTIFY_CLIENT_ID` / `SPOTIFY_CLIENT_SECRET` | https://developer.spotify.com/dashboard → create an app (Client Credentials; no redirect URI needed) | For Spotify stats |
| `YOUTUBE_API_KEY` | https://console.cloud.google.com → enable "YouTube Data API v3" → create an API key | Optional (skips YT if blank) |
| `ADMIN_TOKEN` | Any random string | Optional; only needed if deployed publicly |

Keys are used **only** server-side in `backend/refresh.py`. They are never sent
to the browser, so they stay private even though the site itself is static.

## Publishing a new week

1. Edit `backend/seed.py` — update `CURRENT_WEEK`, `CURRENT_WEEK_LABEL`, and the
   `ARTISTS` list.
2. Re-seed the database: `python -m backend.db --reseed`
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
