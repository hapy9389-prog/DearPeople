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
        CREATE TABLE IF NOT EXISTS profiles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            emoji TEXT NOT NULL DEFAULT '🙂',
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        );

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
            includes_me INTEGER NOT NULL DEFAULT 1,
            is_custom INTEGER NOT NULL DEFAULT 0
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

        CREATE TABLE IF NOT EXISTS deleted_rooms (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            profile_id INTEGER NOT NULL REFERENCES profiles(id),
            room_key TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        );
        """
    )
    existing_cols = [row["name"] for row in conn.execute("PRAGMA table_info(messages)").fetchall()]
    if "image_path" not in existing_cols:
        conn.execute("ALTER TABLE messages ADD COLUMN image_path TEXT")

    char_cols = [row["name"] for row in conn.execute("PRAGMA table_info(characters)").fetchall()]
    if "profile_id" not in char_cols:
        conn.execute("ALTER TABLE characters ADD COLUMN profile_id INTEGER REFERENCES profiles(id)")

    room_cols = [row["name"] for row in conn.execute("PRAGMA table_info(rooms)").fetchall()]
    if "profile_id" not in room_cols:
        conn.execute("ALTER TABLE rooms ADD COLUMN profile_id INTEGER REFERENCES profiles(id)")

    profile_cols = [row["name"] for row in conn.execute("PRAGMA table_info(profiles)").fetchall()]
    if "emoji" not in profile_cols:
        conn.execute("ALTER TABLE profiles ADD COLUMN emoji TEXT NOT NULL DEFAULT '🙂'")

    room_cols2 = [row["name"] for row in conn.execute("PRAGMA table_info(rooms)").fetchall()]
    if "is_custom" not in room_cols2:
        conn.execute("ALTER TABLE rooms ADD COLUMN is_custom INTEGER NOT NULL DEFAULT 0")

    # 기존 데이터 보존용 1회성 백필: profiles가 비어있고 characters에 데이터가 있으면
    # me_name으로 프로필 하나를 만들어 기존 캐릭터·방을 모두 그 프로필에 연결한다.
    profile_count = conn.execute("SELECT COUNT(*) AS n FROM profiles").fetchone()["n"]
    character_count = conn.execute("SELECT COUNT(*) AS n FROM characters").fetchone()["n"]
    if profile_count == 0 and character_count > 0:
        me_row = conn.execute("SELECT value FROM settings WHERE key = 'me_name'").fetchone()
        profile_name = me_row["value"] if me_row else "나"
        cur = conn.execute("INSERT INTO profiles (name) VALUES (?)", (profile_name,))
        profile_id = cur.lastrowid
        conn.execute("UPDATE characters SET profile_id = ?", (profile_id,))
        conn.execute("UPDATE rooms SET profile_id = ?", (profile_id,))
        conn.execute(
            "INSERT OR REPLACE INTO settings (key, value) VALUES ('current_profile_id', ?)",
            (str(profile_id),),
        )

    conn.commit()
    conn.close()


def get_current_profile_id(conn) -> int:
    """settings.current_profile_id가 유효하면 그대로 쓰고, 아니면 가장 작은 id의 프로필로,
    프로필이 아예 없으면 me_name으로 기본 프로필을 만들어 대체한다. 대체 시 settings도 갱신한다."""
    row = conn.execute("SELECT value FROM settings WHERE key = 'current_profile_id'").fetchone()
    if row is not None:
        candidate_id = int(row["value"])
        if conn.execute("SELECT 1 FROM profiles WHERE id = ?", (candidate_id,)).fetchone():
            return candidate_id

    fallback = conn.execute("SELECT id FROM profiles ORDER BY id LIMIT 1").fetchone()
    if fallback is not None:
        profile_id = fallback["id"]
    else:
        me_row = conn.execute("SELECT value FROM settings WHERE key = 'me_name'").fetchone()
        profile_name = me_row["value"] if me_row else "나"
        cur = conn.execute("INSERT INTO profiles (name) VALUES (?)", (profile_name,))
        profile_id = cur.lastrowid

    conn.execute(
        "INSERT OR REPLACE INTO settings (key, value) VALUES ('current_profile_id', ?)",
        (str(profile_id),),
    )
    conn.commit()
    return profile_id


def clear_profile_data(profile_id: int) -> None:
    """settings나 다른 프로필의 데이터는 건드리지 않고, 이 프로필의 캐릭터·기억·방·멤버·메시지만 지운다.
    자식 테이블부터 지워 FK 제약을 피한다."""
    conn = get_connection()
    try:
        conn.execute(
            "DELETE FROM messages WHERE room_id IN (SELECT id FROM rooms WHERE profile_id = ?)",
            (profile_id,),
        )
        conn.execute(
            "DELETE FROM room_members WHERE room_id IN (SELECT id FROM rooms WHERE profile_id = ?)",
            (profile_id,),
        )
        conn.execute(
            "DELETE FROM memories WHERE character_id IN (SELECT id FROM characters WHERE profile_id = ?)",
            (profile_id,),
        )
        conn.execute("DELETE FROM rooms WHERE profile_id = ?", (profile_id,))
        conn.execute("DELETE FROM characters WHERE profile_id = ?", (profile_id,))
        conn.execute("DELETE FROM deleted_rooms WHERE profile_id = ?", (profile_id,))
        conn.commit()
    finally:
        conn.close()
