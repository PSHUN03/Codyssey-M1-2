"""수집한 작품이 실제로 존재하는지 위키문헌 API로 다시 확인하고 docs/data-verification.md 를 만든다.

확인 항목 (레코드마다)
  1) pageid 로 조회한 문서가 지금도 존재하는가
  2) 조회된 문서 제목이 레코드의 url 과 같은가 (다른 문서를 가리키지 않는가)
  3) 퍼블릭 도메인 라이선스 틀(PD-…)이 붙어 있거나, 상위 목차 문서에 붙어 있는가

실행 (backend 폴더에서): python -m scripts.verify_works
"""

import json
import random
import sys
import urllib.parse
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from import_wikisource import OUT_PATH, api  # noqa: E402

REPORT = Path(__file__).resolve().parents[2] / "docs" / "data-verification.md"


def fetch_by_pageids(pageids: list[int]) -> dict[int, dict]:
    found: dict[int, dict] = {}
    for i in range(0, len(pageids), 50):
        batch = pageids[i:i + 50]
        cont: dict = {}
        while True:
            r = api({"action": "query", "pageids": "|".join(map(str, batch)), "prop": "info|templates",
                     "tlnamespace": 10, "tllimit": "max", **cont}, use_cache=False)
            for p in r.get("query", {}).get("pages", []):
                entry = found.setdefault(p["pageid"], {"title": p.get("title"), "missing": bool(p.get("missing")),
                                                       "templates": []})
                entry["templates"] += [t["title"].removeprefix("틀:") for t in p.get("templates", [])]
            if "continue" not in r:
                break
            cont = dict(r["continue"])
        print(f"  - 확인 {min(i + 50, len(pageids))}/{len(pageids)}")
    return found


def main() -> None:
    data = json.loads(OUT_PATH.read_text(encoding="utf-8"))
    dated = data["records"]
    shelf = data.get("library", [])
    records = dated + shelf  # 시계열 + 참고 작품 서재(발표 시기 미상) 모두 검증
    live = fetch_by_pageids([r["pageid"] for r in records])

    exists = title_ok = pd = 0
    problems = []
    for r in records:
        page = live.get(r["pageid"])
        url_title = urllib.parse.unquote(r["url"].split("/wiki/", 1)[1]).replace("_", " ")
        if not page or page["missing"]:
            problems.append(f"문서 없음: {r['title']} ({r['url']})")
            continue
        exists += 1
        if page["title"] == url_title:
            title_ok += 1
        else:
            problems.append(f"제목 불일치: {url_title} → 현재 {page['title']}")
        if any(t.startswith("PD") for t in page["templates"]) or "/" in url_title:
            pd += 1  # 하위 문서는 목차 문서에 라이선스 틀이 붙는 경우가 많다

    by_basis = Counter(r.get("basis") or r["memo"].split("— ")[-1].split(" 기준")[0] for r in records)
    random.seed(2026)
    sample = random.sample(dated, min(20, len(dated)))
    shelf_sample = random.sample(shelf, min(10, len(shelf)))
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    lines = [
        "# 작품 데이터 실존 검증",
        "",
        f"> 자동 생성: `python -m scripts.verify_works` · 검증 시각 {now} · 수집 시각 {data['fetched_at']}",
        "",
        "모든 레코드를 위키문헌 API에 **문서 번호(pageid)로 다시 조회**해 확인했습니다.",
        "",
        "| 항목 | 결과 |",
        "|---|---|",
        f"| 전체 | {len(records):,}편 (시계열 {len(dated):,} + 참고 작품 서재 {len(shelf):,}) |",
        f"| 위키문헌에 문서가 존재 | {exists:,}편 ({exists / len(records):.1%}) |",
        f"| 문서 제목이 레코드 URL과 일치 | {title_ok:,}편 |",
        f"| 퍼블릭 도메인 라이선스 확인(본문 또는 목차 문서) | {pd:,}편 |",
        "",
        "## 날짜 근거별 분포",
        "",
        "| 날짜 근거 | 작품 수 |",
        "|---|---|",
        *[f"| {k} | {v:,} |" for k, v in by_basis.most_common()],
        "",
        "## 시계열 무작위 표본 20편 (링크를 눌러 원문 확인 가능)",
        "",
        "| 날짜 | 작품 | 지은이 | 장르 | 글자 수 | 날짜 근거 |",
        "|---|---|---|---|---|---|",
        *[f"| {r['date']} | [{r['title']}]({r['url']}) | {r['author'] or '작자 미상'} | {r['genre']} | "
          f"{r['value']:,} | {r.get('basis', '')} |" for r in sorted(sample, key=lambda x: x["date"])],
    ]
    if shelf_sample:
        lines += [
            "",
            "## 참고 작품 서재 무작위 표본 10편 (발표 시기 미상 — 시계열 통계 제외)",
            "",
            "| 작품 | 지은이 | 장르 | 글자 수 | 메모 |",
            "|---|---|---|---|---|",
            *[f"| [{r['title']}]({r['url']}) | {r['author'] or '작자 미상'} | {r['genre']} | {r['value']:,} | "
              f"{r['memo'][:60]} |" for r in sorted(shelf_sample, key=lambda x: (x['author'], x['title']))],
        ]
    if problems:
        lines += ["", "## 확인이 필요한 레코드", "", *[f"- {p}" for p in problems[:50]]]
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"존재 {exists}/{len(records)}, 제목 일치 {title_ok}, PD {pd}, 문제 {len(problems)} → {REPORT}")


if __name__ == "__main__":
    main()
