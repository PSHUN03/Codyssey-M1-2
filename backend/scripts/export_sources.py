"""사용한 자료를 출처별 폴더(저장소 루트의 sources/)로 내보낸다.

  - 본문을 가질 수 있는 퍼블릭 도메인 작품(위키문헌·구텐베르크): 작품마다 전체 본문 .txt + 목록 CSV
  - 본문이 없는 출처(공유마당·KCISA·공공데이터 보충 자료): 목록 CSV(제목·저자·장르·연도·링크) + 설명 README
  CSV 는 엑셀에서 한글이 깨지지 않도록 UTF-8(BOM) 으로 저장한다.

실행 (backend 폴더에서, 위키문헌 수집기를 한 번 돌린 뒤): python -m scripts.export_sources
"""

from __future__ import annotations

import csv
import json
import os
import re
import shutil
import sys
import time
import urllib.request
from collections import Counter
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
DATA = BACKEND / "data"
OUT = BACKEND.parent / "sources"
sys.path.insert(0, str(BACKEND))
os.environ.setdefault("STORAGE_BACKEND", "memory")

from app.services import books_service, catalog_service  # noqa: E402

USER_AGENT = "geulbeot-writing-assistant/0.3 (https://github.com/PSHUN03/Codyssey-M1-2; educational project)"


def safe(name: str, limit: int = 60) -> str:
    """Windows·macOS 에서 쓸 수 있는 파일 이름."""
    name = re.sub(r'[\\/:*?"<>|\r\n\t]', " ", name or "").strip(" .")
    return re.sub(r"\s+", " ", name)[:limit].strip() or "제목 없음"


def write_csv(path: Path, header: list[str], rows: list[list]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)


