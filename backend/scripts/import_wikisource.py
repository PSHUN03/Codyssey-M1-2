"""한국어 위키문헌(ko.wikisource.org) MediaWiki API에서 퍼블릭 도메인 문학 작품을 수집해
시계열 데이터(date, value, memo + 부가 필드)로 변환한다.

수집 범위
  1) 장르 분류(시·시조·수필·소설·동화·희곡·한시·가사·고전시가·평론·편지 등)의 문서
  2) 연도별 작품 분류(세기 → 연대 → 'NNNN년 작품')의 문서 중 장르 분류가 있는 것
  3) 시집·수필집 목차 문서의 하위 문서(개별 작품)

날짜(date) 결정 순서 — 앞의 근거가 있으면 그것을 쓴다
  1) 본문 끝의 창작일 (예: 1941. 11. 20.)
  2) 머리말 설명란의 발표 연·월·일 (예: 《조선일보》 1936년 4월 2일, 〈조선〉 1932.4.) — 월까지 있으면 분류보다 우선
  3) 문서 자신의 'NNNN년 작품' 분류
  4) 저자 문서(저자:○○)의 작품 목록에 적힌 발표 연도 (예: * [[빈처]] (1921년))
  5) (시집 수록작) 수록 시집의 날짜 — 메모에 '수록 문집 … 기준'으로 밝힌다
     단, 시집이 지은이 사망 후에 나왔으면 '사후 간행 문집'으로 표시하고, 사망 후 10년이 넘어 나온
     후대 판본(재간행·선집)의 연도는 발표일로 볼 수 없어 쓰지 않는다.
  날짜를 알 수 없는 작품은 넣지 않는다.

같은 지은이의 같은 제목 작품이 여러 문서(초판 시집과 후대 합본 등)에 있으면 날짜 근거가 가장
정확하고 가장 이른 것 하나만 남긴다.

- value : 본문 글자 수(공백 제외, 현대어 표기가 병기된 경우 현대어만)
- memo  : 제목·지은이·날짜 근거·수록 문집

결과는 backend/data/wikisource_works.json 에 저장되며, seed_firestore.py 로 Firestore에 적재한다.
응답은 data/.wikisource_*.json 에 캐시되어(git 제외) 다시 실행할 때 요청 제한을 피한다.

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
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

API = "https://ko.wikisource.org/w/api.php"
USER_AGENT = "geulbeot-writing-assistant/0.2 (https://github.com/PSHUN03/Codyssey-M1-2; educational project)"
DATA_DIR = Path(__file__).resolve().parent.parent / "data"
OUT_PATH = DATA_DIR / "wikisource_works.json"
CACHE_PATH = DATA_DIR / ".wikisource_cache.json"        # 목록 조회 응답 (쿼리 단위)
PAGE_CACHE_PATH = DATA_DIR / ".wikisource_pages.json"   # 문서 본문·분류 (문서 단위)

# 장르 분류 → 장르. 한 작품이 여러 분류에 속하면 GENRE_PRIORITY 앞쪽이 우선한다.
CATEGORY_GENRE = {
    "일제 강점기의 시": "시", "대한민국의 시": "시", "대한제국의 시": "시", "한국의 시": "시", "시": "시",
    "서사시": "시", "소네트": "시",
    "시조": "시조",
    "한시": "한시",
    "가사": "가사",
    "향가": "고전시가", "고려속요": "고전시가", "악장": "고전시가", "잡가": "고전시가",
    "수필": "수필",
    "편지": "서간",
    "평론": "평론", "논설문": "평론", "시론": "평론",
    "단편소설": "단편소설", "중편소설": "중편소설", "장편소설": "장편소설",
    "소설": "소설", "역사소설": "소설", "추리소설": "소설", "번안소설": "소설", "연작소설": "소설",
    "공포소설": "소설", "사변소설": "소설",
    "동화": "동화", "우화": "동화",
    "희곡": "희곡",
}
COLLECTION_GENRE = {"시집": "시", "수필집": "수필"}
GENRE_PRIORITY = ["장편소설", "중편소설", "단편소설", "소설", "동화", "희곡", "평론", "서간", "수필",
                  "가사", "고전시가", "한시", "시조", "시"]
CENTURIES = ["15세기 작품", "16세기 작품", "17세기 작품", "18세기 작품", "19세기 작품", "20세기 작품"]

# 날짜 근거의 정확도 순위 (작을수록 정확) — 중복 작품 중 무엇을 남길지 정할 때 쓴다
PRECISION_RANK = {"창작일": 0, "발표일": 1, "창작 월": 2, "발표 월": 3, "발표 연도": 4, "저자 문서 발표 연도": 5,
                  "수록 문집 간행 월": 6, "수록 문집 간행 연도": 7}  # 그 밖(사후 간행 문집 등)은 8

MIN_YEAR, MAX_YEAR = 1400, 1990
# 시집의 부속 글(서문·발문 등)은 작품이 아니고 다른 사람이 쓴 경우도 많아 제외한다 ('서시'는 작품이라 제외하지 않음)
PARATEXT = {"서", "서문", "序", "序文", "자서", "自序", "발", "발문", "跋", "跋文", "후기", "後記", "편집후기", "머리말",
            "목차", "차례", "판권", "해설", "부록", "범례", "일러두기"}
# 번역 시집: 수록작의 지은이 칸은 역자다 ('번역' 분류가 없는 대표 번역 시집은 이름으로 지정)
TRANSLATED_COLLECTIONS = {"오뇌의 무도"}
POSTHUMOUS_LIMIT = 10  # 사망 후 이 햇수를 넘겨 나온 문집의 연도는 쓰지 않는다
MIN_CHARS = 20
MAX_EXCERPT = 300

_last_call = 0.0


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


_cache: dict[str, dict] = _load(CACHE_PATH)
_pages: dict[str, dict] = _load(PAGE_CACHE_PATH)


def save_caches() -> None:
    CACHE_PATH.write_text(json.dumps(_cache, ensure_ascii=False), encoding="utf-8")
    PAGE_CACHE_PATH.write_text(json.dumps(_pages, ensure_ascii=False), encoding="utf-8")


def api(params: dict, use_cache: bool = True) -> dict:
    """위키문헌 API 호출 (요청 간격 1.5초 유지 + 429/5xx 재시도)."""
    global _last_call
    query = urllib.parse.urlencode({**params, "format": "json", "formatversion": 2})
    if use_cache and query in _cache:
        return _cache[query]
    for attempt in range(8):
        wait = 1.5 - (time.time() - _last_call)
        if wait > 0:
            time.sleep(wait)
        _last_call = time.time()
        req = urllib.request.Request(f"{API}?{query}", headers={"User-Agent": USER_AGENT})
        try:
            with urllib.request.urlopen(req, timeout=30) as res:
                data = json.loads(res.read())
                if use_cache:
                    _cache[query] = data
                    if len(_cache) % 25 == 0:  # 중간에 멈춰도 진행분이 남도록
                        save_caches()
                return data
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


def category_members(category: str, kind: str = "page") -> list[str]:
    """kind='page' 이면 본문 문서(ns 0), 'subcat' 이면 하위 분류 이름."""
    out, cont = [], {}
    extra = {"cmnamespace": 0} if kind == "page" else {"cmtype": "subcat"}
    while True:
        r = api({"action": "query", "list": "categorymembers", "cmtitle": f"분류:{category}",
                 "cmlimit": 500, **extra, **cont})
        out += [m["title"].removeprefix("분류:") for m in r["query"]["categorymembers"]]
        if "continue" not in r:
            return out
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


def year_categories() -> list[str]:
    """세기 → 연대 → 'NNNN년 작품' 분류를 모두 찾는다."""
    found: set[str] = set()
    for century in CENTURIES:
        for sub in category_members(century, "subcat"):
            if re.fullmatch(r"\d{3,4}년 작품", sub):
                found.add(sub)
            elif re.fullmatch(r"\d{3,4}년대 작품", sub):
                found.update(s for s in category_members(sub, "subcat") if re.fullmatch(r"\d{3,4}년 작품", s))
    return sorted(found)


def fetch_pages(titles: list[str]) -> dict[str, dict]:
    """제목 목록 → {title: {pageid, content, categories}} (문서 단위 캐시, 20개씩 요청)."""
    todo = [t for t in dict.fromkeys(titles) if t not in _pages]
    for i in range(0, len(todo), 20):
        batch = todo[i:i + 20]
        cont: dict = {}
        while True:
            r = api({"action": "query", "titles": "|".join(batch), "prop": "revisions|categories",
                     "rvprop": "content", "rvslots": "main", "cllimit": "max", "redirects": 1, **cont},
                    use_cache=False)
            q = r.get("query", {})
            alias = {x["to"]: x["from"] for x in q.get("redirects", []) + q.get("normalized", [])}
            for p in q.get("pages", []):
                key = alias.get(p["title"], p["title"])
                if p.get("missing"):
                    _pages[key] = {"missing": True}
                    continue
                entry = _pages.setdefault(key, {"pageid": p["pageid"], "title": p["title"], "content": None,
                                                "categories": []})
                if p.get("revisions"):
                    entry["content"] = p["revisions"][0]["slots"]["main"]["content"]
                entry["categories"] += [c["title"].removeprefix("분류:") for c in p.get("categories", [])]
            if "continue" not in r:
                break
            cont = dict(r["continue"])
        for t in batch:
            _pages.setdefault(t, {"missing": True})
        if (i // 20) % 10 == 0:
            print(f"  - 본문 {min(i + 20, len(todo))}/{len(todo)}")
            save_caches()
    return {t: _pages[t] for t in titles if not _pages.get(t, {}).get("missing")}


# ---------------------------------------------------------------- 위키텍스트 파싱

def strip_links(text: str) -> str:
    text = re.sub(r"\[\[(?:[^\]|]*\|)?([^\]]*)\]\]", lambda m: m.group(1).lstrip("/"), text)
    return re.sub(r"\[https?://\S+\s+([^\]]*)\]", r"\1", text)


def header_field(wikitext: str, name: str) -> str:
    m = re.search(r"^\s*\|\s*" + name + r"\s*=(.*)$", wikitext, re.M)
    if not m:
        return ""
    value = re.sub(r"<[^>]+>|\{\{[^{}]*\}\}|'{2,}", "", strip_links(m.group(1)))
    return value.split("|")[0].strip()


def author_page(wikitext: str) -> str | None:
    m = re.search(r"^\s*\|\s*(?:지은이|저자)\s*=.*?\[\[((?:저자|글쓴이):[^|\]]+)", wikitext, re.M)
    return m.group(1).strip() if m else None


def clean_body(wikitext: str) -> str:
    text = wikitext
    for marker in ("== 라이선스 ==", "==라이선스==", "== 저작권 ==", "==저작권==", "== 각주 =="):
        text = text.split(marker)[0]
    # 원문/현대 표기가 병기된 경우 현대 표기만 사용
    modern = re.search(r"==\s*현대\s*(?:표기|어|어\s*표기)\s*==(.*?)(?:\n==[^=]|\Z)", text, re.S)
    if modern:
        text = modern.group(1)
    text = re.sub(r"<ref[^>]*/>|<ref[^>]*>.*?</ref>", "", text, flags=re.S)
    text = re.sub(r"<pages[^>]*/>", "", text)  # 스캔본에서 불러오는 원문(본문 없음)
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


def cat_years(categories: list[str]) -> list[int]:
    years = sorted(int(m.group(1)) for c in categories if (m := re.fullmatch(r"(\d{3,4})년 작품", c)))
    return [y for y in years if MIN_YEAR <= y <= MAX_YEAR]


def own_date(body: str, categories: list[str], desc: str) -> tuple[str, str] | None:
    """문서 자신의 근거(본문 끝 창작일 → 설명란 → 연도 분류)로 (YYYY-MM-DD, 근거) 반환."""
    years = cat_years(categories)

    tail = body[-80:]
    m = re.search(r"(1[4-9]\d\d)\s*[.년]\s*(\d{1,2})\s*[.월]\s*(?:(\d{1,2})\s*[.일]?)?", tail)
    if m and (not years or int(m.group(1)) in years):
        y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3) or 1)
        try:
            return datetime(y, mo, d).strftime("%Y-%m-%d"), "창작일" if m.group(3) else "창작 월"
        except ValueError:
            pass

    # 설명란에 월까지 적힌 출전 날짜(예: '1928년 7월 《조선지광》', '〈조선〉, 1932.4.')는 구체적인 인용이라
    # 연도 분류와 달라도 우선한다. 연도만 적힌 설명은 분류와 맞을 때만 쓴다.
    dm = (re.search(r"(1[4-9]\d\d)\s*년\s*(\d{1,2})\s*월\s*(?:(\d{1,2})\s*일)?", desc)
          or re.search(r"(1[4-9]\d\d)\s*\.\s*(\d{1,2})(?!\d)(?:\s*\.\s*(\d{1,2})(?!\d))?", desc))
    if dm and MIN_YEAR <= int(dm.group(1)) <= MAX_YEAR and 1 <= int(dm.group(2)) <= 12:
        y, mo, d = int(dm.group(1)), int(dm.group(2)), int(dm.group(3) or 0)
        if d:
            try:
                return datetime(y, mo, d).strftime("%Y-%m-%d"), "발표일"
            except ValueError:
                pass
        return f"{y:04d}-{mo:02d}-01", "발표 월"
    ym = re.search(r"(1[4-9]\d\d)\s*년", desc)
    if ym and (not years or int(ym.group(1)) in years) and MIN_YEAR <= int(ym.group(1)) <= MAX_YEAR:
        return f"{int(ym.group(1)):04d}-01-01", "발표 연도"

    if years:
        return f"{years[0]:04d}-01-01", "발표 연도"
    return None


# ---------------------------------------------------------------- 저자 문서의 작품 연도 목록

def norm_title(title: str) -> str:
    """비교용 제목: 괄호(한자·동명이인 표시)·공백·문장부호 제거."""
    t = re.sub(r"\(.*?\)|（.*?）", "", title or "")
    return re.sub(r"[\s·.,!?「」『』《》〈〉\"'“”‘’()_\-]", "", t)


def author_deaths(author_titles: list[str]) -> dict[str, int]:
    """저자 문서 머리말의 '사망 연도 = 1950년' → {저자 문서 제목: 1950}."""
    deaths = {}
    for title, page in fetch_pages(author_titles).items():
        m = re.search(r"^\s*\|\s*사망\s*연도\s*=\s*(\d{3,4})", page.get("content") or "", re.M)
        if m:
            deaths[title] = int(m.group(1))
    return deaths


def author_years(author_titles: list[str]) -> dict[str, int]:
    """저자 문서의 '* [[작품]] (1921년)' 같은 줄에서 {문서 제목: 연도}."""
    years: dict[str, int] = {}
    for title, page in fetch_pages(author_titles).items():
        for line in (page.get("content") or "").splitlines():
            if not line.lstrip().startswith(("*", "#")):
                continue
            link = re.search(r"\[\[([^|\]#]+)", line)
            year = re.search(r"\(([^()]*?)(1[4-9]\d\d)\s*년", line)
            if link and year and MIN_YEAR <= int(year.group(2)) <= MAX_YEAR:
                target = link.group(1).strip()
                if not target.startswith(("저자:", "글쓴이:", "분류:", "w:", ":")):
                    years.setdefault(target, int(year.group(2)))
    return years


# ---------------------------------------------------------------- 레코드 만들기

def pick_genre(categories: list[str], fallback: str | None) -> str | None:
    found = {CATEGORY_GENRE[c] for c in categories if c in CATEGORY_GENRE}
    for g in GENRE_PRIORITY:
        if g in found:
            return g
    return fallback


def to_record(title: str, page: dict, genre: str, date: tuple[str, str], parent_title: str | None,
              parent_author: str, translated: bool = False, parent_translator: str = "") -> dict | None:
    content = page.get("content") or ""
    body = clean_body(content)
    chars = len(re.sub(r"\s", "", body))
    if chars < MIN_CHARS:
        return None

    if parent_title:  # 시집 하위 문서: 제목 칸은 시집 이름, 작품 제목은 '부제' 칸 또는 경로 끝
        work_title = header_field(content, "부제") or title.split("/")[-1]
    else:
        work_title = header_field(content, "제목") or title
    work_title = re.sub(r"\s*\((?:[^)]*)\)$", "", work_title.replace("_", " ")).strip() or title
    if parent_title and norm_title(work_title) in PARATEXT:
        return None
    author = header_field(content, "지은이") or header_field(content, "저자") or parent_author
    translator = header_field(content, "역자") or parent_translator
    role = re.compile(r"\s*:\s*(?:작|역|저|글|지음|옮김)\s*$")  # '림 화: 역' 같은 표기 정리
    author, translator = role.sub("", author).strip(), role.sub("", translator).strip()
    if translator and not re.search(r"[가-힣]", translator):
        return None  # 위키 사용자가 요즘 옮긴 번역문: 원작은 실재하지만 이 한글 본문의 날짜가 아니다
    if translated:
        author = f"{author}(옮김)" if author else "역자 미상"
    desc = header_field(content, "설명")
    date_str, basis = date

    memo = f"《{work_title}》 {author or '작자 미상'}" + (f" · {translator} 옮김" if translator else "") + f" — {basis} 기준"
    if parent_title:
        collection = re.sub(r"\s*\(.*?\)$", "", parent_title)
        memo += f" · 《{collection}》 수록"
        if translated:
            memo += " (번역 시집)"
    if desc:
        memo += f" · {desc[:60]}"
    return {
        "date": date_str,
        "value": chars,
        "memo": memo[:200],
        "genre": genre,
        "title": work_title[:100],
        "author": author[:50],
        "source": "위키문헌",
        "excerpt": body[:MAX_EXCERPT],
        "url": "https://ko.wikisource.org/wiki/" + urllib.parse.quote(page.get("title", title).replace(" ", "_")),
        "pageid": page["pageid"],
        "basis": basis,
    }


def dedupe(records: list[dict]) -> tuple[list[dict], int]:
    """같은 지은이·같은 제목 → 날짜 근거가 가장 정확하고 이른 것 하나만."""
    groups: dict[tuple, list[dict]] = defaultdict(list)
    for r in records:
        groups[(r["author"], norm_title(r["title"]), r["genre"])].append(r)
    kept = []
    for group in groups.values():
        group.sort(key=lambda r: (PRECISION_RANK.get(r["basis"], 8), r["date"], -r["value"]))
        kept.append(group[0])
    return kept, len(records) - len(kept)


def main() -> None:
    # 1) 후보 문서 모으기
    title_genre: dict[str, str | None] = {}
    for cat, genre in CATEGORY_GENRE.items():
        titles = category_members(cat)
        if titles:
            print(f"[분류:{cat}] {len(titles)}편")
        for t in titles:
            title_genre.setdefault(t, genre)

    years = year_categories()
    year_only = 0
    for cat in years:
        for t in category_members(cat):
            if t not in title_genre:
                title_genre[t] = None  # 장르는 문서의 분류로 판정 (없으면 제외)
                year_only += 1
    print(f"[연도 분류] {len(years)}개 분류에서 장르 미확인 후보 {year_only}편 추가")

    collections: dict[str, str] = {}
    for cat, genre in COLLECTION_GENRE.items():
        for t in category_members(cat):
            collections.setdefault(t, genre)
    print(f"[시집·수필집] 목차 {len(collections)}개")

    # 2) 본문 가져오기
    print(f"작품 본문: {len(title_genre)}편")
    pages = fetch_pages(list(title_genre))
    col_pages = fetch_pages(list(collections))
    sub_map: dict[str, list[str]] = {c: [t for t in subpage_titles(c) if t not in pages] for c in col_pages}
    print(f"시집 하위 작품: {sum(len(v) for v in sub_map.values())}편")
    sub_pages = fetch_pages([t for subs in sub_map.values() for t in subs])

    # 3) 저자 문서의 작품 연도
    authors = {a for p in (*pages.values(), *col_pages.values(), *sub_pages.values())
               if (a := author_page(p.get("content") or ""))}
    print(f"저자 문서: {len(authors)}명")
    by_author = author_years(sorted(authors))
    deaths = author_deaths(sorted(authors))
    print(f"저자 문서에서 연도를 찾은 작품: {len(by_author)}편 · 사망 연도를 아는 저자: {len(deaths)}명")

    def resolve(title: str, page: dict) -> tuple[str, str] | None:
        content = page.get("content") or ""
        d = own_date(clean_body(content), page["categories"], header_field(content, "설명"))
        if d:
            return d
        y = by_author.get(title) or by_author.get(title.replace("_", " "))
        return (f"{y:04d}-01-01", "저자 문서 발표 연도") if y else None

    records: list[dict] = []
    skipped = defaultdict(int)
    for title, page in pages.items():
        content = page.get("content") or ""
        if not content or content.lstrip().lower().startswith("#redirect") or is_index_page(content):
            skipped["목차·넘겨주기"] += 1
            continue
        genre = pick_genre(page["categories"], title_genre.get(title))
        if not genre:
            skipped["장르 없음"] += 1
            continue
        date = resolve(title, page)
        if not date:
            skipped["날짜 없음"] += 1
            continue
        parent = title.rsplit("/", 1)[0] if "/" in title else None  # 분류에 직접 걸린 하위 문서
        rec = to_record(title, page, genre, date, parent, "")
        if rec:
            records.append(rec)
        else:
            skipped["본문 짧음"] += 1

    for col_title, col_page in col_pages.items():
        col_content = col_page.get("content") or ""
        col_author = header_field(col_content, "지은이") or header_field(col_content, "저자")
        col_date = resolve(col_title, col_page)
        for title in sub_map.get(col_title, []):
            page = sub_pages.get(title)
            if not page:
                continue
            content = page.get("content") or ""
            if not content or is_index_page(content):
                continue
            genre = pick_genre(page["categories"], collections[col_title])
            date = resolve(title, page)
            if not date and col_date:
                death = deaths.get(author_page(content) or author_page(col_content) or "")
                col_year = int(col_date[0][:4])
                if death and col_year - death > POSTHUMOUS_LIMIT:
                    skipped["후대 판본 연도뿐"] += 1
                    continue
                label = "사후 간행 문집" if death and col_year > death else "수록 문집"
                date = (col_date[0], f"{label} {col_date[1].replace('발표', '간행')}")
            if not date:
                skipped["날짜 없음"] += 1
                continue
            translated = (col_title in TRANSLATED_COLLECTIONS or "번역" in col_title
                          or "번역" in col_page["categories"])
            rec = to_record(title, page, genre, date, col_title, col_author, translated,
                            header_field(col_content, "역자"))
            if rec:
                records.append(rec)

    by_pageid: dict[int, dict] = {}
    for r in records:  # 넘겨주기로 같은 문서를 가리키면 날짜 근거가 더 정확하고 이른 쪽을 남긴다
        cur = by_pageid.get(r["pageid"])
        if cur is None or (PRECISION_RANK.get(r["basis"], 8), r["date"]) < (PRECISION_RANK.get(cur["basis"], 8), cur["date"]):
            by_pageid[r["pageid"]] = r
    records = list(by_pageid.values())
    records, dup = dedupe(records)
    save_caches()

    result = sorted(records, key=lambda r: (r["date"], r["title"]))
    OUT_PATH.write_text(json.dumps({
        "source": "한국어 위키문헌 (https://ko.wikisource.org) — 퍼블릭 도메인 저작물",
        "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "count": len(result),
        "records": result,
    }, ensure_ascii=False, indent=1), encoding="utf-8")

    by_genre: dict[str, int] = defaultdict(int)
    by_basis: dict[str, int] = defaultdict(int)
    for r in result:
        by_genre[r["genre"]] += 1
        by_basis[r["basis"]] += 1
    print(f"\n완료: {len(result)}편 → {OUT_PATH}  (중복 제거 {dup}편)")
    print("제외:", dict(skipped))
    print("장르별:", dict(by_genre))
    print("날짜 근거:", dict(by_basis))
    if result:
        print("기간:", result[0]["date"], "~", result[-1]["date"])


if __name__ == "__main__":
    main()
