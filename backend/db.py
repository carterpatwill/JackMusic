"""Database layer: schema, seeding, and the queries that compute the real
week-over-week trend from stored snapshots.

Two backends, same code:
- On the host (Render sets RENDER), DATABASE_URL (a free Neon Postgres) is
  used so the stats history survives redeploys (Render's free disk is wiped
  on each one).
- Locally, a SQLite file (data.db at the project root), even if .env has
  DATABASE_URL: local work and drafts must never write to the live database
  (or spend its free compute). Opt in with USE_LIVE_DB=1. To get the live
  site's saved data locally without any API calls:
      python -m backend.db --pull-live

Queries are written once in SQLite style (`?` and `:name` placeholders);
_PgConn translates them for Postgres. No ORM.
"""

import os
import re
import sqlite3
from datetime import datetime, timedelta, timezone

from . import seed

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data.db")


def _live_database_url():
    return os.environ.get("DATABASE_URL", "").strip()


def _database_url():
    if os.environ.get("RENDER") or os.environ.get("USE_LIVE_DB", "").strip() == "1":
        return _live_database_url()
    return ""


def using_postgres():
    return _database_url().startswith(("postgres://", "postgresql://"))


_NAMED = re.compile(r"(?<!:):([A-Za-z_]\w*)")


def _to_pg(sql):
    sql = sql.replace("%", "%%").replace("?", "%s")
    return _NAMED.sub(r"%(\1)s", sql)


class _PgConn:
    """Tiny sqlite3-style wrapper over psycopg: execute() / executescript() /
    commit() / close(), rows readable as row["column"]."""

    def __init__(self, url):
        import psycopg
        from psycopg.rows import dict_row

        self._conn = psycopg.connect(url, row_factory=dict_row, connect_timeout=15)

    def execute(self, sql, params=()):
        return self._conn.execute(_to_pg(sql), params)

    def executescript(self, script):
        script = script.replace("INTEGER PRIMARY KEY AUTOINCREMENT", "SERIAL PRIMARY KEY")
        for stmt in script.split(";"):
            if stmt.strip():
                self._conn.execute(stmt)
        self._conn.commit()

    def commit(self):
        self._conn.commit()

    def close(self):
        self._conn.close()


def connect():
    if using_postgres():
        return _PgConn(_database_url())
    return _sqlite()


def _sqlite():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


SCHEMA = """
CREATE TABLE IF NOT EXISTS artists (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    slug          TEXT UNIQUE NOT NULL,
    name          TEXT NOT NULL,
    week_of       TEXT NOT NULL,
    tag           TEXT,
    tag_color     TEXT,
    tag_bg        TEXT,
    bio           TEXT,
    spotify_id    TEXT,
    youtube_url   TEXT,
    youtube_channel_id TEXT,   -- resolved once by refresh.py, then cached
    instagram_url TEXT,
    card_photo    TEXT,
    title_font    TEXT,
    profile_href  TEXT,
    invest_href   TEXT,
    is_featured   INTEGER DEFAULT 0,
    sort_order    INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS snapshots (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    artist_id          INTEGER NOT NULL REFERENCES artists(id) ON DELETE CASCADE,
    captured_at        TEXT NOT NULL,
    spotify_followers  INTEGER,
    spotify_popularity INTEGER,
    youtube_subs       INTEGER,
    youtube_views      INTEGER,
    instagram_followers INTEGER,
    instagram_views    INTEGER
);

CREATE INDEX IF NOT EXISTS idx_snapshots_artist ON snapshots(artist_id, captured_at);

CREATE TABLE IF NOT EXISTS api_cache (
    key        TEXT PRIMARY KEY,
    payload    TEXT NOT NULL,
    fetched_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS subscribers (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    email        TEXT UNIQUE NOT NULL,
    subscribed_at TEXT NOT NULL
);
"""


_ARTIST_FIELDS = (
    "slug", "name", "week_of", "tag", "tag_color", "tag_bg", "bio", "spotify_id",
    "youtube_url", "instagram_url", "card_photo", "title_font",
    "profile_href", "invest_href", "is_featured", "sort_order",
)


def init_db():
    """Create tables, then sync seed.py's artists into the DB.

    Artists are matched by slug: new ones are inserted, existing ones get
    their details (week, order, bio, links...) updated from seed.py. Earlier
    weeks' artists, snapshots and subscribers are never touched. So with a
    persistent database, editing seed.py and redeploying is all it takes."""
    conn = connect()
    conn.executescript(SCHEMA)
    _migrate(conn)
    sync_seed(conn)
    conn.close()


def _columns(conn, table):
    if isinstance(conn, _PgConn):
        rows = conn.execute(
            "SELECT column_name AS name FROM information_schema.columns WHERE table_name = ?",
            (table,),
        ).fetchall()
    else:
        rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return {r["name"] for r in rows}


