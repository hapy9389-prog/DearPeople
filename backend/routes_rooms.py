import concurrent.futures
import logging
import os

from fastapi import APIRouter, HTTPException

from ai import call_claude_json
from db import get_connection
from routes_characters import build_character_description

router = APIRouter()


def fetch_characters(conn):
    rows = conn.execute(
        "SELECT id, relation, grp, name, personality, speech_style, calls_me FROM characters"
    ).fetchall()
    return [dict(r) for r in rows]


def build_room_plan(characters):
    """순수 함수, DB/AI 호출 없음."""
    plan = []
    by_relation = {}
    for c in characters:
        by_relation.setdefault(c["relation"], c["id"])

    family = [c for c in characters if c["grp"] == "family"]
    friends = [c for c in characters if c["grp"] == "friend"]

    if len(family) >= 2:
        family_ids = [c["id"] for c in family]
        plan.append({"name": "우리 가족", "type": "group", "includes_me": 1, "member_ids": family_ids})
        plan.append({"name": "나 빼고 가족방", "type": "group", "includes_me": 0, "member_ids": family_ids})

    # elif 아님: 부모님방은 가족방들과 별개로 추가 생성된다.
    if "엄마" in by_relation and "아빠" in by_relation:
        plan.append({
            "name": "부모님방", "type": "group", "includes_me": 0,
            "member_ids": [by_relation["엄마"], by_relation["아빠"]],
        })

    if len(friends) >= 2:
        friend_ids = [c["id"] for c in friends]
        plan.append({"name": "친구들", "type": "group", "includes_me": 1, "member_ids": friend_ids})
        plan.append({"name": "친구들끼리", "type": "group", "includes_me": 0, "member_ids": friend_ids})

    for c in characters:
        plan.append({"name": c["name"], "type": "dm", "includes_me": 1, "member_ids": [c["id"]]})

    return plan


def build_room_message_prompt(conn, room, members, my_name):
    participants_block = "\n".join(build_character_description(conn, m) for m in members)

    if room["includes_me"]:
        me_instruction = (
            f"이 대화방에는 사용자({my_name})도 있지만, 사용자의 발화는 생성하지 마세요. "
            f"캐릭터들이 사용자({my_name})에게 말을 거는 형태로 대화를 만드세요."
        )
    else:
        me_instruction = f"이 대화방에는 사용자({my_name})가 없습니다. 참여자끼리만 대화하세요."

    system_prompt = (
        "당신은 모바일 채팅 앱 'DearPeople'의 대화 메시지를 생성하는 도우미입니다. "
        f"채팅방 이름은 '{room['name']}'이고 참여자는 다음과 같습니다.\n{participants_block}\n"
        f"{me_instruction}\n"
        "각 참여자의 성격, 말투, 추억을 반영한 자연스러운 한국어 대화를 3~5개 메시지로 만드세요. "
        "sender는 반드시 위 참여자 이름 중 하나여야 하며, 그 외의 이름(특히 사용자 이름)을 "
        "sender로 쓰면 안 됩니다. "
        "반드시 아래 JSON 배열 형식으로만 응답하고, 다른 설명이나 코드블록 표시는 출력하지 마세요.\n"
        '[{"sender": "이름", "content": "메시지 내용"}, ...]'
    )
    return system_prompt, "위 설정에 맞는 대화를 생성해 주세요."


def resolve_sender(sender_name, member_name_to_id, my_name):
    """(True, character_id)면 인식됨. (False, None)이면 건너뜀(사용자 이름 포함, 전체 실패시키지 않음)."""
    if sender_name == my_name:
        return False, None
    if sender_name in member_name_to_id:
        return True, member_name_to_id[sender_name]
    return False, None


def generate_room_messages(room, characters_by_id, my_name, chat_model):
    members = [characters_by_id[cid] for cid in room["member_ids"]]
    conn = get_connection()
    try:
        system_prompt, user_message = build_room_message_prompt(conn, room, members, my_name)
    finally:
        conn.close()
    msg_args = [{"role": "user", "content": user_message}]
    try:
        ai_messages = call_claude_json(system_prompt, msg_args, model=chat_model)
    except Exception:
        ai_messages = call_claude_json(system_prompt, msg_args, model=chat_model)  # 방 1회 재시도

    name_to_id = {m["name"]: m["id"] for m in members}
    resolved = []
    for item in ai_messages:
        content = item.get("content", "")
        if not content:
            continue
        ok, sender_id = resolve_sender(item.get("sender", ""), name_to_id, my_name)
        if not ok:
            continue
        resolved.append({"sender_character_id": sender_id, "content": content})
    return {"plan": room, "messages": resolved}


