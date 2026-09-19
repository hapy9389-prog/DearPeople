import os
import re
import sqlite3
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from fastapi import HTTPException

from device import get_device_key

load_dotenv()

DB_PATH = Path(__file__).parent / "dearpeople.db"
MIGRATION_PATH = Path(__file__).parent.parent / "migrations" / "0001_init.sql"

# RETURNING id를 붙이면 안 되는 테이블(id 컬럼이 없음)
NO_ID_TABLES = {"room_members", "settings"}


def use_postgres() -> bool:
    return bool(os.environ.get("DATABASE_URL"))


class PgCursor:
    """sqlite3 커서처럼 fetchone/fetchall/lastrowid/rowcount를 제공하는 얇은 래퍼."""

    def __init__(self, cur, lastrowid=None):
        self._cur = cur
        self.lastrowid = lastrowid

    @property
    def rowcount(self):
        return self._cur.rowcount

    def fetchone(self):
        return self._cur.fetchone()

    def fetchall(self):
        return self._cur.fetchall()


class PgConnection:
    """sqlite3.Connection과 같은 방식(?, execute, row["col"])으로 psycopg2를 쓰게 하는 래퍼."""

    def __init__(self, conn):
        self._conn = conn

    def execute(self, sql, params=()):
        import psycopg2.extras

        sql = sql.replace("?", "%s")
        insert = re.match(r"\s*INSERT\s+INTO\s+(\w+)", sql, re.IGNORECASE)
        returning = bool(
            insert and insert.group(1).lower() not in NO_ID_TABLES
            and "RETURNING" not in sql.upper()
        )
        if returning:
            sql += " RETURNING id"
        cur = self._conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(sql, tuple(params))
        lastrowid = cur.fetchone()["id"] if returning else None
        return PgCursor(cur, lastrowid)

    def commit(self):
        self._conn.commit()

    def close(self):
        self._conn.close()


def get_connection():
    if use_postgres():
        import psycopg2

        return PgConnection(psycopg2.connect(os.environ["DATABASE_URL"]))
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.row_factory = sqlite3.Row
    return conn


def get_setting(conn, key):
    row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
    return row["value"] if row else None


def set_setting(conn, key, value) -> None:
    """커밋은 호출자가 한다. SQLite(3.24+)와 PostgreSQL 모두 지원하는 upsert 문법."""
    conn.execute(
        "INSERT INTO settings (key, value) VALUES (?, ?) "
        "ON CONFLICT (key) DO UPDATE SET value = excluded.value",
        (key, value),
    )


