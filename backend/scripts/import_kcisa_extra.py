"""문화공공데이터광장(한국문화정보원) 보충 자료 API 11종 수집.

    python -m scripts.import_kcisa_extra download [이름 ...]   # 전 쪽을 data/.kcisa_extra/<이름>/ 에 (이어받기, git 제외)
    python -m scripts.import_kcisa_extra build                # 문학 자료만 골라 data/extra_<이름>.json

서비스 키는 backend/.env 의 KCISA_KEY_<이름> 에만 둔다.
연도는 원작 발행 연도를 알 수 있을 때만(소개글·서지 문자열 속 발행 연도) 쓰고, 기관 등록일(regDate)은 쓰지 않는다.
"""

from __future__ import annotations

import html
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

BACKEND = Path(__file__).resolve().parent.parent
DATA = BACKEND / "data"
RAW = DATA / ".kcisa_extra"
load_dotenv(BACKEND / ".env")
ROWS = 1000
WORKERS = int(os.environ.get("KCISA_WORKERS", "4"))

# 이름: (요청 주소, 화면 이름, 기관)
DATASETS = {
    "LIB046": ("https://api.kcisa.kr/openapi/API_LIB_046/request", "번역원 번역출간도서", "한국문학번역원"),
    "LIB047": ("https://api.kcisa.kr/openapi/API_LIB_047/request", "번역원 전문도서관 소장", "한국문학번역원"),
    "NLTOT": ("https://api.kcisa.kr/openapi/service/rest/meta16/getNlTot", "국립중앙도서관 소장자료", "국립중앙도서관"),
    "NLKF021801": ("https://api.kcisa.kr/openapi/service/rest/meta14/getNLKF021801", "국립중앙도서관 OAK", "국립중앙도서관"),
    "NLKF0201": ("https://api.kcisa.kr/openapi/service/rest/meta13/getNLKF0201", "국립중앙도서관 사서추천", "국립중앙도서관"),
    "NLSF0401": ("https://api.kcisa.kr/openapi/service/rest/meta13/getNLSF0401", "국립세종도서관 사서추천", "국립세종도서관"),
    "NLCFSASE": ("https://api.kcisa.kr/openapi/service/rest/meta2/NLCFsase", "국립어린이청소년도서관 사서추천", "국립어린이청소년도서관"),
    "KPEF0102": ("https://api.kcisa.kr/openapi/service/rest/meta13/getKPEF0102", "청소년권장도서", "한국출판문화산업진흥원"),
    "KPEF0103": ("https://api.kcisa.kr/openapi/service/rest/meta13/getKPEF0103", "대학신입생추천도서", "한국출판문화산업진흥원"),
    "NFMBOOK": ("https://api.kcisa.kr/openapi/service/rest/meta/NFMbook", "국립민속박물관 발간도서", "국립민속박물관"),
    "KSCD0820181": ("https://api.kcisa.kr/openapi/service/rest/meta2018/getKSCD0820181", "올림픽공원 도서정보", "한국체육산업개발"),
}


# ---------------------------------------------------------------- 다운로드

def fetch_page(name: str, page: int) -> dict:
    url = DATASETS[name][0]
    key = os.environ.get(f"KCISA_KEY_{name}", "").strip()
    if not key:
        sys.exit(f"KCISA_KEY_{name} 가 없습니다. backend/.env 에 넣어 주세요.")
    q = urllib.parse.urlencode({"serviceKey": key, "numOfRows": ROWS, "pageNo": page})
    for attempt in range(6):
        try:
            req = urllib.request.Request(f"{url}?{q}", headers={"Accept": "application/json",
                                                                "User-Agent": "geulbeot-writing-assistant/0.3 (educational)"})
            with urllib.request.urlopen(req, timeout=180) as res:
                data = json.loads(res.read())
            if data["response"]["header"]["resultCode"] != "0000":
                raise RuntimeError(data["response"]["header"])
            return data["response"]["body"]
        except (urllib.error.URLError, TimeoutError, RuntimeError, json.JSONDecodeError) as e:
            print(f"  ! {name} {page}쪽 실패({str(e)[:50]}), {15 * (attempt + 1)}s 후 재시도", flush=True)
            time.sleep(15 * (attempt + 1))
    raise RuntimeError(f"{name} {page}쪽을 받지 못했습니다.")


