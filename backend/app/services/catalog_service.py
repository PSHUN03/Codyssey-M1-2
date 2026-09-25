"""모든 출처를 한데 모은 작품 목록(카탈로그)과 통합 통계.

출처 (우선순위 순 — 같은 작가·같은 제목이면 앞 출처 하나만 센다)
  1. 위키문헌 시계열·직접 작성 (Firestore data) — 본문·글자 수 있음
  2. 위키문헌 참고 작품 서재 (Firestore library) — 본문 있음, 발표 시기 미상
  3. 구텐베르크 한국 관련 문학 (data/gutenberg_works.json) — 영어 본문
  4. 공유마당 만료저작물 어문 (data/gongu_works.json) — 목록 정보 + 원문 링크
  5. 한국문학번역원 번역 출간 도서 (data/lti_books.json) — 서지 정보
  6. 국립중앙도서관 (data/nlk_books.json) — 서지 정보
  7. KCISA 기관별 도서정보 (data/kcisa_books.json) — 서지 정보, 연도는 제목의 발행 연도 또는 기관 등록 연도

파일 출처는 읽기 전용이라 Firestore 에 넣지 않고 서버 메모리에서 합친다 (무료 한도 보호).
"""

from __future__ import annotations

import json
import re
import threading
import time
from collections import Counter, defaultdict
from functools import lru_cache
from pathlib import Path

from . import books_service, data_service, library_service

DATA = Path(__file__).resolve().parents[2] / "data"

# key, 이름, 본문 여부, 날짜 설명
SOURCES = [
    ("wikisource", "위키문헌", True, "발표·창작 연월일 (문서 근거)"),
    ("mine", "직접 작성", True, "작성일"),
    ("library", "위키문헌 서재", True, "발표 시기 미상"),
    ("gutenberg", "구텐베르크", True, "초판 연도"),
    ("gongu", "공유마당", False, "공표 연월 · 창작 연도"),
    ("lti", "한국문학번역원", False, "번역서 출간 연도"),
    ("nlk", "국립중앙도서관", False, "발행 연도"),
    ("kcisa", "KCISA 도서정보", False, "제목의 발행 연도, 없으면 기관 등록 연도"),
]
SOURCE_LABEL = {k: label for k, label, *_ in SOURCES}
MIN_YEAR = 1400
STATS_TTL = 120

_lock = threading.Lock()
_stats_cache: dict[tuple, tuple[float, dict]] = {}


def norm_title(t: str | None) -> str:
    t = re.sub(r"\(.*?\)|（.*?）|\[.*?\]|<.*?>", "", t or "")
    t = t.split(":")[0].split(" / ")[0]
    return re.sub(r"[\s·.,!?「」『』《》〈〉\"'“”‘’()_\-]", "", t).lower()


def norm_author(a: str | None) -> str:
    return re.sub(r"\s|\(.*?\)|（.*?）|옮김|지음|저$|著", "", a or "").lower()


def work_key(title: str | None, author: str | None) -> tuple[str, str]:
    return norm_author(author), norm_title(title)


def _year(d: str | None) -> int | None:
    return int(d[:4]) if d and d[:4].isdigit() else None


def _read(name: str) -> dict:
    path = DATA / name
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


@lru_cache
def _wikisource_keys() -> frozenset:
    raw = _read("wikisource_works.json")
    return frozenset(work_key(w["title"], w["author"]) for w in raw.get("records", []) + raw.get("library", []))


@lru_cache
def _static() -> tuple[tuple[dict, ...], dict]:
    """파일 출처를 우선순위대로 합치며 중복을 뺀 목록과 출처별 중복 수."""
    seen = set(_wikisource_keys())
    out: list[dict] = []
    dup: Counter = Counter()

    def add(source: str, rows: list[dict], within: bool = False) -> None:
        """앞 순위 출처에 같은 작가·같은 대표 제목이 있으면 뺀다. 같은 출처 안의 중복은 수집 단계에서 이미
        정리했으므로(KCISA 소장본 합치기 등) within=True 인 출처(공유마당의 '제목-1, 제목-2' 연번)만 여기서 합친다."""
        local: set = set()
        for i, r in enumerate(rows):
            key = work_key(r.get("title"), r.get("author"))
            if key[1] and (key in seen or (within and key in local)):
                dup[source] += 1
                continue
            local.add(key)
            out.append({"id": f"{source}-{i}", "source": source, **r})
        seen.update(local)

    add("gutenberg", [{
        "title": w["title"], "author": w.get("author"), "genre": w["genre"], "year": _year(w.get("date")),
        "basis": w.get("basis"), "url": w["url"], "chars": w.get("chars"), "note": w.get("note"),
        "language": w.get("language"),
    } for w in _read("gutenberg_works.json").get("works", [])])
    add("gongu", [{
        "title": w["title"], "author": w.get("author"), "genre": w["genre"], "year": _year(w.get("date")),
        "basis": w.get("basis"), "url": w["url"], "note": w.get("summary"), "origin": w.get("origin"),
        "provider": w.get("provider"),
    } for w in _read("gongu_works.json").get("works", [])], within=True)
    for source, name in (("lti", "lti_books.json"), ("nlk", "nlk_books.json")):
        add(source, [{
            "title": w["title"], "author": w.get("author"), "genre": w.get("genre", "기타"), "year": w.get("year"),
            "basis": w.get("basis"), "url": w.get("url"), "publisher": w.get("publisher"), "note": w.get("note"),
            "language": w.get("language"),
        } for w in _read(name).get("works", [])])
    add("kcisa", [{
        "title": b["title"], "author": b.get("author"), "genre": b["genre"], "year": b.get("year"),
        "basis": b.get("year_basis"), "url": b.get("url"), "publisher": b.get("publisher"),
        "institution": b.get("institution"), "wikisource_url": b.get("wikisource_url"),
    } for b in books_service.all_books()])
    return tuple(out), dict(dup)


