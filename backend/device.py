import threading
import time
from collections import deque
from contextvars import ContextVar

from fastapi import HTTPException, Request

# 헤더가 없으면 'local' — 로컬 개발은 기기 키 없이 지금처럼 동작한다.
_device_key = ContextVar("device_key", default="local")

_hits = {}
_hits_lock = threading.Lock()


def get_device_key() -> str:
    return _device_key.get()


async def read_device_key(request: Request) -> None:
    """전역 의존성: X-Device-Key 헤더를 ContextVar에 저장한다 (sync 핸들러의 스레드로도 전달된다)."""
    _device_key.set((request.headers.get("x-device-key") or "").strip()[:100] or "local")


def check_rate_limit(name: str, limit: int, window_seconds: int = 60) -> None:
    """기기별 메모리 슬라이딩 윈도우. 초과하면 429. uvicorn 워커 1개를 전제로 한다."""
    key = (name, get_device_key())
    now = time.monotonic()
    with _hits_lock:
        hits = _hits.setdefault(key, deque())
        while hits and now - hits[0] >= window_seconds:
            hits.popleft()
        if len(hits) >= limit:
            raise HTTPException(status_code=429, detail="요청이 너무 잦습니다. 잠시 후 다시 시도해 주세요.")
        hits.append(now)
