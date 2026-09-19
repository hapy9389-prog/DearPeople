import logging
import os
from typing import List

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ai import call_claude_json
from db import get_connection, get_current_profile_id, require_current_profile_id

router = APIRouter()


def build_character_description(conn, character) -> str:
    """캐릭터 설명 블록. memories는 매 호출마다 DB에서 새로 조회한다.
    character는 최소 id, name, relation, calls_me, personality, speech_style, reaction_style를 가진 dict/Row."""
    memories = conn.execute(
        "SELECT content FROM memories WHERE character_id = ? ORDER BY id",
        (character["id"],),
    ).fetchall()
    memory_text = "; ".join(m["content"] for m in memories) if memories else "(없음)"
    reaction_style = character["reaction_style"] or "(성격에서 자연스럽게 유추)"
    return (
        f"- {character['name']} (관계: {character['relation']}, "
        f"나를 부르는 호칭: {character['calls_me']})\n"
        f"  성격: {character['personality']}\n"
        f"  말투: {character['speech_style']}\n"
        f"  화나거나 서운할 때: {reaction_style}\n"
        f"  추억: {memory_text}"
    )


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
    reaction_style: str = ""
    memories: List[str]


@router.post("/api/characters/draft")
def create_character_draft(body: CharacterDraftRequest):
    system_prompt = (
        "당신은 모바일 앱 'DearPeople'의 캐릭터 설정을 생성하는 도우미입니다. "
        "사용자가 입력한 관계, 이름, 한 줄 설명을 바탕으로 그 사람의 성격(personality), "
        "말투(speech_style), 그 사람이 사용자를 부르는 호칭(calls_me), "
        "그 사람이 화나거나 서운할 때 어떻게 표현하는지(reaction_style, 예: "
        "\"서운하면 말수가 줄고 '됐다'로 끊는다\", \"화나면 목소리가 커지고 바로 따진다\"), "
        "그 사람과 사용자가 나눈 추억 3개(memories)를 한국어로 생성하세요. "
        "반드시 아래 JSON 형식으로만 응답하고, 다른 설명이나 코드블록 표시는 출력하지 마세요.\n"
        '{"personality": "string", "speech_style": "string", "calls_me": "string", '
        '"reaction_style": "string", "memories": ["string", "string", "string"]}'
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
        "reaction_style": result.get("reaction_style", ""),
        "memories": list(result.get("memories", []))[:3],
    }


@router.post("/api/characters")
def create_character(body: CharacterSaveRequest):
    conn = get_connection()
    try:
        cur = conn.execute(
            "INSERT INTO characters "
            "(profile_id, relation, grp, name, personality, speech_style, calls_me, reaction_style) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                require_current_profile_id(conn), body.relation, body.grp, body.name,
                body.personality, body.speech_style, body.calls_me, body.reaction_style,
            ),
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
            "SELECT id, relation, grp, name, personality, speech_style, calls_me, reaction_style "
            "FROM characters WHERE profile_id = ? ORDER BY id",
            (get_current_profile_id(conn),),
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


class CharacterUpdateRequest(BaseModel):
    name: str
    relation: str
    grp: str
    personality: str
    speech_style: str
    calls_me: str
    reaction_style: str = ""


@router.put("/api/characters/{character_id}")
def update_character(character_id: int, body: CharacterUpdateRequest):
    if not body.name.strip() or not body.relation.strip():
        raise HTTPException(status_code=400, detail="이름과 관계를 입력해주세요.")
    conn = get_connection()
    try:
        owned = conn.execute(
            "SELECT 1 FROM characters WHERE id = ? AND profile_id = ?",
            (character_id, get_current_profile_id(conn)),
        ).fetchone()
        if not owned:
            raise HTTPException(status_code=404, detail="캐릭터를 찾을 수 없습니다.")
        conn.execute(
            "UPDATE characters SET name = ?, relation = ?, grp = ?, personality = ?, "
            "speech_style = ?, calls_me = ?, reaction_style = ? WHERE id = ?",
            (
                body.name.strip(), body.relation.strip(), body.grp,
                body.personality, body.speech_style, body.calls_me, body.reaction_style, character_id,
            ),
        )
        conn.commit()
    finally:
        conn.close()
    return {"ok": True}


