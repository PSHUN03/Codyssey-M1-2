"""AI 호출 비용 보호용 요청 횟수 제한 (서버 메모리 기반, 단일 인스턴스 기준).

- 클라이언트(IP)별: 최근 60초 동안 CHAT_RATE_PER_MINUTE 회
- 서버 전체: 하루(UTC) CHAT_DAILY_LIMIT 회
"""

import threading
import time
from collections import defaultdict, deque
from datetime import datetime, timezone

from fastapi import HTTPException, Request

from .config import settings

_lock = threading.Lock()
_recent: dict[str, deque] = defaultdict(deque)
_daily = {"day": "", "count": 0}


def client_ip(request: Request) -> str:
    # Render 는 프록시 뒤에서 동작하므로 X-Forwarded-For 의 첫 주소가 실제 클라이언트
    forwarded = request.headers.get("x-forwarded-for", "")
    return forwarded.split(",")[0].strip() or (request.client.host if request.client else "unknown")


def check_chat_quota(request: Request) -> None:
    """FastAPI 의존성: 한도를 넘으면 429."""
    now = time.time()
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    ip = client_ip(request)
    with _lock:
        if _daily["day"] != today:
            _daily.update(day=today, count=0)
        if _daily["count"] >= settings.chat_daily_limit:
            raise HTTPException(429, "오늘 AI 대화 사용량이 모두 소진됐어요. 내일 다시 이용해 주세요.")
        window = _recent[ip]
        while window and now - window[0] > 60:
            window.popleft()
        if len(window) >= settings.chat_rate_per_minute:
            wait = int(60 - (now - window[0])) + 1
            raise HTTPException(429, f"요청이 너무 잦아요. {wait}초 후에 다시 시도해 주세요.",
                                headers={"Retry-After": str(wait)})
        window.append(now)
        _daily["count"] += 1


def reset() -> None:
    with _lock:
        _recent.clear()
        _daily.update(day="", count=0)
