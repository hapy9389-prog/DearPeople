import logging
import os

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ai import call_claude_json
from db import get_connection, get_current_profile_id, get_profile_name
from routes_characters import build_character_description, create_memory, MemoryRequest
from routes_messages import fetch_recent_messages, format_recent_conversation, RECENT_LIMIT

router = APIRouter()

MY_MESSAGE_LIMIT = 30
PREVIOUS_SUGGESTION_LIMIT = 30


def fetch_recent_my_message_room_ids(conn, profile_id, limit=MY_MESSAGE_LIMIT):
    """최근 내가 보낸 메시지(최대 limit개)가 속한 방 id를 최근 순으로 중복 없이 반환."""
    rows = conn.execute(
        "SELECT m.room_id FROM messages m JOIN rooms r ON r.id = m.room_id "
        "WHERE r.profile_id = ? AND r.includes_me = 1 AND m.sender_character_id IS NULL "
        "ORDER BY m.id DESC LIMIT ?",
        (profile_id, limit),
    ).fetchall()
    room_ids = []
    for row in rows:
        if row["room_id"] not in room_ids:
            room_ids.append(row["room_id"])
    return room_ids


def fetch_rooms_by_ids(conn, room_ids):
    if not room_ids:
        return []
    placeholders = ",".join("?" for _ in room_ids)
    rows = conn.execute(f"SELECT id, name FROM rooms WHERE id IN ({placeholders})", room_ids).fetchall()
    by_id = {r["id"]: dict(r) for r in rows}
    return [by_id[rid] for rid in room_ids if rid in by_id]


