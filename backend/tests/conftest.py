"""테스트는 Firebase/OpenAI 없이 돈다: 메모리 저장소 + 가짜 GPT 클라이언트."""

import os

os.environ["STORAGE_BACKEND"] = "memory"
os.environ["OPENAI_API_KEY"] = "test-key"
os.environ["CHAT_RATE_PER_MINUTE"] = "3"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

import main  # noqa: E402
from app import rate_limit, storage  # noqa: E402
from app.services import data_service  # noqa: E402


@pytest.fixture
def client():
    storage.get_store.cache_clear()
    data_service.invalidate()
    rate_limit.reset()
    # with 문 없이 만들면 lifespan(1,500여 편 시드)이 돌지 않아 빈 저장소에서 시작한다.
    return TestClient(main.app)


@pytest.fixture
def records(client):
    """날짜가 다른 기록 12건 (앞 6건 100자, 뒤 6건 200자 → 추세 '상승')."""
    ids = []
    for i in range(12):
        body = {"date": f"2026-08-{i + 1:02d}", "value": 100 if i < 6 else 200, "memo": f"기록 {i}",
                "genre": "시" if i % 2 else "수필", "title": f"글 {i}", "stage": "초고"}
        ids.append(client.post("/api/data", json=body).json()["id"])
    return ids