@router.post("/api/rooms/generate")
def generate_rooms():
    conn = get_connection()
    try:
        characters = fetch_characters(conn)
        me_row = conn.execute("SELECT value FROM settings WHERE key = 'me_name'").fetchone()
    finally:
        conn.close()

    if len(characters) == 0:
        raise HTTPException(status_code=400, detail="캐릭터가 없습니다. 먼저 캐릭터를 추가해주세요.")

    my_name = me_row["value"] if me_row else "나"
    room_plan = build_room_plan(characters)
    characters_by_id = {c["id"]: c for c in characters}
    chat_model = os.environ.get("CHAT_MODEL")

    results = [None] * len(room_plan)
    executor = concurrent.futures.ThreadPoolExecutor(max_workers=5)
    future_to_index = {
        executor.submit(generate_room_messages, room, characters_by_id, my_name, chat_model): i
        for i, room in enumerate(room_plan)
    }
    for future in concurrent.futures.as_completed(future_to_index):
        i = future_to_index[future]
        try:
            results[i] = future.result()
        except Exception:
            logging.exception("방 '%s' 대화 생성 실패", room_plan[i]["name"])
            executor.shutdown(wait=False, cancel_futures=True)
            raise HTTPException(
                status_code=502,
                detail=f"'{room_plan[i]['name']}' 방의 대화 생성에 실패했습니다.",
            )
    executor.shutdown(wait=True)
    generated = results

    # 모든 방의 생성이 끝난 뒤에만 DB를 건드린다 (실패 시 기존 데이터 보존).
    conn = get_connection()
    try:
        conn.execute("DELETE FROM messages WHERE room_id IN (SELECT id FROM rooms)")
        conn.execute("DELETE FROM room_members")
        conn.execute("DELETE FROM rooms")

        for entry in generated:
            plan = entry["plan"]
            cur = conn.execute(
                "INSERT INTO rooms (name, type, includes_me) VALUES (?, ?, ?)",
                (plan["name"], plan["type"], plan["includes_me"]),
            )
            room_id = cur.lastrowid
            for cid in plan["member_ids"]:
                conn.execute(
                    "INSERT INTO room_members (room_id, character_id) VALUES (?, ?)", (room_id, cid)
                )
            for msg in entry["messages"]:
                conn.execute(
                    "INSERT INTO messages (room_id, sender_character_id, type, content) "
                    "VALUES (?, ?, 'text', ?)",
                    (room_id, msg["sender_character_id"], msg["content"]),
                )
        conn.commit()
    finally:
        conn.close()

    return {"ok": True, "room_count": len(generated)}


@router.get("/api/rooms")
def list_rooms():
    conn = get_connection()
    try:
        rooms = conn.execute("SELECT id, name, type, includes_me FROM rooms ORDER BY id").fetchall()
        result = []
        for r in rooms:
            members = conn.execute(
                "SELECT c.name FROM room_members rm JOIN characters c ON c.id = rm.character_id "
                "WHERE rm.room_id = ? ORDER BY c.id",
                (r["id"],),
            ).fetchall()
            last = conn.execute(
                "SELECT m.content, c.name AS sender_name FROM messages m "
                "LEFT JOIN characters c ON c.id = m.sender_character_id "
                "WHERE m.room_id = ? ORDER BY m.id DESC LIMIT 1",
                (r["id"],),
            ).fetchone()
            last_message = None
            if last:
                last_message = {
                    "content": last["content"],
                    "sender": last["sender_name"] if last["sender_name"] else "나",
                }
            result.append({
                "id": r["id"],
                "name": r["name"],
                "includes_me": bool(r["includes_me"]),
                "members": [m["name"] for m in members],
                "last_message": last_message,
            })
        return result
    finally:
        conn.close()
