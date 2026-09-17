import logging
import os
from typing import List

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ai import call_claude_json
from db import get_connection

router = APIRouter()


class CharacterDraftRequest(BaseModel):
    relation: str
    grp: str
    name: str
    description: str


class CharacterSaveRequest(BaseModel):
    relation: str
    grp: str
    name: str
    personality: str
    speech_style: str
    calls_me: str
    memories: List[str]


@router.post("/api/characters/draft")
def create_character_draft(body: CharacterDraftRequest):
    system_prompt = (
        "당신은 모바일 앱 'DearPeople'의 캐릭터 설정을 생성하는 도우미입니다. "
        "사용자가 입력한 관계, 이름, 한 줄 설명을 바탕으로 그 사람의 성격(personality), "
        "말투(speech_style), 그 사람이 사용자를 부르는 호칭(calls_me), "
        "그 사람과 사용자가 나눈 추억 3개(memories)를 한국어로 생성하세요. "
        "반드시 아래 JSON 형식으로만 응답하고, 다른 설명이나 코드블록 표시는 출력하지 마세요.\n"
        '{"personality": "string", "speech_style": "string", "calls_me": "string", '
        '"memories": ["string", "string", "string"]}'
    )
    user_message = f"관계: {body.relation}\n이름: {body.name}\n한줄 설명: {body.description}"
    try:
        result = call_claude_json(
            system_prompt=system_prompt,
            messages=[{"role": "user", "content": user_message}],
            model=os.environ.get("FAST_MODEL"),
        )
    except Exception:
        logging.exception("캐릭터 초안 생성 실패")
        raise HTTPException(status_code=502, detail="캐릭터 초안 생성에 실패했습니다.")

    return {
        "personality": result.get("personality", ""),
        "speech_style": result.get("speech_style", ""),
        "calls_me": result.get("calls_me", ""),
        "memories": list(result.get("memories", []))[:3],
    }


@router.post("/api/characters")
def create_character(body: CharacterSaveRequest):
    conn = get_connection()
    try:
        cur = conn.execute(
            "INSERT INTO characters (relation, grp, name, personality, speech_style, calls_me) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (body.relation, body.grp, body.name, body.personality, body.speech_style, body.calls_me),
        )
        character_id = cur.lastrowid
        for memory in body.memories:
            conn.execute(
                "INSERT INTO memories (character_id, content) VALUES (?, ?)",
                (character_id, memory),
            )
        conn.commit()
    finally:
        conn.close()
    return {"id": character_id}


@router.get("/api/characters")
def list_characters():
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT id, relation, grp, name, personality, speech_style, calls_me "
            "FROM characters ORDER BY id"
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


@router.delete("/api/characters/{character_id}")
def delete_character(character_id: int):
    conn = get_connection()
    try:
        conn.execute("DELETE FROM messages WHERE sender_character_id = ?", (character_id,))
        conn.execute("DELETE FROM room_members WHERE character_id = ?", (character_id,))
        conn.execute("DELETE FROM memories WHERE character_id = ?", (character_id,))
        cur = conn.execute("DELETE FROM characters WHERE id = ?", (character_id,))
        conn.commit()
    finally:
        conn.close()
    if cur.rowcount == 0:
        raise HTTPException(status_code=404, detail="캐릭터를 찾을 수 없습니다.")
    return {"ok": True}
