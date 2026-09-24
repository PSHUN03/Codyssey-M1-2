"""글벗 MCP 서버 (보너스: 멀티채널 연동).

웹 채팅의 Function Calling 과 같은 기능을 MCP 도구로 노출한다. 내부 DB 에 직접 붙지 않고
배포된 REST API 를 호출하므로, Claude Desktop / Claude Code 같은 외부 MCP 클라이언트에서도
웹과 똑같은 데이터·규칙(검증, 캐시, 저장)을 거친다.

실행 (stdio):
    GEULBEOT_API_URL=https://<render-app>.onrender.com python mcp_server.py
"""

import os
from typing import Literal, Optional

import httpx
from mcp.server.mcpserver import MCPServer

API_URL = os.getenv("GEULBEOT_API_URL", "http://localhost:8000").rstrip("/")

server = MCPServer(
    name="geulbeot",
    title="글벗 — AI 글쓰기 코치 데이터",
    instructions=(
        "글쓰기 기록 DB(사용자 글쓰기 로그 + 위키문헌 한국 근대문학)와 대화 기록을 조회한다. "
        "글쓰기 조언 전에 get_data_summary 로 사용자의 현황을 먼저 확인하라."
    ),
)


def _get(path: str, params: Optional[dict] = None):
    params = {k: v for k, v in (params or {}).items() if v is not None}
    # Render 무료 티어 콜드스타트 대비 넉넉한 타임아웃
    r = httpx.get(f"{API_URL}{path}", params=params, timeout=90)
    r.raise_for_status()
    return r.json()


@server.tool()
def get_data_summary(genre: Optional[str] = None, mine: Optional[bool] = None) -> dict:
    """글 기록 DB 요약: 기간, 개수, 글자 수 통계(평균/최대/최소 등), 최근 추세, 장르·출처·단계 분포.

    genre: 시, 시조, 수필, 단편소설, 중편소설, 장편소설, 동화, 희곡, 기타 중 하나로 한정
    mine: true 면 사용자가 직접 기록한 글만
    """
    s = _get("/api/data/summary", {"genre": genre, "mine": mine})
    s.pop("generated_at", None)
    return s


@server.tool()
def get_statistics(group: Literal["year", "month", "decade"] = "year", genre: Optional[str] = None,
                   mine: Optional[bool] = None) -> dict:
    """연도/월/연대별 작품 수·평균 글자 수 시계열과 다작 작가 순위, 연속 기록 일수."""
    return _get("/api/data/statistics", {"group": group, "genre": genre, "mine": mine})


@server.tool()
def search_works(keyword: str, genre: Optional[str] = None, limit: int = 5) -> list[dict]:
    """제목·지은이·메모·본문 발췌에서 키워드로 글을 찾는다 (참고 작품/예문 찾기)."""
    res = _get("/api/data", {"q": keyword, "genre": genre, "limit": max(1, min(limit, 10))})
    return [
        {k: r.get(k) for k in ("date", "title", "author", "genre", "value", "memo", "excerpt", "url") if r.get(k)}
        for r in res["items"]
    ]


@server.tool()
def list_my_records(limit: int = 10) -> list[dict]:
    """사용자가 직접 기록한 최근 글쓰기 기록(날짜, 글자 수, 단계, 메모)."""
    res = _get("/api/data", {"mine": True, "limit": max(1, min(limit, 50))})
    return [{k: r.get(k) for k in ("id", "date", "title", "genre", "stage", "value", "memo")} for r in res["items"]]


@server.tool()
def list_conversations(limit: int = 10) -> list[dict]:
    """웹에서 나눈 이전 대화 목록 (제목, 미리보기, 메시지 수)."""
    return _get("/api/conversations")[: max(1, min(limit, 50))]


@server.tool()
def get_conversation(conversation_id: str) -> dict:
    """특정 대화의 전체 메시지를 불러온다."""
    return _get(f"/api/conversations/{conversation_id}")


@server.tool()
def add_writing_record(date: str, value: int, memo: str, title: Optional[str] = None,
                       genre: str = "기타", stage: Optional[str] = None) -> dict:
    """오늘의 글쓰기 기록을 추가한다. date=YYYY-MM-DD, value=글자 수(공백 제외),
    stage=주제 선정/구상·개요/초고/퇴고/완성 중 하나."""
    body = {"date": date, "value": value, "memo": memo, "title": title, "genre": genre, "stage": stage}
    r = httpx.post(f"{API_URL}/api/data", json={k: v for k, v in body.items() if v is not None}, timeout=90)
    if r.status_code >= 400:
        return {"error": r.json().get("detail", r.text)}
    return r.json()


if __name__ == "__main__":
    server.run("stdio")
