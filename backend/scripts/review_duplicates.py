"""출처 간·출처 내 중복을 검토하고 docs/duplicates-report.md 를 만든다.

1) 위키문헌 내부: 수집기가 같은 지은이·같은 작품(여러 판본)을 이미 하나로 줄였다 → 제거 개수 기록
2) 위키문헌 ↔ KCISA 참고 도서: 같은 작가의 같은 제목이면 도서에 원문 링크(wikisource_url)를 단다
   (KCISA 는 서지 정보라 지우지 않고 연결만 한다)
3) KCISA 내부: 같은 책 여러 소장본은 build 단계에서 합쳤고, 같은 제목·작가인데 발행처가 다른 판본을 집계한다

실행 (backend 폴더에서): python -m scripts.review_duplicates
"""

import json
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / "data"
WORKS = DATA / "wikisource_works.json"
BOOKS = DATA / "kcisa_books.json"
REPORT = Path(__file__).resolve().parents[2] / "docs" / "duplicates-report.md"


def norm(text: str | None) -> str:
    t = re.sub(r"\(.*?\)|（.*?）|\[.*?\]", "", text or "")
    t = t.split(":")[0].split(" / ")[0]
    return re.sub(r"[\s·.,!?「」『』《》〈〉\"'“”‘’()_\-]", "", t).lower()


def norm_author(a: str | None) -> str:
    return re.sub(r"\s|\(.*?\)|（.*?）|옮김|저|著|지음", "", a or "")


def catalog_rows() -> list[str]:
    import os
    import sys

    os.environ.setdefault("STORAGE_BACKEND", "memory")
    sys.path.insert(0, str(DATA.parent))
    from app.services import books_service, catalog_service

    books_service._load.cache_clear()
    catalog_service._static.cache_clear()
    entries, dup = catalog_service._static()
    kept = Counter(e["source"] for e in entries)
    rows = []
    for key, label, *_ in catalog_service.SOURCES:
        if kept.get(key) or dup.get(key):
            rows.append(f"| {label} | {kept.get(key, 0) + dup.get(key, 0):,} | {kept.get(key, 0):,} | {dup.get(key, 0):,} |")
    return rows


def main() -> None:
    works = json.loads(WORKS.read_text(encoding="utf-8"))
    ws = works["records"] + works["library"]
    books_raw = json.loads(BOOKS.read_text(encoding="utf-8"))
    books = books_raw["books"]

    by_key: dict[tuple, dict] = {}
    for w in ws:
        by_key.setdefault((norm_author(w["author"]), norm(w["title"])), w)

    linked = []
    for b in books:
        b.pop("wikisource_url", None)
        key = (norm_author(b.get("author")), norm(b.get("title")))
        w = by_key.get(key)
        if w and key[0] and key[1]:
            b["wikisource_url"] = w["url"]
            if b.get("genre") == "기타":  # 한국문학번역원 자료는 장르 정보가 없어 원문의 장르를 따른다
                b["genre"] = w["genre"]
            linked.append((b, w))
    BOOKS.write_text(json.dumps(books_raw, ensure_ascii=False, indent=0), encoding="utf-8")

    editions: dict[tuple, set] = defaultdict(set)
    for b in books:
        editions[(norm_author(b.get("author")), norm(b.get("title")))].add(b.get("publisher") or "")
    multi = {k: v for k, v in editions.items() if len(v) > 1 and k[1]}
    copies = sum(b.get("copies", 1) - 1 for b in books)
    removed = works.get("duplicates_removed", {})

    lines = [
        "# 중복 검토 보고서",
        "",
        f"> 자동 생성: `python -m scripts.review_duplicates` · {datetime.now(timezone.utc).isoformat(timespec='seconds')}",
        "",
        "| 구분 | 결과 | 처리 |",
        "|---|---|---|",
        f"| 위키문헌 내부 — 같은 작품의 여러 판본 (시계열) | {removed.get('records', 0):,}편 | 날짜 근거가 가장 정확하고 이른 판본 하나만 남김 |",
        f"| 위키문헌 내부 — 서재 중복·날짜 있는 판본과 겹침 | {removed.get('library', 0):,}편 | 날짜 있는 판본을 남기고, 서재 안에서는 본문이 긴 쪽 하나만 |",
        f"| KCISA 내부 — 같은 책의 소장본 여러 권 | {copies:,}권 | 한 권으로 합치고 `copies`에 권수 기록 |",
        f"| KCISA 내부 — 같은 제목·작가, 발행처가 다른 판본 | {len(multi):,}종 | 서로 다른 판본이라 모두 유지 |",
        f"| 위키문헌 ↔ KCISA — 같은 작가·같은 제목 | {len(linked):,}건 | 도서 정보에 위키문헌 원문 링크(`wikisource_url`) 연결 |",
        "",
        "## 통합 통계·검색에서의 출처 간 중복 (`app/services/catalog_service.py`)",
        "",
        "같은 작가·같은 대표 제목이면 **본문이 있는 출처를 우선**해 한 번만 센다: "
        "위키문헌 > 구텐베르크 > 공유마당 > 한국문학번역원 > 국립중앙도서관 > KCISA. "
        "같은 출처 안에서는 합치지 않는다 (공유마당의 '무제'·'其二'처럼 제목이 같아도 다른 작품이 많다).",
        "",
        "| 출처 | 원자료 | 통계에 넣은 수 | 앞 순위 출처와 겹쳐 뺀 수 |",
        "|---|---|---|---|",
        *catalog_rows(),
        "",
    ]
    if linked:
        lines += ["## 위키문헌 원문과 연결된 참고 도서 (최대 40건)", "",
                  "| 도서 제목 | 저자 | 소장 기관 | 위키문헌 원문 |", "|---|---|---|---|"]
        lines += [f"| {b['title']} | {b.get('author') or ''} | {b.get('institution') or ''} | [{w['title']}]({w['url']}) |"
                  for b, w in linked[:40]]
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"연결 {len(linked)}건 · 판본 {len(multi)}종 · 소장본 중복 {copies}권 → {REPORT}")


if __name__ == "__main__":
    main()