def _migrate(conn):
    """Add columns introduced after a database was first created."""
    if "instagram_followers" not in _columns(conn, "snapshots"):
        conn.execute("ALTER TABLE snapshots ADD COLUMN instagram_followers INTEGER")
    if "instagram_views" not in _columns(conn, "snapshots"):
        conn.execute("ALTER TABLE snapshots ADD COLUMN instagram_views INTEGER")
    conn.commit()


def sync_seed(conn):
    """Upsert seed.ARTISTS (this week's drop). Returns how many are new."""
    cols = ", ".join(_ARTIST_FIELDS)
    vals = ", ".join(f":{f}" for f in _ARTIST_FIELDS)
    updates = ", ".join(f"{f} = excluded.{f}" for f in _ARTIST_FIELDS if f != "slug")
    existing = {r["slug"] for r in conn.execute("SELECT slug FROM artists").fetchall()}
    for a in seed.ARTISTS:
        row = {f: a.get(f) for f in _ARTIST_FIELDS}
        row["week_of"] = seed.CURRENT_WEEK
        # A changed YouTube link must re-resolve its channel.
        conn.execute(
            "UPDATE artists SET youtube_channel_id = NULL "
            "WHERE slug = :slug AND COALESCE(youtube_url, '') <> COALESCE(:youtube_url, '')",
            row,
        )
        conn.execute(
            f"INSERT INTO artists ({cols}) VALUES ({vals}) "
            f"ON CONFLICT(slug) DO UPDATE SET {updates}",
            row,
        )
    conn.commit()
    return sum(1 for a in seed.ARTISTS if a["slug"] not in existing)


def _seed_artists(conn):
    sync_seed(conn)


def publish_week():
    """Add/refresh seed.py's current week WITHOUT touching earlier weeks, so
    the archive (/archive.html) keeps every past drop and its stats history.
    (The server also does this on every startup.)
    Returns (week_of, number of artists added)."""
    conn = connect()
    conn.executescript(SCHEMA)
    added = sync_seed(conn)
    conn.close()
    return seed.CURRENT_WEEK, added


def reseed():
    """Wipe ALL artists/snapshots (every week, including the archive) and
    re-insert only seed.py's current week. Subscribers kept. To add a new
    week and keep past ones, use publish_week() / --publish instead."""
    conn = connect()
    conn.executescript(SCHEMA)
    conn.execute("DELETE FROM snapshots")
    conn.execute("DELETE FROM artists")
    _seed_artists(conn)
    conn.commit()
    conn.close()


def get_weeks():
    conn = connect()
    rows = conn.execute(
        "SELECT DISTINCT week_of FROM artists ORDER BY week_of DESC"
    ).fetchall()
    conn.close()
    return [r["week_of"] for r in rows]


def latest_week():
    weeks = get_weeks()
    return weeks[0] if weeks else seed.CURRENT_WEEK


# A trend compares the latest snapshot with one taken at least this long
# before it, so "+X%" is a real week-over-week change no matter how often
# Refresh is clicked. (Slightly under 7 days so a weekly refresh that runs a
# few hours early still counts.)
TREND_MIN_GAP = timedelta(days=6)


def _latest_and_week_ago(conn, artist_id):
    """Return (latest snapshot, most recent snapshot >= TREND_MIN_GAP older).
    Either may be None."""
    latest = conn.execute(
        "SELECT * FROM snapshots WHERE artist_id = ? ORDER BY captured_at DESC LIMIT 1",
        (artist_id,),
    ).fetchone()
    if not latest:
        return None, None
    cutoff = (datetime.fromisoformat(latest["captured_at"]) - TREND_MIN_GAP).isoformat()
    previous = conn.execute(
        "SELECT * FROM snapshots WHERE artist_id = ? AND captured_at <= ? "
        "ORDER BY captured_at DESC LIMIT 1",
        (artist_id, cutoff),
    ).fetchone()
    return latest, previous


def _first_snapshot_at(conn, artist_id):
    row = conn.execute(
        "SELECT MIN(captured_at) AS first FROM snapshots WHERE artist_id = ?",
        (artist_id,),
    ).fetchone()
    return row["first"] if row else None


def _pct_change(current, previous):
    if current is None or previous in (None, 0):
        return None
    return round((current - previous) / previous * 100, 1)


