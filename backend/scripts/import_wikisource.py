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
  날짜를 알 수 없는 작품은 시계열(records)에 넣지 않고 '참고 작품 서재'(library)에 따로 담는다.
  (AI 작품 검색에는 쓰이지만 요약·추세 통계에는 들어가지 않는다)

본문이 스캔본 페이지에서 불러오는 형식(<pages index=…>)이면 위키문헌이 렌더링한 본문을 받아 글자를 센다.

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
from html import unescape
from html.parser import HTMLParser
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
    # v4: 문학 분류 트리 전체
    "고전소설": "소설", "신소설": "소설", "한국의 소설": "소설", "판소리 소설": "소설", "춘향전": "소설",
    "판타지": "소설", "공포": "소설", "단편소설집": "단편소설",
    "판소리": "판소리", "판소리 사설": "판소리",
    "한국의 노래": "노래", "대한민국의 노래": "노래", "조선민주주의인민공화국의 노래": "노래",
    "한국의 동요": "노래", "한국의 민요": "노래",
    "문학 평론": "평론",
}
COLLECTION_GENRE = {"시집": "시", "수필집": "수필", "단편소설집": "단편소설"}
# 장르 분류가 없는 대표 문집: 이름으로 장르를 정한다
NAMED_COLLECTION_GENRE = {"가곡원류": "시조", "청구영언": "시조", "해동가요": "시조", "열하일기": "수필",
                          "조선동요백곡집": "노래"}
# 문집 이름의 끝말 → 장르 (소제목·분류보다 확실하다)
COLLECTION_NAME_GENRE = [(r"산문집|수필집", "수필"), (r"동화집", "동화"), (r"소설집|창작집", "단편소설"),
                         (r"희곡집", "희곡"), (r"시조집", "시조"), (r"시집|시선", "시"), (r"동요집|가요집|백곡집", "노래")]
# 저자 문서에 함께 걸린 비문학 문헌(의서·정치 문헌·학습서·역사 연구)
NON_LITERARY_TITLES = {"동의보감", "언해태산집요", "언해두창집요", "천의소감언해", "석봉 천자문", "조선사연구초",
                      "소학생"}  # 소학생: 잡지 호(號) 단위 문서라 한 작품이 아니다
# 목차 하위 문서가 대부분 이런 이름이면 한 작품의 장(章)이다 → 합산 (예: 피노키오의 모험/제1장)
CHAPTER_TITLE = re.compile(r"^(제\s*)?[\d一二三四五六七八九十百]+\s*[장회편부화절막권]?(\.|\s.*)?$|^[상중하]\s*(권|편)?$|"
                           r"^(서장|종장|프롤로그|에필로그|序章|終章|머리말|끝)$")
GENRE_PRIORITY = ["장편소설", "중편소설", "단편소설", "소설", "동화", "희곡", "판소리", "평론", "서간", "수필",
                  "노래", "가사", "고전시가", "한시", "시조", "시"]

# 문학 분류 트리: 이 분류들에서 하위 분류를 재귀적으로 내려가며 본문 문서를 모은다
LITERATURE_ROOTS = ["문학", "장르별 문학", "한국의 문학", "시", "소설", "수필", "희곡", "동화", "전승문학", "아동문학"]
# 문학이 아닌 분류, 작가 인물 분류(작품은 저자 문서로 따로 찾는다)는 내려가지 않는다
NON_LITERARY = {"요리책", "논문", "비소설", "안내서", "죽음", "유서", "민속", "문학상 수상자", "노벨 문학상 수상자",
                "맨부커상 수상자", "퓰리처상 수상자"}
# 장편·연재물: 목차 문서의 장별 하위 문서를 합쳐 한 작품으로 센다
SERIAL_GENRES = {"장편소설", "중편소설", "소설", "희곡", "판소리"}
# 작가 인물 분류 (저자 문서 네임스페이스) — 여기 속한 저자 문서의 작품 목록에서 새 작품을 찾는다
AUTHOR_ROOTS = ["시인", "소설가", "수필가", "평론가", "한국의 시인", "한국의 소설가"]
CENTURIES = ["15세기 작품", "16세기 작품", "17세기 작품", "18세기 작품", "19세기 작품", "20세기 작품"]

# 날짜 근거의 정확도 순위 (작을수록 정확) — 중복 작품 중 무엇을 남길지 정할 때 쓴다
PRECISION_RANK = {"창작일": 0, "발표일": 1, "창작 월": 2, "발표 월": 3, "발표 연도": 4, "저자 문서 발표 연도": 5,
                  "수록 문집 간행 월": 6, "수록 문집 간행 연도": 7}  # 그 밖(사후 간행 문집 등)은 8

