import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent / "dearpeople.db"


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    conn = get_connection()
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS characters (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            relation TEXT NOT NULL,
            grp TEXT NOT NULL,
            name TEXT NOT NULL,
            personality TEXT,
            speech_style TEXT,
            calls_me TEXT
        );

        CREATE TABLE IF NOT EXISTS memories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            character_id INTEGER NOT NULL REFERENCES characters(id),
            content TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS rooms (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            type TEXT NOT NULL,
            includes_me INTEGER NOT NULL DEFAULT 1
        );

        CREATE TABLE IF NOT EXISTS room_members (
            room_id INTEGER NOT NULL REFERENCES rooms(id),
            character_id INTEGER NOT NULL REFERENCES characters(id),
            PRIMARY KEY (room_id, character_id)
        );

        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            room_id INTEGER NOT NULL REFERENCES rooms(id),
            sender_character_id INTEGER REFERENCES characters(id),
            type TEXT NOT NULL,
            content TEXT,
            caption TEXT,
            image_path TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        );
        """
    )
    existing_cols = [row["name"] for row in conn.execute("PRAGMA table_info(messages)").fetchall()]
    if "image_path" not in existing_cols:
        conn.execute("ALTER TABLE messages ADD COLUMN image_path TEXT")
    conn.commit()
    conn.close()
