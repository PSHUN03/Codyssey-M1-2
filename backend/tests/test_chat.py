import json
from types import SimpleNamespace

import pytest

from app.services import chat_service, tools


class FakeCompletions:
    """1번째 호출: search_works 도구 요청 → 2번째 호출: 최종 답변."""

    def __init__(self):
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        if len(self.calls) == 1:
            call = SimpleNamespace(id="call_1", type="function", function=SimpleNamespace(
                name="search_works", arguments=json.dumps({"keyword": "글 1", "reason": "예문을 찾기 위해"})))
            message = SimpleNamespace(content=None, tool_calls=[call], model_dump=lambda **_: {
                "role": "assistant", "tool_calls": [{"id": "call_1", "type": "function",
                                                     "function": {"name": "search_works", "arguments": "{}"}}]})
        else:
            message = SimpleNamespace(content="요약을 보니 평균 150자예요.", tool_calls=None)
        usage = SimpleNamespace(prompt_tokens=10, completion_tokens=5)
        return SimpleNamespace(choices=[SimpleNamespace(message=message)], usage=usage, model="fake-gpt")


@pytest.fixture
def fake_gpt(monkeypatch):
    completions = FakeCompletions()
    client = SimpleNamespace(chat=SimpleNamespace(completions=completions))
    monkeypatch.setattr(chat_service, "_client", lambda: client)
    return completions


def test_chat_injects_summary_calls_tool_and_saves(client, records, fake_gpt):
    res = client.post("/api/chat", json={"message": "평균 알려줘", "stage": "퇴고", "genre": "수필"})
    assert res.status_code == 200
    body = res.json()

    # ① 요약 조회 → ② 시스템 프롬프트 주입
    system = fake_gpt.calls[0]["messages"][0]
    assert system["role"] == "system"
    assert "데이터 기간: 2026-08-01 ~ 2026-08-12" in system["content"]
    assert "총 레코드: 12개" in system["content"] and "평균 150자" in system["content"]
    assert "[현재 작업 단계: 퇴고]" in system["content"] and "선택한 장르: 수필" in system["content"]
    assert fake_gpt.calls[0]["max_completion_tokens"] > 0

    # ③ 도구 실행 결과가 두 번째 호출에 role=tool 로 전달
    tool_msg = fake_gpt.calls[1]["messages"][-1]
    assert tool_msg["role"] == "tool" and "글 1" in tool_msg["content"]
    assert body["tool_calls"] == [{"name": "search_works", "arguments": {"keyword": "글 1"}, "reason": "예문을 찾기 위해"}]
    assert body["summary_used"]["count"] == 12

    # ④ 대화 자동 저장 + 이어서 대화
    conv = client.get(f"/api/conversations/{body['conversation_id']}").json()
    assert [m["role"] for m in conv["messages"]] == ["user", "assistant"]
    assert conv["messages"][1]["tool_calls"][0]["name"] == "search_works"

    fake_gpt.calls.clear()
    again = client.post("/api/chat", json={"message": "고마워", "conversation_id": body["conversation_id"]})
    assert again.json()["conversation_id"] == body["conversation_id"]
    assert [m["role"] for m in fake_gpt.calls[0]["messages"]][:3] == ["system", "user", "assistant"]
    assert client.get(f"/api/conversations/{body['conversation_id']}").json()["message_count"] == 4


def test_chat_errors(client, fake_gpt):
    assert client.post("/api/chat", json={"message": "   "}).status_code == 422
    assert client.post("/api/chat", json={"message": "hi", "conversation_id": "nope"}).status_code == 404


def test_chat_rate_limit(client, fake_gpt):
    codes = [client.post("/api/chat", json={"message": f"질문 {i}"}).status_code for i in range(4)]
    assert codes == [200, 200, 200, 429]  # 테스트 설정: 분당 3회


def test_conversation_api(client):
    msgs = [{"role": "user", "content": "가을 수필을 쓰고 싶어"}, {"role": "assistant", "content": "좋아요"}]
    created = client.post("/api/conversations", json={"messages": msgs}).json()
    assert created["title"] == "가을 수필을 쓰고 싶어" and created["message_count"] == 2
    listed = client.get("/api/conversations").json()
    assert "messages" not in listed[0] and listed[0]["preview"] == "좋아요"
    assert client.get(f"/api/conversations/{created['id']}").json()["messages"][0]["content"] == msgs[0]["content"]
    assert client.delete(f"/api/conversations/{created['id']}").status_code == 200
    assert client.get(f"/api/conversations/{created['id']}").status_code == 404
    assert client.post("/api/conversations", json={"messages": []}).status_code == 422


def test_analyze_text():
    r = tools.analyze_text("그날 나는 정말 피곤했다. 그리고 버스를 탔다. 그리고 창밖을 봤다. 그리고 울었다.")
    assert r["sentences"] == 4
    assert r["conjunctions"] == {"그리고": 3}
    assert r["chars_without_spaces"] == len("그날나는정말피곤했다.그리고버스를탔다.그리고창밖을봤다.그리고울었다.")


def test_search_works_ranks_title_matches_first(client):
    for i, (title, memo) in enumerate([("가을밤", "고향 생각이 나는 밤"), ("고향", "고향을 떠나며"), ("먼 길", "메모")]):
        client.post("/api/data", json={"date": f"2026-01-0{i + 1}", "value": 100, "memo": memo, "title": title,
                                       "genre": "시"})
    items = tools.execute("search_works", {"keyword": "고향", "limit": 5})["items"]
    assert [i["title"] for i in items] == ["고향", "가을밤"]
