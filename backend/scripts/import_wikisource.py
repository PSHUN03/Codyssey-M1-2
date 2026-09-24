"""한국어 위키문헌(ko.wikisource.org) MediaWiki API에서 퍼블릭 도메인 문학 작품을 수집해
시계열 데이터(date, value, memo + 부가 필드)로 변환한다.

- date  : 작품 발표/창작 날짜 (본문 끝의 날짜 > 설명란의 연·월 > 'NNNN년 작품' 분류 순으로 추출)
- value : 본문 글자 수(공백 제외)
- memo  : 제목·지은이·발표 정보 요약

결과는 backend/data/wikisource_works.json 에 저장되며, seed_firestore.py 로 Firestore에 적재한다.

실행: python scripts/import_wikisource.py
"""

from __future__ import annotations

import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

API = "https://ko.wikisource.org/w/api.php"
USER_AGENT = "writing-assistant-edu/0.1 (Codyssey student project)"
OUT_PATH = Path(__file__).resolve().parent.parent / "data" / "wikisource_works.json"
# API 응답 캐시 (재실행 시 요청 제한을 피하려고 사용, git 에는 올리지 않음)
CACHE_PATH = OUT_PATH.parent / ".wikisource_cache.json"
_cache: dict[str, dict] = json.loads(CACHE_PATH.read_text(encoding="utf-8")) if CACHE_PATH.exists() else {}

# 수집할 분류 → 장르. 한 작품이 여러 분류에 속하면 GENRE_PRIORITY 앞쪽이 우선한다.
CATEGORY_GENRE = {
    "일제 강점기의 시": "시",
    "대한민국의 시": "시",
    "시": "시",
    "시조": "시조",
    "수필": "수필",
    "단편소설": "단편소설",
    "중편소설": "중편소설",
    "장편소설": "장편소설",
    "동화": "동화",
    "희곡": "희곡",
}
# 목차 페이지 → 하위 페이지(개별 작품)를 따라가며 수집
COLLECTION_GENRE = {"시집": "시", "수필집": "수필"}
GENRE_PRIORITY = ["장편소설", "중편소설", "단편소설", "동화", "희곡", "수필", "시조", "시"]

MIN_YEAR, MAX_YEAR = 1400, 1990
MIN_CHARS = 20
MAX_EXCERPT = 300

_last_call = 0.0


def api(params: dict) -> dict:
    """위키문헌 API 호출 (요청 간격 유지 + 429 재시도)."""
    global _last_call
    query = urllib.parse.urlencode({**params, "format": "json", "formatversion": 2})
    if query in _cache:
        return _cache[query]
    for attempt in range(6):
        wait = 1.2 - (time.time() - _last_call)
        if wait > 0:
            time.sleep(wait)
        _last_call = time.time()
        req = urllib.request.Request(f"{API}?{query}", headers={"User-Agent": USER_AGENT})
        try:
            with urllib.request.urlopen(req, timeout=30) as res:
                _cache[query] = json.loads(res.read())
                return _cache[query]
        except urllib.error.HTTPError as e:
            if e.code == 429 or e.code >= 500:
                delay = int(e.headers.get("Retry-After") or 0) or 5 * (attempt + 1)
                print(f"  ! HTTP {e.code}, {delay}s 후 재시도", file=sys.stderr)
                time.sleep(delay)
                continue
            raise
        except urllib.error.URLError:
            time.sleep(5 * (attempt + 1))
    raise RuntimeError("위키문헌 API 요청이 계속 실패했습니다.")


def category_titles(category: str) -> list[str]:
    titles, cont = [], {}
    while True:
        r = api({"action": "query", "list": "categorymembers", "cmtitle": f"분류:{category}",
                 "cmnamespace": 0, "cmlimit": 500, **cont})
        titles += [m["title"] for m in r["query"]["categorymembers"]]
        if "continue" not in r:
            return titles
        cont = {"cmcontinue": r["continue"]["cmcontinue"]}


def subpage_titles(parent: str) -> list[str]:
    titles, cont = [], {}
    while True:
        r = api({"action": "query", "list": "allpages", "apprefix": f"{parent}/",
                 "apnamespace": 0, "aplimit": 500, **cont})
        titles += [p["title"] for p in r["query"]["allpages"]]
        if "continue" not in r:
            return titles
        cont = {"apcontinue": r["continue"]["apcontinue"]}


