"""글쓰기 기록(data 컬렉션) CRUD + 조회 캐시.

요약/검색/통계는 전체 레코드를 기반으로 계산하므로, Firestore 읽기 비용을 줄이려고
전체 목록을 메모리에 캐시한다. 이 서버를 거친 쓰기(추가/수정/삭제)는 바뀐 문서만 캐시에 반영해서
기록 1건을 저장할 때 전체(1,500여 건)를 다시 읽지 않는다. 서버 밖(시드 스크립트 등)에서 바뀐 내용은
TTL 이 지나면 다시 읽어 온다.

Firestore 가 응답하지 못하면(무료 한도 초과 등) 직전 캐시를 계속 쓰고, 캐시도 없으면 백엔드에 포함된
위키문헌 스냅샷(data/wikisource_works.json)으로 읽기 전용 목록을 만든다 → 사이트 전체가 멈추지 않는다.
"""

from __future__ import annotations

import logging
import threading
import time

from google.api_core.exceptions import GoogleAPIError

from ..firebase import DATA_COLLECTION
from ..schemas import DataCreate, DataUpdate
from ..storage import get_store

CACHE_TTL_SECONDS = 6 * 3600  # 읽기 한도(하루 5만 회) 보호: API 를 거친 쓰기는 캐시에 바로 반영된다
RETRY_SECONDS = 600           # Firestore 실패 후 다시 시도하기까지

logger = logging.getLogger("geulbeot")
degraded = False              # True 면 Firestore 대신 캐시·스냅샷으로 응답 중

_lock = threading.Lock()
_cache: list[dict] | None = None
_cached_at = 0.0


def invalidate() -> None:
    global _cache
    with _lock:
        _cache = None


def _sort_key(r: dict):
    return (r.get("date", ""), r.get("title") or "", r["id"])


def _apply(doc_id: str, doc: dict | None) -> None:
    """캐시에 문서 1건 반영 (doc=None 이면 삭제). 캐시가 없으면 다음 조회 때 새로 읽는다."""
    global _cache
    with _lock:
        if _cache is None:
            return
        records = [r for r in _cache if r["id"] != doc_id]
        if doc is not None:
            records.append(doc)
            records.sort(key=_sort_key)
        _cache = records


def _snapshot() -> list[dict]:
    """Firestore 없이 쓸 읽기 전용 위키문헌 목록 (id 는 스냅샷 전용 'ws-<문서 번호>')."""
    from ..seed import load_seed_records  # 순환 import 방지

    return [{**r, "id": f"ws-{r['pageid']}", "source": r.get("source", "위키문헌")} for r in load_seed_records()]


def all_records() -> list[dict]:
    """날짜 오름차순으로 정렬된 전체 레코드 (캐시)."""
    global _cache, _cached_at, degraded
    with _lock:
        if _cache is None or time.time() - _cached_at > CACHE_TTL_SECONDS:
            try:
                records = get_store().list_all(DATA_COLLECTION)
                degraded = False
            except GoogleAPIError as e:
                logger.warning("Firestore 읽기 실패 → %s: %s", "직전 캐시 유지" if _cache else "스냅샷 사용", e)
                degraded = True
                records = _cache if _cache is not None else _snapshot()
                # 10분 뒤 다시 시도하도록 캐시 시각을 조정
                _cache, _cached_at = sorted(records, key=_sort_key), time.time() - CACHE_TTL_SECONDS + RETRY_SECONDS
                return _cache
            records.sort(key=_sort_key)
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
    _apply(doc["id"], doc)
    return doc


def update_record(record_id: str, payload: DataUpdate) -> dict | None:
    doc = get_store().update(DATA_COLLECTION, record_id, payload.model_dump(mode="json", exclude_unset=True))
    if doc is not None:
        _apply(record_id, doc)
    return doc


def delete_record(record_id: str) -> bool:
    ok = get_store().delete(DATA_COLLECTION, record_id)
    if ok:
        _apply(record_id, None)
    return ok
