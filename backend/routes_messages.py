import logging
import os
import random

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ai import call_claude_json
from db import get_connection
from routes_characters import build_character_description
from routes_rooms import resolve_sender

router = APIRouter()

RECENT_LIMIT = 20


class MessageCreateRequest(BaseModel):
    content: str


def fetch_recent_messages(conn, room_id, limit=RECENT_LIMIT):
    rows = conn.execute(
        "SELECT m.sender_character_id, m.content, c.name AS sender_name "
        "FROM messages m LEFT JOIN characters c ON c.id = m.sender_character_id "
        "WHERE m.room_id = ? ORDER BY m.id DESC LIMIT ?",
        (room_id, limit),
    ).fetchall()
    return list(reversed(rows))


def format_recent_conversation(recent_messages, my_name):
    if not recent_messages:
        return "(대화 없음)"
    return "\n".join(
        f"{m['sender_name'] if m['sender_name'] else my_name}: {m['content']}"
        for m in recent_messages
    )


def judge_responders(conn, room, members, recent_messages, my_name, fast_model):
    """1~3명, 순서 포함. 나를 직접 부른 사람/관련 기억이 있는 사람을 판단하려면
    각 멤버의 성격·말투·기억이 프롬프트에 필요하므로 build_character_description을 쓴다."""
    member_blocks = "\n".join(build_character_description(conn, m) for m in members)
    conversation = format_recent_conversation(recent_messages, my_name)
    system_prompt = (
        "당신은 모바일 채팅 앱 'DearPeople'의 그룹 채팅방에서, 대화의 가장 마지막 메시지"
        "(사용자가 방금 보낸 메시지)에 대해 누가 반응할지 판단하는 도우미입니다. "
        f"채팅방 이름은 '{room['name']}'이고 참여자는 다음과 같습니다.\n{member_blocks}\n"
        f"최근 대화 (마지막 줄이 사용자의 새 메시지):\n{conversation}\n"
        "이 메시지에 반응할 참여자를 1명 이상 3명 이하로, 반응이 나올 순서대로 고르세요. "
        "사용자가 직접 호명한 사람이나 메시지 내용과 관련된 추억이 있는 사람을 우선하세요. "
        "반드시 아래 JSON 형식으로만 응답하고, 다른 설명이나 코드블록 표시는 출력하지 마세요.\n"
        '{"responders": ["이름", "이름", ...]}'
    )
    result = call_claude_json(
        system_prompt=system_prompt,
        messages=[{"role": "user", "content": "위 대화를 보고 반응할 참여자를 순서대로 골라주세요."}],
        model=fast_model,
    )
    name_to_id = {m["name"]: m["id"] for m in members}
    ordered_ids = []
    for name in result.get("responders", []):
        ok, cid = resolve_sender(name, name_to_id, my_name)
        if ok and cid not in ordered_ids:
            ordered_ids.append(cid)
    return ordered_ids[:3]


def generate_character_reply(conn, member, room, recent_messages, my_name, chat_model):
    description = build_character_description(conn, member)
    conversation = format_recent_conversation(recent_messages, my_name)
    system_prompt = (
        "당신은 모바일 채팅 앱 'DearPeople'에서 아래 캐릭터가 되어 채팅 메시지를 생성하는 도우미입니다.\n"
        f"{description}\n채팅방: '{room['name']}'\n최근 대화:\n{conversation}\n"
        f"위 캐릭터({member['name']})의 성격과 말투를 반영해서, 대화 흐름에 자연스럽게 이어지는 "
        "답장을 1~2문장으로 짧게(카카오톡 메시지처럼 간결하게) 작성하세요. "
        "반드시 아래 JSON 형식으로만 응답하고, 다른 설명이나 코드블록 표시는 출력하지 마세요.\n"
        '{"content": "메시지 내용"}'
    )
    result = call_claude_json(
        system_prompt=system_prompt,
        messages=[{"role": "user", "content": "위 대화에 자연스럽게 이어지는 답장을 작성해 주세요."}],
        model=chat_model,
    )
    return (result.get("content") or "").strip()


def judge_and_generate_followup(conn, room, members, recent_messages, my_name, chat_model):
    """방금 오간 대화에 한 번 더 반응이 자연스러운지 AI가 스스로 판단하고,
    필요하면 그 캐릭터의 답장까지 함께 생성한다. 불필요하면 None."""
    member_blocks = "\n".join(build_character_description(conn, m) for m in members)
    conversation = format_recent_conversation(recent_messages, my_name)
    system_prompt = (
        "당신은 'DearPeople' 그룹 채팅방의 대화 흐름을 살펴보는 도우미입니다. "
        f"채팅방 이름은 '{room['name']}'이고 참여자는 다음과 같습니다.\n{member_blocks}\n"
        f"최근 대화:\n{conversation}\n"
        "방금 오간 대화에 자연스럽게 한 번 더 반응할 만한 참여자가 있다면 그 사람의 이름과 "
        "1~2문장의 짧은 메시지를 작성하고, 부자연스럽거나 굳이 필요 없다면 반응하지 마세요. "
        "있어도 반응은 1명, 1턴뿐입니다. "
        "반드시 아래 JSON 형식으로만 응답하고, 다른 설명이나 코드블록 표시는 출력하지 마세요.\n"
        '{"needed": true 또는 false, "sender": "이름 또는 빈 문자열", "content": "메시지 내용 또는 빈 문자열"}'
    )
    result = call_claude_json(
        system_prompt=system_prompt,
        messages=[{"role": "user", "content": "한 번 더 반응이 필요한지 판단해 주세요."}],
        model=chat_model,
    )
    if not result.get("needed"):
        return None
    content = (result.get("content") or "").strip()
    if not content:
        return None
    name_to_id = {m["name"]: m["id"] for m in members}
    ok, sender_id = resolve_sender(result.get("sender", ""), name_to_id, my_name)
    if not ok:
        return None
    return {"sender_character_id": sender_id, "content": content}


