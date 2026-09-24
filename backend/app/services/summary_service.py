"""시계열 분석: 전체 레코드 → 요약(프롬프트 주입용) / 기간별 통계(시각화용)."""

from __future__ import annotations

import statistics
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone

from . import data_service

TREND_THRESHOLD_PCT = 5.0


def _brief(r: dict) -> dict:
    return {
        "id": r["id"], "date": r.get("date", ""), "title": r.get("title"), "author": r.get("author"),
        "genre": r.get("genre", "기타"), "value": int(r.get("value", 0)), "stage": r.get("stage"),
        "source": r.get("source", "직접 작성"),
    }


def _group(records: list[dict], key: str) -> list[dict]:
    buckets: dict[str, list[int]] = defaultdict(list)
    for r in records:
        if r.get(key):
            buckets[r[key]].append(int(r.get("value", 0)))
    stats = [{"key": k, "count": len(v), "average": round(sum(v) / len(v), 1)} for k, v in buckets.items()]
    return sorted(stats, key=lambda s: -s["count"])


def compute_trend(records: list[dict]) -> tuple[str, str, float | None]:
    """최근 N건 평균 글자 수 vs 직전 N건 평균 글자 수 비교 (records 는 날짜 오름차순)."""
    n = len(records)
    if n < 10:
        return "데이터 부족 (10건 이상 필요)", "데이터 부족", None
    window = max(5, min(30, n // 5))
    recent = [int(r.get("value", 0)) for r in records[-window:]]
    prev = [int(r.get("value", 0)) for r in records[-2 * window:-window]]
    avg_recent, avg_prev = sum(recent) / len(recent), sum(prev) / len(prev)
    pct = 0.0 if avg_prev == 0 else (avg_recent - avg_prev) / avg_prev * 100
    direction = "상승" if pct >= TREND_THRESHOLD_PCT else "하락" if pct <= -TREND_THRESHOLD_PCT else "유지"
    text = f"{direction} (최근 {window}건 평균 {avg_recent:,.0f}자, 직전 {window}건 대비 {pct:+.1f}%)"
    return text, direction, round(pct, 1)


def build_summary(records: list[dict]) -> dict:
    values = [int(r.get("value", 0)) for r in records]
    trend, direction, pct = compute_trend(records)
    summary = {
        "period": f"{records[0]['date']} ~ {records[-1]['date']}" if records else "기록 없음",
        "period_start": records[0]["date"] if records else None,
        "period_end": records[-1]["date"] if records else None,
        "count": len(records),
        "metrics": None,
        "trend": trend,
        "trend_direction": direction,
        "trend_change_pct": pct,
        "longest": None,
        "shortest": None,
        "by_genre": _group(records, "genre"),
        "by_source": _group(records, "source"),
        "by_stage": _group(records, "stage"),
        "recent": [_brief(r) for r in reversed(records[-5:])],
        "generated_at": datetime.now(timezone.utc),
    }
    if values:
        summary["metrics"] = {
            "total": sum(values),
            "average": round(statistics.fmean(values), 1),
            "median": float(statistics.median(values)),
            "max": max(values),
            "min": min(values),
            "std": round(statistics.pstdev(values), 1),
        }
        summary["longest"] = _brief(max(records, key=lambda r: int(r.get("value", 0))))
        summary["shortest"] = _brief(min(records, key=lambda r: int(r.get("value", 0))))
    return summary


def get_summary(**filters) -> dict:
    records = data_service.filter_records(data_service.all_records(), **filters)
    return build_summary(records)


def _period_key(d: str, group: str) -> str:
    if group == "month":
        return d[:7]
    if group == "decade":
        return f"{d[:3]}0년대"
    return d[:4]


def _longest_streak(dates: list[str]) -> int:
    days = sorted({date.fromisoformat(d) for d in dates if d})
    best = cur = 1 if days else 0
    for a, b in zip(days, days[1:]):
        cur = cur + 1 if b - a == timedelta(days=1) else 1
        best = max(best, cur)
    return best


def get_statistics(group: str = "year", **filters) -> dict:
    records = data_service.filter_records(data_service.all_records(), **filters)
    buckets: dict[str, list[int]] = defaultdict(list)
    for r in records:
        buckets[_period_key(r["date"], group)].append(int(r.get("value", 0)))
    series = [
        {"period": k, "count": len(v), "total": sum(v), "average": round(sum(v) / len(v), 1)}
        for k, v in sorted(buckets.items())
    ]
    return {
        "group": group,
        "filters": {k: v for k, v in filters.items() if v is not None},
        "series": series,
        "top_authors": _group(records, "author")[:10],
        "active_days": len({r["date"] for r in records}),
        "longest_streak_days": _longest_streak([r["date"] for r in records]),
        "busiest_period": max(series, key=lambda s: s["count"]) if series else None,
    }
