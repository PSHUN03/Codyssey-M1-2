"""한국문화정보원 문화 공공데이터광장 — 문화체육관광부 외_기관별 도서정보(API_LIB_051) 수집.

이 API 는 검색 조건 없이 전체(약 39만 건)를 페이지로만 내려주므로
  1) download : 전 페이지를 data/.kcisa_raw/ 에 받아 두고 (이어받기 가능, git 제외)
  2) build    : 로컬에서 문학 자료만 골라 data/kcisa_books.json 을 만든다.

본문(글자 수)이 없고 발행일도 원작 발표일이 아닌 경우가 많아 시계열이 아닌 '참고 도서 목록'으로 쓴다.

실행 (backend 폴더에서):
    python -m scripts.import_kcisa download
    python -m scripts.import_kcisa build
환경 변수: KCISA_API_KEY (backend/.env, 서비스 키는 코드에 넣지 않는다)
"""

import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from dotenv import load_dotenv

BACKEND = Path(__file__).resolve().parent.parent
load_dotenv(BACKEND / ".env")

API = "https://api.kcisa.kr/openapi/API_LIB_051/request"
RAW_DIR = BACKEND / "data" / ".kcisa_raw"
ROWS = 1000
WORKERS = int(os.environ.get("KCISA_WORKERS", "4"))


def fetch_page(page: int) -> dict:
    key = os.environ.get("KCISA_API_KEY", "").strip()
    if not key:
        sys.exit("KCISA_API_KEY 가 없습니다. backend/.env 에 넣어 주세요.")
    url = f"{API}?{urllib.parse.urlencode({'serviceKey': key, 'numOfRows': ROWS, 'pageNo': page})}"
    for attempt in range(6):
        try:
            req = urllib.request.Request(url, headers={"Accept": "application/json",
                                                       "User-Agent": "geulbeot-writing-assistant/0.2 (educational)"})
            with urllib.request.urlopen(req, timeout=120) as res:
                data = json.loads(res.read())
            if data["response"]["header"]["resultCode"] != "0000":
                raise RuntimeError(data["response"]["header"])
            return data["response"]["body"]
        except (urllib.error.URLError, TimeoutError, RuntimeError, json.JSONDecodeError) as e:
            print(f"  ! {page}쪽 실패({str(e)[:60]}), {10 * (attempt + 1)}s 후 재시도", flush=True)
            time.sleep(10 * (attempt + 1))
    raise RuntimeError(f"{page}쪽을 받지 못했습니다.")


def download() -> None:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    first = RAW_DIR / "p0001.json"
    if not first.exists():
        first.write_text(json.dumps(fetch_page(1), ensure_ascii=False), encoding="utf-8")
    total = int(json.loads(first.read_text(encoding="utf-8"))["totalCount"])
    pages = (total + ROWS - 1) // ROWS
    print(f"전체 {total:,}건 · {pages}쪽", flush=True)
    todo = [p for p in range(2, pages + 1) if not (RAW_DIR / f"p{p:04d}.json").exists()]
    print(f"남은 {len(todo)}쪽 · 동시 {WORKERS}개 요청", flush=True)

    def save(page: int) -> int:
        body = fetch_page(page)
        tmp = RAW_DIR / f"p{page:04d}.json.part"   # 다 받은 뒤에만 이름을 바꿔 반쪽 파일이 남지 않게
        tmp.write_text(json.dumps(body, ensure_ascii=False), encoding="utf-8")
        tmp.replace(RAW_DIR / f"p{page:04d}.json")
        return page

    # 한 쪽(1,000건) 응답에 30초 이상 걸려 순차로는 몇 시간이 걸린다 → 적은 수로 동시에 요청
    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        for n, _ in enumerate(as_completed([pool.submit(save, p) for p in todo]), 1):
            if n % 10 == 0 or n == len(todo):
                print(f"  - {n}/{len(todo)}쪽 완료", flush=True)
    print("다운로드 완료", flush=True)


def iter_items():
    for path in sorted(RAW_DIR.glob("p*.json")):
        body = json.loads(path.read_text(encoding="utf-8"))
        items = (body.get("items") or {}).get("item") or []
        yield from (items if isinstance(items, list) else [items])


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "download"
    if cmd == "download":
        download()
    else:
        from scripts.kcisa_build import build  # 문학 자료 선별 규칙은 따로 둔다

        build(list(iter_items()))
