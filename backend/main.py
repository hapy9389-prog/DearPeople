from contextlib import asynccontextmanager

from fastapi import FastAPI
from pydantic import BaseModel

from db import get_connection, init_db
from routes_characters import router as characters_router
from routes_rooms import router as rooms_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(lifespan=lifespan)
app.include_router(characters_router)
app.include_router(rooms_router)


@app.get("/api/health")
def health():
    return {"status": "ok"}


class SettingsMeRequest(BaseModel):
    name: str


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
