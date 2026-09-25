"""공유마당(한국저작권위원회) 만료저작물 어문 목록 수집.

만료저작물 = 저작재산권 보호 기간이 끝난 퍼블릭 도메인 저작물. 제공처 중
  - 한국저작권위원회(04): 근대시·소설·수필·한시 등 문학 작품 (창작·공표 연도, 장르 태그, 원문 출전)
  - 한국고전번역원(03): 고전 문집 번역
만 모은다. 국립중앙도서관(05) 제공분은 호적·교지 같은 고문서 스캔본이 대부분이라 제외.

robots.txt 는 상세 페이지 수집을 허용하지만 원문 파일 경로(/upload/)와 다운로드 팝업은 막고 있고,
다운로드에는 이용 동의 절차가 있으므로 **본문 파일은 받지 않고 목록 정보와 원문 링크만** 저장한다.

실행 (backend 폴더에서):
    python -m scripts.import_gongu fetch   # 목록 → 상세 (이어받기 가능, 요청 간격 1초, 약 4시간)
    python -m scripts.import_gongu build   # data/gongu_works.json 생성
"""

import html
import json
import re
import sys
import time
import urllib.error
import urllib.request
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

BASE = "https://gongu.copyright.or.kr"
USER_AGENT = "geulbeot-writing-assistant/0.3 (https://github.com/PSHUN03/Codyssey-M1-2; educational project)"
DATA = Path(__file__).resolve().parent.parent / "data"
CACHE = DATA / ".gongu_cache"          # git 제외: 목록·상세 원자료
OUT = DATA / "gongu_works.json"
PROVIDERS = {"04": "한국저작권위원회", "03": "한국고전번역원"}
PAGE_UNIT = 100
PAUSE = 1.0

_last = 0.0


def get(path: str) -> str:
    global _last
    for attempt in range(5):
        wait = PAUSE - (time.time() - _last)
        if wait > 0:
            time.sleep(wait)
        _last = time.time()
        try:
            req = urllib.request.Request(BASE + path, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=60) as res:
                return res.read().decode("utf-8", "replace")
        except (urllib.error.URLError, TimeoutError) as e:
            print(f"  ! {path[:60]} 실패({e}), {10 * (attempt + 1)}s 후 재시도", flush=True)
            time.sleep(10 * (attempt + 1))
    raise RuntimeError(f"받지 못함: {path}")


def list_ids(code: str) -> list[int]:
    path = CACHE / f"ids_{code}.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    ids: list[int] = []
    page = 1
    while True:
        t = get(f"/gongu/wrt/wrtCl/listWrtText.do?menuNo=200023&licenseCd=97&searchSrcTrgetInttCd={code}"
                f"&pageUnit={PAGE_UNIT}&pageIndex={page}")
        found = [int(x) for x in dict.fromkeys(re.findall(r"view\.do\?wrtSn=(\d+)", t))]
        new = [x for x in found if x not in ids]
        if not new:
            break
        ids += new
        total = re.search(r"총 : <strong>([\d,]+)</strong>", t)
        print(f"  - {PROVIDERS[code]} 목록 {page}쪽 · {len(ids)}/{total.group(1) if total else '?'}", flush=True)
        page += 1
    path.write_text(json.dumps(ids), encoding="utf-8")
    return ids


def _field(t: str, name: str) -> str:
    m = re.search(r"<dt>\s*" + re.escape(name) + r"\s*</dt>\s*<dd>(.*?)</dd>", t, re.S)
    if not m:
        return ""
    raw = re.sub(r"<br\s*/?>", "|", m.group(1))  # 줄바꿈은 '|' 로 구분 (원문 파일 목록)
    text = html.unescape(re.sub(r"<[^>]+>", " ", raw))
    return re.sub(r"\s*\|\s*", "|", re.sub(r"\s+", " ", text)).strip(" |")


