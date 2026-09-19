import concurrent.futures
import contextvars
import logging
import os
from typing import List

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ai import call_claude_json
from db import get_connection, get_current_profile_id, get_profile_name
from routes_characters import build_character_description

router = APIRouter()


def fetch_characters(conn, profile_id):
    rows = conn.execute(
        "SELECT id, relation, grp, name, personality, speech_style, calls_me, reaction_style "
        "FROM characters WHERE profile_id = ?",
        (profile_id,),
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
        plan.append({"name": "가족들끼리", "type": "group", "includes_me": 0, "member_ids": family_ids})

    # elif 아님: "엄마와 아빠" 방은 가족방들과 별개로 추가 생성된다.
    if "엄마" in by_relation and "아빠" in by_relation:
        plan.append({
            "name": "엄마와 아빠", "type": "group", "includes_me": 0,
            "member_ids": [by_relation["엄마"], by_relation["아빠"]],
        })

    if len(friends) >= 2:
        friend_ids = [c["id"] for c in friends]
        plan.append({"name": "친구들", "type": "group", "includes_me": 1, "member_ids": friend_ids})
        plan.append({"name": "친구들끼리", "type": "group", "includes_me": 0, "member_ids": friend_ids})

    for c in characters:
        plan.append({"name": c["name"], "type": "dm", "includes_me": 1, "member_ids": [c["id"]]})

    return plan


def build_room_message_prompt(conn, room, members, my_name, is_new_room=False):
    participants_block = "\n".join(build_character_description(conn, m) for m in members)

    if room["type"] == "dm":
        count_instruction = "그 캐릭터가 사용자에게 가볍게 말을 거는 정도로 1~2개의 메시지를 만드세요."
    elif room["includes_me"]:
        count_instruction = "여러 참여자가 사용자에게 한두 마디씩 건네는 정도로 2~4개의 메시지를 만드세요."
    else:
        count_instruction = "자연스러운 한국어 대화를 3~5개의 메시지로 만드세요."

    if room["includes_me"]:
        me_instruction = (
            f"이 대화방에는 사용자({my_name})도 있지만, 사용자의 발화는 생성하지 마세요. "
            f"캐릭터들이 사용자({my_name})에게 말을 거는 형태로 대화를 만드세요."
        )
    else:
        me_instruction = f"이 대화방에는 사용자({my_name})가 없습니다. 참여자끼리만 대화하세요."

    new_room_line = ""
    if is_new_room:
        if room["includes_me"]:
            new_room_instruction = (
                f"이 방은 방금 사용자({my_name})가 이 사람들을 한 방에 모아 새로 만든 방입니다. "
                "'무슨 일이야?', '오랜만에 다 모였네' 같은 반응으로 대화를 시작하세요."
            )
        else:
            new_room_instruction = (
                "이 방은 참여자들이 방금 모인 새로운 방입니다. "
                "서로 인사하거나 왜 모였는지 궁금해하는 반응으로 대화를 시작하세요."
            )
        new_room_line = f"{new_room_instruction} 이미 오래 대화해온 것처럼 쓰지 마세요.\n"

    system_prompt = (
        "당신은 모바일 채팅 앱 'DearPeople'의 대화 메시지를 생성하는 도우미입니다. "
        f"채팅방 이름은 '{room['name']}'이고 참여자는 다음과 같습니다.\n{participants_block}\n"
        f"{me_instruction}\n"
        f"{new_room_line}"
        f"각 참여자의 성격, 말투, 추억을 반영해서 {count_instruction} "
        "같은 캐릭터가 3개 이상 연속으로 메시지를 보내지 않게 하세요. "
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


def generate_room_messages(room, characters_by_id, my_name, chat_model, is_new_room=False):
    members = [characters_by_id[cid] for cid in room["member_ids"]]
    conn = get_connection()
    try:
        system_prompt, user_message = build_room_message_prompt(
            conn, room, members, my_name, is_new_room
        )
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
        profile_id = get_current_profile_id(conn)
        characters = fetch_characters(conn, profile_id)
        my_name = get_profile_name(conn, profile_id)
        deleted_rows = conn.execute(
            "SELECT room_key FROM deleted_rooms WHERE profile_id = ?", (profile_id,)
        ).fetchall()
    finally:
        conn.close()

    if len(characters) == 0:
        raise HTTPException(status_code=400, detail="캐릭터가 없습니다. 먼저 캐릭터를 추가해주세요.")

    deleted_names = {row["room_key"] for row in deleted_rows}
    room_plan = [r for r in build_room_plan(characters) if r["name"] not in deleted_names]
    characters_by_id = {c["id"]: c for c in characters}
    chat_model = os.environ.get("CHAT_MODEL")

    results = [None] * len(room_plan)
    executor = concurrent.futures.ThreadPoolExecutor(max_workers=5)
    future_to_index = {
        executor.submit(
            contextvars.copy_context().run, generate_room_messages,
            room, characters_by_id, my_name, chat_model,
        ): i
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
        conn.execute(
            "DELETE FROM messages WHERE room_id IN "
            "(SELECT id FROM rooms WHERE profile_id = ? AND is_custom = 0)",
            (profile_id,),
        )
        conn.execute(
            "DELETE FROM room_members WHERE room_id IN "
            "(SELECT id FROM rooms WHERE profile_id = ? AND is_custom = 0)",
            (profile_id,),
        )
        conn.execute("DELETE FROM rooms WHERE profile_id = ? AND is_custom = 0", (profile_id,))

        for entry in generated:
            plan = entry["plan"]
            cur = conn.execute(
                "INSERT INTO rooms (profile_id, name, type, includes_me) VALUES (?, ?, ?, ?)",
                (profile_id, plan["name"], plan["type"], plan["includes_me"]),
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
        rooms = conn.execute(
            "SELECT id, name, type, includes_me, is_custom FROM rooms WHERE profile_id = ? ORDER BY id",
            (get_current_profile_id(conn),),
        ).fetchall()
        result = []
        for r in rooms:
            members = conn.execute(
                "SELECT c.name FROM room_members rm JOIN characters c ON c.id = rm.character_id "
                "WHERE rm.room_id = ? ORDER BY c.id",
                (r["id"],),
            ).fetchall()
            last = conn.execute(
                "SELECT m.type, m.content, m.created_at, c.name AS sender_name FROM messages m "
                "LEFT JOIN characters c ON c.id = m.sender_character_id "
                "WHERE m.room_id = ? ORDER BY m.id DESC LIMIT 1",
                (r["id"],),
            ).fetchone()
            last_message = None
            if last:
                last_message = {
                    "type": last["type"],
                    "content": last["content"],
                    "sender": last["sender_name"] if last["sender_name"] else "나",
                    "created_at": last["created_at"],
                }
            result.append({
                "id": r["id"],
                "name": r["name"],
                "includes_me": bool(r["includes_me"]),
                "is_custom": bool(r["is_custom"]),
                "members": [m["name"] for m in members],
                "last_message": last_message,
            })
        return result
    finally:
        conn.close()


class RoomCreateRequest(BaseModel):
    name: str = ""
    member_ids: List[int]
    includes_me: bool = True


@router.post("/api/rooms")
def create_room(body: RoomCreateRequest):
    if not body.member_ids:
        raise HTTPException(status_code=400, detail="멤버를 1명 이상 선택해주세요.")
    conn = get_connection()
    try:
        profile_id = get_current_profile_id(conn)
        characters = fetch_characters(conn, profile_id)
        my_name = get_profile_name(conn, profile_id)
    finally:
        conn.close()

    characters_by_id = {c["id"]: c for c in characters}
    if any(mid not in characters_by_id for mid in body.member_ids):
        raise HTTPException(status_code=400, detail="캐릭터를 찾을 수 없습니다.")

    member_names = [characters_by_id[mid]["name"] for mid in body.member_ids]
    room_name = body.name.strip() or ", ".join(member_names)
    includes_me_flag = 1 if body.includes_me else 0
    # type을 "group"으로 고정: build_room_message_prompt의 group 분기(나 있음 2~4개,
    # 나 없음 3~5개)를 타게 해 멤버 수와 무관하게 "dm"의 1~2개보다 많은 대화가 생성되게 한다.
    room_plan_entry = {
        "name": room_name, "type": "group",
        "includes_me": includes_me_flag, "member_ids": body.member_ids,
    }
    chat_model = os.environ.get("CHAT_MODEL")
    result = generate_room_messages(
        room_plan_entry, characters_by_id, my_name, chat_model, is_new_room=True
    )

    conn = get_connection()
    try:
        cur = conn.execute(
            "INSERT INTO rooms (profile_id, name, type, includes_me, is_custom) "
            "VALUES (?, ?, 'group', ?, 1)",
            (profile_id, room_name, includes_me_flag),
        )
        room_id = cur.lastrowid
        for cid in body.member_ids:
            conn.execute(
                "INSERT INTO room_members (room_id, character_id) VALUES (?, ?)", (room_id, cid)
            )
        for msg in result["messages"]:
            conn.execute(
                "INSERT INTO messages (room_id, sender_character_id, type, content, caption, image_path) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (
                    room_id, msg["sender_character_id"], msg.get("type", "text"),
                    msg["content"], msg.get("caption"), msg.get("image_path"),
                ),
            )
        conn.commit()
    finally:
        conn.close()
    return {"id": room_id, "name": room_name}


@router.delete("/api/rooms/{room_id}")
def delete_room(room_id: int):
    conn = get_connection()
    try:
        profile_id = get_current_profile_id(conn)
        room = conn.execute(
            "SELECT id, name, is_custom FROM rooms WHERE id = ? AND profile_id = ?",
            (room_id, profile_id),
        ).fetchone()
        if not room:
            raise HTTPException(status_code=404, detail="방을 찾을 수 없습니다.")
        conn.execute("DELETE FROM messages WHERE room_id = ?", (room_id,))
        conn.execute("DELETE FROM room_members WHERE room_id = ?", (room_id,))
        conn.execute("DELETE FROM rooms WHERE id = ?", (room_id,))
        if not room["is_custom"]:
            # 자동 생성 방만 기록 — "방 다시 만들기"가 같은 이름으로 되살리지 않게 한다.
            conn.execute(
                "INSERT INTO deleted_rooms (profile_id, room_key) VALUES (?, ?)",
                (profile_id, room["name"]),
            )
        conn.commit()
    finally:
        conn.close()
    return {"ok": True}
