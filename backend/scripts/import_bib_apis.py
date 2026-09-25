"""서지 정보 API 두 곳 수집 (키는 backend/.env 에만 둔다).

  lti : 한국문학번역원 번역출간DB — 원작가 이름(DB_AI_OR_NAME)으로 번역서 검색
        대상 작가 = 위키문헌·공유마당에서 모은 작가 → data/lti_books.json
  nlk : 국립중앙도서관 사서추천도서 — 문학 분야(drCode=11) 전체 → data/nlk_books.json

응답 필드 이름이 문서마다 조금씩 달라, 먼저 `probe` 로 실제 응답을 확인한 뒤 수집한다.

실행 (backend 폴더에서):
    python -m scripts.import_bib_apis probe lti      # 첫 응답 원문 확인
    python -m scripts.import_bib_apis lti
    python -m scripts.import_bib_apis probe nlk
    python -m scripts.import_bib_apis nlk
환경 변수: LTI_API_KEY, NLK_API_KEY
"""

from __future__ import annotations

import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

BACKEND = Path(__file__).resolve().parent.parent
DATA = BACKEND / "data"
load_dotenv(BACKEND / ".env")
USER_AGENT = "geulbeot-writing-assistant/0.3 (https://github.com/PSHUN03/Codyssey-M1-2; educational project)"

LTI_URL = "https://library.ltikorea.or.kr/api/open/bibliography"
NLK_SASEO_URL = "https://nl.go.kr/NL/search/openApi/saseoApi.do"

# 번역서 언어·서명 등에서 장르 추정
GENRE_WORDS = [(r"시집|poems?|poetry|gedichte|poèmes|poesía", "시"), (r"소설|novel|roman|novela", "소설"),
               (r"단편|stories|short|nouvelles|cuentos|erzählungen", "단편소설"), (r"수필|essays?", "수필"),
               (r"희곡|plays?|drama|théâtre", "희곡"), (r"동화|fairy|tales|märchen|contes", "동화")]


def key(name: str) -> str:
    k = os.environ.get(name, "").strip()
    if not k:
        sys.exit(f"{name} 가 없습니다. backend/.env 에 넣어 주세요.")
    return k


def get(url: str, params: dict) -> str:
    q = urllib.parse.urlencode(params)
    for attempt in range(5):
        try:
            req = urllib.request.Request(f"{url}?{q}", headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=60) as res:
                return res.read().decode("utf-8", "replace")
        except (urllib.error.URLError, TimeoutError) as e:
            print(f"  ! 실패({e}), {5 * (attempt + 1)}s 후 재시도", flush=True)
            time.sleep(5 * (attempt + 1))
    raise RuntimeError("요청 실패")


def records(xml_text: str) -> list[dict]:
    """XML 에서 '자식이 모두 텍스트인 요소'를 레코드로 본다 (필드 이름을 몰라도 동작)."""
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return []
    out = []
    for el in root.iter():
        kids = list(el)
        if len(kids) >= 3 and all(len(k) == 0 for k in kids):
            out.append({k.tag: (k.text or "").strip() for k in kids})
    return out


def pick(rec: dict, *names: str) -> str:
    low = {k.lower(): v for k, v in rec.items()}
    return next((low[n.lower()] for n in names if low.get(n.lower())), "")


def year_of(text: str) -> int | None:
    m = re.search(r"(1[89]\d\d|20[0-2]\d)", text or "")
    return int(m.group(1)) if m else None


def genre_of(*texts: str) -> str:
    t = " ".join(texts).lower()
    return next((g for pattern, g in GENRE_WORDS if re.search(pattern, t)), "기타")


def our_authors() -> list[str]:
    names = Counter()
    ws = json.loads((DATA / "wikisource_works.json").read_text(encoding="utf-8"))
    for w in ws["records"] + ws["library"]:
        names[w["author"]] += 1
    gongu = DATA / "gongu_works.json"
    if gongu.exists():
        for w in json.loads(gongu.read_text(encoding="utf-8"))["works"]:
            names[w.get("author") or ""] += 1
    return [n for n, _ in names.most_common() if re.fullmatch(r"[가-힣]{2,4}", n or "")]


