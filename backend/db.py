"""Database layer: schema, seeding, and the queries that compute the real
week-over-week trend from stored snapshots.

Two backends, same code:
- DATABASE_URL set (e.g. a free Neon Postgres): used in production so the
  stats history survives redeploys (Render's free disk is wiped on each one).
- Otherwise a local SQLite file (data.db at the project root), created on
  first use. Handy for development; disposable.

Queries are written once in SQLite style (`?` and `:name` placeholders);
_PgConn translates them for Postgres. No ORM.
"""

import os
import re
import sqlite3
from datetime import datetime, timedelta, timezone

from . import seed

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data.db")


def _database_url():
    return os.environ.get("DATABASE_URL", "").strip()


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
    instagram_followers INTEGER
);

CREATE INDEX IF NOT EXISTS idx_snapshots_artist ON snapshots(artist_id, captured_at);

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


if __name__ == "__main__":
    import sys

    if "--publish" in sys.argv:
        week, added = publish_week()
        print(f"Published week {week}: added {added} artist(s); earlier weeks kept.")
    elif "--reseed" in sys.argv:
        reseed()
        print("Reseeded artists from backend/seed.py (all earlier weeks deleted)")
    else:
        init_db()
        print("Initialized " + ("Postgres (DATABASE_URL)" if using_postgres() else DB_PATH))
