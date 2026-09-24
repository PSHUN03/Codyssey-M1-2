import json

from app.services import books_service, tools


def _books_file(tmp_path, monkeypatch):
    path = tmp_path / "kcisa_books.json"
    path.write_text(json.dumps({"source": "테스트", "books": [
        {"title": "하늘과 바람과 별과 시", "author": "윤동주", "publisher": "정음사", "genre": "시",
         "institution": "한국문화예술위원회", "collection": "예술자료원-소장자료", "url": "https://example.org/1", "copies": 2},
        {"title": "고도를 기다리며", "author": "극단 대하", "publisher": None, "genre": "희곡",
         "institution": "한국문화예술위원회", "collection": "예술자료원-소장자료", "url": None, "copies": 1},
    ]}, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(books_service, "BOOKS_PATH", path)
    books_service._load.cache_clear()


def test_books_endpoint_and_tool(client, tmp_path, monkeypatch):
    _books_file(tmp_path, monkeypatch)
    res = client.get("/api/books", params={"q": "윤동주"}).json()
    assert res["total"] == 1 and res["items"][0]["copies"] == 2
    assert client.get("/api/books", params={"genre": "희곡"}).json()["total"] == 1
    found = tools.execute("search_books", {"keyword": "고도"})
    assert found["items"][0]["title"] == "고도를 기다리며" and "본문" in found["note"]
    assert client.get("/api/data/summary").json()["count"] == 0  # 시계열 통계에 들어가지 않는다
    books_service._load.cache_clear()