def lti(probe: bool = False) -> None:
    k = key("LTI_API_KEY")
    authors = our_authors()
    if probe:
        print(get(LTI_URL, {"key": k, "search_field": "DB_AI_OR_NAME", "search_keyword": "김소월", "perpage": 3})[:3000])
        return
    rows, seen = [], set()
    for i, name in enumerate(authors, 1):
        page = 1
        while True:
            recs = records(get(LTI_URL, {"key": k, "search_field": "DB_AI_OR_NAME", "search_keyword": name,
                                         "perpage": 100, "page": page}))
            recs = [r for r in recs if pick(r, "DB_TRNAME", "trname", "title")]
            for r in recs:
                tr_title = pick(r, "DB_TRNAME", "trname", "title")
                kr_title = pick(r, "DB_KRNAME", "krname", "orgtitle")
                author = pick(r, "DB_AI_OR_NAME", "ainame", "author") or name
                if name not in author:
                    continue  # 이름이 일부만 겹친 다른 작가
                lang = pick(r, "DB_LANG", "language", "lang")
                sig = (tr_title, lang)
                if sig in seen:
                    continue
                seen.add(sig)
                rows.append({
                    "title": tr_title,
                    "author": name,
                    "genre": genre_of(kr_title, tr_title),
                    "year": year_of(pick(r, "DB_PUBYEAR", "pubyear", "pubdate", "year")),
                    "basis": "번역서 출간 연도",
                    "publisher": pick(r, "DB_PUBLISHER", "publisher") or None,
                    "language": lang or None,
                    "note": " · ".join(x for x in (f"원서 《{kr_title}》" if kr_title else "",
                                                   f"옮김 {pick(r, 'DB_TR_OR_NAME', 'trorname', 'translator')}"
                                                   if pick(r, 'DB_TR_OR_NAME', 'trorname', 'translator') else "") if x),
                    "url": pick(r, "DB_URL", "url", "link") or None,
                })
            if len(recs) < 100:
                break
            page += 1
            time.sleep(0.5)
        if i % 25 == 0:
            print(f"  - 작가 {i}/{len(authors)} · 번역서 {len(rows)}권", flush=True)
        time.sleep(0.5)
    write("lti_books.json", "한국문학번역원 번역출간DB (원작가 검색)", rows)


def nlk(probe: bool = False) -> None:
    k = key("NLK_API_KEY")
    base = {"key": k, "drCode": 11}  # 11 = 문학
    if probe:
        print(get(NLK_SASEO_URL, {**base, "startRowNumApi": 1, "endRowNumApi": 3})[:3000])
        return
    rows, start = [], 1
    while True:
        recs = records(get(NLK_SASEO_URL, {**base, "startRowNumApi": start, "endRowNumApi": start + 99}))
        recs = [r for r in recs if pick(r, "recomtitle", "title")]
        if not recs:
            break
        for r in recs:
            title = pick(r, "recomtitle", "title")
            rows.append({
                "title": title,
                "author": re.sub(r"\s*(지음|글|저|옮김.*)$", "", pick(r, "recomauthor", "author")) or None,
                "genre": genre_of(title, pick(r, "recomcontens", "contents")),
                "year": year_of(pick(r, "publishYear", "recomYear", "pubyear")),
                "basis": "발행 연도",
                "publisher": pick(r, "recompublisher", "publisher") or None,
                "note": "국립중앙도서관 사서추천도서 (문학)",
                "url": pick(r, "detailUrl", "url") or None,
            })
        print(f"  - {len(rows)}권", flush=True)
        start += 100
        time.sleep(0.5)
    write("nlk_books.json", "국립중앙도서관 사서추천도서 — 문학", rows)


def write(name: str, source: str, rows: list[dict]) -> None:
    (DATA / name).write_text(json.dumps({
        "source": source,
        "built_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "count": len(rows),
        "works": rows,
    }, ensure_ascii=False, indent=0), encoding="utf-8")
    print(f"{len(rows):,}건 → data/{name}")
    print("장르:", Counter(r["genre"] for r in rows).most_common())


if __name__ == "__main__":
    args = sys.argv[1:]
    probe = bool(args) and args[0] == "probe"
    target = args[1] if probe else (args[0] if args else "")
    {"lti": lti, "nlk": nlk}[target](probe)
