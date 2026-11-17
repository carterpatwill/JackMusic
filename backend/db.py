"""SQLite layer: schema, seeding, and the queries that compute the real
week-over-week trend from stored snapshots.

The DB is a single file (data.db at the project root) and is created on
first use. No ORM — just the stdlib sqlite3 module to keep the handoff
dependency-light.
"""

import os
import sqlite3
from datetime import datetime, timezone

from . import seed

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data.db")


def connect():
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
    youtube_views      INTEGER
);

CREATE INDEX IF NOT EXISTS idx_snapshots_artist ON snapshots(artist_id, captured_at);

CREATE TABLE IF NOT EXISTS subscribers (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    email        TEXT UNIQUE NOT NULL,
    subscribed_at TEXT NOT NULL
);
"""


def init_db():
    conn = connect()
    conn.executescript(SCHEMA)
    conn.commit()
    # Seed artists only if the table is empty so we never clobber live data.
    count = conn.execute("SELECT COUNT(*) AS c FROM artists").fetchone()["c"]
    if count == 0:
        _seed_artists(conn)
    conn.close()


def _seed_artists(conn):
    for a in seed.ARTISTS:
        conn.execute(
            """
            INSERT INTO artists
              (slug, name, week_of, tag, tag_color, tag_bg, bio, spotify_id,
               youtube_url, instagram_url, card_photo, title_font,
               profile_href, invest_href, is_featured, sort_order)
            VALUES
              (:slug, :name, :week_of, :tag, :tag_color, :tag_bg, :bio, :spotify_id,
               :youtube_url, :instagram_url, :card_photo, :title_font,
               :profile_href, :invest_href, :is_featured, :sort_order)
            """,
            {**a, "week_of": seed.CURRENT_WEEK},
        )
    conn.commit()


def reseed():
    """Wipe artists/snapshots and re-insert from seed.py. Subscribers kept."""
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


def _two_latest_snapshots(conn, artist_id):
    rows = conn.execute(
        "SELECT * FROM snapshots WHERE artist_id = ? ORDER BY captured_at DESC LIMIT 2",
        (artist_id,),
    ).fetchall()
    return rows


def _pct_change(current, previous):
    if current is None or previous in (None, 0):
        return None
    return round((current - previous) / previous * 100, 1)


def get_artists_for_week(week_of=None):
    """Return artists for a week, each enriched with latest stats and the
    real week-over-week trend computed from the two most recent snapshots."""
    week_of = week_of or latest_week()
    conn = connect()
    artist_rows = conn.execute(
        "SELECT * FROM artists WHERE week_of = ? ORDER BY sort_order ASC",
        (week_of,),
    ).fetchall()

    artists = []
    for ar in artist_rows:
        snaps = _two_latest_snapshots(conn, ar["id"])
        current = snaps[0] if snaps else None
        previous = snaps[1] if len(snaps) > 1 else None

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
    try:
        conn.execute(
            "INSERT INTO subscribers (email, subscribed_at) VALUES (?, ?)",
            (email.strip().lower(), datetime.now(timezone.utc).isoformat()),
        )
        conn.commit()
        created = True
    except sqlite3.IntegrityError:
        created = False  # already subscribed
    finally:
        conn.close()
    return created


if __name__ == "__main__":
    import sys

    if "--reseed" in sys.argv:
        reseed()
        print("Reseeded artists from backend/seed.py")
    else:
        init_db()
        print(f"Initialized {DB_PATH}")