def fetch_pages(titles: list[str]) -> dict[str, dict]:
    """제목 목록 → {title: {pageid, content, categories}} (20개씩 묶어서 요청)."""
    pages: dict[str, dict] = {}
    for i in range(0, len(titles), 20):
        batch = titles[i:i + 20]
        cont: dict = {}
        while True:
            r = api({"action": "query", "titles": "|".join(batch), "prop": "revisions|categories",
                     "rvprop": "content", "rvslots": "main", "cllimit": "max", "redirects": 1, **cont})
            for p in r.get("query", {}).get("pages", []):
                if p.get("missing"):
                    continue
                entry = pages.setdefault(p["title"], {"pageid": p["pageid"], "content": None, "categories": []})
                if p.get("revisions"):
                    entry["content"] = p["revisions"][0]["slots"]["main"]["content"]
                entry["categories"] += [c["title"].removeprefix("분류:") for c in p.get("categories", [])]
            if "continue" not in r:
                break
            cont = {k: v for k, v in r["continue"].items()}
        print(f"  - 본문 {min(i + 20, len(titles))}/{len(titles)}")
    return pages


# ---------------------------------------------------------------- 위키텍스트 파싱

def header_field(wikitext: str, name: str) -> str:
    m = re.search(r"^\s*\|\s*" + name + r"\s*=(.*)$", wikitext, re.M)
    if not m:
        return ""
    value = re.sub(r"<[^>]+>|\{\{[^{}]*\}\}|'{2,}", "", strip_links(m.group(1)))
    return value.split("|")[0].strip()


def strip_links(text: str) -> str:
    text = re.sub(r"\[\[(?:[^\]|]*\|)?([^\]]*)\]\]", lambda m: m.group(1).lstrip("/"), text)
    return re.sub(r"\[https?://\S+\s+([^\]]*)\]", r"\1", text)


def clean_body(wikitext: str) -> str:
    text = wikitext
    for marker in ("== 라이선스 ==", "==라이선스==", "== 저작권 ==", "==저작권==", "== 각주 =="):
        text = text.split(marker)[0]
    # 원문/현대 표기가 병기된 경우 현대 표기만 사용
    modern = re.search(r"==\s*현대\s*표기\s*==(.*?)(?:\n==[^=]|\Z)", text, re.S)
    if modern:
        text = modern.group(1)
    text = re.sub(r"<ref[^>]*/>|<ref[^>]*>.*?</ref>", "", text, flags=re.S)
    prev = None
    while prev != text:  # 중첩 틀 제거
        prev = text
        text = re.sub(r"\{\{[^{}]*\}\}", "", text)
    text = re.sub(r"\{\|.*?\|\}", "", text, flags=re.S)  # 표
    text = re.sub(r"\[\[(?:분류|Category|파일|File|그림|Image):[^\]]*\]\]", "", text)
    text = strip_links(text)
    text = re.sub(r"<br\s*/?>", "\n", text)
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"__[A-Z]+__", "", text)
    text = re.sub(r"^=+[^=\n]*=+\s*$", "", text, flags=re.M)
    text = re.sub(r"'{2,}", "", text)
    text = re.sub(r"^[:;*#]+\s*", "", text, flags=re.M)
    text = re.sub(r"[ \t　]+", " ", text)
    text = re.sub(r"\n\s*\n+", "\n\n", text)
    return text.strip()


def is_index_page(wikitext: str) -> bool:
    body = re.sub(r"\{\{.*?\}\}", "", wikitext, flags=re.S)
    lines = [l for l in body.splitlines() if l.strip() and not l.startswith("[[분류")]
    link_lines = [l for l in lines if re.match(r"^\s*[*#:]\s*\[\[", l)]
    return len(lines) > 0 and len(link_lines) / len(lines) > 0.5


def extract_date(content: str, body: str, categories: list[str], desc: str) -> tuple[str, str] | None:
    """(YYYY-MM-DD, 정밀도 설명) 반환. 알 수 없으면 None."""
    cat_years = sorted(int(m.group(1)) for c in categories if (m := re.fullmatch(r"(\d{3,4})년 작품", c)))
    cat_years = [y for y in cat_years if MIN_YEAR <= y <= MAX_YEAR]

    # 1) 본문 끝의 창작일 (예: 1941. 11. 20. / 1938.10)
    tail = body[-80:]
    m = re.search(r"(1[4-9]\d\d)\s*[.년]\s*(\d{1,2})\s*[.월]\s*(?:(\d{1,2})\s*[.일]?)?", tail)
    if m and (not cat_years or int(m.group(1)) in cat_years):
        y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3) or 1)
        if 1 <= mo <= 12 and 1 <= d <= 31:
            try:
                return datetime(y, mo, d).strftime("%Y-%m-%d"), "창작일" if m.group(3) else "창작 월"
            except ValueError:
                pass

    # 2) 설명란의 발표 연·월
    dm = re.search(r"(1[4-9]\d\d)\s*년\s*(?:(\d{1,2})\s*월)?\s*(?:(\d{1,2})\s*일)?", desc)
    if dm and (not cat_years or int(dm.group(1)) in cat_years):
        y, mo, d = int(dm.group(1)), int(dm.group(2) or 0), int(dm.group(3) or 0)
        if MIN_YEAR <= y <= MAX_YEAR:
            if 1 <= mo <= 12:
                if d:
                    try:
                        return datetime(y, mo, d).strftime("%Y-%m-%d"), "발표일"
                    except ValueError:
                        pass
                return f"{y:04d}-{mo:02d}-01", "발표 월"
            return f"{y:04d}-01-01", "발표 연도"

    # 3) 'NNNN년 작품' 분류
    if cat_years:
        return f"{cat_years[0]:04d}-01-01", "발표 연도"
    return None


