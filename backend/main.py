import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI
from fastapi.staticfiles import StaticFiles

from db import clear_profile_data, get_connection, get_current_profile_id, init_db
from device import read_device_key
from images import PHOTOS_DIR
from routes_characters import router as characters_router
from routes_memory_suggestions import router as memory_suggestions_router
from routes_messages import router as messages_router
from routes_profiles import router as profiles_router
from routes_rooms import router as rooms_router
from routes_tick import router as tick_router


logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logging.getLogger("httpx").setLevel(logging.WARNING)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


STATIC_DIR = Path(__file__).parent / "static"
STATIC_DIR.mkdir(parents=True, exist_ok=True)

PHOTOS_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI(lifespan=lifespan, dependencies=[Depends(read_device_key)])
# 더 구체적인 경로를 먼저 마운트한다 (PHOTOS_DIR이 저장소 밖일 수 있음).
app.mount("/static/photos", StaticFiles(directory=str(PHOTOS_DIR)), name="photos")
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
app.include_router(characters_router)
app.include_router(memory_suggestions_router)
app.include_router(rooms_router)
app.include_router(messages_router)
app.include_router(tick_router)
app.include_router(profiles_router)


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.post("/api/reset")
def reset_all_data():
    conn = get_connection()
    try:
        profile_id = get_current_profile_id(conn)
    finally:
        conn.close()
    clear_profile_data(profile_id)
    return {"ok": True}