def get_artists_for_week(week_of=None):
    """Return artists for a week, each enriched with latest stats and the
    real week-over-week trend (latest snapshot vs. one ~a week older)."""
    week_of = week_of or latest_week()
    conn = connect()
    artist_rows = conn.execute(
        "SELECT * FROM artists WHERE week_of = ? ORDER BY sort_order ASC",
        (week_of,),
    ).fetchall()

    artists = []
    for ar in artist_rows:
        current, previous = _latest_and_week_ago(conn, ar["id"])

        stats = {
            "spotify_followers": current["spotify_followers"] if current else None,
            "spotify_popularity": current["spotify_popularity"] if current else None,
            "youtube_subs": current["youtube_subs"] if current else None,
            "youtube_views": current["youtube_views"] if current else None,
            "captured_at": current["captured_at"] if current else None,
            "followers_trend_pct": _pct_change(
                current["spotify_followers"] if current else None,
                previous["spotify_followers"] if previous else None,
            ),
            "popularity_delta": (
                (current["spotify_popularity"] - previous["spotify_popularity"])
                if current and previous
                and current["spotify_popularity"] is not None
                and previous["spotify_popularity"] is not None
                else None
            ),
            "subs_trend_pct": _pct_change(
                current["youtube_subs"] if current else None,
                previous["youtube_subs"] if previous else None,
            ),
            "views_trend_pct": _pct_change(
                current["youtube_views"] if current else None,
                previous["youtube_views"] if previous else None,
            ),
            "has_youtube_data": bool(current and current["youtube_views"] is not None),
            "has_data": current is not None,
            "has_trend": previous is not None,
            "trend_compared_to": previous["captured_at"] if previous else None,
            "tracking_since": _first_snapshot_at(conn, ar["id"]),
        }

        artists.append(
            {
                "slug": ar["slug"],
                "name": ar["name"],
                "tag": ar["tag"],
                "tag_color": ar["tag_color"],
                "tag_bg": ar["tag_bg"],
                "bio": ar["bio"],
                "spotify_url": (
                    f"https://open.spotify.com/artist/{ar['spotify_id']}"
                    if ar["spotify_id"]
                    else ""
                ),
                "youtube_url": ar["youtube_url"] or "",
                "has_youtube": bool(ar["youtube_url"]),
                "instagram_url": ar["instagram_url"] or "",
                "card_photo": (f"/assets/{ar['card_photo']}" if ar["card_photo"] else ""),
                "has_card_photo": bool(ar["card_photo"]),
                "title_font": ar["title_font"],
                "profile_href": ar["profile_href"] or "",
                "invest_href": ar["invest_href"] or "",
                "is_featured": bool(ar["is_featured"]),
                "stats": stats,
            }
        )
    conn.close()
    return artists


def get_spotify_id(slug):
    conn = connect()
    row = conn.execute(
        "SELECT spotify_id FROM artists WHERE slug = ?", (slug,)
    ).fetchone()
    conn.close()
    return row["spotify_id"] if row else None


def add_subscriber(email):
    conn = connect()
    cur = conn.execute(
        "INSERT INTO subscribers (email, subscribed_at) VALUES (?, ?) "
        "ON CONFLICT(email) DO NOTHING",
        (email.strip().lower(), datetime.now(timezone.utc).isoformat()),
    )
    created = cur.rowcount == 1  # 0 = already subscribed
    conn.commit()
    conn.close()
    return created


def get_artist(slug):
    conn = connect()
    row = conn.execute("SELECT * FROM artists WHERE slug = ?", (slug,)).fetchone()
    conn.close()
    return dict(row) if row else None


def set_channel_id(artist_id, channel_id):
    conn = connect()
    conn.execute(
        "UPDATE artists SET youtube_channel_id = ? WHERE id = ?", (channel_id, artist_id)
    )
    conn.commit()
    conn.close()


def get_week_trends(week_of=None):
    """YouTube views + subscribers and Instagram Reel views + followers over
    time for every artist in a week, oldest first, from the saved snapshots
    only (no API calls). Powers the homepage chart."""
    week_of = week_of or latest_week()
    conn = connect()
    artists = conn.execute(
        "SELECT id, slug, name, is_featured FROM artists WHERE week_of = ? "
        "ORDER BY sort_order ASC",
        (week_of,),
    ).fetchall()
    out = []
    for a in artists:
        rows = conn.execute(
            "SELECT captured_at, youtube_views, youtube_subs, instagram_views, "
            "instagram_followers FROM snapshots WHERE artist_id = ? ORDER BY captured_at ASC",
            (a["id"],),
        ).fetchall()
        points = [dict(r) for r in rows]
        out.append(
            {
                "slug": a["slug"],
                "name": a["name"],
                "is_featured": bool(a["is_featured"]),
                "points": points,
            }
        )
    conn.close()
    return {"week_of": week_of, "artists": out}


