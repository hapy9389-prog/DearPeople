import concurrent.futures
import logging
import os
import random

from fastapi import APIRouter, HTTPException

from ai import call_claude_json
from db import get_connection
from routes_characters import build_character_description
from routes_messages import fetch_recent_messages, format_recent_conversation
from routes_rooms import resolve_sender

router = APIRouter()

INITIATE_PROBABILITY = 0.3


def fetch_room_members(conn, room_id):
    rows = conn.execute(
        "SELECT c.id, c.name, c.relation, c.personality, c.speech_style, c.calls_me "
        "FROM room_members rm JOIN characters c ON c.id = rm.character_id "
        "WHERE rm.room_id = ? ORDER BY c.id", (room_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def fetch_my_recent_messages_for_room(conn, member_ids, limit=10):
    """대상 방 멤버 중 누구라도 속한 '나 포함 방'에서 내가 보낸 메시지만 가져온다.
    (예: 엄마·아빠는 친구와의 1:1 대화를 알면 안 됨 — 전체 조회가 아니라 멤버 교집합으로 필터링)"""
    if not member_ids:
        return []
    placeholders = ",".join("?" for _ in member_ids)
    rows = conn.execute(
        f"SELECT m.content, r.name AS room_name FROM messages m "
        f"JOIN rooms r ON r.id = m.room_id "
        f"WHERE m.sender_character_id IS NULL AND EXISTS ("
        f"  SELECT 1 FROM room_members rm WHERE rm.room_id = m.room_id AND rm.character_id IN ({placeholders})"
        f") ORDER BY m.id DESC LIMIT ?",
        (*member_ids, limit),
    ).fetchall()
    return list(reversed(rows))


def resolve_generated_messages(items, name_to_id, my_name):
    resolved = []
    for item in items:
        content = item.get("content", "")
        if not content:
            continue
        ok, sender_id = resolve_sender(item.get("sender", ""), name_to_id, my_name)
        if not ok:
            continue
        resolved.append({"sender_character_id": sender_id, "content": content, "type": "text"})
    return resolved


def generate_no_me_conversation(conn, room, members, my_name, chat_model):
    member_blocks = "\n".join(build_character_description(conn, m) for m in members)
    conversation = format_recent_conversation(fetch_recent_messages(conn, room["id"], 20), my_name)
    my_recent = fetch_my_recent_messages_for_room(conn, [m["id"] for m in members], 10)
    my_recent_text = (
        "\n".join(f"[{r['room_name']}] {r['content']}" for r in my_recent) if my_recent else "(없음)"
    )
    system_prompt = (
        "당신은 모바일 채팅 앱 'DearPeople'에서, 사용자가 없는 채팅방의 대화를 생성하는 도우미입니다. "
        f"채팅방 이름은 '{room['name']}'이고 참여자는 다음과 같습니다.\n{member_blocks}\n"
        f"이 방의 최근 대화:\n{conversation}\n"
        f"사용자({my_name})가 다른 방들에서 최근에 한 말(참고용, 방 이름 포함):\n{my_recent_text}\n"
        f"참여자들은 사용자({my_name})를 아끼는 사이입니다. 대화 주제는 주로 사용자에 대한 이야기로, "
        "위 참고 내용을 화제 삼아 자연스럽게 이어가세요. 가벼운 놀림은 괜찮지만 "
        "비난이나 험담은 하지 마세요. 이전 대화를 반복하지 말고 새로운 내용으로 이어가세요. "
        "추억과 최근 대화에 없는 사건을 사실처럼 지어내지 마세요. "
        "5개 이상 8개 이하의 메시지를 만드세요. "
        "sender는 반드시 위 참여자 이름 중 하나여야 하며, 사용자 이름을 sender로 쓰면 안 됩니다. "
        "반드시 아래 JSON 배열 형식으로만 응답하고, 다른 설명이나 코드블록 표시는 출력하지 마세요.\n"
        '[{"sender": "이름", "content": "메시지 내용"}, ...]'
    )
    result = call_claude_json(
        system_prompt=system_prompt,
        messages=[{"role": "user", "content": "위 설정에 맞는 대화를 생성해 주세요."}],
        model=chat_model,
    )
    name_to_id = {m["name"]: m["id"] for m in members}
    return resolve_generated_messages(result, name_to_id, my_name)


def generate_initiate_messages(conn, room, members, my_name, chat_model):
    member_blocks = "\n".join(build_character_description(conn, m) for m in members)
    conversation = format_recent_conversation(fetch_recent_messages(conn, room["id"], 20), my_name)
    system_prompt = (
        "당신은 모바일 채팅 앱 'DearPeople'에서, 시간이 좀 지난 뒤 캐릭터가 사용자에게 먼저 "
        "말을 거는 메시지를 생성하는 도우미입니다. "
        f"채팅방 이름은 '{room['name']}'이고 참여자는 다음과 같습니다.\n{member_blocks}\n"
        f"이 방의 최근 대화:\n{conversation}\n"
        f"참여자 중 한 명이 사용자({my_name})에게 먼저 말을 거는 메시지를 1~2개 만드세요. "
        "이전 대화를 반복하지 말고 자연스럽게 새로 시작하세요. "
        "추억과 최근 대화에 없는 사건을 사실처럼 지어내지 마세요. "
        "sender는 반드시 위 참여자 이름 중 하나여야 하며, 사용자 이름을 sender로 쓰면 안 됩니다. "
        "반드시 아래 JSON 배열 형식으로만 응답하고, 다른 설명이나 코드블록 표시는 출력하지 마세요.\n"
        '[{"sender": "이름", "content": "메시지 내용"}, ...]'
    )
    result = call_claude_json(
        system_prompt=system_prompt,
        messages=[{"role": "user", "content": "먼저 말을 거는 메시지를 만들어 주세요."}],
        model=chat_model,
    )
    name_to_id = {m["name"]: m["id"] for m in members}
    return resolve_generated_messages(result, name_to_id, my_name)


def generate_tick_messages_for_room(room, my_name, chat_model):
    """방 정보를 받아 메시지 dict 목록을 반환한다 (DB 쓰기 없음).
    5단계에서 사진 타입을 추가할 때도 이 함수의 반환 형태(list of dict)를 그대로 확장한다."""
    conn = get_connection()
    try:
        members = fetch_room_members(conn, room["id"])
        if not members:
            return []
        if room["includes_me"]:
            if random.random() >= INITIATE_PROBABILITY:
                return []
            return generate_initiate_messages(conn, room, members, my_name, chat_model)
        return generate_no_me_conversation(conn, room, members, my_name, chat_model)
    finally:
        conn.close()


@router.post("/api/tick")
def tick():
    conn = get_connection()
    try:
        rooms = [dict(r) for r in conn.execute(
            "SELECT id, name, includes_me FROM rooms ORDER BY id"
        ).fetchall()]
        me_row = conn.execute("SELECT value FROM settings WHERE key = 'me_name'").fetchone()
    finally:
        conn.close()

    if not rooms:
        raise HTTPException(status_code=400, detail="방이 없습니다.")

    my_name = me_row["value"] if me_row else "나"
    chat_model = os.environ.get("CHAT_MODEL")

    results = [None] * len(rooms)
    failures = 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        future_to_index = {
            executor.submit(generate_tick_messages_for_room, room, my_name, chat_model): i
            for i, room in enumerate(rooms)
        }
        for future in concurrent.futures.as_completed(future_to_index):
            i = future_to_index[future]
            try:
                results[i] = future.result()
            except Exception:
                logging.exception("방 '%s' 시간 흐르기 생성 실패", rooms[i]["name"])
                failures += 1

    if failures == len(rooms):
        raise HTTPException(status_code=502, detail="시간 흐르기에 실패했습니다.")

    conn = get_connection()
    counts = {}
    try:
        for room, messages in zip(rooms, results):
            if not messages:
                continue
            for msg in messages:
                conn.execute(
                    "INSERT INTO messages (room_id, sender_character_id, type, content) VALUES (?, ?, ?, ?)",
                    (room["id"], msg["sender_character_id"], msg["type"], msg["content"]),
                )
            counts[str(room["id"])] = len(messages)
        conn.commit()
    finally:
        conn.close()

    return {"counts": counts}
