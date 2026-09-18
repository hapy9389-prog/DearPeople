from contextlib import asynccontextmanager

from fastapi import FastAPI
from pydantic import BaseModel

from db import get_connection, init_db
from routes_characters import router as characters_router
from routes_messages import router as messages_router
from routes_rooms import router as rooms_router
from routes_tick import router as tick_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(lifespan=lifespan)
app.include_router(characters_router)
app.include_router(rooms_router)
app.include_router(messages_router)
app.include_router(tick_router)


@app.get("/api/health")
def health():
    return {"status": "ok"}


class SettingsMeRequest(BaseModel):
    name: str


@app.get("/api/settings/me")
def get_my_name():
    conn = get_connection()
    try:
        me_row = conn.execute("SELECT value FROM settings WHERE key = 'me_name'").fetchone()
    finally:
        conn.close()
    return {"name": me_row["value"] if me_row else "나"}


@app.put("/api/settings/me")
def set_my_name(body: SettingsMeRequest):
    conn = get_connection()
    try:
        conn.execute(
            "INSERT OR REPLACE INTO settings (key, value) VALUES ('me_name', ?)", (body.name,)
        )
        conn.commit()
    finally:
        conn.close()
    return {"ok": True}
