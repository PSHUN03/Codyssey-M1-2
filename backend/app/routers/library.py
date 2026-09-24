from typing import Optional

from fastapi import APIRouter, Query

from ..schemas import Genre, LibraryListOut
from ..services import library_service

router = APIRouter(prefix="/api/library", tags=["library (참고 작품 서재)"])


@router.get("", response_model=LibraryListOut, summary="참고 작품 서재 조회 (발표 시기 미상 작품)")
def list_library(
    q: Optional[str] = Query(None, max_length=50, description="제목·지은이·메모·발췌 검색어"),
    genre: Optional[Genre] = None,
    limit: int = Query(20, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """위키문헌에 실제로 있지만 발표 시기를 확인할 수 없는 작품. 시계열 요약·통계에는 들어가지 않고
    AI 작품 검색(search_works)과 이 목록에서만 쓰인다."""
    return library_service.list_works(q=q, genre=genre, limit=limit, offset=offset)
