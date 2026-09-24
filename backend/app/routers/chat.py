from fastapi import APIRouter, Depends, HTTPException

from ..rate_limit import check_chat_quota
from ..schemas import ChatRequest, ChatResponse
from ..services import chat_service

router = APIRouter(prefix="/api", tags=["chat (AI 글쓰기 코치)"])


@router.post(
    "/chat",
    response_model=ChatResponse,
    summary="AI 대화 (데이터 요약 컨텍스트 주입 + 자동 저장)",
    dependencies=[Depends(check_chat_quota)],
    responses={429: {"description": "요청 횟수 제한 초과 (IP별 분당 / 하루 전체)"}},
)
def chat(payload: ChatRequest):
    """① 데이터 요약 조회 → ② 시스템 프롬프트에 삽입 → ③ GPT 호출(필요 시 도구 호출) → ④ conversations 자동 저장.

    `conversation_id` 를 보내면 해당 대화에 이어서 저장하고, 없으면 새 대화를 만든다.
    비용 보호를 위해 IP별 분당 요청 수와 서버 전체 하루 요청 수를 제한한다.
    """
    try:
        return chat_service.chat(payload)
    except chat_service.ChatError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail) from e