def get_snapshots(artist_id):
    """Every stored snapshot for an artist, oldest first (for the growth line)."""
    conn = connect()
    rows = conn.execute(
        "SELECT captured_at, youtube_views, youtube_subs, instagram_followers FROM snapshots "
        "WHERE artist_id = ? ORDER BY captured_at ASC",
        (artist_id,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# --------------------------------------------------------------- API cache --
# Responses from rate-limited APIs (Spotify, Instagram, YouTube) are kept here
# so restarts / free-tier sleep don't trigger fresh calls, and so the last good
# answer can still be shown while a service is rate-limiting us.
def cache_get(key, max_age=None):
    """Cached payload for key if younger than max_age seconds (any age if None)."""
    import json, time
    try:
        conn = connect()
        row = conn.execute("SELECT payload, fetched_at FROM api_cache WHERE key = ?", (key,)).fetchone()
        conn.close()
    except Exception:  # noqa: BLE001 - a cache miss is never fatal
        return None
    if not row or (max_age is not None and time.time() - row["fetched_at"] > max_age):
        return None
    return json.loads(row["payload"])


def cache_put(key, payload):
    import json, time
    try:
        conn = connect()
        conn.execute(
            "INSERT INTO api_cache (key, payload, fetched_at) VALUES (?, ?, ?) "
            "ON CONFLICT(key) DO UPDATE SET payload = excluded.payload, fetched_at = excluded.fetched_at",
            (key, json.dumps(payload), time.time()),
        )
        conn.commit()
        conn.close()
    except Exception:  # noqa: BLE001
        pass


def pull_live():
    """Copy the live database's artists, snapshots and saved API responses
    into the local SQLite file (read-only on the live side). Lets local work
    and drafts show real data without calling Spotify/YouTube/Instagram.
    Then re-applies seed.py, so a draft week stays on top."""
    url = _live_database_url()
    if not url.startswith(("postgres://", "postgresql://")):
        raise SystemExit("No DATABASE_URL in .env to pull from.")
    live = _PgConn(url)
    artists = live.execute("SELECT * FROM artists").fetchall()
    snaps = live.execute(
        "SELECT a.slug, s.* FROM snapshots s JOIN artists a ON a.id = s.artist_id"
    ).fetchall()
    cache = live.execute("SELECT key, payload, fetched_at FROM api_cache").fetchall()
    live.close()

    local = _sqlite()
    local.executescript(SCHEMA)
    _migrate(local)
    fields = _ARTIST_FIELDS + ("youtube_channel_id",)
    cols = ", ".join(fields)
    vals = ", ".join(f":{f}" for f in fields)
    updates = ", ".join(f"{f} = excluded.{f}" for f in fields if f != "slug")
    for a in artists:
        local.execute(
            f"INSERT INTO artists ({cols}) VALUES ({vals}) ON CONFLICT(slug) DO UPDATE SET {updates}",
            {f: a.get(f) for f in fields},
        )
    ids = {r["slug"]: r["id"] for r in local.execute("SELECT id, slug FROM artists").fetchall()}
    pulled = {s["slug"] for s in snaps}
    for slug in pulled:  # replace, so pulling twice doesn't duplicate points
        local.execute("DELETE FROM snapshots WHERE artist_id = ?", (ids[slug],))
    for s in snaps:
        local.execute(
            "INSERT INTO snapshots (artist_id, captured_at, spotify_followers, spotify_popularity, "
            "youtube_subs, youtube_views, instagram_followers, instagram_views) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (ids[s["slug"]], s["captured_at"], s["spotify_followers"], s["spotify_popularity"],
             s["youtube_subs"], s["youtube_views"], s["instagram_followers"],
             s.get("instagram_views")),
        )
    for c in cache:
        local.execute(
            "INSERT INTO api_cache (key, payload, fetched_at) VALUES (?, ?, ?) "
            "ON CONFLICT(key) DO UPDATE SET payload = excluded.payload, fetched_at = excluded.fetched_at",
            (c["key"], c["payload"], c["fetched_at"]),
        )
    local.commit()
    sync_seed(local)
    local.close()
    return len(artists), len(snaps), len(cache)


if __name__ == "__main__":
    import sys

    try:
        from dotenv import load_dotenv

        load_dotenv()
    except ImportError:
        pass

    if "--pull-live" in sys.argv:
        n_a, n_s, n_c = pull_live()
        print(f"Copied {n_a} artists, {n_s} snapshots and {n_c} saved API responses "
              f"from the live database into {DB_PATH}.")
        sys.exit(0)

    if "--publish" in sys.argv:
        week, added = publish_week()
        print(f"Published week {week}: added {added} artist(s); earlier weeks kept.")
    elif "--reseed" in sys.argv:
        reseed()
        print("Reseeded artists from backend/seed.py (all earlier weeks deleted)")
    else:
        init_db()
        print("Initialized " + ("Postgres (DATABASE_URL)" if using_postgres() else DB_PATH))
