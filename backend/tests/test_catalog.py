import json

from app.services import books_service, catalog_service, tools


def _write(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


def _sources(tmp_path, monkeypatch):
    """위키문헌 1편 + 공유마당 3건(1건은 위키문헌과 중복, 1건은 연번만 다른 중복) + KCISA 2건."""
    _write(tmp_path / "wikisource_works.json", {"records": [{"title": "가는 길", "author": "김소월"}], "library": []})
    _write(tmp_path / "gongu_works.json", {"works": [
        {"title": "가는 길", "author": "김소월", "genre": "시", "date": "1923-10-01", "basis": "공표 월", "url": "u1"},
        {"title": "승사주면(僧舍晝眠)", "author": "정철", "genre": "한시", "date": None, "basis": "발표 시기 미상", "url": "u2"},
        {"title": "승사주면(僧舍晝眠)", "author": "정철", "genre": "한시", "date": None, "basis": "발표 시기 미상", "url": "u3"},
    ]})
    kcisa = tmp_path / "kcisa_books.json"
    _write(kcisa, {"books": [
        {"title": "2008 연간희곡집", "author": "한국희곡작가협회", "genre": "희곡", "year": 2008, "year_basis": "제목의 발행 연도"},
        {"title": "무인도", "author": "극단 가교", "genre": "희곡", "year": 2017, "year_basis": "기관 등록 연도"},
    ]})
    monkeypatch.setattr(catalog_service, "DATA", tmp_path)
    monkeypatch.setattr(books_service, "BOOKS_PATH", kcisa)
    for f in (books_service._load, catalog_service._static, catalog_service._wikisource_keys):
        f.cache_clear()
    catalog_service.invalidate()


def _clear():
    for f in (books_service._load, catalog_service._static, catalog_service._wikisource_keys):
        f.cache_clear()
    catalog_service.invalidate()


def test_catalog_dedupes_across_and_within_sources(client, tmp_path, monkeypatch, records):
    _sources(tmp_path, monkeypatch)
    stats = client.get("/api/catalog/stats").json()
    by = {s["key"]: s for s in stats["sources"]}
    assert by["gongu"]["total"] == 1 and by["gongu"]["duplicates_removed"] == 2  # 위키문헌 중복 1 + 연번 중복 1
    assert by["kcisa"]["total"] == 2 and by["mine"]["total"] == 12
    assert stats["total"] == 12 + 1 + 2 and stats["undated_by_source"] == {"gongu": 1}
    periods = {p["period"]: p["by_source"] for p in stats["series"]}
    assert periods["2000년대"] == {"kcisa": 1} and periods["2010년대"] == {"kcisa": 1}
    assert periods["2020년대"] == {"mine": 12}
    assert client.get("/api/catalog/stats", params={"group": "century"}).json()["series"][-1]["period"] == "21세기"
    _clear()


def test_catalog_search_and_tool(client, tmp_path, monkeypatch):
    _sources(tmp_path, monkeypatch)
    res = client.get("/api/catalog", params={"source": "kcisa", "q": "희곡"}).json()
    assert res["total"] == 1 and res["items"][0]["year"] == 2008 and res["items"][0]["source_label"] == "KCISA 도서정보"
    found = tools.execute("search_books", {"keyword": "승사주면"})
    assert found["total"] == 1 and found["items"][0]["source_label"] == "공유마당"
    assert client.get("/api/catalog", params={"source": "wikisource"}).status_code == 422  # 위키문헌은 /api/data
    _clear()
