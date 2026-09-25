"""프로젝트 구텐베르크 — 한국 관련 문학 작품(영어 번역 설화·한국 배경 소설).

구텐베르크의 한국어 책은 사전 1권뿐이라, 주제어 Korea 로 찾은 36권 중 문학 작품만 골랐다
(역사·여행기·전쟁 기록·동식물 보고서는 제외, 저작권이 남은 1950년대 이후 작가의 작품 제외).
발행 연도는 구텐베르크 서지의 'Original Publication' 또는 초판 서지로 확인했다.

실행 (backend 폴더에서): python -m scripts.import_gutenberg  → data/gutenberg_works.json
"""

import json
import re
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "data" / "gutenberg_works.json"
USER_AGENT = "geulbeot-writing-assistant/0.3 (https://github.com/PSHUN03/Codyssey-M1-2; educational project)"

# (구텐베르크 번호, 한국어 장르, 초판 연도, 비고)
WORKS = [
    (55539, "소설", 1889, "Horace N. Allen 이 한국 고전소설·설화(춘향전·심청전 등)를 옮긴 책"),
    (34810, "소설", 1895, "한국 배경 아동소설"),
    (12048, "동화", 1905, "한국 어린이를 그린 아동문학"),
    (71728, "소설", 1904, "한국·만주 배경 아동 모험소설"),
    (51002, "소설", 1913, "임방·이륙 원작 설화를 J. S. Gale 이 옮김 (천예록·용재총화 등)"),
    (78208, "소설", 1919, "한국 전설"),
    (67180, "동화", 1922, "W. E. Griffis 가 엮은 한국 전래동화 (1911년 판, 1922년 저작권)"),
]


def fetch(url: str) -> bytes:
    for attempt in range(6):  # Gutendex 는 무료 서버라 503 이 자주 난다
        try:
            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=90) as res:
                return res.read()
        except (urllib.error.URLError, TimeoutError) as e:
            print(f"  ! {url} 실패({e}), {15 * (attempt + 1)}s 후 재시도", flush=True)
            time.sleep(15 * (attempt + 1))
    raise RuntimeError(f"받지 못함: {url}")


def fetch_json(url: str) -> dict:
    return json.loads(fetch(url))


def fetch_text(url: str) -> str:
    return fetch(url).decode("utf-8", "replace")


def body_of(text: str) -> str:
    """구텐베르크 머리말·꼬리말(라이선스 안내)을 뺀 본문."""
    start = re.search(r"\*\*\* ?START OF (THE|THIS) PROJECT GUTENBERG.*?\*\*\*", text)
    end = re.search(r"\*\*\* ?END OF (THE|THIS) PROJECT GUTENBERG", text)
    return text[start.end() if start else 0:end.start() if end else len(text)]


def main() -> None:
    rows = []
    for gid, genre, year, note in WORKS:
        meta = fetch_json(f"https://gutendex.com/books/{gid}")
        fmt = meta["formats"]
        txt_url = next((u for k, u in fmt.items() if k.startswith("text/plain")), None)
        body = body_of(fetch_text(txt_url)) if txt_url else ""
        authors = [a["name"] for a in meta["authors"]]
        rows.append({
            "title": re.sub(r"\s*:\s*\$b\s*", ": ", meta["title"]),
            "author": ", ".join(authors) or None,
            "genre": genre,
            "date": f"{year}-01-01",
            "basis": "초판 연도",
            "language": "영어",
            "chars": len(re.sub(r"\s", "", body)),
            "excerpt": re.sub(r"\s+", " ", body.strip())[:300],
            "note": note,
            "url": f"https://www.gutenberg.org/ebooks/{gid}",
        })
        print(f"  - {gid} {meta['title'][:50]} · {rows[-1]['chars']:,}자", flush=True)
        time.sleep(1)
    OUT.write_text(json.dumps({
        "source": "Project Gutenberg — 한국 관련 문학 (영어, 퍼블릭 도메인)",
        "built_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "count": len(rows),
        "works": rows,
    }, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{len(rows)}편 → {OUT}")


if __name__ == "__main__":
    main()