@router.delete("/api/characters/{character_id}")
def delete_character(character_id: int):
    conn = get_connection()
    try:
        owned = conn.execute(
            "SELECT 1 FROM characters WHERE id = ? AND profile_id = ?",
            (character_id, get_current_profile_id(conn)),
        ).fetchone()
        if not owned:
            raise HTTPException(status_code=404, detail="캐릭터를 찾을 수 없습니다.")
        conn.execute("DELETE FROM messages WHERE sender_character_id = ?", (character_id,))
        conn.execute("DELETE FROM room_members WHERE character_id = ?", (character_id,))
        conn.execute("DELETE FROM memories WHERE character_id = ?", (character_id,))
        conn.execute("DELETE FROM characters WHERE id = ?", (character_id,))
        conn.commit()
    finally:
        conn.close()
    return {"ok": True}


class MemoryRequest(BaseModel):
    content: str


@router.get("/api/characters/{character_id}/memories")
def list_memories(character_id: int):
    conn = get_connection()
    try:
        character = conn.execute(
            "SELECT id FROM characters WHERE id = ? AND profile_id = ?",
            (character_id, get_current_profile_id(conn)),
        ).fetchone()
        if character is None:
            raise HTTPException(status_code=404, detail="캐릭터를 찾을 수 없습니다.")
        rows = conn.execute(
            "SELECT id, character_id, content, created_at FROM memories "
            "WHERE character_id = ? ORDER BY id",
            (character_id,),
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


@router.post("/api/characters/{character_id}/memories")
def create_memory(character_id: int, body: MemoryRequest):
    if not body.content.strip():
        raise HTTPException(status_code=400, detail="내용을 입력해주세요.")
    conn = get_connection()
    try:
        character = conn.execute(
            "SELECT id FROM characters WHERE id = ? AND profile_id = ?",
            (character_id, get_current_profile_id(conn)),
        ).fetchone()
        if character is None:
            raise HTTPException(status_code=404, detail="캐릭터를 찾을 수 없습니다.")
        cur = conn.execute(
            "INSERT INTO memories (character_id, content) VALUES (?, ?)",
            (character_id, body.content.strip()),
        )
        conn.commit()
        memory_id = cur.lastrowid
    finally:
        conn.close()
    return {"id": memory_id, "character_id": character_id, "content": body.content.strip()}


@router.put("/api/memories/{memory_id}")
def update_memory(memory_id: int, body: MemoryRequest):
    if not body.content.strip():
        raise HTTPException(status_code=400, detail="내용을 입력해주세요.")
    conn = get_connection()
    try:
        owned = conn.execute(
            "SELECT 1 FROM memories m JOIN characters c ON c.id = m.character_id "
            "WHERE m.id = ? AND c.profile_id = ?",
            (memory_id, get_current_profile_id(conn)),
        ).fetchone()
        if not owned:
            raise HTTPException(status_code=404, detail="기억을 찾을 수 없습니다.")
        conn.execute("UPDATE memories SET content = ? WHERE id = ?", (body.content.strip(), memory_id))
        conn.commit()
    finally:
        conn.close()
    return {"id": memory_id, "content": body.content.strip()}


@router.delete("/api/memories/{memory_id}")
def delete_memory(memory_id: int):
    conn = get_connection()
    try:
        owned = conn.execute(
            "SELECT 1 FROM memories m JOIN characters c ON c.id = m.character_id "
            "WHERE m.id = ? AND c.profile_id = ?",
            (memory_id, get_current_profile_id(conn)),
        ).fetchone()
        if not owned:
            raise HTTPException(status_code=404, detail="기억을 찾을 수 없습니다.")
        conn.execute("DELETE FROM memories WHERE id = ?", (memory_id,))
        conn.commit()
    finally:
        conn.close()
    return {"ok": True}
