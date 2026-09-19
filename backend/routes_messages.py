import base64
import logging
import os
import random
import uuid
from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from pydantic import BaseModel

from ai import call_claude_json
from db import get_connection, get_current_profile_id, get_profile_name
from device import check_rate_limit
from images import PHOTOS_DIR, pick_photo
from routes_characters import build_character_description
from routes_rooms import resolve_sender

router = APIRouter()

RECENT_LIMIT = 20
CHARACTER_PHOTO_PROBABILITY = 0.15

REALISTIC_REACTION_INSTRUCTION = (
    "이 캐릭터는 사용자를 아끼지만 무조건 받아주는 존재가 아니라, 실제 사람처럼 반응합니다. "
    "사용자가 무례하게 말하거나 걱정을 무시하면 성격에 맞는 방식으로 반응하세요"
    "(서운해하기, 잔소리, 정색, 농담으로 넘기기, 말수가 줄어들기 등 캐릭터마다 다르게 표현). "
    "관계에 따라서도 다르게 반응하세요: 부모는 걱정과 잔소리로, 형제자매는 놀리거나 맞받아치는 식으로, "
    "친구는 직설적으로 반응할 수 있습니다. "
    "매번 조언하거나 대화를 마무리 지으려 하지 말고, 때로는 짧게만 답하거나 질문만 던지세요. "
    "사용자 말에 항상 동의할 필요는 없습니다 — 생각이 다르면 다르다고 말하세요. "
    "단, 인신공격·욕설·폭언은 어떤 경우에도 하지 않고 감정 표현은 실제 가족이나 친구가 할 법한 수준으로 유지하며, "
    "사용자가 힘들어하는 상황에서는 감정적 반응보다 걱정을 먼저 표현하세요."
)

UPLOAD_DIR = PHOTOS_DIR / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
ALLOWED_IMAGE_TYPES = {"image/png": "png", "image/jpeg": "jpg", "image/webp": "webp"}
MAX_PHOTO_BYTES = 5 * 1024 * 1024


class MessageCreateRequest(BaseModel):
    content: str


def fetch_recent_messages(conn, room_id, limit=RECENT_LIMIT):
    rows = conn.execute(
        "SELECT m.sender_character_id, m.type, m.content, m.caption, c.name AS sender_name "
        "FROM messages m LEFT JOIN characters c ON c.id = m.sender_character_id "
        "WHERE m.room_id = ? ORDER BY m.id DESC LIMIT ?",
        (room_id, limit),
    ).fetchall()
    return list(reversed(rows))


def format_recent_conversation(recent_messages, my_name):
    if not recent_messages:
        return "(대화 없음)"
    lines = []
    for m in recent_messages:
        sender = m["sender_name"] if m["sender_name"] else my_name
        if m["type"] == "photo":
            lines.append(f"{sender}: [사진: {m['content']}] {m['caption'] or ''}".rstrip())
        else:
            lines.append(f"{sender}: {m['content']}")
    return "\n".join(lines)


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