def download(name: str) -> None:
    d = RAW / name
    d.mkdir(parents=True, exist_ok=True)
    first = d / "p0001.json"
    if not first.exists():
        first.write_text(json.dumps(fetch_page(name, 1), ensure_ascii=False), encoding="utf-8")
    total = int(json.loads(first.read_text(encoding="utf-8"))["totalCount"])
    pages = max(1, (total + ROWS - 1) // ROWS)
    todo = [p for p in range(2, pages + 1) if not (d / f"p{p:04d}.json").exists()]
    print(f"[{name}] 전체 {total:,}건 · {pages}쪽 · 남은 {len(todo)}쪽", flush=True)

    def save(page: int) -> None:
        body = fetch_page(name, page)
        tmp = d / f"p{page:04d}.json.part"
        tmp.write_text(json.dumps(body, ensure_ascii=False), encoding="utf-8")
        tmp.replace(d / f"p{page:04d}.json")

    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        for n, _ in enumerate(as_completed([pool.submit(save, p) for p in todo]), 1):
            if n % 20 == 0 or n == len(todo):
                print(f"  - {name} {n}/{len(todo)}쪽", flush=True)


def items(name: str) -> list[dict]:
    out = []
    for path in sorted((RAW / name).glob("p*.json")):
        body = json.loads(path.read_text(encoding="utf-8"))
        it = (body.get("items") or {}).get("item") or []
        out += it if isinstance(it, list) else [it]
    return out


# ---------------------------------------------------------------- 공통 규칙
# 한국십진분류(KDC) 문학(8xx): 둘째 자리 = 나라, 셋째 자리 = 형식
KDC_FORM = {"1": "시", "2": "희곡", "3": "소설", "4": "수필", "5": "기타", "6": "수필", "7": "기타", "8": "기타", "9": "기타"}
# 소개글로 문학을 판단할 때는 뚜렷한 말만 ('에세이'는 과학·경제 에세이가 많아 쓰지 않는다)
STRONG_GENRE = [(r"희곡|극본", "희곡"), (r"동시집", "노래"), (r"동화|그림책", "동화"), (r"장편소설", "장편소설"),
                (r"단편소설|소설집|단편집", "단편소설"), (r"(?<![가-힣])소설(?![가-힣])|소설이다|소설로", "소설"),
                (r"시집|시선집", "시")]
KDC_NATION = {"0": "", "1": "한국", "2": "중국", "3": "일본", "4": "영미", "5": "독일", "6": "프랑스", "7": "스페인",
              "8": "이탈리아", "9": "기타 나라"}
# 제목·소개글로 문학 여부·장르 판단 (추천도서 목록처럼 분류번호가 없는 자료)
TEXT_GENRE = [
    (r"희곡|극본|시나리오", "희곡"), (r"동시집|동시(?![가-힣])", "노래"), (r"동화|그림책", "동화"),
    (r"장편소설|장편 소설", "장편소설"), (r"단편소설|소설집|단편집|단편 소설", "단편소설"),
    (r"소설|추리|판타지|SF|로맨스|청소년문학|성장\s*이야기", "소설"), (r"시집|시선집|(?<![가-힣])시(?:를|는|로|와|가)?\s", "시"),
    (r"시조", "시조"), (r"수필|에세이|산문집", "수필"), (r"평론|비평|문학론", "평론"),
    (r"설화|민담|전설|옛이야기|신화", "소설"), (r"민요|무가|노동요", "노래"),
]
NON_LIT = re.compile(r"과학|수학|경제|경영|투자|주식|요리|건강|의학|법률|정치|철학|심리학|사회학|역사책|교과서|학습|"
                     r"문제집|공부법|자기계발|컴퓨터|코딩|여행 안내|가이드북|IT|인공지능|로봇|환경|기후|우주")


# 번역서 제목의 외국어 표현으로 장르 추정 (번역원 자료는 장르 정보가 없다)
FOREIGN_GENRE = [(r"\bpoems?\b|poetry|gedichte|poèmes|poesía|poesie|poesia|стихи|诗|詩", "시"),
                 (r"\bstories\b|short stories|nouvelles|erzählungen|cuentos|racconti|短篇|小説集", "단편소설"),
                 (r"\bnovel\b|\broman\b|novela|romanzo|роман|长篇|長篇", "장편소설"),
                 (r"\bplays?\b|drama|théâtre|teatro|戏剧|戯曲", "희곡"),
                 (r"\bessays?\b|essais|ensayos|散文|随笔|エッセイ", "수필"),
                 (r"fairy|folk ?tales|märchen|contes|cuentos populares|童话|童話|昔話", "동화")]


def foreign_genre(text: str) -> str | None:
    t = text.lower()
    return next((g for pattern, g in FOREIGN_GENRE if re.search(pattern, t)), None)


def text_genre(*texts: str) -> str | None:
    t = " ".join(x or "" for x in texts)
    return next((g for pattern, g in TEXT_GENRE if re.search(pattern, t)), None)


def clean(s: str | None) -> str:
    s = html.unescape(re.sub(r"<[^>]+>", " ", s or ""))
    return re.sub(r"\s+", " ", s).strip()


def year_in(s: str | None, lo: int = 1400, hi: int = 2026) -> int | None:
    for m in re.finditer(r"(?<!\d)(1[4-9]\d\d|20[0-2]\d)(?!\d)", s or ""):
        y = int(m.group(1))
        if lo <= y <= hi:
            return y
    return None


CONTACT = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+|(?<!\d)0\d{1,2}-\d{3,4}-\d{4}(?!\d)")


def no_contact(s: str | None) -> str:
    """원 서지의 저자 칸 등에 잘못 들어간 개인 이메일·전화번호는 지운다 (공개 저장소·API 로 내보내므로)."""
    s = CONTACT.sub("", clean(s))
    return re.sub(r"\s*,\s*(,\s*)+", ", ", s).strip(" ,;")


def row(title, author, genre, year, basis, url=None, publisher=None, language=None, note=None, **extra) -> dict:
    return {"title": clean(title)[:150], "author": no_contact(author)[:80] or None, "genre": genre, "year": year,
            "basis": basis if year else "발표 시기 미상", "url": url or None, "publisher": no_contact(publisher)[:80] or None,
            "language": language or None, "note": no_contact(note)[:200] or None, **extra}


# ---------------------------------------------------------------- 자료별 선별
def build_lti() -> dict[str, list[dict]]:
    """번역원 두 자료: 같은 원작의 여러 언어 번역을 원작 한 편으로 묶는다 (번역 언어·권수는 note 에)."""
    def korean_author(a: str) -> str:
        a = re.sub(r"\s*\d{4}\s*-\s*(\d{4})?", "", a or "")  # '이광수 1892-1950' → '이광수'
        names = [x.strip() for x in re.split(r"[,;]", a or "") if re.fullmatch(r"\s*[가-힣]{2,4}\s*", x or "")]
        return names[0] if names else (a or "").split(",")[0].strip()

    out = {}
    seen_works: set = set()
    for name in ("LIB046", "LIB047"):
        works: dict[tuple, dict] = {}
        for it in items(name):
            if name == "LIB046":
                orig, trans = it.get("alternativeTitle") or "", it.get("title") or ""
                lang = it.get("language") or ""
            else:
                t = it.get("title") or ""
                trans, orig = (t.split("=", 1) + [""])[:2] if "=" in t else (t, "")
                lang = ""
            orig = clean(orig) or clean(trans)
            author = korean_author(it.get("author") or "")
            key = (re.sub(r"\s", "", author), re.sub(r"[\s\W]", "", orig))
            w = works.get(key)
            if not w:
                w = works[key] = {"orig": orig, "author": author, "langs": Counter(), "trans_set": set(),
                                  "url": it.get("url"), "trans": clean(trans)}
            # 2022년 일괄 등록분은 같은 기록이 수십 번 반복돼 있어, 기록 수가 아니라 서로 다른 번역서 수를 센다
            w["trans_set"].add((clean(trans), it.get("isbn") or ""))
            w["url"] = w["url"] or it.get("url")
            if lang:
                w["langs"][lang] += 1
        rows = []
        for key, w in works.items():
            if key in seen_works:
                continue  # 046 에 이미 있는 원작 (047 은 046 에 없는 원작만)
            seen_works.add(key)
            langs = ", ".join(l for l, _ in w["langs"].most_common(5))
            n = len(w["trans_set"])
            note = f"번역서 {n}종" + (f" · {langs}" if langs else "") + (f" · 예: {w['trans']}" if w["trans"] else "")
            genre = text_genre(w["orig"]) or foreign_genre(" ".join(t for t, _ in w["trans_set"])) or "기타"
            rows.append(row(w["orig"], w["author"], genre, None, "", w["url"],
                            language="번역서", note=note, translations=n))
        out[name] = rows
    return out


def build_nltot() -> list[dict]:
    rows = []
    for it in items("NLTOT"):
        m = re.search(r"KDC:\s*8(\d)(\d)", it.get("subDescription") or "")
        if not m:
            continue
        nation = KDC_NATION.get(m.group(1), "")
        # 80x 문학 일반: 801 이론·809 문학사 = 평론, 804 수필·강연 = 수필, 808 전집·총서 등은 기타
        form = ({"1": "평론", "9": "평론", "4": "수필"}.get(m.group(2), "기타") if m.group(1) == "0"
                else KDC_FORM.get(m.group(2), "기타"))
        people = [x.strip() for x in (it.get("person") or "").split("|") if x.strip()]
        rows.append(row(it.get("title"), ", ".join(people[:2]), form, None, "",  # 발행 연도 필드가 없다
                        it.get("url"), language=f"{nation}문학" if nation else None,
                        note=f"KDC 8{m.group(1)}{m.group(2)}"))
    return rows


def build_recommend(name: str) -> list[dict]:
    """추천도서 목록류: 청구기호(KDC 8xx)·주제 분류('문학'·'어문학')·제목으로 문학만.
    발행 연도는 형식이 분명할 때만 (세종도서관 소개글의 '출판사 ｜ 2021') — 소개글 속 작가 생년 등을 잘못 읽지 않게."""
    rows = []
    for it in items(name):
        title = it.get("title") or it.get("alternativeTitle") or ""
        desc = clean(it.get("description"))
        author = clean(it.get("rights") or it.get("person") or "")
        cat = it.get("subjectCategory") or ""
        kdc = re.search(r"(?<![\d.])8(\d)(\d)(?:\.\d+)?-", desc)  # 청구기호 '813.7-21-3'
        if kdc:
            genre = "평론" if kdc.group(1) == "0" else KDC_FORM.get(kdc.group(2), "기타")
        elif cat in ("문학", "어문학"):
            genre = text_genre(title) or next((g for pat, g in STRONG_GENRE if re.search(pat, desc)), "기타")
        else:
            if (NON_LIT.search(title) or NON_LIT.search(desc[:300])
                    or cat in {"인문과학", "자연과학", "사회과학", "철학", "역사", "예술"}):
                continue
            genre = text_genre(title) or next((g for pat, g in STRONG_GENRE if re.search(pat, desc[:300])), None)
            if not genre:
                continue
        y = re.search(r"｜\s*(1[89]\d\d|20[0-2]\d)(?!\d)", desc[:200])
        year = int(y.group(1)) if y else None
        rows.append(row(title, re.sub(r"\s*(지음|글|저|옮김|그림).*$", "", author.split("//")[0]), genre, year,
                        "발행 연도", it.get("url")))  # 소개글은 기관이 쓴 창작 글이라 저장하지 않고 링크로 본다
    return rows


def build_nfm() -> list[dict]:
    """국립민속박물관 발간도서: 설화·민요·구비문학 자료만 (발행일 = 실제 발간일)."""
    rows = []
    for it in items("NFMBOOK"):
        title = it.get("alternativeTitle") or it.get("title") or ""
        if (not re.search(r"설화|민요|민담|전설|무가|옛이야기|탈춤|대본", title)
                or re.search(r"학술|사전|대회|세미나|백서|연구|조사|보고|도록|전시|목록|총서 해제", title)):
            continue  # 설화·민요 자료집만 (연구서·전시 자료는 제외)
        genre = "노래" if re.search(r"민요|무가|노래", title) else "희곡" if re.search(r"탈춤|대본", title) else "소설"
        issued = (it.get("issuedDate") or "")[:4]
        rows.append(row(title, None, genre, int(issued) if issued.isdigit() else None, "발간 연도", it.get("url"),
                        publisher="국립민속박물관", note=it.get("extent")))
    return rows


def build_kscd() -> list[dict]:
    """올림픽공원 도서: 서지 문자열 '서명/저자사항:시공사,2015'의 발행 연도, 제목으로 문학만."""
    rows = []
    for it in items("KSCD0820181"):
        title, rights = it.get("title") or "", it.get("rights") or ""
        genre = text_genre(title, rights)
        if not genre or NON_LIT.search(title):
            continue
        author = re.search(r"개인저자:([^|]+)", rights)
        rows.append(row(title, author.group(1) if author else None, genre, year_in(it.get("description")), "발행 연도",
                        it.get("url"), publisher=(it.get("description") or "").split(",")[0]))
    return rows


def build() -> None:
    out = {}
    lti = build_lti()
    out.update(lti)
    out["NLTOT"] = build_nltot()
    for name in ("NLKF0201", "NLSF0401", "NLCFSASE", "KPEF0102", "KPEF0103", "NLKF021801"):
        if (RAW / name).exists():
            out[name] = build_recommend(name)
    out["NFMBOOK"] = build_nfm()
    out["KSCD0820181"] = build_kscd()
    for name, rows in out.items():
        if name not in ("LIB046", "LIB047"):  # 같은 목록 안에 같은 책이 여러 번(권별·중복 등록) 있으면 하나로
            seen, uniq = set(), []
            for r in rows:
                k = (re.sub(r"[\s\W]", "", r["title"].split(":")[0].split(".")[0]), r["author"] or "")
                if k not in seen:
                    seen.add(k)
                    uniq.append(r)
            rows = uniq
        url, label, org = DATASETS[name]
        (DATA / f"extra_{name.lower()}.json").write_text(json.dumps({
            "key": name.lower(), "label": label, "organization": org,
            "source": f"문화공공데이터광장 — {org} {label}",
            "built_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "raw": len(items(name)) if (RAW / name).exists() else 0,
            "count": len(rows), "works": rows,
        }, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        years = sum(1 for r in rows if r["year"])
        print(f"{label}: 원자료 {len(items(name)) if (RAW / name).exists() else 0:,} → 문학 {len(rows):,} (연도 {years:,})"
              f" · {Counter(r['genre'] for r in rows).most_common(6)}")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "build"
    if cmd == "download":
        for n in sys.argv[2:] or list(DATASETS):
            try:
                download(n)
            except RuntimeError as e:
                print(f"  ! {n} 건너뜀: {e}", flush=True)
    else:
        build()
