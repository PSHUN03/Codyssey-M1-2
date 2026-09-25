"""원격 MCP 서버 (보너스: 멀티채널 연동).

배포된 백엔드의 `/mcp` 경로에서 MCP Streamable HTTP 로 도구를 노출한다.
Claude·ChatGPT 같은 외부 MCP 클라이언트가 URL 하나로 연결해, 웹 채팅의 Function Calling 과
같은 서비스 함수(services.tools / data_service)를 호출한다.

로컬 stdio 방식은 backend/mcp_server.py (REST API 를 호출하는 클라이언트형) 를 쓴다.
"""

from typing import Literal, Optional

from mcp.server.mcpserver import MCPServer
from mcp.server.transport_security import TransportSecuritySettings

from .config import settings
from .schemas import DataCreate
from .services import data_service, tools

mcp = MCPServer(
    name="geulbeot",
    title="글벗 — AI 글쓰기 코치 데이터",
    instructions=(
        "글쓰기 기록 DB(사용자 글쓰기 로그 + 위키문헌 한국 문학 작품)와 대화 기록을 조회한다. "
        "글쓰기 조언 전에 get_data_summary 로 사용자의 현황을 먼저 확인하라."
    ),
)


def _call(name: str, **args) -> dict:
    return tools.execute(name, {k: v for k, v in args.items() if v is not None})


@mcp.tool()
def get_data_summary(genre: Optional[str] = None, mine: Optional[bool] = None) -> dict:
    """글 기록 DB 요약: 기간, 개수, 글자 수 통계, 최근 추세, 장르·출처·단계 분포. mine=true 면 사용자가 쓴 기록만."""
    return _call("get_data_summary", genre=genre, mine=mine)


@mcp.tool()
def get_statistics(group: Literal["year", "month", "decade"] = "year", genre: Optional[str] = None,
                   mine: Optional[bool] = None) -> dict:
    """연도/월/연대별 작품 수·평균 글자 수 시계열, 다작 작가 순위, 연속 기록 일수."""
    return _call("get_statistics", group=group, genre=genre, mine=mine)


@mcp.tool()
def search_works(keyword: str, genre: Optional[str] = None, limit: int = 5) -> dict:
    """제목·지은이·메모·본문 발췌에서 키워드로 글을 찾는다 (참고 작품/예문 찾기)."""
    return _call("search_works", keyword=keyword, genre=genre, limit=limit)


@mcp.tool()
def search_books(keyword: str, genre: Optional[str] = None, source: Optional[str] = None, limit: int = 5) -> dict:
    """참고 자료(공유마당·구텐베르크·공공데이터 보충 자료 11종·KCISA)를 제목·저자·발행처로 찾는다 (목록 정보와 링크)."""
    return _call("search_books", keyword=keyword, genre=genre, source=source, limit=limit)


@mcp.tool()
def read_work(id: str) -> dict:
    """search_works 로 찾은 글(시계열 기록 또는 참고 작품 서재)의 저장된 본문을 읽는다."""
    return _call("read_work", id=id)


@mcp.tool()
def list_my_records(limit: int = 10) -> dict:
    """사용자가 직접 기록한 최근 글쓰기 기록(날짜, 글자 수, 단계, 메모)."""
    return _call("list_my_records", limit=limit)


@mcp.tool()
def list_conversations(limit: int = 10) -> dict:
    """웹에서 나눈 이전 대화 목록 (제목, 미리보기)."""
    return _call("list_conversations", limit=limit)


@mcp.tool()
def get_conversation(conversation_id: str) -> dict:
    """특정 대화의 최근 메시지를 불러온다."""
    return _call("get_conversation", conversation_id=conversation_id)


@mcp.tool()
def analyze_text(text: Optional[str] = None, id: Optional[str] = None) -> dict:
    """원고의 글자 수·원고지 매수·문장 길이·반복어·반복 어미·접속사를 측정한다 (퇴고용).
    원고를 직접 넘기거나(text), 저장된 글의 id 를 넘긴다."""
    return _call("analyze_text", text=text, id=id)


@mcp.tool()
def add_writing_record(date: str, value: int, memo: str, title: Optional[str] = None,
                       genre: str = "기타", stage: Optional[str] = None) -> dict:
    """글쓰기 기록을 추가한다. date=YYYY-MM-DD, value=글자 수(공백 제외), stage=주제 선정/구상·개요/초고/퇴고/완성."""
    payload = DataCreate(**{k: v for k, v in {"date": date, "value": value, "memo": memo, "title": title,
                                                "genre": genre, "stage": stage}.items() if v is not None})
    doc = data_service.create_record(payload)
    return {k: doc.get(k) for k in ("id", "date", "value", "memo", "title", "genre", "stage")}


def build_routes():
    """FastAPI 에 붙일 `/mcp` 라우트. 세션 관리자는 main.py 의 lifespan 에서 실행한다."""
    app = mcp.streamable_http_app(
        streamable_http_path="/mcp",
        stateless_http=True,   # Render 무료 티어(재시작·슬립)에서도 세션 없이 요청마다 처리
        json_response=True,
        transport_security=TransportSecuritySettings(
            enable_dns_rebinding_protection=True,
            allowed_hosts=settings.mcp_allowed_hosts,
            allowed_origins=settings.allowed_origins,
        ),
    )
    return app.routes
