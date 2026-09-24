"""Pydantic 모델: 요청 본문 검증 + 응답 형태 정의 (Swagger 문서에도 그대로 노출된다)."""

from datetime import date as Date, datetime, timedelta
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

Genre = Literal[
    "시", "시조", "한시", "가사", "고전시가", "수필", "서간", "평론",
    "소설", "단편소설", "중편소설", "장편소설", "동화", "희곡", "판소리", "노래", "기타",
]
Stage = Literal["주제 선정", "구상·개요", "초고", "퇴고", "완성"]
ChatStage = Literal["자유", "주제 선정", "구상·개요", "초고", "퇴고"]

GENRES: tuple[str, ...] = Genre.__args__
STAGES: tuple[str, ...] = Stage.__args__


def _not_blank(v: Optional[str]) -> Optional[str]:
    if v is None:
        return v
    v = v.strip()
    if not v:
        raise ValueError("공백만 입력할 수 없습니다.")
    return v


def _not_future(v: Optional[Date]) -> Optional[Date]:
    if v is not None and v > Date.today() + timedelta(days=1):
        raise ValueError("미래 날짜는 기록할 수 없습니다.")
    return v


# ------------------------------------------------------------------ data (시계열 글쓰기 기록)

class DataCreate(BaseModel):
    """시계열 1건. 핵심 3필드(date, value, memo) + 글쓰기 도메인 부가 필드."""

    model_config = ConfigDict(json_schema_extra={"example": {
        "date": "2026-09-20", "value": 1240, "memo": "첫 문단을 새로 썼다. 도입이 너무 길어서 절반으로 줄임.",
        "genre": "수필", "title": "가을 산책", "stage": "초고",
    }})

    date: Date = Field(description="작성(발표)일 YYYY-MM-DD")
    value: int = Field(ge=0, le=2_000_000, description="글자 수(공백 제외)")
    memo: str = Field(min_length=1, max_length=500, description="작업 메모")
    genre: Genre = "기타"
    title: Optional[str] = Field(default=None, max_length=100)
    author: Optional[str] = Field(default=None, max_length=50)
    stage: Optional[Stage] = Field(default=None, description="글쓰기 단계")
    source: str = Field(default="직접 작성", max_length=30)
    excerpt: Optional[str] = Field(default=None, max_length=20000, description="본문 (직접 쓴 글은 전문, 가져온 작품은 앞부분)")
    url: Optional[str] = Field(default=None, max_length=300)

    _blank = field_validator("memo", "title", "author", "source")(_not_blank)
    _future = field_validator("date")(_not_future)


class DataUpdate(BaseModel):
    """부분 수정: 보낸 필드만 바뀐다."""

    model_config = ConfigDict(json_schema_extra={"example": {"value": 1580, "stage": "퇴고", "memo": "결말 문장 교체"}})

    date: Optional[Date] = None
    value: Optional[int] = Field(default=None, ge=0, le=2_000_000)
    memo: Optional[str] = Field(default=None, min_length=1, max_length=500)
    genre: Optional[Genre] = None
    title: Optional[str] = Field(default=None, max_length=100)
    author: Optional[str] = Field(default=None, max_length=50)
    stage: Optional[Stage] = None
    source: Optional[str] = Field(default=None, max_length=30)
    excerpt: Optional[str] = Field(default=None, max_length=20000)
    url: Optional[str] = Field(default=None, max_length=300)

    _blank = field_validator("memo", "title", "author", "source")(_not_blank)
    _future = field_validator("date")(_not_future)

    @model_validator(mode="after")
    def _at_least_one(self):
        if not self.model_dump(exclude_unset=True):
            raise ValueError("수정할 필드를 하나 이상 보내야 합니다.")
        return self


class DataOut(BaseModel):
    id: str
    date: str
    value: int
    memo: str
    genre: str = "기타"
    title: Optional[str] = None
    author: Optional[str] = None
    stage: Optional[str] = None
    source: str = "직접 작성"
    excerpt: Optional[str] = None
    url: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class DataListOut(BaseModel):
    total: int = Field(description="필터 적용 후 전체 개수")
    limit: int
    offset: int
    items: list[DataOut]


# ------------------------------------------------------------------ summary / statistics

class Metrics(BaseModel):
    total: int
    average: float
    median: float
    max: int
    min: int
    std: float


class RecordBrief(BaseModel):
    id: str
    date: str
    title: Optional[str] = None
    author: Optional[str] = None
    genre: str
    value: int
    stage: Optional[str] = None
    source: str


class GroupStat(BaseModel):
    key: str
    count: int
    average: float


