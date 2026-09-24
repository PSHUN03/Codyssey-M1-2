"""수집한 시계열 데이터를 분석해 docs/data-analysis.md 리포트를 만든다.

서비스와 같은 함수(summary_service.build_summary / compute_trend)를 사용하므로
리포트의 숫자와 /api/data/summary 가 돌려주는 숫자가 같은 규칙으로 계산된다.

실행 (backend 폴더에서): python -m scripts.analyze_data
"""

import json
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services.summary_service import build_summary  # noqa: E402

DATA = Path(__file__).resolve().parent.parent / "data" / "wikisource_works.json"
OUT = Path(__file__).resolve().parents[2] / "docs" / "data-analysis.md"


def table(headers: list[str], rows: list[list]) -> str:
    lines = ["| " + " | ".join(headers) + " |", "|" + "|".join("---" for _ in headers) + "|"]
    lines += ["| " + " | ".join(str(c) for c in r) + " |" for r in rows]
    return "\n".join(lines)


def main() -> None:
    raw = json.loads(DATA.read_text(encoding="utf-8"))
    records = sorted(({**r, "id": str(r["pageid"])} for r in raw["records"]), key=lambda r: (r["date"], r["title"]))
    s = build_summary(records)
    m = s["metrics"]

    by_decade: dict[str, list[int]] = defaultdict(list)
    for r in records:
        by_decade[f"{r['date'][:3]}0년대"].append(r["value"])
    modern = [(k, v) for k, v in sorted(by_decade.items()) if k >= "1900년대"]
    pre_modern = sum(len(v) for k, v in by_decade.items() if k < "1900년대")

    by_genre: dict[str, list[int]] = defaultdict(list)
    for r in records:
        by_genre[r["genre"]].append(r["value"])

    precision = Counter(r.get("basis") or r["memo"].split("— ")[-1].split(" 기준")[0] for r in records)
    authors = Counter(r["author"] for r in records if r.get("author")).most_common(10)
    peak_decade = max(modern, key=lambda kv: len(kv[1]))

    md = f"""# 데이터 분석 리포트

> 자동 생성: `python -m scripts.analyze_data` · 원천: {raw['source']} · 수집 {raw['fetched_at']}

## 1. 데이터 개요

| 항목 | 값 |
|---|---|
| 기간 | {s['period']} |
| 레코드 수 | {s['count']:,}개 |
| 글자 수 합계 | {m['total']:,}자 (200자 원고지 약 {m['total'] // 200:,}매) |
| 평균 / 중앙값 | {m['average']:,.1f}자 / {m['median']:,.0f}자 |
| 최대 | {m['max']:,}자 — 《{s['longest']['title']}》 {s['longest']['author'] or ''} |
| 최소 | {m['min']:,}자 — 《{s['shortest']['title']}》 {s['shortest']['author'] or ''} |
| 표준편차 | {m['std']:,.1f}자 |

평균({m['average']:,.0f}자)이 중앙값({m['median']:,.0f}자)보다 훨씬 큰 것은 수십만 자짜리 장편소설 몇 편이 평균을 끌어올리기 때문이다.
그래서 요약에는 평균과 함께 **중앙값**을 넣어, AI가 "보통 길이"를 말할 때 장편에 휘둘리지 않게 했다.

## 2. 날짜 정보의 정밀도

| 날짜 근거 | 작품 수 |
|---|---|
{chr(10).join(f"| {k} | {v:,} |" for k, v in precision.most_common())}

날짜 근거 우선순위: 본문 끝 창작일 → 설명란 발표일 → 문서의 연도 분류 → 저자 문서의 작품 연보 → (시집 수록작) 수록 시집 간행일. 연도까지만 알려진 작품은 그해 1월 1일로 둔다. 같은 지은이의 같은 작품이 여러 판본에 있으면 가장 정확하고 이른 날짜 하나만 남겼다 ([`docs/data-verification.md`](data-verification.md) 참고).

## 3. 연대별 추이 (1900년대 이후, 이전 {pre_modern}편은 고시조 등)

{table(["연대", "작품 수", "평균 글자 수", "중앙값"], [[k, len(v), f"{statistics.fmean(v):,.0f}", f"{statistics.median(v):,.0f}"] for k, v in modern])}

- 작품이 가장 많은 연대: **{peak_decade[0]}** ({len(peak_decade[1]):,}편)
- 최근 추세 (서비스와 같은 규칙): **{s['trend']}**

## 4. 장르별 통계

{table(["장르", "작품 수", "평균 글자 수", "중앙값", "최대"], [[g, len(v), f"{statistics.fmean(v):,.0f}", f"{statistics.median(v):,.0f}", f"{max(v):,}"] for g, v in sorted(by_genre.items(), key=lambda kv: -len(kv[1]))])}

## 5. 많이 수록된 작가 Top 10

{table(["순위", "작가", "작품 수"], [[i + 1, a, c] for i, (a, c) in enumerate(authors)])}

## 6. 분석 → 요약 → 서비스 활용

1. **분석**: 위 통계를 `summary_service.build_summary()`가 매 요청마다 Firestore 데이터(서버 메모리 캐시)로 다시 계산한다.
2. **요약**: 기간·개수·합계/평균/중앙값/최대/최소/표준편차·최근 추세·장르/출처/단계 분포를 `GET /api/data/summary`로 제공한다.
3. **활용**:
   - `/api/chat`이 이 요약을 시스템 프롬프트에 넣어 "내 평균 분량 기준 개요", "적게 쓴 장르 도전" 같은 맞춤 답변을 만든다.
   - 프론트엔드 채팅 화면 오른쪽 패널과 통계 탭이 같은 요약을 보여 준다.
   - 더 자세한 정보(연대별 시계열, 작품 발췌)는 GPT가 도구(`get_statistics`, `search_works`)로 필요할 때만 가져온다.
"""
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(md, encoding="utf-8")
    print(f"리포트 생성: {OUT}")


if __name__ == "__main__":
    main()