def parse_detail(wrt_sn: int, t: str) -> dict:
    strip = lambda s: re.sub(r"<[^>]+>", "", s).strip()  # noqa: E731
    author = _field(t, "저작(권)자")
    author = re.sub(r"\(저작물.*$", "", strip(author)).strip()
    tags = re.search(r'<meta property="keywords" content="([^"]*)"', t)
    files = strip(_field(t, "원문제공")).replace("원문파일명", "").strip(" |")
    return {
        "wrtSn": wrt_sn,
        "title": strip(_field(t, "저작물명")),
        "author": author,
        "provider": strip(_field(t, "출처")),
        "published": strip(_field(t, "공표년도")),
        "created": strip(_field(t, "창작년도")),
        "summary": strip(_field(t, "요약정보")),
        "tags": [x.strip() for x in (tags.group(1) if tags else "").split("#") if x.strip()],
        "files": [f.strip() for f in files.split("|") if f.strip()],
    }


def _details(code: str) -> list[dict]:
    """detail_{code}*.jsonl (조각별 파일 포함). 중간에 끊겨 반쯤 쓰인 줄은 건너뛴다."""
    rows = []
    for path in sorted(CACHE.glob(f"detail_{code}*.jsonl")):
        for line in path.read_text(encoding="utf-8").splitlines():
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return rows


def fetch(codes: list[str] | None = None, shard: tuple[int, int] = (0, 1)) -> None:
    """shard=(k, n): 남은 목록을 n 조각으로 나눠 k 번째만 받는다 (여러 프로세스로 나눠 받을 때)."""
    CACHE.mkdir(parents=True, exist_ok=True)
    k, n_shards = shard
    for code in codes or list(PROVIDERS):
        ids = list_ids(code)
        out = CACHE / (f"detail_{code}.jsonl" if n_shards == 1 else f"detail_{code}_s{k}.jsonl")
        done = {w["wrtSn"] for w in _details(code)}
        todo = [i for i in ids if i not in done and i % n_shards == k]
        print(f"[{PROVIDERS[code]}] 목록 {len(ids)}건 · 남은 상세 {len(todo)}건", flush=True)
        with out.open("a", encoding="utf-8") as f:
            for n, wrt_sn in enumerate(todo, 1):
                t = get(f"/gongu/wrt/wrt/view.do?wrtSn={wrt_sn}&menuNo=200023")
                f.write(json.dumps(parse_detail(wrt_sn, t), ensure_ascii=False) + "\n")
                f.flush()
                if n % 200 == 0 or n == len(todo):
                    print(f"  - 상세 {n}/{len(todo)}", flush=True)
    print("수집 완료", flush=True)


# ---------------------------------------------------------------- 정리
# 태그·요약 → 장르 (앞쪽 규칙 우선). 어느 것에도 안 걸리는 비문학(영화 평론 등)은 뺀다
GENRE_RULES = [
    (r"희곡|시나리오|각본", "희곡"), (r"동화|우화", "동화"), (r"동요|동시", "노래"),
    (r"장편소설|장편 소설", "장편소설"), (r"중편소설", "중편소설"), (r"단편소설|단편 소설", "단편소설"),
    (r"소설|야담|설화|고전소설|신소설", "소설"), (r"시조", "시조"), (r"한시|오언|칠언|절구|율시", "한시"),
    (r"가사(?!\s*없)", "가사"), (r"향가|고려가요|속요|악장", "고전시가"), (r"민요|노래|창가|가곡", "노래"),
    (r"수필|기행|일기|산문|수상|잡문|회고", "수필"), (r"편지|서간", "서간"), (r"평론|비평|문학론|시론", "평론"),
    (r"자유시|현대시|정형시|산문시|서정시|시\b|시$|(?<![가-힣])시(?![가-힣])", "시"),
    (r"칼럼|논설", "평론"), (r"문집|유고|시문|위당", "기타"),
]
NON_LITERARY_TAGS = {"학습물", "교양물"}  # 성경 해설·교양 강좌 등
NON_LITERARY = re.compile(r"영화|사진|미술|음악 평|건축|경제|법률|의학|농업|광업|행정|보도")


def _match(text: str) -> str | None:
    return next((g for pattern, g in GENRE_RULES if re.search(pattern, text)), None)


