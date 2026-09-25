from typing import Literal, Optional

from fastapi import APIRouter, Query

from ..schemas import CatalogListOut, CatalogStatsOut, Genre
from ..services import catalog_service

router = APIRouter(prefix="/api/catalog", tags=["catalog (모든 출처 통합 목록·통계)"])

ReferenceSource = Literal["gutenberg", "gongu", "lti", "nlk", "kcisa"]


@router.get("/stats", response_model=CatalogStatsOut, summary="통합 통계 (모든 출처, 중복 제외)")
def catalog_stats(
    group: Literal["decade", "century"] = "decade",
    genre: Optional[Genre] = None,
):
    """위키문헌(시계열·서재)·직접 작성·구텐베르크·공유마당·번역원·국립중앙도서관·KCISA 를 합친 통계.
    같은 작가·같은 제목은 본문이 있는 출처를 우선해 한 번만 센다. 발표 시기 미상은 `undated_by_source` 로 따로 센다."""
    return catalog_service.get_stats(group=group, genre=genre)


@router.get("", response_model=CatalogListOut, summary="참고 자료 목록 (파일 출처 통합 검색)")
def list_catalog(
    q: Optional[str] = Query(None, max_length=50, description="제목·저자·발행처·요약 검색어"),
    source: Optional[ReferenceSource] = None,
    genre: Optional[Genre] = None,
    limit: int = Query(20, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """구텐베르크·공유마당·한국문학번역원·국립중앙도서관·KCISA 자료 (위키문헌은 /api/data, /api/library)."""
    return catalog_service.list_entries(q=q, source=source, genre=genre, limit=limit, offset=offset)