MIN_YEAR, MAX_YEAR = 1400, 1990
# 시집의 부속 글(서문·발문 등)은 작품이 아니고 다른 사람이 쓴 경우도 많아 제외한다 ('서시'는 작품이라 제외하지 않음)
PARATEXT = {"서", "서문", "序", "序文", "서언", "緖言", "序言", "서론", "자서", "自序", "발", "발문", "跋", "跋文", "후기", "後記", "편집후기", "머리말",
            "목차", "차례", "판권", "해설", "부록", "범례", "일러두기"}
# 번역 시집: 수록작의 지은이 칸은 역자다 ('번역' 분류가 없는 대표 번역 시집은 이름으로 지정)
TRANSLATED_COLLECTIONS = {"오뇌의 무도"}
# 한국 저작권법: 1962년 이전에 사망한 저작자의 저작물만 보호 기간이 끝났다 (1963년 이후 사망 → 사후 70년 보호)
COPYRIGHT_CUTOFF = 1963
# 저자 문서가 없는 연작소설 공동 작가 등의 사망 연도
KNOWN_DEATHS = {"박화성": 1988, "최정희": 1990, "이은상": 1982, "주요한": 1979, "김기진": 1985, "염상섭": 1963,
                "박세영": 1989, "김광균": 1993,
                "이원수": 1981, "정인섭": 1983,  # 번역자 (번역문에는 번역자의 저작권이 따로 있다)
                "윤일주": 1985,  # 윤동주 유고 시집의 후기 필자
                # 번역 원작자: 원작의 보호 기간이 남아 있으면 오래된 번역문도 공개할 수 없다
                "정서림": 1974, "서순": 1967, "언터마이어": 1977, "마거릿 위더머": 1978, "휠록": 1978,
                "존 메이스필드": 1967}
# 위키문헌 사용자가 최근에 옮긴 번역문 (퍼블릭 도메인이 아니라 CC BY-SA) — 역자 칸이 사용자 이름
WIKI_USER_TRANSLATORS = {"연필"}
POSTHUMOUS_LIMIT = 10  # 사망 후 이 햇수를 넘겨 나온 문집의 연도는 쓰지 않는다
MIN_CHARS = 20
TEXTS: dict[int, str] = {}  # 문서 번호 → 전체 본문 (sources/ 폴더용, data/.wikisource_texts.json)
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
                if "error" in data:  # 잘못된 조건 등 API 오류는 캐시하지 않고 호출한 쪽에 알린다
                    print(f"  ! API 오류: {data['error'].get('code')} {data['error'].get('info', '')[:80]}", file=sys.stderr)
                    return {}
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
        out += [m["title"].removeprefix("분류:") for m in r.get("query", {}).get("categorymembers", [])]
        if "continue" not in r:
            return out
        cont = {"cmcontinue": r["continue"]["cmcontinue"]}


def literature_categories() -> dict[str, str | None]:
    """문학 분류 트리를 넓이 우선으로 훑어 {분류: 물려받은 장르} 를 만든다."""
    genre_of: dict[str, str | None] = {}
    frontier = [(c, CATEGORY_GENRE.get(c)) for c in LITERATURE_ROOTS]
    while frontier:
        cat, inherited = frontier.pop(0)
        if cat in genre_of or cat in NON_LITERARY:
            continue
        genre = CATEGORY_GENRE.get(cat, inherited)
        genre_of[cat] = genre
        frontier += [(sub, genre) for sub in category_members(cat, "subcat")]
    return genre_of


def author_members(category: str, depth: int = 0) -> list[str]:
    """작가 분류(하위 분류 포함)에 속한 저자 문서(네임스페이스 100) 제목."""
    out, cont = [], {}
    while True:
        r = api({"action": "query", "list": "categorymembers", "cmtitle": f"분류:{category}",
                 "cmnamespace": 100, "cmlimit": 500, **cont})
        out += [m["title"] for m in r.get("query", {}).get("categorymembers", [])]
        if "continue" not in r:
            break
        cont = {"cmcontinue": r["continue"]["cmcontinue"]}
    if depth < 3:
        for sub in category_members(category, "subcat"):
            out += author_members(sub, depth + 1)
    return out


