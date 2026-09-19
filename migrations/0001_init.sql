-- PostgreSQL 초기 스키마 (현재 완성된 테이블 구조). created_at은 SQLite와 같은 UTC 문자열 형식을 쓴다.

CREATE TABLE profiles (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    emoji TEXT NOT NULL DEFAULT 'user',
    device_key TEXT NOT NULL DEFAULT 'local',
    last_tick_at TEXT,
    created_at TEXT NOT NULL DEFAULT (to_char(now() AT TIME ZONE 'utc', 'YYYY-MM-DD HH24:MI:SS'))
);
CREATE INDEX profiles_device_key_idx ON profiles (device_key);

CREATE TABLE characters (
    id SERIAL PRIMARY KEY,
    profile_id INTEGER NOT NULL REFERENCES profiles(id),
    relation TEXT NOT NULL,
    grp TEXT NOT NULL,
    name TEXT NOT NULL,
    personality TEXT,
    speech_style TEXT,
    calls_me TEXT,
    reaction_style TEXT NOT NULL DEFAULT ''
);

CREATE TABLE memories (
    id SERIAL PRIMARY KEY,
    character_id INTEGER NOT NULL REFERENCES characters(id),
    content TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (to_char(now() AT TIME ZONE 'utc', 'YYYY-MM-DD HH24:MI:SS'))
);

CREATE TABLE rooms (
    id SERIAL PRIMARY KEY,
    profile_id INTEGER NOT NULL REFERENCES profiles(id),
    name TEXT NOT NULL,
    type TEXT NOT NULL,
    includes_me INTEGER NOT NULL DEFAULT 1,
    is_custom INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE room_members (
    room_id INTEGER NOT NULL REFERENCES rooms(id),
    character_id INTEGER NOT NULL REFERENCES characters(id),
    PRIMARY KEY (room_id, character_id)
);

CREATE TABLE messages (
    id SERIAL PRIMARY KEY,
    room_id INTEGER NOT NULL REFERENCES rooms(id),
    sender_character_id INTEGER REFERENCES characters(id),
    type TEXT NOT NULL,
    content TEXT,
    caption TEXT,
    image_path TEXT,
    created_at TEXT NOT NULL DEFAULT (to_char(now() AT TIME ZONE 'utc', 'YYYY-MM-DD HH24:MI:SS'))
);

CREATE TABLE settings (
    key TEXT PRIMARY KEY,
    value TEXT
);

CREATE TABLE deleted_rooms (
    id SERIAL PRIMARY KEY,
    profile_id INTEGER NOT NULL REFERENCES profiles(id),
    room_key TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (to_char(now() AT TIME ZONE 'utc', 'YYYY-MM-DD HH24:MI:SS'))
);

CREATE TABLE memory_suggestions (
    id SERIAL PRIMARY KEY,
    profile_id INTEGER NOT NULL REFERENCES profiles(id),
    character_id INTEGER NOT NULL REFERENCES characters(id),
    content TEXT NOT NULL,
    source_room_id INTEGER NOT NULL REFERENCES rooms(id),
    created_at TEXT NOT NULL DEFAULT (to_char(now() AT TIME ZONE 'utc', 'YYYY-MM-DD HH24:MI:SS')),
    status TEXT NOT NULL DEFAULT 'pending'
);