def init_db() -> None:
    conn = get_connection()
    if use_postgres():
        # 서버 DB는 빈 상태에서 시작한다. 테이블이 없을 때만 초기 스키마를 적용한다.
        if conn.execute("SELECT to_regclass('public.profiles') AS t").fetchone()["t"] is None:
            conn._conn.cursor().execute(MIGRATION_PATH.read_text(encoding="utf-8"))
            conn.commit()
        conn.close()
        return
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS profiles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            emoji TEXT NOT NULL DEFAULT 'user',
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

        CREATE TABLE IF NOT EXISTS memory_suggestions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            profile_id INTEGER NOT NULL REFERENCES profiles(id),
            character_id INTEGER NOT NULL REFERENCES characters(id),
            content TEXT NOT NULL,
            source_room_id INTEGER NOT NULL REFERENCES rooms(id),
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            status TEXT NOT NULL DEFAULT 'pending'
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
        conn.execute("ALTER TABLE profiles ADD COLUMN emoji TEXT NOT NULL DEFAULT 'user'")

    room_cols2 = [row["name"] for row in conn.execute("PRAGMA table_info(rooms)").fetchall()]
    if "is_custom" not in room_cols2:
        conn.execute("ALTER TABLE rooms ADD COLUMN is_custom INTEGER NOT NULL DEFAULT 0")

    char_cols2 = [row["name"] for row in conn.execute("PRAGMA table_info(characters)").fetchall()]
    if "reaction_style" not in char_cols2:
        conn.execute("ALTER TABLE characters ADD COLUMN reaction_style TEXT NOT NULL DEFAULT ''")

    # 1회성 백필: 자동 생성 방 이름 변경("나 빼고 가족방"→"가족들끼리", "부모님방"→"엄마와 아빠").
    # 이미 바뀐 행은 WHERE 조건에 걸리지 않으므로 여러 번 실행해도 안전하다.
    conn.execute("UPDATE rooms SET name = '가족들끼리' WHERE name = '나 빼고 가족방'")
    conn.execute("UPDATE rooms SET name = '엄마와 아빠' WHERE name = '부모님방'")
    conn.execute("UPDATE deleted_rooms SET room_key = '가족들끼리' WHERE room_key = '나 빼고 가족방'")
    conn.execute("UPDATE deleted_rooms SET room_key = '엄마와 아빠' WHERE room_key = '부모님방'")

    # 기기별 분리: 기존 프로필은 모두 'local' 기기 소유로 둔다.
    profile_cols2 = [row["name"] for row in conn.execute("PRAGMA table_info(profiles)").fetchall()]
    if "device_key" not in profile_cols2:
        conn.execute("ALTER TABLE profiles ADD COLUMN device_key TEXT NOT NULL DEFAULT 'local'")
    if "last_tick_at" not in profile_cols2:
        conn.execute("ALTER TABLE profiles ADD COLUMN last_tick_at TEXT")
    # 1회성: 전역 current_profile_id를 'local' 기기용 키로 옮긴다.
    old_current = get_setting(conn, "current_profile_id")
    if old_current is not None:
        if get_setting(conn, "current_profile_id:local") is None:
            set_setting(conn, "current_profile_id:local", old_current)
        conn.execute("DELETE FROM settings WHERE key = 'current_profile_id'")

    # 기존 데이터 보존용 1회성 백필: profiles가 비어있고 characters에 데이터가 있으면
    # 기본 이름('나')으로 프로필 하나를 만들어 기존 캐릭터·방을 모두 그 프로필에 연결한다.
    profile_count = conn.execute("SELECT COUNT(*) AS n FROM profiles").fetchone()["n"]
    character_count = conn.execute("SELECT COUNT(*) AS n FROM characters").fetchone()["n"]
    if profile_count == 0 and character_count > 0:
        cur = conn.execute("INSERT INTO profiles (name, device_key) VALUES (?, 'local')", ("나",))
        profile_id = cur.lastrowid
        conn.execute("UPDATE characters SET profile_id = ?", (profile_id,))
        conn.execute("UPDATE rooms SET profile_id = ?", (profile_id,))
        set_setting(conn, "current_profile_id:local", str(profile_id))

    conn.commit()
    conn.close()


def get_current_profile_id(conn) -> Optional[int]:
    """현재 기기(X-Device-Key)의 current_profile_id가 유효하면 그대로 쓰고, 아니면 그 기기의
    가장 작은 id의 프로필로 대체한다(settings도 갱신). 그 기기에 프로필이 없으면 None —
    프로필은 온보딩에서 사용자가 이름을 입력할 때만 만들어진다."""
    device_key = get_device_key()
    setting_key = "current_profile_id:" + device_key
    value = get_setting(conn, setting_key)
    if value is not None:
        candidate_id = int(value)
        if conn.execute(
            "SELECT 1 FROM profiles WHERE id = ? AND device_key = ?", (candidate_id, device_key)
        ).fetchone():
            return candidate_id

    fallback = conn.execute(
        "SELECT id FROM profiles WHERE device_key = ? ORDER BY id LIMIT 1", (device_key,)
    ).fetchone()
    if fallback is None:
        return None

    set_setting(conn, setting_key, str(fallback["id"]))
    conn.commit()
    return fallback["id"]


def require_current_profile_id(conn) -> int:
    """프로필이 필요한 쓰기·AI 경로용. 프로필이 없으면 404."""
    profile_id = get_current_profile_id(conn)
    if profile_id is None:
        raise HTTPException(status_code=404, detail="프로필이 없습니다.")
    return profile_id


def get_profile_name(conn, profile_id: int) -> str:
    """대화 생성에 쓰는 사용자 이름. 프로필 이름을 그대로 쓰고, 없으면 '나'."""
    row = conn.execute("SELECT name FROM profiles WHERE id = ?", (profile_id,)).fetchone()
    return row["name"] if row else "나"


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
        conn.execute("DELETE FROM memory_suggestions WHERE profile_id = ?", (profile_id,))
        conn.execute("DELETE FROM rooms WHERE profile_id = ?", (profile_id,))
        conn.execute("DELETE FROM characters WHERE profile_id = ?", (profile_id,))
        conn.execute("DELETE FROM deleted_rooms WHERE profile_id = ?", (profile_id,))
        conn.commit()
    finally:
        conn.close()
