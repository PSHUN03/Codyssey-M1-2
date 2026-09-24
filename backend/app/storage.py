"""컬렉션 단위 문서 저장소.

서비스 계층은 이 인터페이스만 사용하므로 Firestore 세부 API가 라우터/서비스로 새어 나가지 않는다.
- FirestoreStore: 실제 운영용 (컬렉션: data, conversations)
- MemoryStore   : Firebase 키 없이 로컬에서 동작만 확인할 때 사용 (STORAGE_BACKEND=memory)
"""

from __future__ import annotations

import uuid
from copy import deepcopy
from datetime import datetime, timezone
from functools import lru_cache
from typing import Protocol

from .config import settings


def now() -> datetime:
    return datetime.now(timezone.utc)


class Store(Protocol):
    def list_all(self, collection: str) -> list[dict]: ...
    def get(self, collection: str, doc_id: str) -> dict | None: ...
    def add(self, collection: str, data: dict) -> dict: ...
    def update(self, collection: str, doc_id: str, data: dict) -> dict | None: ...
    def delete(self, collection: str, doc_id: str) -> bool: ...
    def add_many(self, collection: str, items: list[dict]) -> int: ...
    def clear(self, collection: str, where: tuple[str, str] | None = None) -> int: ...


class FirestoreStore:
    def __init__(self):
        from .firebase import get_db

        self.db = get_db()

    def _col(self, collection: str):
        return self.db.collection(collection)

    def list_all(self, collection: str) -> list[dict]:
        return [{"id": d.id, **d.to_dict()} for d in self._col(collection).stream()]

    def get(self, collection: str, doc_id: str) -> dict | None:
        snap = self._col(collection).document(doc_id).get()
        return {"id": snap.id, **snap.to_dict()} if snap.exists else None

    def add(self, collection: str, data: dict) -> dict:
        ts = now()
        doc = {**data, "created_at": ts, "updated_at": ts}
        _, ref = self._col(collection).add(doc)
        return {"id": ref.id, **doc}

    def update(self, collection: str, doc_id: str, data: dict) -> dict | None:
        ref = self._col(collection).document(doc_id)
        if not ref.get().exists:
            return None
        ref.update({**data, "updated_at": now()})
        return self.get(collection, doc_id)

    def delete(self, collection: str, doc_id: str) -> bool:
        ref = self._col(collection).document(doc_id)
        if not ref.get().exists:
            return False
        ref.delete()
        return True

    def add_many(self, collection: str, items: list[dict]) -> int:
        ts = now()
        for i in range(0, len(items), 400):  # Firestore 배치 한도 500
            batch = self.db.batch()
            for item in items[i:i + 400]:
                batch.set(self._col(collection).document(), {**item, "created_at": ts, "updated_at": ts})
            batch.commit()
        return len(items)

    def clear(self, collection: str, where: tuple[str, str] | None = None) -> int:
        query = self._col(collection)
        if where:
            query = query.where(field_path=where[0], op_string="==", value=where[1])
        refs = [d.reference for d in query.stream()]
        for i in range(0, len(refs), 400):
            batch = self.db.batch()
            for ref in refs[i:i + 400]:
                batch.delete(ref)
            batch.commit()
        return len(refs)


class MemoryStore:
    def __init__(self):
        self.data: dict[str, dict[str, dict]] = {}

    def _col(self, collection: str) -> dict[str, dict]:
        return self.data.setdefault(collection, {})

    def list_all(self, collection: str) -> list[dict]:
        return [{"id": k, **deepcopy(v)} for k, v in self._col(collection).items()]

    def get(self, collection: str, doc_id: str) -> dict | None:
        doc = self._col(collection).get(doc_id)
        return {"id": doc_id, **deepcopy(doc)} if doc is not None else None

    def add(self, collection: str, data: dict) -> dict:
        ts = now()
        doc_id = uuid.uuid4().hex[:20]
        self._col(collection)[doc_id] = {**deepcopy(data), "created_at": ts, "updated_at": ts}
        return self.get(collection, doc_id)

    def update(self, collection: str, doc_id: str, data: dict) -> dict | None:
        col = self._col(collection)
        if doc_id not in col:
            return None
        col[doc_id].update({**deepcopy(data), "updated_at": now()})
        return self.get(collection, doc_id)

    def delete(self, collection: str, doc_id: str) -> bool:
        return self._col(collection).pop(doc_id, None) is not None

    def add_many(self, collection: str, items: list[dict]) -> int:
        for item in items:
            self.add(collection, item)
        return len(items)

    def clear(self, collection: str, where: tuple[str, str] | None = None) -> int:
        col = self._col(collection)
        ids = [k for k, v in col.items() if not where or v.get(where[0]) == where[1]]
        for k in ids:
            del col[k]
        return len(ids)


@lru_cache
def get_store() -> Store:
    if settings.storage_backend == "memory":
        return MemoryStore()
    return FirestoreStore()