def generate_character_reply(
    conn, member, room, recent_messages, my_name, chat_model,
    image_content=None, allow_photo=False, no_caption=False,
):
    """image_content가 있으면(내가 올린 사진에 반응) 그 이미지를 함께 보내 실제 내용을 보고 답하게 한다.
    allow_photo는 image_content가 없을 때만 의미가 있고, CHARACTER_PHOTO_PROBABILITY 확률로
    캐릭터가 먼저 사진을 보내는 답장을 생성하게 한다. 반환값은 dict(type/content/caption/image_path),
    빈 답장이면 None."""
    description = build_character_description(conn, member)
    conversation = format_recent_conversation(recent_messages, my_name)

    send_photo = allow_photo and image_content is None and random.random() < CHARACTER_PHOTO_PROBABILITY
    if send_photo:
        photo_instruction = (
            "이번 답장은 사진을 공유하는 형태로 만들 수도 있습니다. 사진으로 답하는 게 자연스럽다면 "
            "type을 'photo'로 하고 category(food/scenery/pet/object/place 중 하나), "
            "description(사진 속 장면을 한두 문장으로 묘사, 사람 얼굴은 묘사하지 않음), "
            "caption(짧은 말)을 채우세요. 그렇지 않다면 type을 'text'로 하고 content만 채우세요."
        )
        format_hint = (
            '{"type": "text", "content": "메시지 내용"} 또는 '
            '{"type": "photo", "category": "food", "description": "장면 묘사", "caption": "캡션"}'
        )
    else:
        photo_instruction = ""
        format_hint = '{"content": "메시지 내용"}'

    system_prompt = (
        "당신은 모바일 채팅 앱 'DearPeople'에서 아래 캐릭터가 되어 채팅 메시지를 생성하는 도우미입니다.\n"
        f"{description}\n채팅방: '{room['name']}'\n최근 대화:\n{conversation}\n"
        f"위 캐릭터({member['name']})의 성격과 말투를 반영해서, 대화 흐름에 자연스럽게 이어지는 "
        "답장을 1~2문장으로 짧게(카카오톡 메시지처럼 간결하게) 작성하세요. "
        f"{REALISTIC_REACTION_INSTRUCTION} "
        f"{photo_instruction} "
        "반드시 아래 JSON 형식으로만 응답하고, 다른 설명이나 코드블록 표시는 출력하지 마세요.\n"
        f"{format_hint}"
    )

    if image_content:
        if no_caption:
            prompt_text = (
                "사용자가 아무 말 없이 사진만 보냈습니다. 위 사진을 보고 자연스럽게 반응하거나 "
                "궁금한 점을 먼저 물어보는 답장을 작성해 주세요."
            )
        else:
            prompt_text = "위 사진을 보고, 대화 흐름에 자연스럽게 이어지는 답장을 작성해 주세요."
        user_content = [image_content, {"type": "text", "text": prompt_text}]
    else:
        user_content = "위 대화에 자연스럽게 이어지는 답장을 작성해 주세요."

    result = call_claude_json(
        system_prompt=system_prompt,
        messages=[{"role": "user", "content": user_content}],
        model=chat_model,
    )

    if send_photo and result.get("type") == "photo":
        description_text = (result.get("description") or "").strip()
        if description_text:
            return {
                "type": "photo",
                "content": description_text,
                "caption": (result.get("caption") or "").strip(),
                "image_path": pick_photo(result.get("category", "")),
            }
    content = (result.get("content") or "").strip()
    if not content:
        return None
    return {"type": "text", "content": content, "caption": None, "image_path": None}


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
        f"{REALISTIC_REACTION_INSTRUCTION} "
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


def save_message(conn, room_id, sender_character_id, content, type="text", caption=None, image_path=None):
    cur = conn.execute(
        "INSERT INTO messages (room_id, sender_character_id, type, content, caption, image_path) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (room_id, sender_character_id, type, content, caption, image_path),
    )
    conn.commit()
    row = conn.execute("SELECT id, created_at FROM messages WHERE id = ?", (cur.lastrowid,)).fetchone()
    return {"id": row["id"], "created_at": row["created_at"]}


