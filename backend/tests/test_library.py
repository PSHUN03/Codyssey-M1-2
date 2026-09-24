from app.firebase import LIBRARY_COLLECTION
from app.services import library_service, tools
from app.storage import get_store


def _shelf():
    store = get_store()
    for title, author in [("고향", "정지용"), ("가는 봄 삼월", "김소월")]:
        store.add(LIBRARY_COLLECTION, {"title": title, "author": author, "genre": "시", "value": 100,
                                       "memo": f"《{title}》 {author} — 발표 시기 미상 기준", "source": "위키문헌",
                                       "excerpt": f"{title} 본문"})
    library_service.invalidate()


def test_library_endpoint(client):
    _shelf()
    res = client.get("/api/library", params={"q": "김소월"}).json()
    assert res["total"] == 1 and res["items"][0]["date"] is None
    assert client.get("/api/library").json()["by_genre"] == [{"key": "시", "count": 2, "average": 100.0}]


def test_library_not_in_summary_but_in_search(client, records):
    _shelf()
    assert client.get("/api/data/summary").json()["count"] == 12  # 시계열 통계에는 들어가지 않는다
    items = tools.execute("search_works", {"keyword": "고향"})["items"]
    assert items[0]["title"] == "고향" and items[0]["date"] is None and items[0]["shelf"] == "참고 작품 서재"
    assert tools.execute("search_works", {"keyword": "고향", "mine": True})["items"] == []


def test_read_work_returns_saved_text(client):
    rid = client.post("/api/data", json={"date": "2026-09-20", "value": 12, "memo": "초고", "title": "내 글",
                                         "excerpt": "전문 " * 3000}).json()["id"]  # 2,000자 넘는 본문도 저장
    work = tools.execute("read_work", {"id": rid})
    assert work["title"] == "내 글" and work["text"].startswith("전문") and work["text_is_partial"] is False
    assert "error" in tools.execute("read_work", {"id": "없음"})


def test_analyze_text_by_saved_id(client):
    rid = client.post("/api/data", json={"date": "2026-09-20", "value": 10, "memo": "초고", "title": "내 글",
                                         "excerpt": "그리고 갔다. 그리고 왔다. 그리고 잤다."}).json()["id"]
    assert tools.execute("analyze_text", {"id": rid})["conjunctions"] == {"그리고": 3}
    assert "error" in tools.execute("analyze_text", {})
