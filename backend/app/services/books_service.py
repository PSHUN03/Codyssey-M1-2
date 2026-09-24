"""참고 도서 목록: 한국문화정보원 기관별 도서정보(KCISA API_LIB_051)에서 고른 문학 자료.

본문이 없는 서지 정보(제목·저자·발행처·소장 기관)이고 발행일도 원작 발표일이 아니므로
시계열·요약 통계에는 넣지 않는다. 읽기 전용 참고 목록이라 Firestore 대신 백엔드에 포함된
JSON 파일(data/kcisa_books.json)을 메모리에 올려 검색한다 (Firestore 무료 읽기·쓰기 한도 보호).
"""

from __future__ import annotations

import json
from collections import Counter
from functools import lru_cache
from pathlib import Path

BOOKS_PATH = Path(__file__).resolve().parents[2] / "data" / "kcisa_books.json"


@lru_cache
def _load() -> tuple[dict, list[dict]]:
    if not BOOKS_PATH.exists():
        return {}, []
    raw = json.loads(BOOKS_PATH.read_text(encoding="utf-8"))
    books = [{"id": f"kcisa-{i}", **b} for i, b in enumerate(raw.get("books", []))]
    meta = {k: v for k, v in raw.items() if k != "books"}
    return meta, books


def all_books() -> list[dict]:
    return _load()[1]


def meta() -> dict:
    return _load()[0]


def filter_books(books: list[dict], *, q: str | None = None, genre: str | None = None) -> list[dict]:
    out = books
    if genre:
        out = [b for b in out if b.get("genre") == genre]
    if q:
        needle = q.strip().lower()
        out = [b for b in out if any(needle in (b.get(k) or "").lower() for k in ("title", "author", "publisher"))]
    return out


def list_books(*, q: str | None = None, genre: str | None = None, limit: int = 20, offset: int = 0) -> dict:
    books = filter_books(all_books(), q=q, genre=genre)
    if q:
        k = q.strip().lower()
        books = sorted(books, key=lambda b: 0 if k in (b.get("title") or "").lower() else 1)
    return {
        "total": len(books),
        "limit": limit,
        "offset": offset,
        "by_genre": [{"key": g, "count": c, "average": 0.0}
                     for g, c in Counter(b.get("genre") for b in books).most_common()],
        "source": meta().get("source"),
        "items": books[offset:offset + limit],
    }
