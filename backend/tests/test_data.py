def test_crud_flow(client):
    body = {"date": "2026-09-20", "value": 1240, "memo": "첫 문단", "genre": "수필", "title": "가을 산책", "stage": "초고"}
    created = client.post("/api/data", json=body)
    assert created.status_code == 201
    rid = created.json()["id"]

    listed = client.get("/api/data").json()
    assert listed["total"] == 1 and listed["items"][0]["title"] == "가을 산책"

    updated = client.put(f"/api/data/{rid}", json={"value": 1580, "stage": "퇴고"}).json()
    assert updated["value"] == 1580 and updated["stage"] == "퇴고" and updated["memo"] == "첫 문단"

    assert client.delete(f"/api/data/{rid}").json() == {"deleted": True, "id": rid}
    assert client.delete(f"/api/data/{rid}").status_code == 404
    assert client.put(f"/api/data/{rid}", json={"value": 1}).status_code == 404


def test_validation_errors(client):
    bad = client.post("/api/data", json={"date": "2999-01-01", "value": -1, "memo": "   ", "genre": "랩"})
    assert bad.status_code == 422
    detail = bad.json()["detail"]
    assert "미래 날짜" in detail and "memo" in detail and "genre" in detail
    assert client.post("/api/data", json={"date": "2026-02-30", "value": 1, "memo": "x"}).status_code == 422
    assert client.put("/api/data/anything", json={}).status_code == 422  # 수정할 필드 없음


def test_filters_and_pagination(client, records):
    assert client.get("/api/data", params={"genre": "시"}).json()["total"] == 6
    assert client.get("/api/data", params={"q": "글 1"}).json()["total"] == 3  # 글 1, 글 10, 글 11
    page = client.get("/api/data", params={"limit": 5, "offset": 10, "order": "asc"}).json()
    assert page["total"] == 12 and [i["title"] for i in page["items"]] == ["글 10", "글 11"]
    assert client.get("/api/data", params={"mine": "false"}).json()["total"] == 0


def test_summary(client, records):
    s = client.get("/api/data/summary").json()
    assert s["period"] == "2026-08-01 ~ 2026-08-12"
    assert s["count"] == 12
    assert s["metrics"] == {"total": 1800, "average": 150.0, "median": 150.0, "max": 200, "min": 100, "std": 50.0}
    # 비교 창 5건: 최근 5건 평균 200 vs 직전 5건(100×4, 200×1) 평균 120 → +66.7%
    assert s["trend_direction"] == "상승" and s["trend_change_pct"] == 66.7
    assert {g["key"]: g["count"] for g in s["by_genre"]} == {"시": 6, "수필": 6}
    assert len(s["recent"]) == 5 and s["recent"][0]["date"] == "2026-08-12"


def test_summary_small_data(client):
    s = client.get("/api/data/summary").json()
    assert s["count"] == 0 and s["metrics"] is None and s["trend_direction"] == "데이터 부족"


def test_statistics_and_export(client, records):
    st = client.get("/api/data/statistics", params={"group": "month"}).json()
    assert st["series"] == [{"period": "2026-08", "count": 12, "total": 1800, "average": 150.0}]
    assert st["longest_streak_days"] == 12
    csv = client.get("/api/data/export", params={"format": "csv"})
    assert csv.headers["content-disposition"].startswith("attachment")
    assert csv.text.lstrip("﻿").splitlines()[0].startswith("id,date,value,memo")
    assert len(client.get("/api/data/export", params={"format": "json"}).json()) == 12


def test_firestore_quota_falls_back_to_snapshot(client, monkeypatch):
    """Firestore 가 한도 초과 등으로 실패하면 포함된 위키문헌 스냅샷으로 읽기 전용 응답을 한다."""
    from google.api_core.exceptions import ResourceExhausted

    from app import storage
    from app.services import data_service

    def boom(*_a, **_k):
        raise ResourceExhausted("Quota exceeded.")

    monkeypatch.setattr(storage.get_store(), "list_all", boom)
    data_service.invalidate()
    res = client.get("/api/data/summary")
    assert res.status_code == 200 and res.json()["count"] > 100
    assert data_service.degraded is True
    data_service.invalidate()
    data_service.degraded = False