def fetch_room_members(conn, room_id):
    rows = conn.execute(
        "SELECT c.id, c.name, c.relation, c.personality, c.speech_style, c.calls_me, c.reaction_style "
        "FROM room_members rm JOIN characters c ON c.id = rm.character_id "
        "WHERE rm.room_id = ? ORDER BY c.id", (room_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def collect_touched_characters(conn, rooms):
    """rooms는 최근 순(가장 최근에 내가 메시지를 보낸 방이 먼저). 캐릭터별로 가장 먼저(=가장 최근)
    등장한 방을 source_room_id 후보로 기록한다."""
    characters_by_id = {}
    char_to_source_room = {}
    for room in rooms:
        for member in fetch_room_members(conn, room["id"]):
            if member["id"] not in characters_by_id:
                characters_by_id[member["id"]] = member
                char_to_source_room[member["id"]] = room["id"]
    return list(characters_by_id.values()), char_to_source_room


def build_room_conversation_block(conn, room, my_name):
    recent = fetch_recent_messages(conn, room["id"], RECENT_LIMIT)
    return f"[채팅방: {room['name']}]\n{format_recent_conversation(recent, my_name)}"


def fetch_previous_suggestion_contents(conn, profile_id, limit=PREVIOUS_SUGGESTION_LIMIT):
    """최근 것부터 최대 limit개만 가져온다(계속 쌓여도 프롬프트가 무한히 길어지지 않도록)."""
    rows = conn.execute(
        "SELECT c.name AS character_name, ms.content FROM memory_suggestions ms "
        "JOIN characters c ON c.id = ms.character_id "
        "WHERE ms.profile_id = ? ORDER BY ms.id DESC LIMIT ?",
        (profile_id, limit),
    ).fetchall()
    return list(reversed(rows))


def fetch_all_profile_memories(conn, profile_id):
    """겹침 판단 범위를 넓히기 위해, 이 프로필의 모든 캐릭터가 가진 기억 전체를 가져온다.
    (제안 대상 캐릭터의 기억뿐 아니라 다른 캐릭터가 이미 아는 사실과도 겹치지 않게 하기 위함)"""
    rows = conn.execute(
        "SELECT c.name AS character_name, m.content FROM memories m "
        "JOIN characters c ON c.id = m.character_id "
        "WHERE c.profile_id = ? ORDER BY m.id",
        (profile_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def generate_memory_suggestion_candidates(conn, profile_id, my_name, fast_model):
    room_ids = fetch_recent_my_message_room_ids(conn, profile_id, MY_MESSAGE_LIMIT)
    if not room_ids:
        return []
    rooms = fetch_rooms_by_ids(conn, room_ids)
    touched_characters, char_to_source_room = collect_touched_characters(conn, rooms)
    if not touched_characters:
        return []

    member_blocks = "\n".join(build_character_description(conn, c) for c in touched_characters)
    rooms_text = "\n\n".join(build_room_conversation_block(conn, r, my_name) for r in rooms)

    previous = fetch_previous_suggestion_contents(conn, profile_id)
    previous_text = (
        "\n".join(f"{p['character_name']}: {p['content']}" for p in previous) if previous else "(없음)"
    )

    all_memories = fetch_all_profile_memories(conn, profile_id)
    all_memories_text = (
        "\n".join(f"{m['character_name']}: {m['content']}" for m in all_memories) if all_memories else "(없음)"
    )

    system_prompt = (
        "당신은 모바일 채팅 앱 'DearPeople'에서, 사용자와 캐릭터들의 최근 대화를 보고 "
        "앞으로 캐릭터들이 기억해두면 좋을 사용자에 대한 새로운 사실을 찾아내는 도우미입니다. "
        f"참여 캐릭터 정보는 다음과 같습니다.\n{member_blocks}\n"
        f"최근 대화 내용은 다음과 같습니다(여러 채팅방일 수 있습니다).\n{rooms_text}\n"
        f"이 사용자의 모든 캐릭터가 이미 알고 있는 기억 전체 목록입니다(제안 대상 캐릭터가 아니어도 "
        f"의미가 겹치면 제안하면 안 됩니다).\n{all_memories_text}\n"
        f"지금까지 제안되었던 후보 목록입니다(상태와 무관하게 이미 검토된 내용이므로 겹치면 안 됨).\n"
        f"{previous_text}\n"
        "위 대화에서 사용자(캐릭터가 아닌 쪽 화자)에 대해 '새롭게 드러난, 기억해둘 만한 사실'을 "
        "최대 5개까지 뽑으세요. 취향, 근황, 고민, 최근 있었던 일처럼 구체적인 사실이어야 하고, "
        "위에 나열된 기억 전체 목록이나 이전 제안 목록과 의미가 겹치는 내용은 절대 포함하지 마세요. "
        "새로 기억할 만한 내용이 없다면 빈 배열을 반환해도 됩니다. "
        "각 항목마다 그 사실을 가장 잘 기억해둘 만한 캐릭터 한 명을 위 참여 캐릭터 이름 중에서 "
        "정확히 골라 character 필드에 쓰고, content 필드에는 그 캐릭터 입장에서 기억할 만한 "
        "사실을 한 문장으로 쓰세요. "
        "반드시 아래 JSON 배열 형식으로만 응답하고, 다른 설명이나 코드블록 표시는 출력하지 마세요.\n"
        '[{"character": "이름", "content": "기억할 내용"}]'
    )

    result = call_claude_json(
        system_prompt=system_prompt,
        messages=[{"role": "user", "content": "위 대화를 보고 기억할 만한 사실을 찾아주세요."}],
        model=fast_model,
    )
    if not isinstance(result, list):
        result = []

    name_to_id = {c["name"]: c["id"] for c in touched_characters}
    candidates = []
    for item in result:
        if len(candidates) >= 5:
            break
        if not isinstance(item, dict):
            continue
        character_name = str(item.get("character") or "").strip()
        content = str(item.get("content") or "").strip()
        if not content or character_name not in name_to_id:
            continue
        character_id = name_to_id[character_name]
        candidates.append({
            "character_id": character_id,
            "content": content,
            "source_room_id": char_to_source_room.get(character_id),
        })
    return candidates


class SuggestionAcceptRequest(BaseModel):
    content: str


@router.post("/api/memories/suggest")
def suggest_memories():
    conn = get_connection()
    try:
        profile_id = get_current_profile_id(conn)
        my_name = get_profile_name(conn, profile_id)
        try:
            candidates = generate_memory_suggestion_candidates(
                conn, profile_id, my_name, os.environ.get("FAST_MODEL")
            )
        except Exception:
            logging.exception("기억 제안 생성 실패")
            raise HTTPException(status_code=502, detail="기억 제안 생성에 실패했습니다.")

        new_ids = []
        for c in candidates:
            cur = conn.execute(
                "INSERT INTO memory_suggestions (profile_id, character_id, content, source_room_id, status) "
                "VALUES (?, ?, ?, ?, 'pending')",
                (profile_id, c["character_id"], c["content"], c["source_room_id"]),
            )
            new_ids.append(cur.lastrowid)
        conn.commit()

        if not new_ids:
            return []
        placeholders = ",".join("?" for _ in new_ids)
        rows = conn.execute(
            f"SELECT ms.id, ms.character_id, c.name AS character_name, ms.content, "
            f"ms.source_room_id, ms.created_at, ms.status "
            f"FROM memory_suggestions ms JOIN characters c ON c.id = ms.character_id "
            f"WHERE ms.id IN ({placeholders}) ORDER BY ms.id",
            new_ids,
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


@router.get("/api/memories/suggestions")
def list_memory_suggestions():
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT ms.id, ms.character_id, c.name AS character_name, ms.content, "
            "ms.source_room_id, ms.created_at, ms.status "
            "FROM memory_suggestions ms JOIN characters c ON c.id = ms.character_id "
            "WHERE ms.profile_id = ? AND ms.status = 'pending' ORDER BY ms.id",
            (get_current_profile_id(conn),),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


@router.post("/api/memories/suggestions/{suggestion_id}/accept")
def accept_memory_suggestion(suggestion_id: int, body: SuggestionAcceptRequest):
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT character_id, status FROM memory_suggestions WHERE id = ? AND profile_id = ?",
            (suggestion_id, get_current_profile_id(conn)),
        ).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="제안을 찾을 수 없습니다.")
        if row["status"] != "pending":
            raise HTTPException(status_code=400, detail="이미 처리된 제안입니다.")
        character_id = row["character_id"]
    finally:
        conn.close()

    memory = create_memory(character_id, MemoryRequest(content=body.content))

    conn = get_connection()
    try:
        conn.execute("UPDATE memory_suggestions SET status = 'accepted' WHERE id = ?", (suggestion_id,))
        conn.commit()
    finally:
        conn.close()
    return memory


@router.post("/api/memories/suggestions/{suggestion_id}/reject")
def reject_memory_suggestion(suggestion_id: int):
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT status FROM memory_suggestions WHERE id = ? AND profile_id = ?",
            (suggestion_id, get_current_profile_id(conn)),
        ).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="제안을 찾을 수 없습니다.")
        if row["status"] != "pending":
            raise HTTPException(status_code=400, detail="이미 처리된 제안입니다.")
        conn.execute("UPDATE memory_suggestions SET status = 'rejected' WHERE id = ?", (suggestion_id,))
        conn.commit()
    finally:
        conn.close()
    return {"ok": True}
