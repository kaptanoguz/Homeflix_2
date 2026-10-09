import os
import sqlite3
from contextlib import contextmanager

from .config import DB_FILE, DEFAULT_MOVIE_DIRS, DEFAULT_SERIES_DIRS, OMDB_KEYS

SCHEMA = """
CREATE TABLE IF NOT EXISTS config (key TEXT PRIMARY KEY, value TEXT);
CREATE TABLE IF NOT EXISTS movies (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL, year TEXT, path TEXT UNIQUE NOT NULL,
    poster TEXT, rating TEXT, plot TEXT, genre TEXT, candidates TEXT
);
CREATE TABLE IF NOT EXISTS series (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT UNIQUE NOT NULL, year TEXT, poster TEXT, rating TEXT, plot TEXT, genre TEXT, candidates TEXT
);
CREATE TABLE IF NOT EXISTS episodes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    series_id INTEGER NOT NULL, series_name TEXT NOT NULL,
    season INTEGER NOT NULL, episode INTEGER NOT NULL,
    title TEXT, path TEXT UNIQUE NOT NULL, filename TEXT NOT NULL,
    FOREIGN KEY(series_id) REFERENCES series(id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS collections (
    id INTEGER PRIMARY KEY, name TEXT, overview TEXT, poster TEXT, backdrop TEXT,
    parts INTEGER DEFAULT 0, fetched INTEGER DEFAULT 0
);
CREATE TABLE IF NOT EXISTS progress (
    key TEXT PRIMARY KEY, position REAL, duration REAL, finished INTEGER DEFAULT 0, updated_at REAL
);
CREATE TABLE IF NOT EXISTS mylist (key TEXT PRIMARY KEY, added_at REAL);
CREATE TABLE IF NOT EXISTS season_fetch (series_id INTEGER, season INTEGER, fetched_at REAL,
    PRIMARY KEY (series_id, season));
CREATE INDEX IF NOT EXISTS idx_episodes_series ON episodes(series_id, season, episode);
"""

EXTRA_COLUMNS = {
    "movies": {"meta_tries": "INTEGER DEFAULT 0", "original_title": "TEXT", "tmdb_id": "INTEGER",
               "imdb_id": "TEXT", "collection_id": "INTEGER", "runtime": "INTEGER", "backdrop": "TEXT",
               "added_at": "REAL", "size": "INTEGER", "enriched": "INTEGER DEFAULT 0", "cert": "TEXT"},
    "series": {"meta_tries": "INTEGER DEFAULT 0", "original_title": "TEXT", "tmdb_id": "INTEGER",
               "backdrop": "TEXT", "added_at": "REAL", "enriched": "INTEGER DEFAULT 0", "display_title": "TEXT",
               "cert": "TEXT"},
    "episodes": {"ep_name": "TEXT", "ep_overview": "TEXT", "still": "TEXT", "runtime": "INTEGER"},
}


def connect():
    conn = sqlite3.connect(DB_FILE, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


@contextmanager
def session():
    conn = connect()
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    with session() as c:
        c.execute("PRAGMA journal_mode = WAL")
        c.executescript(SCHEMA)
        for table, cols in EXTRA_COLUMNS.items():
            have = {r[1] for r in c.execute(f"PRAGMA table_info({table})")}
            for name, decl in cols.items():
                if name not in have:
                    c.execute(f"ALTER TABLE {table} ADD COLUMN {name} {decl}")
        c.execute("CREATE INDEX IF NOT EXISTS idx_movies_tmdb ON movies(tmdb_id)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_movies_collection ON movies(collection_id)")
        if not c.execute("SELECT 1 FROM config WHERE key = 'v2_title_pass'").fetchone():
            c.execute("UPDATE movies SET enriched = 0 WHERE tmdb_id IS NOT NULL")
            c.execute("UPDATE series SET enriched = 0 WHERE tmdb_id IS NOT NULL")
            c.execute("INSERT INTO config (key, value) VALUES ('v2_title_pass', '1')")
        if not c.execute("SELECT 1 FROM config WHERE key = 'v2_rematch'").fetchone():
            c.execute("UPDATE movies SET tmdb_id = NULL, original_title = NULL, enriched = 0, meta_tries = 0")
            c.execute("INSERT INTO config (key, value) VALUES ('v2_rematch', '1')")
        if not c.execute("SELECT 1 FROM config WHERE key = 'v2_caps_pass'").fetchone():
            for r in c.execute("SELECT id, title FROM movies WHERE tmdb_id IS NOT NULL").fetchall():
                if r['title'].isupper():
                    c.execute("UPDATE movies SET enriched = 0 WHERE id = ?", (r['id'],))
            c.execute("INSERT INTO config (key, value) VALUES ('v2_caps_pass', '1')")


def _first_existing(paths):
    return next((p for p in paths if os.path.isdir(p) and os.listdir(p)), paths[0])


def load_settings():
    with session() as c:
        conf = {r["key"]: r["value"] for r in c.execute("SELECT key, value FROM config")}
    conf.setdefault("movie_dir", _first_existing(DEFAULT_MOVIE_DIRS))
    conf.setdefault("series_dir", _first_existing(DEFAULT_SERIES_DIRS))
    conf.setdefault("omdb_api_key", OMDB_KEYS[0] if OMDB_KEYS else "")
    return conf


def save_settings(values):
    with session() as c:
        for k, v in values.items():
            c.execute("INSERT OR REPLACE INTO config (key, value) VALUES (?, ?)", (k, str(v)))
