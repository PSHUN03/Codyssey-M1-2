from fastapi import APIRouter, HTTPException, status

from ..schemas import ConversationBrief, ConversationCreate, ConversationOut
from ..services import conversation_service

router = APIRouter(prefix="/api/conversations", tags=["conversations (대화 기록)"])


@router.post("", response_model=ConversationOut, status_code=status.HTTP_201_CREATED, summary="대화 저장")
def create_conversation(payload: ConversationCreate):
    return conversation_service.create_conversation(payload.messages, payload.title)


@router.get("", response_model=list[ConversationBrief], summary="대화 목록 조회 (messages 미포함)")
def list_conversations():
    """최근 수정순. 응답에는 messages 를 넣지 않고 message_count/preview 만 준다.
    전체 메시지는 GET /api/conversations/{id} 로 불러온다."""
    return conversation_service.list_conversations()


@router.get("/{conversation_id}", response_model=ConversationOut, summary="특정 대화 불러오기 (전체 messages)")
def get_conversation(conversation_id: str):
    conv = conversation_service.get_conversation(conversation_id)
    if conv is None:
        raise HTTPException(status_code=404, detail="해당 대화를 찾을 수 없습니다.")
    return conv


@router.delete("/{conversation_id}", summary="대화 삭제")
def delete_conversation(conversation_id: str):
    if not conversation_service.delete_conversation(conversation_id):
        raise HTTPException(status_code=404, detail="해당 대화를 찾을 수 없습니다.")
    return {"deleted": True, "id": conversation_id}
