"""data/wikisource_works.json(수집 결과) → data(시계열) · library(발표 시기 미상) 컬렉션 적재."""

import json
from pathlib import Path

from .firebase import DATA_COLLECTION, LIBRARY_COLLECTION
from .schemas import DataCreate, LibraryWork
from .services import data_service, library_service
from .storage import Store

SEED_PATH = Path(__file__).resolve().parent.parent / "data" / "wikisource_works.json"
SEED_SOURCE = "위키문헌"


def _raw() -> dict:
    return json.loads(SEED_PATH.read_text(encoding="utf-8")) if SEED_PATH.exists() else {}


def _clean(r: dict) -> dict:
    return {k: v for k, v in r.items() if k not in ("pageid", "basis") and v not in ("", None)}


def load_seed_records(limit: int | None = None) -> list[dict]:
    records = []
    for r in _raw().get("records", [])[:limit]:
        # 적재 전에 API 와 같은 Pydantic 검증을 통과시킨다.
        valid = DataCreate(**_clean(r))
        records.append({**valid.model_dump(mode="json", exclude_none=True), "pageid": r["pageid"]})
    return records


def load_seed_library(limit: int | None = None) -> list[dict]:
    works = []
    for r in _raw().get("library", [])[:limit]:
        valid = LibraryWork(**_clean(r))
        works.append({**valid.model_dump(mode="json", exclude_none=True), "pageid": r["pageid"]})
    return works


def _load(store: Store, collection: str, rows: list[dict], reset: bool) -> tuple[int, int, int]:
    removed = store.clear(collection, where=("source", SEED_SOURCE)) if reset else 0
    existing = {r.get("pageid") for r in store.list_all(collection) if r.get("pageid")}
    added = store.add_many(collection, [r for r in rows if r["pageid"] not in existing])
    return removed, added, len(existing)


def seed(store: Store, reset: bool = False, limit: int | None = None) -> dict:
    removed, added, skipped = _load(store, DATA_COLLECTION, load_seed_records(limit), reset)
    lib_removed, lib_added, lib_skipped = _load(store, LIBRARY_COLLECTION, load_seed_library(limit), reset)
    data_service.invalidate()
    library_service.invalidate()
    return {"removed": removed, "added": added, "skipped": skipped,
            "library_removed": lib_removed, "library_added": lib_added, "library_skipped": lib_skipped}
