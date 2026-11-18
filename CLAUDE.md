# CLAUDE.md — Quigley Discovery

Context for Claude Code working on this repo. Read this first.

> **Which data is actually available from Spotify / YouTube (and what's
> blocked) is documented in [`DATA_SOURCES.md`](DATA_SOURCES.md).** Read it
> before proposing or building any stats feature — e.g. Spotify followers /
> popularity are NOT available on this tier; YouTube views/subs ARE.

## What this is

A weekly independent-music discovery site. Each week features 5 independent
artists. The defining feature: artist stats are **real and live** — pulled from
the Spotify and YouTube APIs — and the trend badge is a genuine week-over-week
change, not a placeholder.

Grew out of a design mockup (a single exported `.dc.html` file). That mockup is
gone; its design values were ported into `frontend/styles.css`. The original
fake "+X%" (a hash of the artist's name) was the thing this rebuild replaced
with real data.

## Stack & why

- **Vanilla HTML/CSS/JS front end** — deliberately no framework/build step so
  the project is trivial to run and hand off (one ecosystem: Python).
- **FastAPI + SQLite back end** — the backend exists for one reason: API keys
  can't live in a public page, and the trend % needs stored history. Running
  locally, keys sit in `.env` and never reach the browser.

## Architecture

```
Browser ──GET /api/artists──> FastAPI ──> SQLite (latest + previous snapshot)
Browser ──POST /api/refresh─> FastAPI ──> refresh.py ──> Spotify + YouTube APIs
                                                   └──> writes a snapshot row
```

- Trend % = `(latest - week_ago) / week_ago`, computed in
  `db.get_artists_for_week()` by comparing the latest snapshot with the most
  recent snapshot at least 6 days older (`TREND_MIN_GAP`). The homepage badge
  uses YouTube views.
- A snapshot is one row per artist per refresh. No trend appears until there
  is a snapshot ~a week older than the latest one; refreshing more often is
  fine (it always compares against ~a week back).
- Refresh is **manual** (a button). No cron/scheduler by design.

## Files

- `backend/seed.py` — the artist roster + week metadata. **This is the file you
  edit to publish a new week.** Then `python -m backend.db --publish`, which adds
  the week and keeps earlier weeks for the archive. Artist slugs are UNIQUE
  across all weeks, so each week's artists need new slugs.
- `backend/db.py` — schema, seeding, trend query, subscribers. Stdlib sqlite3,
  no ORM.
- `backend/refresh.py` — the ONLY place API keys are used. Spotify Client
  Credentials flow; YouTube resolves a channel id from the artist's video URL
  once and caches it on the artist row.
- `backend/spotify.py` — the Spotify data this tier DOES return: artist image +
  discography (albums/singles with art + release dates). Powers the
  "Discography" modal via `GET /api/artist/{slug}/spotify`. Token + album
  responses are cached in-process. NOTE: this tier caps the albums `limit` at
  10, so `get_albums` paginates; and it 400s above that.
- `backend/app.py` — routes + static mounts. `/api/*` is defined before the
  static mounts so it takes precedence.
- `frontend/app.js` — renders featured card + grid; handles refresh + signup.
- `frontend/archive.html` — "See Previous Weeks": every published week from
  `/api/weeks` + `/api/artists?week=`, with week stepper, genre filter and
  "Surprise me".
- `frontend/styles.css` — design tokens in `:root`; `--accent` drives theme.

## Conventions

- Keys come from env (`.env`, loaded via python-dotenv). Never hardcode or log
  secrets. Never expose them to the front end.
- Per-artist fetch failures are collected (not raised) so one bad lookup doesn't
  abort the whole refresh — see `refresh.refresh_week()` `errors` lists.
- `data.db` and `.env` are gitignored. The DB is disposable; it rebuilds from
  `seed.py`.
- Image/font filenames in `assets/` are content hashes from the original design.
  Map artist → photo in `seed.py` (`card_photo`), not in markup.

## Run / common tasks

```bash
pip install -r requirements.txt
cp .env.example .env            # add Spotify/YouTube keys
uvicorn backend.app:app --reload
python -m backend.refresh       # take a snapshot from the CLI
python -m backend.db --publish  # add seed.py's week, keep earlier weeks (archive)
python -m backend.db --reseed   # wipe ALL weeks + stats, reseed current week only
```

## Known caveats / future work

- Spotify's API does **not** expose "monthly listeners" (only followers +
  popularity). Monthly listeners would need a paid provider (Chartmetric,
  Songstats) or scraping — intentionally not implemented.
- `profile_href` / `invest_href` point at the old `.dc.html` filenames from the
  mockup; those per-artist pages don't exist yet.
- For public deployment: set `ADMIN_TOKEN` and send it as the `X-Admin-Token`
  header from the refresh button (currently the button sends no token, relying
  on the localhost allowance).