def pick_genre(categories: list[str], fallback: str) -> str:
    found = {CATEGORY_GENRE[c] for c in categories if c in CATEGORY_GENRE}
    for g in GENRE_PRIORITY:
        if g in found:
            return g
    return fallback


def to_record(title: str, page: dict, genre: str, parent: dict | None = None) -> dict | None:
    content = page.get("content") or ""
    if not content or content.lstrip().lower().startswith("#redirect") or is_index_page(content):
        return None
    body = clean_body(content)
    chars = len(re.sub(r"\s", "", body))
    if chars < MIN_CHARS:
        return None

    work_title = header_field(content, "제목") or title.split("/")[-1]
    work_title = re.sub(r"\s*\([^)]*\)$", "", work_title).strip() or title
    author = header_field(content, "지은이") or header_field(content, "저자") or (parent or {}).get("author", "")
    desc = header_field(content, "설명")
    date = extract_date(content, body, page["categories"], desc)
    if date:
        date_str, precision = date
    elif parent and (inherited := extract_date("", "", parent["categories"], parent["desc"])):
        # 개별 작품 날짜가 없으면 수록된 시집·수필집의 간행 날짜를 쓰고, 그 사실을 메모에 밝힌다.
        date_str, precision = inherited[0], f"수록 문집 {inherited[1].replace('발표', '간행')}"
    else:
        return None

    info = f"{precision} 기준"
    if desc:
        info += f" · {desc[:60]}"
    memo = f"《{work_title}》 {author or '작자 미상'} — {info}"
    return {
        "date": date_str,
        "value": chars,
        "memo": memo[:200],
        "genre": genre,
        "title": work_title[:100],
        "author": author[:50],
        "source": "위키문헌",
        "excerpt": body[:MAX_EXCERPT],
        "url": "https://ko.wikisource.org/wiki/" + urllib.parse.quote(title.replace(" ", "_")),
        "pageid": page["pageid"],
    }


def main() -> None:
    title_genre: dict[str, str] = {}
    for cat, genre in CATEGORY_GENRE.items():
        titles = category_titles(cat)
        print(f"[분류:{cat}] {len(titles)}편")
        for t in titles:
            title_genre.setdefault(t, genre)

    collections: dict[str, str] = {}
    for cat, genre in COLLECTION_GENRE.items():
        titles = category_titles(cat)
        print(f"[분류:{cat}] 목차 {len(titles)}개")
        for t in titles:
            collections.setdefault(t, genre)

    print(f"작품 본문 수집: {len(title_genre)}편")
    pages = fetch_pages(list(title_genre))

    records: dict[int, dict] = {}
    for title, page in pages.items():
        rec = to_record(title, page, pick_genre(page["categories"], title_genre.get(title, "시")))
        if rec:
            records[rec["pageid"]] = rec

    print(f"시집·수필집 목차 수집: {len(collections)}개")
    col_pages = fetch_pages(list(collections))
    for col_title, col_page in col_pages.items():
        content = col_page.get("content") or ""
        parent = {
            "author": header_field(content, "지은이") or header_field(content, "저자"),
            "desc": header_field(content, "설명"),
            "categories": col_page["categories"],
        }
        subs = [t for t in subpage_titles(col_title) if t not in pages]
        if not subs:
            continue
        print(f"  《{col_title}》 하위 작품 {len(subs)}편")
        for title, page in fetch_pages(subs).items():
            genre = pick_genre(page["categories"], collections.get(col_title, "시"))
            rec = to_record(title, page, genre, parent)
            if rec:
                records.setdefault(rec["pageid"], rec)

    result = sorted(records.values(), key=lambda r: (r["date"], r["title"]))
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps({
        "source": "한국어 위키문헌 (https://ko.wikisource.org) — 퍼블릭 도메인 저작물",
        "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "count": len(result),
        "records": result,
    }, ensure_ascii=False, indent=1), encoding="utf-8")

    by_genre: dict[str, int] = {}
    for r in result:
        by_genre[r["genre"]] = by_genre.get(r["genre"], 0) + 1
    print(f"\n완료: {len(result)}편 → {OUT_PATH}")
    print("장르별:", by_genre)
    if result:
        print("기간:", result[0]["date"], "~", result[-1]["date"])


if __name__ == "__main__":
    main()