# 저자 문서 소제목(== 소설 ==, === 동시/동요 === …) → 장르. 앞쪽 규칙이 우선한다
HEADING_GENRE = [
    (r"장편", "장편소설"), (r"중편", "중편소설"), (r"단편", "단편소설"),
    (r"동극|희곡|각본|시나리오", "희곡"), (r"동화|우화", "동화"), (r"소설|야담|번안", "소설"),
    (r"시조", "시조"), (r"한시", "한시"), (r"가사", "가사"), (r"동시|동요|시집|^시$|(?<![가-힣])시(?![가-힣])", "시"),
    (r"수필|잡문|기행|산문|수상", "수필"), (r"평론|비평|논설|시론|문학론", "평론"), (r"편지|서간", "서간"),
    (r"노래|가곡|창가", "노래"),
]


def heading_genre(heading: str) -> str | None:
    found = [genre for pattern, genre in HEADING_GENRE if re.search(pattern, heading)]
    # '평론, 수필, 희곡'처럼 여러 장르를 묶은 소제목은 장르를 정하지 않는다 (문서 분류·기타로)
    return found[0] if len(set(found)) == 1 else None


def linked_works(content: str) -> list[tuple[str, str | None]]:
    """저자 문서의 작품 목록 줄('* [[작품]] …')에 걸린 본문 문서 제목과, 그 줄이 속한 소제목의 장르."""
    titles, stack = [], []  # stack: [(수준, 장르)] — 가장 가까운 소제목부터 장르를 찾는다
    for line in content.splitlines():
        h = re.match(r"^(=+)\s*(.*?)\s*=+\s*$", line)
        if h:
            level = len(h.group(1))
            stack = [(lv, g) for lv, g in stack if lv < level] + [(level, heading_genre(h.group(2)))]
            continue
        if not line.lstrip().startswith(("*", "#")):
            continue
        genre = next((g for _, g in reversed(stack) if g), None)
        for m in re.finditer(r"\[\[([^|\]#]+)", line):
            t = m.group(1).strip()
            if t and not re.match(r"^(저자|글쓴이|분류|파일|File|w|wikt|:|위키문헌|포털|색인|페이지)[:：]", t, re.I):
                titles.append((t, genre))
    return titles


def subpage_titles(parent: str) -> list[str]:
    titles, cont = [], {}
    while True:
        r = api({"action": "query", "list": "allpages", "apprefix": f"{parent}/",
                 "apnamespace": 0, "aplimit": 500, **cont})
        titles += [p["title"] for p in r.get("query", {}).get("allpages", [])]
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


# 머리말 틀마다 필드 이름이 달라(한글 {{머리말}}·영문 {{header}}) 같은 뜻의 이름을 함께 찾는다
FIELD_ALIASES = {"지은이": ("지은이", "글쓴이", "author"), "제목": ("제목", "title"), "설명": ("설명", "notes"),
                 "역자": ("역자", "옮긴이", "translator"), "부제": ("부제", "section")}


def header_field(wikitext: str, name: str) -> str:
    # 각주(<ref>) 안의 인용 틀에도 '|제목=' 같은 필드가 있어 먼저 지운다 (예: 백범일지 설명란의 신문 기사 인용)
    wikitext = re.sub(r"<ref[^>/]*>.*?</ref>|<ref[^>]*/>", "", wikitext, flags=re.S)
    first = strip_links(wikitext.split("\n", 1)[0]) if wikitext.startswith("{{") else ""
    for alias in FIELD_ALIASES.get(name, (name,)):
        m = re.search(r"^\s*\|\s*" + alias + r"\s*=(.*)$", wikitext, re.M)
        if m and m.group(1).strip():
            break
        # 머리말 틀을 한 줄로 쓴 문서: {{머리말|제목=…|저자=…|설명=…
        m = re.search(r"\|\s*" + alias + r"\s*=([^|}]*)", first)
        if m and m.group(1).strip():
            break
    else:
        return ""
    value = re.sub(r"<[^>]+>|\{\{[^{}]*\}\}|'{2,}", "", strip_links(m.group(1)))
    return value.split("|")[0].strip()


def author_page(wikitext: str) -> str | None:
    m = re.search(r"^\s*\|\s*(?:지은이|저자|글쓴이|author)\s*=.*?\[\[((?:저자|글쓴이):[^|\]]+)", wikitext, re.M)
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