def genre_of(w: dict) -> str | None:
    """태그가 장르를 가리키면 태그를 따르고(요약문의 '미술 사학자' 같은 말에 휘둘리지 않게),
    태그가 없을 때만 요약문으로 판단한다. 요약문에 비문학 분야가 보이면 넣지 않는다."""
    by_tag = _match(" ".join(w["tags"]))
    if by_tag == "시":  # '시' 태그는 넓어서 요약문의 더 구체적인 갈래(시조·한시·가사·동요)를 따른다
        specific = _match(w["summary"])
        return specific if specific in {"시조", "한시", "가사", "고전시가", "노래"} else by_tag
    if by_tag:
        return by_tag
    if set(w["tags"]) & NON_LITERARY_TAGS or NON_LITERARY.search(w["summary"]):
        return None
    return _match(w["summary"]) or ("기타" if w["provider"] == "한국고전번역원" else None)


def date_of(w: dict) -> tuple[str | None, str]:
    m = re.match(r"(1[3-9]\d\d)\.?\s*(\d{1,2})?", w["published"])
    if m:
        return (f"{m.group(1)}-{int(m.group(2)):02d}-01", "공표 월") if m.group(2) else (f"{m.group(1)}-01-01", "공표 연도")
    m = re.match(r"(1[3-9]\d\d)", w["created"])
    if m:
        return f"{m.group(1)}-01-01", "창작 연도"
    return None, "발표 시기 미상"


def build() -> None:
    rows, skipped = [], Counter()
    for code, provider in PROVIDERS.items():
        seen = set()
        for w in _details(code):
            if w["wrtSn"] in seen:
                continue
            seen.add(w["wrtSn"])
            if not w["title"]:
                skipped["제목 없음"] += 1
                continue
            genre = genre_of(w)
            if not genre:
                skipped["비문학·장르 확인 불가"] += 1
                continue
            date, basis = date_of(w)
            title = re.sub(r"-\d+$", "", w["title"]).strip()   # '승사주면-2' 처럼 붙은 연번 제거
            summary = w["summary"]
            if provider == "한국고전번역원" and date:
                # 공표 연도는 번역본이 나온 해(1960~80년대)라 원작의 시기가 아니다
                summary = f"{summary} (번역본 공표 {date[:4]}년)".strip()
                date, basis = None, "발표 시기 미상"
            if (genre in ("시", "시조") and re.search(r"\([\u4e00-\u9fff]{2,}\)", title)
                    and re.search(r"조선|고려|신라|문신|유학자|성리학자", w["summary"]) and not date):
                genre = "한시"  # 조선·고려 문인의 한자 제목 작품 (예: 차증일암(次贈一菴))
            # 원문 파일명 '김정식-가는_길-개벽.txt' → 출전 '개벽' (저자-제목-출전 형식일 때만)
            parts = next((f.rsplit(".", 1)[0].split("-") for f in w["files"]), [])
            origin = parts[-1].replace("_", " ") if len(parts) >= 3 and not parts[-1].isdigit() else ""
            rows.append({
                "title": title,
                "author": w["author"] or None,
                "genre": genre,
                "date": date,
                "basis": basis,
                "summary": summary[:200] or None,
                "origin": origin or None,
                "provider": provider,
                "url": f"{BASE}/gongu/wrt/wrt/view.do?wrtSn={w['wrtSn']}&menuNo=200023",
            })
    OUT.write_text(json.dumps({
        "source": "공유마당(한국저작권위원회) 만료저작물 — 어문",
        "built_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "count": len(rows),
        "skipped": dict(skipped),
        "works": rows,
    }, ensure_ascii=False, indent=0), encoding="utf-8")
    print(f"문학 {len(rows):,}건 → {OUT}  (제외 {dict(skipped)})")
    print("장르:", Counter(r["genre"] for r in rows).most_common())
    print("날짜:", Counter(r["basis"] for r in rows).most_common())


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "fetch"
    if cmd == "fetch":
        # 예: fetch 03 → 한국고전번역원만 / fetch 04 --shard 1/3 → 남은 목록의 두 번째 1/3 조각
        args = sys.argv[2:]
        shard = (0, 1)
        if "--shard" in args:
            i = args.index("--shard")
            k, n = args[i + 1].split("/")
            shard, args = (int(k), int(n)), args[:i] + args[i + 2:]
        fetch(args or None, shard)
    else:
        build()