def save_message(conn, room_id, sender_character_id, content):
    cur = conn.execute(
        "INSERT INTO messages (room_id, sender_character_id, type, content) VALUES (?, ?, 'text', ?)",
        (room_id, sender_character_id, content),
    )
    conn.commit()
    row = conn.execute("SELECT id, created_at FROM messages WHERE id = ?", (cur.lastrowid,)).fetchone()
    return {"id": row["id"], "created_at": row["created_at"]}


@router.get("/api/rooms/{room_id}/messages")
def get_room_messages(room_id: int):
    conn = get_connection()
    try:
        room = conn.execute(
            "SELECT id, name, includes_me FROM rooms WHERE id = ?", (room_id,)
        ).fetchone()
        if not room:
            raise HTTPException(status_code=404, detail="채팅방을 찾을 수 없습니다.")
        members = conn.execute(
            "SELECT c.name FROM room_members rm JOIN characters c ON c.id = rm.character_id "
            "WHERE rm.room_id = ? ORDER BY c.id", (room_id,),
        ).fetchall()
        rows = conn.execute(
            "SELECT m.id, m.sender_character_id, m.content, m.created_at, c.name AS sender_name "
            "FROM messages m LEFT JOIN characters c ON c.id = m.sender_character_id "
            "WHERE m.room_id = ? ORDER BY m.id", (room_id,),
        ).fetchall()
    finally:
        conn.close()
    return {
        "room": {
            "id": room["id"], "name": room["name"], "includes_me": bool(room["includes_me"]),
            "members": [m["name"] for m in members],
        },
        "messages": [
            {
                "id": r["id"],
                "sender": r["sender_name"] if r["sender_name"] else "나",
                "sender_character_id": r["sender_character_id"],
                "content": r["content"],
                "created_at": r["created_at"],
            }
            for r in rows
        ],
    }


@router.post("/api/rooms/{room_id}/messages")
def post_room_message(room_id: int, body: MessageCreateRequest):
    conn = get_connection()
    try:
        room_row = conn.execute(
            "SELECT id, name, includes_me FROM rooms WHERE id = ?", (room_id,)
        ).fetchone()
        if not room_row:
            raise HTTPException(status_code=404, detail="채팅방을 찾을 수 없습니다.")
        room = dict(room_row)
        if not room["includes_me"]:
            raise HTTPException(status_code=400, detail="이 채팅방에는 메시지를 보낼 수 없습니다.")

        member_rows = conn.execute(
            "SELECT c.id, c.name, c.relation, c.personality, c.speech_style, c.calls_me "
            "FROM room_members rm JOIN characters c ON c.id = rm.character_id "
            "WHERE rm.room_id = ? ORDER BY c.id", (room_id,),
        ).fetchall()
        members = [dict(r) for r in member_rows]
        members_by_id = {m["id"]: m for m in members}

        me_row = conn.execute("SELECT value FROM settings WHERE key = 'me_name'").fetchone()
        my_name = me_row["value"] if me_row else "나"
        fast_model = os.environ.get("FAST_MODEL")
        chat_model = os.environ.get("CHAT_MODEL")

        # 1) 내 메시지 저장 (무조건 먼저)
        save_message(conn, room_id, None, body.content)
        new_messages = []

        # 2) 반응할 캐릭터/순서 결정
        if len(members) == 1:
            responder_ids = [members[0]["id"]]
        else:
            recent = fetch_recent_messages(conn, room_id)
            try:
                responder_ids = judge_responders(conn, room, members, recent, my_name, fast_model)
                if not responder_ids:
                    responder_ids = [random.choice(members)["id"]]
            except Exception:
                logging.exception("방 %s 반응자 판단 실패, 무작위 1명으로 대체", room_id)
                responder_ids = [random.choice(members)["id"]]

        # 3) 순서대로 순차 생성 (매번 최근 대화를 다시 읽어 직전 답변을 반영)
        aborted = False
        for cid in responder_ids:
            member = members_by_id.get(cid)
            if member is None:
                continue
            recent = fetch_recent_messages(conn, room_id)
            try:
                content = generate_character_reply(conn, member, room, recent, my_name, chat_model)
                if not content:
                    raise RuntimeError("빈 답장이 생성되었습니다.")
            except Exception:
                logging.exception("방 %s 캐릭터 '%s' 답장 생성 실패", room_id, member["name"])
                aborted = True
                break
            saved = save_message(conn, room_id, member["id"], content)
            new_messages.append({
                "id": saved["id"], "sender": member["name"], "sender_character_id": member["id"],
                "content": content, "created_at": saved["created_at"],
            })

        # 4) 중단되지 않았고 멤버가 2명 이상이면 후속 반응 최대 1턴
        if not aborted and len(members) > 1:
            recent = fetch_recent_messages(conn, room_id)
            try:
                followup = judge_and_generate_followup(conn, room, members, recent, my_name, chat_model)
            except Exception:
                logging.exception("방 %s 후속 반응 생성 실패", room_id)
                followup = None
            if followup:
                saved = save_message(conn, room_id, followup["sender_character_id"], followup["content"])
                member = members_by_id[followup["sender_character_id"]]
                new_messages.append({
                    "id": saved["id"], "sender": member["name"],
                    "sender_character_id": member["id"], "content": followup["content"],
                    "created_at": saved["created_at"],
                })
    finally:
        conn.close()
    return new_messages
