from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from db import clear_profile_data, get_connection, get_current_profile_id

router = APIRouter()


class ProfileCreateRequest(BaseModel):
    name: str


class ProfileSwitchRequest(BaseModel):
    id: int


class ProfileRenameRequest(BaseModel):
    name: str


class ProfileEmojiRequest(BaseModel):
    emoji: str


EMOJI_CHOICES = ["🙂", "😀", "😎", "🐱", "🐶", "🌸", "⭐", "🍀"]


@router.get("/api/profiles")
def list_profiles():
    conn = get_connection()
    try:
        current_id = get_current_profile_id(conn)
        rows = conn.execute(
            "SELECT p.id, p.name, p.emoji, COUNT(c.id) AS character_count "
            "FROM profiles p LEFT JOIN characters c ON c.profile_id = p.id "
            "GROUP BY p.id ORDER BY p.id"
        ).fetchall()
        profiles = [dict(r) for r in rows]
    finally:
        conn.close()
    return {"profiles": profiles, "current_profile_id": current_id}


@router.post("/api/profiles")
def create_profile(body: ProfileCreateRequest):
    name = body.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="이름을 입력해주세요.")
    conn = get_connection()
    try:
        cur = conn.execute("INSERT INTO profiles (name) VALUES (?)", (name,))
        profile_id = cur.lastrowid
        conn.execute(
            "INSERT OR REPLACE INTO settings (key, value) VALUES ('current_profile_id', ?)",
            (str(profile_id),),
        )
        conn.commit()
    finally:
        conn.close()
    return {"id": profile_id, "name": name}


@router.put("/api/profiles/current")
def switch_current_profile(body: ProfileSwitchRequest):
    conn = get_connection()
    try:
        if not conn.execute("SELECT 1 FROM profiles WHERE id = ?", (body.id,)).fetchone():
            raise HTTPException(status_code=404, detail="프로필을 찾을 수 없습니다.")
        conn.execute(
            "INSERT OR REPLACE INTO settings (key, value) VALUES ('current_profile_id', ?)",
            (str(body.id),),
        )
        conn.commit()
    finally:
        conn.close()
    return {"ok": True, "current_profile_id": body.id}


@router.put("/api/profiles/current/name")
def rename_current_profile(body: ProfileRenameRequest):
    name = body.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="이름을 입력해주세요.")
    conn = get_connection()
    try:
        profile_id = get_current_profile_id(conn)
        conn.execute("UPDATE profiles SET name = ? WHERE id = ?", (name, profile_id))
        conn.commit()
    finally:
        conn.close()
    return {"id": profile_id, "name": name}


@router.put("/api/profiles/{profile_id}/emoji")
def set_profile_emoji(profile_id: int, body: ProfileEmojiRequest):
    if body.emoji not in EMOJI_CHOICES:
        raise HTTPException(status_code=400, detail="지원하지 않는 이모지입니다.")
    conn = get_connection()
    try:
        if not conn.execute("SELECT 1 FROM profiles WHERE id = ?", (profile_id,)).fetchone():
            raise HTTPException(status_code=404, detail="프로필을 찾을 수 없습니다.")
        conn.execute("UPDATE profiles SET emoji = ? WHERE id = ?", (body.emoji, profile_id))
        conn.commit()
    finally:
        conn.close()
    return {"id": profile_id, "emoji": body.emoji}


@router.delete("/api/profiles/{profile_id}")
def delete_profile(profile_id: int):
    conn = get_connection()
    try:
        if not conn.execute("SELECT id FROM profiles WHERE id = ?", (profile_id,)).fetchone():
            raise HTTPException(status_code=404, detail="프로필을 찾을 수 없습니다.")
        if conn.execute("SELECT COUNT(*) AS n FROM profiles").fetchone()["n"] <= 1:
            raise HTTPException(status_code=400, detail="마지막 남은 프로필은 삭제할 수 없습니다.")
        current_id = get_current_profile_id(conn)
    finally:
        conn.close()

    clear_profile_data(profile_id)

    conn = get_connection()
    try:
        conn.execute("DELETE FROM profiles WHERE id = ?", (profile_id,))
        if current_id == profile_id:
            new_current_id = conn.execute("SELECT id FROM profiles ORDER BY id LIMIT 1").fetchone()["id"]
            conn.execute(
                "INSERT OR REPLACE INTO settings (key, value) VALUES ('current_profile_id', ?)",
                (str(new_current_id),),
            )
        else:
            new_current_id = current_id
        conn.commit()
    finally:
        conn.close()
    return {"ok": True, "current_profile_id": new_current_id}
