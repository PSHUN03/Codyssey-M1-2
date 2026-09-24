"""data/wikisource_works.json(수집 결과) → data 컬렉션 적재."""

import json
from pathlib import Path

from .firebase import DATA_COLLECTION
from .schemas import DataCreate
from .services import data_service
from .storage import Store

SEED_PATH = Path(__file__).resolve().parent.parent / "data" / "wikisource_works.json"
SEED_SOURCE = "위키문헌"


def load_seed_records(limit: int | None = None) -> list[dict]:
    if not SEED_PATH.exists():
        return []
    raw = json.loads(SEED_PATH.read_text(encoding="utf-8"))["records"]
    records = []
    for r in raw[:limit]:
        # 적재 전에 API 와 같은 Pydantic 검증을 통과시킨다.
        valid = DataCreate(**{k: v for k, v in r.items() if k != "pageid" and v not in ("", None)})
        records.append({**valid.model_dump(mode="json", exclude_none=True), "pageid": r["pageid"]})
    return records


def seed(store: Store, reset: bool = False, limit: int | None = None) -> dict:
    removed = store.clear(DATA_COLLECTION, where=("source", SEED_SOURCE)) if reset else 0
    existing = {r.get("pageid") for r in store.list_all(DATA_COLLECTION) if r.get("pageid")}
    new = [r for r in load_seed_records(limit) if r["pageid"] not in existing]
    added = store.add_many(DATA_COLLECTION, new)
    data_service.invalidate()
    return {"removed": removed, "added": added, "skipped": len(existing)}
