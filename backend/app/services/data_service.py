"""글쓰기 기록(data 컬렉션) CRUD + 조회 캐시.

요약/검색/통계는 전체 레코드를 기반으로 계산하므로, Firestore 읽기 비용을 줄이려고
전체 목록을 메모리에 캐시하고 쓰기(추가/수정/삭제)가 일어나면 즉시 무효화한다.
"""

from __future__ import annotations

import threading
import time

from ..firebase import DATA_COLLECTION
from ..schemas import DataCreate, DataUpdate
from ..storage import get_store

CACHE_TTL_SECONDS = 300

_lock = threading.Lock()
_cache: list[dict] | None = None
_cached_at = 0.0


def invalidate() -> None:
    global _cache
    with _lock:
        _cache = None


def all_records() -> list[dict]:
    """날짜 오름차순으로 정렬된 전체 레코드 (캐시)."""
    global _cache, _cached_at
    with _lock:
        if _cache is None or time.time() - _cached_at > CACHE_TTL_SECONDS:
            records = get_store().list_all(DATA_COLLECTION)
            records.sort(key=lambda r: (r.get("date", ""), r.get("title") or "", r["id"]))
            _cache, _cached_at = records, time.time()
        return _cache


def filter_records(
    records: list[dict],
    *,
    genre: str | None = None,
    source: str | None = None,
    stage: str | None = None,
    q: str | None = None,
    start: str | None = None,
    end: str | None = None,
    mine: bool | None = None,
) -> list[dict]:
    out = records
    if genre:
        out = [r for r in out if r.get("genre") == genre]
    if source:
        out = [r for r in out if r.get("source") == source]
    if mine is not None:
        out = [r for r in out if (r.get("source") != "위키문헌") == mine]
    if stage:
        out = [r for r in out if r.get("stage") == stage]
    if start:
        out = [r for r in out if r.get("date", "") >= start]
    if end:
        out = [r for r in out if r.get("date", "") <= end]
    if q:
        needle = q.strip().lower()
        out = [
            r for r in out
            if any(needle in (r.get(k) or "").lower() for k in ("title", "author", "memo", "excerpt"))
        ]
    return out


def list_records(*, order: str = "desc", limit: int = 20, offset: int = 0, **filters) -> tuple[int, list[dict]]:
    records = filter_records(all_records(), **filters)
    if order == "desc":
        records = list(reversed(records))
    return len(records), records[offset:offset + limit]


def get_record(record_id: str) -> dict | None:
    return get_store().get(DATA_COLLECTION, record_id)


def create_record(payload: DataCreate) -> dict:
    doc = get_store().add(DATA_COLLECTION, payload.model_dump(mode="json", exclude_none=True))
    invalidate()
    return doc


def update_record(record_id: str, payload: DataUpdate) -> dict | None:
    doc = get_store().update(DATA_COLLECTION, record_id, payload.model_dump(mode="json", exclude_unset=True))
    invalidate()
    return doc


def delete_record(record_id: str) -> bool:
    ok = get_store().delete(DATA_COLLECTION, record_id)
    invalidate()
    return ok