def reference_entries() -> list[dict]:
    """파일 출처(구텐베르크·공유마당·번역원·국립중앙도서관·KCISA) 중복 제거 목록."""
    return list(_static()[0])


def _runtime_entries() -> list[dict]:
    """Firestore 에 있는 위키문헌·직접 작성·서재 (본문 있는 작품)."""
    rows = []
    for r in data_service.all_records():
        source = "wikisource" if r.get("source") == "위키문헌" else "mine"
        rows.append({"source": source, "title": r.get("title"), "author": r.get("author"), "genre": r.get("genre"),
                     "year": _year(r.get("date")), "chars": r.get("value")})
    for w in library_service.all_works():
        rows.append({"source": "library", "title": w.get("title"), "author": w.get("author"),
                     "genre": w.get("genre"), "year": None, "chars": w.get("value")})
    return rows


def _period(year: int, group: str) -> str:
    if group == "century":
        return f"{year // 100 + 1}세기"
    return f"{year // 10 * 10}년대"


def get_stats(group: str = "decade", genre: str | None = None) -> dict:
    key = (group, genre)
    with _lock:
        hit = _stats_cache.get(key)
        if hit and time.time() - hit[0] < STATS_TTL:
            return hit[1]
    entries = _runtime_entries() + reference_entries()
    if genre:
        entries = [e for e in entries if e.get("genre") == genre]

    per_source: dict[str, Counter] = defaultdict(Counter)
    series: dict[str, Counter] = defaultdict(Counter)
    order: dict[str, int] = {}
    genres: dict[str, Counter] = defaultdict(Counter)
    for e in entries:
        s = e["source"]
        y = e.get("year")
        per_source[s]["total"] += 1
        genres[e.get("genre") or "기타"][s] += 1
        if y and y >= MIN_YEAR:
            per_source[s]["dated"] += 1
            p = _period(y, group)
            series[p][s] += 1
            order[p] = min(order.get(p, y), y)
        else:
            per_source[s]["undated"] += 1
        if e.get("chars"):
            per_source[s]["with_text"] += 1

    dup = _static()[1]
    sources = [{
        "key": k, "label": label, "has_text": has_text, "date_basis": basis,
        "total": per_source[k]["total"], "dated": per_source[k]["dated"], "undated": per_source[k]["undated"],
        "duplicates_removed": dup.get(k, 0),
    } for k, label, has_text, basis in SOURCES if per_source[k]["total"] or dup.get(k)]
    result = {
        "group": group,
        "genre": genre,
        "total": sum(c["total"] for c in per_source.values()),
        "dated": sum(c["dated"] for c in per_source.values()),
        "undated": sum(c["undated"] for c in per_source.values()),
        "with_text": sum(c["with_text"] for c in per_source.values()),
        "duplicates_removed": sum(dup.values()),
        "sources": sources,
        "series": [{"period": p, "total": sum(series[p].values()), "by_source": dict(series[p])}
                   for p in sorted(series, key=lambda p: order[p])],
        "undated_by_source": {k: c["undated"] for k, c in per_source.items() if c["undated"]},
        "by_genre": sorted(({"key": g, "total": sum(c.values()), "by_source": dict(c)} for g, c in genres.items()),
                           key=lambda x: -x["total"]),
    }
    with _lock:
        _stats_cache[key] = (time.time(), result)
    return result


def invalidate() -> None:
    with _lock:
        _stats_cache.clear()


def list_entries(*, q: str | None = None, source: str | None = None, genre: str | None = None,
                 limit: int = 20, offset: int = 0) -> dict:
    rows = reference_entries()
    if source:
        rows = [r for r in rows if r["source"] == source]
    if genre:
        rows = [r for r in rows if r.get("genre") == genre]
    if q:
        k = q.strip().lower()
        rows = [r for r in rows if any(k in (r.get(f) or "").lower()
                                       for f in ("title", "author", "publisher", "note", "origin"))]
        rows.sort(key=lambda r: 0 if k in (r.get("title") or "").lower() else 1)
    return {
        "total": len(rows),
        "limit": limit,
        "offset": offset,
        "by_source": [{"key": s, "label": SOURCE_LABEL[s], "count": c}
                      for s, c in Counter(r["source"] for r in rows).most_common()],
        "items": [{**r, "source_label": SOURCE_LABEL[r["source"]]} for r in rows[offset:offset + limit]],
    }
