from typing import Optional

from fastapi import APIRouter, Query

from ..schemas import BookListOut, Genre
from ..services import books_service

router = APIRouter(prefix="/api/books", tags=["books (참고 도서 목록, KCISA)"])


@router.get("", response_model=BookListOut, summary="참고 도서 목록 조회 (KCISA 기관별 도서정보 중 문학 자료)")
def list_books(
    q: Optional[str] = Query(None, max_length=50, description="제목·저자·발행처 검색어"),
    genre: Optional[Genre] = None,
    limit: int = Query(20, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """한국문화정보원 문화 공공데이터광장의 '문화체육관광부 외_기관별 도서정보'에서 제목으로 고른 문학 자료.
    본문이 없는 서지 정보라 시계열·요약 통계에는 들어가지 않는다."""
    return books_service.list_books(q=q, genre=genre, limit=limit, offset=offset)