def generate_reactions(
    conn, room, members, members_by_id, my_name, fast_model, chat_model,
    image_content=None, no_caption=False,
):
    """멤버들의 반응(반응자 판단 → 순차 생성 → 후속 반응 최대 1턴)을 생성하고 저장까지 한다.
    image_content가 있으면 첫 반응자에게만 이미지를 함께 보내고, 실패하면 텍스트만으로 한 번 더 시도한다."""
    new_messages = []
    if len(members) == 1:
        responder_ids = [members[0]["id"]]
    else:
        recent = fetch_recent_messages(conn, room["id"])
        try:
            responder_ids = judge_responders(conn, room, members, recent, my_name, fast_model)
            if not responder_ids:
                responder_ids = [random.choice(members)["id"]]
        except Exception:
            logging.exception("방 %s 반응자 판단 실패, 무작위 1명으로 대체", room["id"])
            responder_ids = [random.choice(members)["id"]]

    aborted = False
    for idx, cid in enumerate(responder_ids):
        member = members_by_id.get(cid)
        if member is None:
            continue
        recent = fetch_recent_messages(conn, room["id"])
        img = image_content if idx == 0 else None
        try:
            reply = generate_character_reply(
                conn, member, room, recent, my_name, chat_model,
                image_content=img, allow_photo=(img is None), no_caption=no_caption,
            )
            if reply is None:
                raise RuntimeError("빈 답장이 생성되었습니다.")
        except Exception:
            logging.exception("방 %s 캐릭터 '%s' 답장 생성 실패", room["id"], member["name"])
            if img is not None:
                try:
                    reply = generate_character_reply(
                        conn, member, room, recent, my_name, chat_model,
                        image_content=None, allow_photo=False,
                    )
                    if reply is None:
                        raise RuntimeError("빈 답장이 생성되었습니다.")
                except Exception:
                    logging.exception("방 %s 캐릭터 '%s' 텍스트 대체 생성도 실패", room["id"], member["name"])
                    aborted = True
                    break
            else:
                aborted = True
                break
        saved = save_message(
            conn, room["id"], member["id"], reply["content"], reply["type"], reply["caption"], reply["image_path"],
        )
        new_messages.append({
            "id": saved["id"], "sender": member["name"], "sender_character_id": member["id"],
            "type": reply["type"], "content": reply["content"], "caption": reply["caption"],
            "image_path": reply["image_path"], "created_at": saved["created_at"],
        })

    if not aborted and len(members) > 1:
        recent = fetch_recent_messages(conn, room["id"])
        try:
            followup = judge_and_generate_followup(conn, room, members, recent, my_name, chat_model)
        except Exception:
            logging.exception("방 %s 후속 반응 생성 실패", room["id"])
            followup = None
        if followup:
            saved = save_message(conn, room["id"], followup["sender_character_id"], followup["content"])
            member = members_by_id[followup["sender_character_id"]]
            new_messages.append({
                "id": saved["id"], "sender": member["name"], "sender_character_id": member["id"],
                "type": "text", "content": followup["content"], "caption": None, "image_path": None,
                "created_at": saved["created_at"],
            })
    return new_messages


@router.get("/api/rooms/{room_id}/messages")
def get_room_messages(room_id: int):
    conn = get_connection()
    try:
        room = conn.execute(
            "SELECT id, name, includes_me FROM rooms WHERE id = ? AND profile_id = ?",
            (room_id, get_current_profile_id(conn)),
        ).fetchone()
        if not room:
            raise HTTPException(status_code=404, detail="채팅방을 찾을 수 없습니다.")
        members = conn.execute(
            "SELECT c.name FROM room_members rm JOIN characters c ON c.id = rm.character_id "
            "WHERE rm.room_id = ? ORDER BY c.id", (room_id,),
        ).fetchall()
        rows = conn.execute(
            "SELECT m.id, m.sender_character_id, m.type, m.content, m.caption, m.image_path, "
            "m.created_at, c.name AS sender_name "
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
                "type": r["type"],
                "content": r["content"],
                "caption": r["caption"],
                "image_path": r["image_path"],
                "created_at": r["created_at"],
            }
            for r in rows
        ],
    }


