import concurrent.futures
import logging
import os
import random

from fastapi import APIRouter, HTTPException

from ai import call_claude_json
from db import get_connection, get_current_profile_id, get_profile_name
from images import pick_photo
from routes_characters import build_character_description
from routes_messages import CHARACTER_PHOTO_PROBABILITY, fetch_recent_messages, format_recent_conversation
from routes_rooms import resolve_sender

router = APIRouter()

INITIATE_PROBABILITY = 0.3
PHOTO_PROBABILITY = 0.5


def fetch_room_members(conn, room_id):
    rows = conn.execute(
        "SELECT c.id, c.name, c.relation, c.personality, c.speech_style, c.calls_me, c.reaction_style "
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


def resolve_generated_messages(items, name_to_id, my_name, allow_photo=False):
    resolved = []
    photo_used = False
    for item in items:
        ok, sender_id = resolve_sender(item.get("sender", ""), name_to_id, my_name)
        if not ok:
            continue
        if allow_photo and item.get("type") == "photo" and not photo_used:
            description = (item.get("description") or "").strip()
            if not description:
                continue
            resolved.append({
                "sender_character_id": sender_id,
                "type": "photo",
                "content": description,
                "caption": (item.get("caption") or "").strip(),
                "image_path": pick_photo(item.get("category", "")),
            })
            photo_used = True
            continue
        content = item.get("content", "")
        if not content:
            continue
        resolved.append({
            "sender_character_id": sender_id, "type": "text",
            "content": content, "caption": None, "image_path": None,
        })
    return resolved


def generate_no_me_conversation(conn, room, members, my_name, chat_model):
    member_blocks = "\n".join(build_character_description(conn, m) for m in members)
    conversation = format_recent_conversation(fetch_recent_messages(conn, room["id"], 20), my_name)
    my_recent = fetch_my_recent_messages_for_room(conn, [m["id"] for m in members], 10)
    my_recent_text = (
        "\n".join(f"[{r['room_name']}] {r['content']}" for r in my_recent) if my_recent else "(없음)"
    )
    if random.random() < PHOTO_PROBABILITY:
        photo_instruction = (
            "메시지 중 정확히 1개는 반드시 참여자가 사진을 공유하는 형태로 만드세요(그 메시지의 type은 'photo'). "
            "사진 메시지는 category(food/scenery/pet/object/place 중 하나), "
            "description(사진 속 장면을 한두 문장으로 묘사, 사람 얼굴은 묘사하지 않음), "
            "caption(그 사진에 캐릭터가 붙이는 짧은 말)을 포함하세요. "
            "사진 메시지 바로 다음 메시지는 다른 참여자 한 명이 그 사진에 반응하는 내용으로 만드세요."
        )
    else:
        photo_instruction = "이번에는 사진 없이 텍스트 메시지만 만드세요(모든 메시지의 type은 'text')."
    system_prompt = (
        "당신은 모바일 채팅 앱 'DearPeople'에서, 사용자가 없는 채팅방의 대화를 생성하는 도우미입니다. "
        f"채팅방 이름은 '{room['name']}'이고 참여자는 다음과 같습니다.\n{member_blocks}\n"
        f"이 방의 최근 대화:\n{conversation}\n"
        f"사용자({my_name})가 다른 방들에서 최근에 한 말(참고용, 방 이름 포함):\n{my_recent_text}\n"
        f"참여자들은 사용자({my_name})를 아끼는 사이입니다. 대화 주제는 주로 사용자에 대한 이야기로, "
        "위 참고 내용을 화제 삼아 자연스럽게 이어가세요. 가벼운 놀림은 물론, 걱정이나 답답함을 "
        "솔직하게 나누는 것도 괜찮습니다(예: '요즘 연락이 뜸하네', '그 말은 좀 서운했어'). "
        "다만 악의적인 뒷담화나 인신공격은 하지 마세요. 이전 대화를 반복하지 말고 새로운 내용으로 이어가세요. "
        "추억과 최근 대화에 없는 사건을 사실처럼 지어내지 마세요. "
        "5개 이상 8개 이하의 메시지를 만드세요. "
        f"{photo_instruction} "
        "사진이 아닌 메시지는 type을 'text'로 하고 content만 채우세요. "
        "sender는 반드시 위 참여자 이름 중 하나여야 하며, 사용자 이름을 sender로 쓰면 안 됩니다. "
        "반드시 아래 JSON 배열 형식으로만 응답하고, 다른 설명이나 코드블록 표시는 출력하지 마세요.\n"
        '[{"sender": "이름", "type": "text", "content": "메시지 내용"}, '
        '{"sender": "이름", "type": "photo", "category": "food", "description": "장면 묘사", "caption": "캡션"}]'
    )
    result = call_claude_json(
        system_prompt=system_prompt,
        messages=[{"role": "user", "content": "위 설정에 맞는 대화를 생성해 주세요."}],
        model=chat_model,
    )
    name_to_id = {m["name"]: m["id"] for m in members}
    return resolve_generated_messages(result, name_to_id, my_name, allow_photo=True)


def generate_initiate_messages(conn, room, members, my_name, chat_model):
    member_blocks = "\n".join(build_character_description(conn, m) for m in members)
    conversation = format_recent_conversation(fetch_recent_messages(conn, room["id"], 20), my_name)
    if random.random() < CHARACTER_PHOTO_PROBABILITY:
        photo_instruction = (
            "메시지 중 하나는 사진을 공유하는 형태로 만들 수 있습니다(그 메시지의 type은 'photo'). "
            "사진 메시지는 category(food/scenery/pet/object/place 중 하나), "
            "description(사진 속 장면을 한두 문장으로 묘사, 사람 얼굴은 묘사하지 않음), "
            "caption(그 사진에 캐릭터가 붙이는 짧은 말)을 포함하세요."
        )
    else:
        photo_instruction = "이번에는 사진 없이 텍스트 메시지만 만드세요(모든 메시지의 type은 'text')."
    system_prompt = (
        "당신은 모바일 채팅 앱 'DearPeople'에서, 시간이 좀 지난 뒤 캐릭터가 사용자에게 먼저 "
        "말을 거는 메시지를 생성하는 도우미입니다. "
        f"채팅방 이름은 '{room['name']}'이고 참여자는 다음과 같습니다.\n{member_blocks}\n"
        f"이 방의 최근 대화:\n{conversation}\n"
        f"참여자 중 한 명이 사용자({my_name})에게 먼저 말을 거는 메시지를 1~2개 만드세요. "
        "이전 대화를 반복하지 말고 자연스럽게 새로 시작하세요. "
        "추억과 최근 대화에 없는 사건을 사실처럼 지어내지 마세요. "
        f"{photo_instruction} "
        "사진이 아닌 메시지는 type을 'text'로 하고 content만 채우세요. "
        "sender는 반드시 위 참여자 이름 중 하나여야 하며, 사용자 이름을 sender로 쓰면 안 됩니다. "
        "반드시 아래 JSON 배열 형식으로만 응답하고, 다른 설명이나 코드블록 표시는 출력하지 마세요.\n"
        '[{"sender": "이름", "type": "text", "content": "메시지 내용"}, '
        '{"sender": "이름", "type": "photo", "category": "food", "description": "장면 묘사", "caption": "캡션"}]'
    )
    result = call_claude_json(
        system_prompt=system_prompt,
        messages=[{"role": "user", "content": "먼저 말을 거는 메시지를 만들어 주세요."}],
        model=chat_model,
    )
    name_to_id = {m["name"]: m["id"] for m in members}
    return resolve_generated_messages(result, name_to_id, my_name, allow_photo=True)


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
        profile_id = get_current_profile_id(conn)
        rooms = [dict(r) for r in conn.execute(
            "SELECT id, name, includes_me FROM rooms WHERE profile_id = ? ORDER BY id",
            (profile_id,),
        ).fetchall()]
        my_name = get_profile_name(conn, profile_id)
    finally:
        conn.close()

    if not rooms:
        raise HTTPException(status_code=400, detail="방이 없습니다.")

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
                    "INSERT INTO messages (room_id, sender_character_id, type, content, caption, image_path) "
                    "VALUES (?, ?, ?, ?, ?, ?)",
                    (
                        room["id"], msg["sender_character_id"], msg["type"],
                        msg["content"], msg["caption"], msg["image_path"],
                    ),
                )
            counts[str(room["id"])] = len(messages)
        conn.commit()
    finally:
        conn.close()

    return {"counts": counts}