def write_readme(path: Path, lines: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


# ---------------------------------------------------------------- 위키문헌 (전체 본문)
def export_wikisource(folder: str) -> dict:
    works = json.loads((DATA / "wikisource_works.json").read_text(encoding="utf-8"))
    texts = json.loads((DATA / ".wikisource_texts.json").read_text(encoding="utf-8"))
    base = OUT / folder
    rows, used = [], set()
    for kind, items in (("시계열", works["records"]), ("발표 시기 미상", works["library"])):
        for w in items:
            when = w.get("date") or "시기 미상"
            fname = safe(f"{w['author'] or '작자 미상'} - {w['title']} ({when[:10]})", 90)
            rel = Path("본문") / safe(w["genre"], 10) / f"{fname}.txt"
            if rel in used:
                rel = rel.with_name(f"{fname} [{w['pageid']}].txt")
            used.add(rel)
            body = texts.get(str(w["pageid"]), w.get("excerpt") or "")
            head = [f"제목: {w['title']}", f"지은이: {w['author'] or '작자 미상'}", f"장르: {w['genre']}",
                    f"날짜: {w.get('date') or '발표 시기 미상'} ({w.get('basis') or kind})",
                    f"글자 수(공백 제외): {w['value']:,}", f"메모: {w.get('memo', '')}", f"원문: {w['url']}",
                    "출처: 한국어 위키문헌 (퍼블릭 도메인)", "", "-" * 40, ""]
            (base / rel).parent.mkdir(parents=True, exist_ok=True)
            (base / rel).write_text("\n".join(head) + body.strip() + "\n", encoding="utf-8")
            rows.append([kind, w.get("date") or "", w.get("basis") or "", w["genre"], w["title"], w["author"] or "",
                         w["value"], w["url"], rel.as_posix()])
    write_csv(base / "목록.csv", ["구분", "날짜", "날짜 근거", "장르", "제목", "지은이", "글자 수", "원문 링크", "본문 파일"], rows)
    genres = Counter(r[3] for r in rows)
    write_readme(base / "README.md", [
        "# 한국어 위키문헌",
        "",
        f"- 출처: [한국어 위키문헌](https://ko.wikisource.org) — MediaWiki API (`backend/scripts/import_wikisource.py`)",
        f"- 작품 수: **{len(rows):,}편** (시계열 {len(works['records']):,} + 발표 시기 미상 {len(works['library']):,})",
        "- 본문: `본문/<장르>/<지은이> - <제목> (<날짜>).txt` — 파일 맨 위에 제목·지은이·날짜 근거·원문 링크",
        "- 목록: [`목록.csv`](목록.csv) (엑셀로 열림)",
        "- 라이선스: 퍼블릭 도메인 — 1962년 이전에 사망한 작가·작자 미상 고전만 수록",
        "- 장편·연재물은 장별 문서를 목차 순서로 이어 붙였고(【장 제목】으로 구분), 스캔본 문서는 위키문헌이 렌더링한 본문",
        "",
        "| 장르 | 편 수 |",
        "|---|---|",
        *[f"| {g} | {n:,} |" for g, n in genres.most_common()],
    ])
    return {"count": len(rows), "text": True}


# ---------------------------------------------------------------- 구텐베르크 (전체 본문)
def gutenberg_body(url: str) -> str:
    gid = url.rstrip("/").split("/")[-1]
    req = urllib.request.Request(f"https://www.gutenberg.org/ebooks/{gid}.txt.utf-8", headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=120) as res:
        text = res.read().decode("utf-8", "replace")
    start = re.search(r"\*\*\* ?START OF (THE|THIS) PROJECT GUTENBERG.*?\*\*\*", text)
    end = re.search(r"\*\*\* ?END OF (THE|THIS) PROJECT GUTENBERG", text)
    return text[start.end() if start else 0:end.start() if end else len(text)].strip()


def export_gutenberg(folder: str) -> dict:
    works = json.loads((DATA / "gutenberg_works.json").read_text(encoding="utf-8"))["works"]
    base = OUT / folder
    rows = []
    for w in works:
        rel = Path("본문") / f"{safe(w['title'], 70)} ({w['date'][:4]}).txt"
        (base / rel).parent.mkdir(parents=True, exist_ok=True)
        if not (base / rel).exists():
            body = gutenberg_body(w["url"])
            head = [f"Title: {w['title']}", f"Author: {w['author'] or ''}", f"First published: {w['date'][:4]}",
                    f"장르: {w['genre']} · {w['note']}", f"Source: {w['url']} (Project Gutenberg, public domain)",
                    "", "-" * 40, ""]
            (base / rel).write_text("\n".join(head) + body + "\n", encoding="utf-8")
            time.sleep(1)
        rows.append([w["date"][:4], w["genre"], w["title"], w["author"] or "", w["chars"], w["url"], rel.as_posix()])
    write_csv(base / "목록.csv", ["초판 연도", "장르", "제목", "저자", "글자 수(공백 제외)", "링크", "본문 파일"], rows)
    write_readme(base / "README.md", [
        "# Project Gutenberg — 한국 관련 문학 (영어)",
        "",
        "- 출처: [Project Gutenberg](https://www.gutenberg.org) (`backend/scripts/import_gutenberg.py`)",
        f"- 작품 수: **{len(rows)}편** — 한국어 책은 사전 1권뿐이라 주제어 Korea 36권 중 설화·소설·아동문학만",
        "- 본문: `본문/*.txt` (구텐베르크 머리말·라이선스 꼬리말을 뺀 본문)",
        "- 라이선스: 퍼블릭 도메인 (초판 1889~1922, 작가 모두 1945년 이전 사망)",
        "",
        "| 초판 | 제목 | 저자 |",
        "|---|---|---|",
        *[f"| {r[0]} | [{r[2]}]({r[5]}) | {r[3]} |" for r in rows],
    ])
    return {"count": len(rows), "text": True}


# ---------------------------------------------------------------- 목록만 있는 출처
def kept_ids() -> set[str]:
    entries, _ = catalog_service._static()
    return {e["id"] for e in entries}


def export_listing(folder: str, key: str, title: str, lines: list[str], rows_src: list[dict], fields: list[tuple]) -> dict:
    kept = kept_ids()
    base = OUT / folder
    rows = []
    for i, r in enumerate(rows_src):
        stat = "포함" if f"{key}-{i}" in kept else "중복 제외 (앞 순위 출처에 있음)"
        rows.append([r.get(f) if not callable(f) else f(r) for _, f in fields] + [stat])
    write_csv(base / "목록.csv", [h for h, _ in fields] + ["통합 통계"], rows)
    n_kept = sum(1 for r in rows if r[-1] == "포함")
    genres = Counter(r.get("genre") for r in rows_src)
    write_readme(base / "README.md", [
        f"# {title}",
        "",
        *lines,
        f"- 자료 수: **{len(rows):,}건** (통합 통계 포함 {n_kept:,} · 앞 순위 출처와 겹쳐 제외 {len(rows) - n_kept:,})",
        "- 목록: [`목록.csv`](목록.csv) (엑셀로 열림) — 각 행의 링크로 원문·소장 자료를 볼 수 있음",
        "",
        "| 장르 | 건수 |",
        "|---|---|",
        *[f"| {g} | {n:,} |" for g, n in genres.most_common()],
    ])
    return {"count": len(rows), "kept": n_kept, "text": False}


COMMON = [("제목", "title"), ("저자", "author"), ("장르", "genre"), ("연도", "year"), ("연도 근거", "basis"),
          ("링크", "url"), ("발행처", "publisher"), ("비고", "note")]


def main() -> None:
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir()
    for f in (books_service._load, catalog_service._static, catalog_service._wikisource_keys):
        f.cache_clear()
    summary = []

    summary.append(("01_위키문헌", "한국어 위키문헌", export_wikisource("01_위키문헌")))
    summary.append(("02_구텐베르크", "Project Gutenberg (한국 관련, 영어)", export_gutenberg("02_구텐베르크")))

    gongu = json.loads((DATA / "gongu_works.json").read_text(encoding="utf-8"))["works"]
    gongu_rows = [{"title": w["title"], "author": w.get("author"), "genre": w["genre"], "year": (w.get("date") or "")[:4],
                   "basis": w.get("basis"), "url": w["url"], "publisher": w.get("provider"),
                   "note": " · ".join(x for x in (f"출전 {w['origin']}" if w.get("origin") else "", w.get("summary") or "")
                                      if x)} for w in gongu]
    summary.append(("03_공유마당", "공유마당 만료저작물", export_listing(
        "03_공유마당", "gongu", "공유마당 만료저작물 (한국저작권위원회)",
        ["- 출처: [공유마당](https://gongu.copyright.or.kr) 어문 '만료저작물' — 한국저작권위원회·한국고전번역원 제공분 "
         "(`backend/scripts/import_gongu.py`)",
         "- 본문: 원문 파일은 robots.txt 가 수집을 막고 다운로드에 이용 동의 절차가 있어 저장하지 않았고, 각 행의 공유마당 링크에서 볼 수 있음",
         "- 연도: 공표 연월 → 창작 연도, 한국고전번역원 제공분의 공표 연도는 번역본이 나온 해라 쓰지 않음"],
        gongu_rows, COMMON)))

    books = books_service.all_books()
    summary.append(("04_KCISA_기관별도서정보", "KCISA 기관별 도서정보", export_listing(
        "04_KCISA_기관별도서정보", "kcisa", "문화체육관광부 외 기관별 도서정보 (KCISA API_LIB_051)",
        ["- 출처: [문화 공공데이터광장](https://www.culture.go.kr/data) 기관별 도서정보 39만 건 중 문학 자료 "
         "(`backend/scripts/import_kcisa.py`, `kcisa_build.py`)",
         "- 공연대본·평론 기사·시집·소설집 등 서지 정보 (본문 없음), 같은 자료의 소장본은 한 건으로 합침",
         "- 연도: 제목에 적힌 발행 연도 → 없으면 기관 등록 연도"],
        [{**b, "basis": b.get("year_basis"), "note": " · ".join(x for x in (b.get("institution"), b.get("collection"),
                                                                             b.get("wikisource_url")) if x)}
         for b in books], COMMON)))

    n = 5
    for key, label, *_rest in catalog_service.SOURCES[catalog_service.SOURCES.index(
            next(s for s in catalog_service.SOURCES if s[0] == "lib046")):-1]:
        path = DATA / f"extra_{key}.json"
        if not path.exists():
            continue
        raw = json.loads(path.read_text(encoding="utf-8"))
        rows = [w for w in raw["works"] if w.get("title")]
        if not rows:
            continue  # 문학 자료가 없는 출처 (OAK-PORTAL)
        folder = f"{n:02d}_{safe(label, 30).replace(' ', '_')}"
        n += 1
        summary.append((folder, label, export_listing(
            folder, key, f"{label} ({raw['organization']})",
            [f"- 출처: [문화 공공데이터광장](https://www.culture.go.kr/data) — {raw['source']} "
             "(`backend/scripts/import_kcisa_extra.py`)",
             f"- 원자료 {raw['raw']:,}건 중 문학 자료만 (서지 정보, 본문 없음)",
             "- 연도: 형식이 분명한 발행 연도만, 없으면 비워 둠 (기관 등록일은 쓰지 않음)"],
            rows, COMMON)))

    write_readme(OUT / "README.md", [
        "# 사용한 자료 (출처별)",
        "",
        "글벗이 참고 작품·통계에 쓰는 자료를 출처별 폴더로 모았습니다. 폴더마다 `README.md`(출처·수집 방법·건수)와 "
        "`목록.csv`(엑셀로 열림)가 있고, 퍼블릭 도메인 작품은 `본문/` 폴더에 전체 본문 텍스트가 있습니다.",
        "",
        "| 폴더 | 출처 | 자료 수 | 본문 |",
        "|---|---|---|---|",
        *[f"| [`{folder}`]({folder}/) | {label} | {info['count']:,} | {'전체 본문 txt' if info['text'] else '목록 + 링크'} |"
          for folder, label, info in summary],
        "",
        "- 사용자가 직접 작성한 기록은 Firestore 에만 저장하고 이 폴더(공개 저장소)에는 넣지 않습니다.",
        "- 다시 만들기: `cd backend && python scripts/import_wikisource.py && python -m scripts.export_sources`",
    ])
    for folder, label, info in summary:
        print(f"{folder}: {info['count']:,}")


if __name__ == "__main__":
    main()
