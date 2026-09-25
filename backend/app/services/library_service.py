"""참고 작품 서재(library 컬렉션): 발표 시기를 확인할 수 없는 실존 작품.

시계열(data)과 분리해 요약·추세 통계는 왜곡하지 않고, AI 작품 검색과 목록 조회에만 쓴다.
API 로는 읽기만 하고(적재는 scripts/seed_firestore.py), 전체 목록을 메모리에 1시간 캐시한다.
"""

from __future__ import annotations

import logging
import threading
import time
from collections import Counter

from google.api_core.exceptions import GoogleAPIError

from ..firebase import LIBRARY_COLLECTION
from ..storage import get_store

CACHE_TTL_SECONDS = 6 * 3600
RETRY_SECONDS = 600
logger = logging.getLogger("geulbeot")

_lock = threading.Lock()
_cache: list[dict] | None = None
_cached_at = 0.0


def invalidate() -> None:
    global _cache
    with _lock:
        _cache = None


def all_works() -> list[dict]:
    """지은이·제목 순으로 정렬된 전체 서재 (캐시)."""
    global _cache, _cached_at
    with _lock:
        if _cache is None or time.time() - _cached_at > CACHE_TTL_SECONDS:
            try:
                works = get_store().list_all(LIBRARY_COLLECTION)
            except GoogleAPIError as e:  # 무료 한도 초과 등: 직전 캐시 → 없으면 포함된 스냅샷
                logger.warning("Firestore 서재 읽기 실패: %s", e)
                if _cache is None:
                    from ..seed import load_seed_library

                    works = [{**w, "id": f"lib-{w['pageid']}", "date": None} for w in load_seed_library()]
                    works.sort(key=lambda w: (w.get("author") or "", w.get("title") or "", w["id"]))
                    _cache = works
                _cached_at = time.time() - CACHE_TTL_SECONDS + RETRY_SECONDS
                return _cache
            for w in works:
                w["date"] = None
            works.sort(key=lambda w: (w.get("author") or "", w.get("title") or "", w["id"]))
            _cache, _cached_at = works, time.time()
        return _cache


def filter_works(works: list[dict], *, q: str | None = None, genre: str | None = None) -> list[dict]:
    out = works
    if genre:
        out = [w for w in out if w.get("genre") == genre]
    if q:
        needle = q.strip().lower()
        out = [w for w in out if any(needle in (w.get(k) or "").lower() for k in ("title", "author", "memo", "excerpt"))]
    return out


def list_works(*, q: str | None = None, genre: str | None = None, limit: int = 20, offset: int = 0) -> dict:
    works = filter_works(all_works(), q=q, genre=genre)
    by_genre = Counter(w.get("genre", "기타") for w in works)
    return {
        "total": len(works),
        "limit": limit,
        "offset": offset,
        "by_genre": [{"key": g, "count": c, "average": round(sum(w.get("value", 0) for w in works
                                                                   if w.get("genre") == g) / c, 1)}
                     for g, c in by_genre.most_common()],
        "items": works[offset:offset + limit],
    }


def get_work(work_id: str) -> dict | None:
    return next((w for w in all_works() if w["id"] == work_id), None)