@router.post("/api/rooms/{room_id}/messages")
def post_room_message(room_id: int, body: MessageCreateRequest):
    check_rate_limit("message", 10)  # 메시지 1개당 AI를 최대 5회 호출하므로 가장 비용이 큰 경로
    conn = get_connection()
    try:
        room_row = conn.execute(
            "SELECT id, name, includes_me FROM rooms WHERE id = ? AND profile_id = ?",
            (room_id, get_current_profile_id(conn)),
        ).fetchone()
        if not room_row:
            raise HTTPException(status_code=404, detail="채팅방을 찾을 수 없습니다.")
        room = dict(room_row)
        if not room["includes_me"]:
            raise HTTPException(status_code=400, detail="이 채팅방에는 메시지를 보낼 수 없습니다.")

        member_rows = conn.execute(
            "SELECT c.id, c.name, c.relation, c.personality, c.speech_style, c.calls_me, c.reaction_style "
            "FROM room_members rm JOIN characters c ON c.id = rm.character_id "
            "WHERE rm.room_id = ? ORDER BY c.id", (room_id,),
        ).fetchall()
        members = [dict(r) for r in member_rows]
        members_by_id = {m["id"]: m for m in members}

        my_name = get_profile_name(conn, get_current_profile_id(conn))
        fast_model = os.environ.get("FAST_MODEL")
        chat_model = os.environ.get("CHAT_MODEL")

        # 1) 내 메시지 저장 (무조건 먼저)
        save_message(conn, room_id, None, body.content)

        # 2~4) 반응자 판단 → 순차 생성 → 후속 반응 최대 1턴
        new_messages = generate_reactions(conn, room, members, members_by_id, my_name, fast_model, chat_model)
    finally:
        conn.close()
    return new_messages


@router.post("/api/rooms/{room_id}/photo")
def post_room_photo(room_id: int, file: UploadFile = File(...), caption: str = Form("")):
    check_rate_limit("photo", 5)
    if file.content_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(status_code=400, detail="png, jpg, webp 파일만 업로드할 수 있습니다.")
    data = file.file.read()
    if len(data) > MAX_PHOTO_BYTES:
        raise HTTPException(status_code=400, detail="5MB 이하 파일만 업로드할 수 있습니다.")

    caption_value = caption.strip() or None

    # 1) 파일 저장 + 내 메시지 기록까지만 연결을 짧게 잡는다.
    conn = get_connection()
    try:
        room_row = conn.execute(
            "SELECT id, name, includes_me FROM rooms WHERE id = ? AND profile_id = ?",
            (room_id, get_current_profile_id(conn)),
        ).fetchone()
        if not room_row:
            raise HTTPException(status_code=404, detail="채팅방을 찾을 수 없습니다.")
        room = dict(room_row)
        if not room["includes_me"]:
            raise HTTPException(status_code=400, detail="이 채팅방에는 메시지를 보낼 수 없습니다.")

        member_rows = conn.execute(
            "SELECT c.id, c.name, c.relation, c.personality, c.speech_style, c.calls_me, c.reaction_style "
            "FROM room_members rm JOIN characters c ON c.id = rm.character_id "
            "WHERE rm.room_id = ? ORDER BY c.id", (room_id,),
        ).fetchall()
        members = [dict(r) for r in member_rows]
        my_name = get_profile_name(conn, get_current_profile_id(conn))

        ext = ALLOWED_IMAGE_TYPES[file.content_type]
        filename = f"{uuid.uuid4().hex}.{ext}"
        (UPLOAD_DIR / filename).write_bytes(data)
        image_path = f"/static/photos/uploads/{filename}"
        save_message(conn, room_id, None, "[사진]", type="photo", caption=caption_value, image_path=image_path)
    finally:
        conn.close()

    members_by_id = {m["id"]: m for m in members}
    fast_model = os.environ.get("FAST_MODEL")
    chat_model = os.environ.get("CHAT_MODEL")
    image_content = {
        "type": "image",
        "source": {
            "type": "base64", "media_type": file.content_type,
            "data": base64.standard_b64encode(data).decode("utf-8"),
        },
    }

    # 2) 반응 생성은 새 연결로 — 오래 걸리는 AI 호출 동안 DB를 붙잡지 않는다
    # (자동 시간 흐르기의 tick()과 겹치면 DB 잠금 오류가 날 수 있음).
    conn = get_connection()
    try:
        new_messages = generate_reactions(
            conn, room, members, members_by_id, my_name, fast_model, chat_model,
            image_content=image_content, no_caption=(caption_value is None),
        )
    finally:
        conn.close()
    return new_messages