class SummaryOut(BaseModel):
    period: str
    period_start: Optional[str]
    period_end: Optional[str]
    count: int
    metrics: Optional[Metrics]
    trend: str
    trend_direction: Literal["상승", "하락", "유지", "데이터 부족"]
    trend_change_pct: Optional[float]
    longest: Optional[RecordBrief]
    shortest: Optional[RecordBrief]
    by_genre: list[GroupStat]
    by_source: list[GroupStat]
    by_stage: list[GroupStat]
    recent: list[RecordBrief]
    generated_at: datetime


class SeriesPoint(BaseModel):
    period: str
    count: int
    total: int
    average: float


class StatisticsOut(BaseModel):
    group: Literal["year", "month", "decade"]
    filters: dict
    series: list[SeriesPoint]
    top_authors: list[GroupStat]
    active_days: int = Field(description="기록이 있는 서로 다른 날짜 수")
    longest_streak_days: int = Field(description="연속으로 기록한 최장 일수")
    busiest_period: Optional[SeriesPoint] = None


# ------------------------------------------------------------------ conversations

class ToolCallLog(BaseModel):
    name: str
    arguments: dict = {}
    reason: Optional[str] = None


class Message(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=20000)
    created_at: Optional[datetime] = None
    stage: Optional[str] = None
    tool_calls: Optional[list[ToolCallLog]] = None


class ConversationCreate(BaseModel):
    model_config = ConfigDict(json_schema_extra={"example": {
        "title": "가을 수필 주제 찾기",
        "messages": [
            {"role": "user", "content": "가을을 주제로 수필을 쓰고 싶어."},
            {"role": "assistant", "content": "좋아요! 가을에 대한 개인적인 기억부터 떠올려 볼까요?"},
        ],
    }})

    title: Optional[str] = Field(default=None, max_length=100)
    messages: list[Message] = Field(min_length=1, max_length=200)


class ConversationBrief(BaseModel):
    """목록 조회용: messages 는 포함하지 않는다 (전체는 GET /api/conversations/{id})."""

    id: str
    title: str
    message_count: int
    preview: str
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class ConversationOut(ConversationBrief):
    messages: list[Message]


# ------------------------------------------------------------------ chat

class ChatRequest(BaseModel):
    model_config = ConfigDict(json_schema_extra={"example": {
        "message": "요즘 내 글쓰기 기록을 보고, 이번 주에 써볼 만한 수필 주제 3개 추천해줘.",
        "stage": "주제 선정", "genre": "수필", "conversation_id": None,
    }})

    message: str = Field(min_length=1, max_length=8000)
    conversation_id: Optional[str] = Field(default=None, max_length=64, description="이어서 대화할 ID (없으면 새 대화)")
    stage: ChatStage = "자유"
    genre: Optional[Genre] = None

    _blank = field_validator("message")(_not_blank)


class ChatResponse(BaseModel):
    conversation_id: str
    reply: str
    tool_calls: list[ToolCallLog]
    summary_used: dict = Field(description="시스템 프롬프트에 주입된 요약(핵심 항목)")
    model: str
    usage: Optional[dict] = None


# ------------------------------------------------------------------ library (참고 작품 서재: 발표 시기 미상)

class LibraryWork(BaseModel):
    """날짜를 확인할 수 없는 실존 작품. 시계열(data)과 달리 date 가 없다."""

    value: int = Field(ge=0, le=2_000_000, description="글자 수(공백 제외)")
    memo: str = Field(min_length=1, max_length=500)
    genre: Genre = "기타"
    title: str = Field(min_length=1, max_length=100)
    author: Optional[str] = Field(default=None, max_length=50)
    source: str = Field(default="위키문헌", max_length=30)
    excerpt: Optional[str] = Field(default=None, max_length=2000)
    url: Optional[str] = Field(default=None, max_length=300)


class LibraryOut(LibraryWork):
    id: str
    date: Optional[str] = Field(default=None, description="항상 null (발표 시기 미상)")


class LibraryListOut(BaseModel):
    total: int
    limit: int
    offset: int
    by_genre: list[GroupStat]
    items: list[LibraryOut]


# ------------------------------------------------------------------ books (참고 도서 목록: KCISA 서지 정보)

class BookOut(BaseModel):
    id: str
    title: str
    author: Optional[str] = None
    publisher: Optional[str] = None
    genre: str
    issued_date: Optional[str] = Field(default=None, description="기관 등록·디지털 발행일 (원작 발표일 아님)")
    institution: Optional[str] = None
    collection: Optional[str] = None
    url: Optional[str] = None
    copies: int = 1
    wikisource_url: Optional[str] = Field(default=None, description="같은 작품의 위키문헌 원문 (중복 검토로 연결)")


class BookListOut(BaseModel):
    total: int
    limit: int
    offset: int
    by_genre: list[GroupStat]
    source: Optional[str] = None
    items: list[BookOut]