class _BodyText(HTMLParser):
    """렌더링된 HTML 에서 본문 글자만 모은다 (머리말 상자·쪽번호·각주·스타일은 통째로 건너뜀)."""

    SKIP_CLASSES = ("ws-noexport", "noprint", "ws-header", "wst-header", "mw-editsection", "reference",
                    "mw-references-wrap", "pagenum", "ws-pagenum", "mw-cite-backlink", "licenseContainer",
                    "messagebox", "ambox", "metadata")  # 안내 상자(옛한글·이체자 안내 등)
    BLOCK = {"p", "div", "li", "tr", "h1", "h2", "h3", "h4", "h5", "h6", "dd", "dt"}
    VOID = {"br", "img", "hr", "wbr", "meta", "link", "input"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.out: list[str] = []
        self.skip_depth = 0
        self.stack: list[bool] = []

    def handle_starttag(self, tag, attrs):
        if tag in self.VOID:
            if not self.skip_depth and tag == "br":
                self.out.append("\n")
            return
        classes = (dict(attrs).get("class") or "").split()
        skip = tag in ("style", "script") or any(c in classes for c in self.SKIP_CLASSES)
        self.stack.append(skip)
        if skip:
            self.skip_depth += 1
        elif not self.skip_depth and tag in self.BLOCK:
            self.out.append("\n")

    def handle_endtag(self, tag):
        if tag in self.VOID or not self.stack:
            return
        if self.stack.pop():
            self.skip_depth -= 1
        elif not self.skip_depth and tag in self.BLOCK:
            self.out.append("\n")

    def handle_data(self, data):
        if not self.skip_depth:
            self.out.append(data)


_rendered_log: list[str] = []


def rendered_text(title: str, page: dict) -> str:
    """스캔본(<pages index=…>)에서 본문을 불러오는 문서: 위키문헌이 렌더링한 본문을 텍스트로."""
    if "rendered" not in page:
        r = api({"action": "parse", "page": page.get("title", title), "prop": "text",
                 "disableeditsection": 1, "disabletoc": 1}, use_cache=False)
        page["rendered"] = (r.get("parse") or {}).get("text", "")
        _rendered_log.append(title)
        if len(_rendered_log) % 20 == 0:
            print(f"  - 스캔본 본문 {len(_rendered_log)}건")
            save_caches()
    # 라이선스·저작권·각주 절부터는 본문이 아니다
    html = re.split(r'<h2 id="(?:라이선스|저작권|각주)"', page["rendered"])[0]
    parser = _BodyText()
    parser.feed(html)
    text = unescape("".join(parser.out)).replace("\u200b", "")
    text = re.sub(r"[ \t\u3000]+", " ", text)
    return re.sub(r"\n\s*\n+", "\n\n", text).strip()


def work_body(title: str, page: dict) -> str:
    """작품 본문. 위키 문법 본문이 비어 있고 스캔본을 불러오는 문서면 렌더링된 본문을 쓴다."""
    content = page.get("content") or ""
    body = clean_body(content)
    if len(re.sub(r"\s", "", body)) < MIN_CHARS and "<pages" in content:
        body = rendered_text(title, page)
    return body


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
    # 단, '1971년 2월 1일 2판'·'재판'처럼 대본으로 쓴 후대 판본의 날짜는 발표일이 아니므로 건너뛴다 (예: 담원시조)
    def not_edition(m: re.Match) -> bool:
        after = desc[m.end():m.end() + 6]
        return "판" not in after or "초판" in after

    dm = (next(filter(not_edition, re.finditer(r"(1[4-9]\d\d)\s*년\s*(\d{1,2})\s*월\s*(?:(\d{1,2})\s*일)?", desc)), None)
          or next(filter(not_edition, re.finditer(r"(1[4-9]\d\d)\s*\.\s*(\d{1,2})(?!\d)(?:\s*\.\s*(\d{1,2})(?!\d))?",
                                                  desc)), None))
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

# 장르 분류가 없는 문서: 머리말 설명란의 문구로 장르를 정한다 (예: '작자 미상의 고전소설', '연경기행 가사', '편지글')
DESC_GENRE = [
    (r"희곡|각본", "희곡"), (r"가사(?:이다|로|체|\s*작품)|기행\s*가사|강호가사|불교가사|규방가사", "가사"),
    (r"소설|딱지본", "소설"), (r"시조", "시조"), (r"전래동화|창작동화|동화(?:이다|집|로|를|작품)", "동화"),
    (r"편지글|서간", "서간"), (r"창가|동요", "노래"), (r"수필|기행문|산문", "수필"), (r"평론|비평", "평론"),
    (r"(?<![가-힣])시(?:이다|로|를|집)|서정시|신체시", "시"),
]
# 비문학: 설명이나 제목에 이런 말이 있으면 장르를 붙이지 않는다 (선언서·성명·역사서·연구서 등)
NON_LITERARY_TEXT = re.compile(r"선언|성명|聲明|헌법|퇴임|遺憾|유감|상고사|사론|신론|연구|사온고|탈퇴|취지서|역사를|서술하였다|"
                               r"협정|조약|법령|고시|통계|교과서|문법|철자법")


def desc_genre(desc: str) -> str | None:
    if not desc or NON_LITERARY_TEXT.search(desc):
        return None
    return next((g for pattern, g in DESC_GENRE if re.search(pattern, desc)), None)


def pick_genre(categories: list[str], fallback: str | None) -> str | None:
    found = {CATEGORY_GENRE[c] for c in categories if c in CATEGORY_GENRE}
    for g in GENRE_PRIORITY:
        if g in found:
            return g
    return fallback


def to_record(title: str, page: dict, genre: str, date: tuple[str, str] | None, parent_title: str | None,
              parent_author: str, translated: bool = False, parent_translator: str = "",
              note: str = "") -> dict | None:
    """date 가 None 이면 '발표 시기 미상' 작품(참고 작품 서재용)으로 만든다."""
    if title.split("/")[0] in NON_LITERARY_TITLES:
        return None
    content = page.get("content") or ""
    body = page.get("_body") if page.get("_body") is not None else work_body(title, page)
    chars = len(re.sub(r"\s", "", body))
    if chars < MIN_CHARS:
        return None
    TEXTS[page["pageid"]] = body
    latin = len(re.findall(r"[A-Za-z]", body))
    if latin > chars * 0.5:
        return None  # 한국어 본문이 아닌 외국어 원문·목차(예: 모비딕 영문 장 목록)

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
    # '김소월(김정식)'처럼 괄호 속 본명·한자 병기는 떼어 같은 작가가 통계에서 둘로 갈리지 않게 한다
    author = re.sub(r"\s*[(（][^)）]*[)）]\s*$", "", author).strip() or author
    if translator and not re.search(r"[가-힣]", translator):
        return None  # 위키 사용자가 요즘 옮긴 번역문: 원작은 실재하지만 이 한글 본문의 날짜가 아니다
    if translated:
        author = f"{author}(옮김)" if author else "역자 미상"
    desc = header_field(content, "설명")
    date_str, basis = date if date else (None, "발표 시기 미상")

    memo = f"《{work_title}》 {author or '작자 미상'}" + (f" · {translator} 옮김" if translator else "") + f" — {basis} 기준"
    if parent_title:
        collection = re.sub(r"\s*\(.*?\)$", "", parent_title)
        memo += f" · 《{collection}》 수록"
        if translated:
            memo += " (번역 시집)"
    if note:
        memo += f" · {note}"
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
    # 1) 후보 문서 모으기 ------------------------------------------------------------
    title_genre: dict[str, str | None] = {}
    lit_cats = literature_categories()
    for cat, genre in lit_cats.items():
        for t in category_members(cat):
            if title_genre.get(t) is None:
                title_genre[t] = genre
    print(f"[문학 분류 트리] {len(lit_cats)}개 분류 · 후보 {len(title_genre)}편")
    literary = set(title_genre)          # 문학 분류에서 찾은 문서 (장르를 몰라도 '기타'로 넣는다)

    years = year_categories()
    for cat in years:
        for t in category_members(cat):
            title_genre.setdefault(t, None)  # 연도 분류만 있는 문서는 문서 자신의 장르 분류가 있어야 넣는다
    print(f"[연도 분류] {len(years)}개 · 누적 후보 {len(title_genre)}편")

    collections: dict[str, str] = {}
    for cat, genre in COLLECTION_GENRE.items():
        for t in category_members(cat):
            collections.setdefault(t, genre)

    # 2) 저자 문서로 새 작품 찾기 -----------------------------------------------------
    pages = fetch_pages(list(title_genre))
    authors = {a for p in pages.values() if (a := author_page(p.get("content") or ""))}
    lit_authors: set[str] = set()   # 시인·소설가·수필가·평론가 분류에 속한 저자
    for root in AUTHOR_ROOTS:
        lit_authors.update(author_members(root))
    authors |= lit_authors
    author_pages = fetch_pages(sorted(authors))
    via_author: dict[str, str] = {}
    heading_of: dict[str, str] = {}  # 저자 문서 소제목으로 정한 장르
    unsure = 0
    for a_title, a_page in author_pages.items():
        links = linked_works(a_page.get("content") or "")
        # 문학 작가 분류에 없고 문학 소제목도 없는 저자 문서(의서·실록 편찬자 등)의 '저작' 목록은 문학으로 보지 않는다
        literary_author = a_title in lit_authors or any(g for _, g in links)
        for t, g in links:
            if t.split("/")[0] in collections or t.split("/")[0] in NON_LITERARY_TITLES:
                continue
            if t in title_genre:
                # 연도 분류로 먼저 찾았지만 장르 분류가 없던 문서(예: 현진건 「고향」)도 저자 문서의 소제목·
                # 문학 작가 여부로 장르를 보충한다
                if title_genre[t] is None and (g or literary_author):
                    via_author.setdefault(t, a_title)
                    if g:
                        heading_of.setdefault(t, g)
                continue
            if not g and not literary_author:
                unsure += 1
                continue
            via_author.setdefault(t, a_title)
            if g:
                heading_of.setdefault(t, g)
    print(f"[저자 문서] {len(author_pages)}명 · 새 작품 링크 {len(via_author)}개 "
          f"(소제목으로 장르 확인 {len(heading_of)}개 · 비문학 저자 목록 제외 {unsure}개)")
    pages.update(fetch_pages(list(via_author)))
    for t in via_author:
        if t in pages:
            if title_genre.get(t) is None:
                title_genre[t] = heading_of.get(t)
            literary.add(t)

    # 3) 목차 문서 → 시집형(수록작 각각) / 연재형(장 합산) ----------------------------
    serials: dict[str, str] = {}
    for t, p in pages.items():
        c = p.get("content") or ""
        desc = header_field(c, "설명")
        if t in collections or not c or not is_index_page(c) or (t not in literary and not desc_genre(desc)):
            continue
        if NON_LITERARY_TEXT.search(t) and not pick_genre(p["categories"], None):
            continue  # 역사서·선언문 등 (예: 조선상고사)
        by_name = next((g for pat, g in COLLECTION_NAME_GENRE if re.search(pat, t)), None)
        genre = (NAMED_COLLECTION_GENRE.get(t) or by_name or pick_genre(p["categories"], title_genre.get(t))
                 or desc_genre(desc) or "기타")
        subs = [x.split("/")[-1] for x in subpage_titles(t)]
        chapters = subs and sum(bool(CHAPTER_TITLE.match(x.strip())) for x in subs) / len(subs) >= 0.6
        if t in NAMED_COLLECTION_GENRE or re.search(r"(집|선|전집)$", t):
            collections[t] = genre
        elif genre in SERIAL_GENRES or chapters:
            serials[t] = genre
        else:
            collections[t] = genre
    print(f"[목차] 시집·문집형 {len(collections)}개 · 연재형(장 합산) {len(serials)}개")

    col_pages = fetch_pages(list(collections))
    sub_map: dict[str, list[str]] = {c: subpage_titles(c) for c in col_pages}
    serial_map: dict[str, list[str]] = {c: subpage_titles(c) for c in serials}
    sub_pages = fetch_pages([t for subs in (*sub_map.values(), *serial_map.values()) for t in subs])
    print(f"시집·문집 하위 {sum(len(v) for v in sub_map.values())}편 · 연재 장 {sum(len(v) for v in serial_map.values())}개")

    # 4) 저자 문서의 작품 연보·사망 연도 ---------------------------------------------
    authors |= {a for p in (*col_pages.values(), *sub_pages.values()) if (a := author_page(p.get("content") or ""))}
    by_author = author_years(sorted(authors))
    deaths = author_deaths(sorted(authors))
    print(f"저자 문서 연보 {len(by_author)}편 · 사망 연도 {len(deaths)}명")

    def resolve(title: str, page: dict) -> tuple[str, str] | None:
        content = page.get("content") or ""
        d = own_date(work_body(title, page), page["categories"], header_field(content, "설명"))
        if d:
            return d
        y = by_author.get(title) or by_author.get(title.replace("_", " "))
        return (f"{y:04d}-01-01", "저자 문서 발표 연도") if y else None

    records: list[dict] = []
    library: list[dict] = []   # 발표 시기 미상 (참고 작품 서재)
    skipped = defaultdict(int)
    skipped_titles: dict[str, list[str]] = defaultdict(list)  # 재검토용 (data/.wikisource_skipped.json)

    def keep(rec, date, title=""):
        if rec:
            (records if date else library).append(rec)
        else:
            skipped["본문 없음·부속 글·현대 번역"] += 1
            skipped_titles["본문 없음·부속 글·현대 번역"].append(title)

    # 5) 독립 문서 --------------------------------------------------------------------
    for title, page in pages.items():
        content = page.get("content") or ""
        if (title in collections or title in serials or not content
                or content.lstrip().lower().startswith("#redirect") or is_index_page(content)):
            skipped["목차·넘겨주기"] += 1
            continue
        parent = title.rsplit("/", 1)[0] if "/" in title else None
        if parent in col_pages or parent in serials:
            continue  # 시집·연재 경로에서 처리
        genre = pick_genre(page["categories"], title_genre.get(title)) or desc_genre(header_field(content, "설명"))
        own_author = author_page(content)
        if (not genre and (title in literary or own_author in lit_authors)
                and not NON_LITERARY_TEXT.search(title + " " + header_field(content, "설명"))):
            genre = "기타"  # 문학 분류·문학 저자 문서에서 찾았지만 장르 분류가 없는 작품
        if not genre:
            skipped["장르 없음(비문학)"] += 1
            skipped_titles["장르 없음(비문학)"].append(title)
            continue
        date = resolve(title, page)
        parent_content = ((_pages.get(parent) or {}).get("content") or "") if parent else ""
        parent_author = header_field(parent_content, "지은이") or header_field(parent_content, "저자")
        if not parent_author and title in via_author:
            parent_author = via_author[title].split(":", 1)[-1]
        note = "저자 문서의 작품 목록에서 찾음" if title in via_author and genre == "기타" else ""
        keep(to_record(title, page, genre, date, parent, parent_author, note=note), date, title)

    # 6) 시집·수필집·문집·단편소설집 수록작 ------------------------------------------
    for col_title, col_page in col_pages.items():
        col_content = col_page.get("content") or ""
        col_author = header_field(col_content, "지은이") or header_field(col_content, "저자")
        col_date = resolve(col_title, col_page)
        translated = (col_title in TRANSLATED_COLLECTIONS or "번역" in col_title or "번역" in col_page["categories"])
        for title in sub_map.get(col_title, []):
            page = sub_pages.get(title)
            if not page:
                continue
            content = page.get("content") or ""
            if not content or is_index_page(content):
                continue
            genre = pick_genre(page["categories"], collections[col_title]) or "기타"
            date = resolve(title, page)
            note = ""
            if not date and col_date:
                death = deaths.get(author_page(content) or author_page(col_content) or "")
                col_year = int(col_date[0][:4])
                if death and col_year - death > POSTHUMOUS_LIMIT:
                    note = f"수록 판본은 {col_year}년 후대 간행본"
                else:
                    label = "사후 간행 문집" if death and col_year > death else "수록 문집"
                    date = (col_date[0], f"{label} {col_date[1].replace('발표', '간행')}")
            keep(to_record(title, page, genre, date, col_title, col_author, translated,
                           header_field(col_content, "역자"), note), date, title)

    # 7) 장편·연재물: 장별 하위 문서를 합쳐 한 작품 -------------------------------------
    for s_title, genre in serials.items():
        idx = pages[s_title]
        bodies = [(t, sub_pages[t], work_body(t, sub_pages[t])) for t in serial_map.get(s_title, []) if t in sub_pages]
        chars = sum(len(re.sub(r"\s", "", b)) for _, _, b in bodies)
        if chars < MIN_CHARS:
            skipped["연재물 본문 없음"] += 1
            skipped_titles["연재물 본문 없음"].append(s_title)
            continue
        ch_dates = sorted(d for _, ch, b in bodies
                          if (d := own_date(b, ch["categories"], header_field(ch.get("content") or "", "설명"))))
        date = resolve(s_title, idx) or (ch_dates[0] if ch_dates else None)
        if date and ch_dates and date is ch_dates[0]:
            date = (date[0], f"연재 첫 회 {date[1]}")
        order = re.findall(r"\[\[/?([^|\]#]+)", idx.get("content") or "")
        first = next((b for t, _, b in bodies if t.split("/")[-1] in order[:3]), bodies[0][2] if bodies else "")
        synthetic = dict(idx)
        synthetic["_body"] = first
        rec = to_record(s_title, synthetic, genre, date, None, "",
                        note=f"장·연재분 {len(bodies)}개 합산")
        if rec:
            rec["value"] = chars
            # 전체 본문 = 장별 본문을 목차에 적힌 순서(없으면 장 번호 숫자 순)로 이어 붙인 것
            pos = {name.split("/")[-1].strip(): i for i, name in enumerate(order)}

            def natural(t: str) -> list:
                return [int(x) if x.isdigit() else x for x in re.split(r"(\d+)", t)]

            ordered = sorted(bodies, key=lambda x: (pos.get(x[0].split("/")[-1], 10 ** 6), natural(x[0])))
            TEXTS[rec["pageid"]] = "\n\n".join(f"【{t.split('/')[-1]}】\n{b.strip()}" for t, _, b in ordered)
            keep(rec, date)

    # 저작권이 남은 작품(공동 작가 중 한 명이라도 1963년 이후 사망)은 뺀다 — 위키문헌의 라이선스 틀보다 우선
    death_by_name = {**KNOWN_DEATHS, **{t.split(":", 1)[1]: y for t, y in deaths.items()}}

    def protected(r: dict) -> bool:
        name = r["author"].replace("(옮김)", "")
        tr = re.search(r"· ([^—·]+?) 옮김 —", r["memo"])
        names = [name, *re.split(r"[\s,·]+", name)]
        if tr:
            if tr.group(1).strip() in WIKI_USER_TRANSLATORS:
                return True
            names += [tr.group(1).strip(), *re.split(r"[\s,·]+", tr.group(1).strip())]
        return any(death_by_name.get(n, 0) >= COPYRIGHT_CUTOFF for n in names)

    before = len(records) + len(library)
    records = [r for r in records if not protected(r)]
    library = [r for r in library if not protected(r)]
    skipped["저작권 보호 기간(1963년 이후 사망 작가·번역자) · 위키 사용자 번역"] = before - len(records) - len(library)

    by_pageid: dict[int, dict] = {}
    for r in records:  # 넘겨주기로 같은 문서를 가리키면 날짜 근거가 더 정확하고 이른 쪽을 남긴다
        cur = by_pageid.get(r["pageid"])
        if cur is None or (PRECISION_RANK.get(r["basis"], 8), r["date"]) < (PRECISION_RANK.get(cur["basis"], 8), cur["date"]):
            by_pageid[r["pageid"]] = r
    records = list(by_pageid.values())
    records, dup = dedupe(records)

    # 서재: 이미 날짜와 함께 수록된 작품(다른 판본)은 빼고, 서재 안의 중복은 본문이 긴 쪽 하나로
    dated_keys = {(r["author"], norm_title(r["title"])) for r in records}
    dated_ids = {r["pageid"] for r in records}
    shelf: dict[tuple, dict] = {}
    lib_dup = 0
    for r in library:
        if (r["author"], norm_title(r["title"])) in dated_keys or r["pageid"] in dated_ids:
            lib_dup += 1
            continue
        key = (r["author"], norm_title(r["title"]), r["genre"])
        if key in shelf:
            lib_dup += 1
        if key not in shelf or r["value"] > shelf[key]["value"]:
            shelf[key] = r
    library = sorted(shelf.values(), key=lambda r: (r["author"], r["title"]))
    save_caches()
    kept_ids = {r["pageid"] for r in records + library}
    (DATA_DIR / ".wikisource_texts.json").write_text(
        json.dumps({str(k): v for k, v in TEXTS.items() if k in kept_ids}, ensure_ascii=False), encoding="utf-8")
    (DATA_DIR / ".wikisource_skipped.json").write_text(json.dumps(skipped_titles, ensure_ascii=False, indent=1),
                                                     encoding="utf-8")

    result = sorted(records, key=lambda r: (r["date"], r["title"]))
    OUT_PATH.write_text(json.dumps({
        "source": "한국어 위키문헌 (https://ko.wikisource.org) — 퍼블릭 도메인 저작물",
        "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "count": len(result),
        "library_count": len(library),
        "duplicates_removed": {"records": dup, "library": lib_dup},
        "records": result,
        "library": library,
    }, ensure_ascii=False, indent=1), encoding="utf-8")

    count = lambda rows, key: dict(sorted(defaultdict(int, {k: sum(1 for r in rows if r[key] == k)
                                                           for k in {r[key] for r in rows}}).items(),
                                          key=lambda kv: -kv[1]))
    print(f"\n완료: 시계열 {len(result)}편 + 참고 작품 서재(발표 시기 미상) {len(library)}편 → {OUT_PATH}"
          f"  (중복 제거 시계열 {dup}편·서재 {lib_dup}편, 스캔본 본문 {len(_rendered_log)}건 새로 받음)")
    print("제외:", dict(skipped))
    print("시계열 장르:", count(result, "genre"))
    print("서재 장르:", count(library, "genre"))
    print("날짜 근거:", count(result, "basis"))
    if result:
        print("기간:", result[0]["date"], "~", result[-1]["date"])


if __name__ == "__main__":
    main()
