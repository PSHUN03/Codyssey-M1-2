import csv
import io
import json
from datetime import datetime
from typing import Literal, Optional

from fastapi import APIRouter, HTTPException, Query, Response, status

from ..schemas import DataCreate, DataListOut, DataOut, DataUpdate, Genre, Stage, StatisticsOut, SummaryOut
from ..services import data_service, summary_service

router = APIRouter(prefix="/api/data", tags=["data (글쓰기 기록)"])

EXPORT_FIELDS = ["id", "date", "value", "memo", "genre", "title", "author", "stage", "source", "url"]


def _filters(genre, source, stage, q, start, end, mine) -> dict:
    return {"genre": genre, "source": source, "stage": stage, "q": q, "start": start, "end": end, "mine": mine}


@router.post("", response_model=DataOut, status_code=status.HTTP_201_CREATED, summary="새 데이터 추가")
def create_data(payload: DataCreate):
    return data_service.create_record(payload)


@router.get("", response_model=DataListOut, summary="데이터 목록 조회 (필터·페이지네이션)")
def list_data(
    genre: Optional[Genre] = None,
    source: Optional[str] = Query(None, max_length=30, description="예: 위키문헌, 직접 작성"),
    stage: Optional[Stage] = None,
    q: Optional[str] = Query(None, max_length=50, description="제목·지은이·메모·발췌 검색어"),
    start: Optional[str] = Query(None, pattern=r"^\d{4}-\d{2}-\d{2}$"),
    end: Optional[str] = Query(None, pattern=r"^\d{4}-\d{2}-\d{2}$"),
    mine: Optional[bool] = Query(None, description="true: 직접 작성한 기록만 / false: 가져온 작품만"),
    order: Literal["asc", "desc"] = "desc",
    limit: int = Query(20, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    total, items = data_service.list_records(
        order=order, limit=limit, offset=offset, **_filters(genre, source, stage, q, start, end, mine)
    )
    return {"total": total, "limit": limit, "offset": offset, "items": items}


@router.get("/summary", response_model=SummaryOut, summary="데이터 요약 (프롬프트 주입용)")
def data_summary(
    genre: Optional[Genre] = None,
    source: Optional[str] = Query(None, max_length=30),
    mine: Optional[bool] = None,
):
    """기간·개수·글자 수 통계(합계/평균/중앙값/최대/최소/표준편차)·최근 추세·장르/출처/단계 분포.

    추세: 날짜순으로 정렬한 뒤 최근 N건 평균과 직전 N건 평균을 비교(±5% 이상이면 상승/하락).
    """
    return summary_service.get_summary(genre=genre, source=source, mine=mine)


@router.get("/statistics", response_model=StatisticsOut, summary="기간별 통계 (시각화용, 보너스)")
def data_statistics(
    group: Literal["year", "month", "decade"] = "year",
    genre: Optional[Genre] = None,
    source: Optional[str] = Query(None, max_length=30),
    mine: Optional[bool] = None,
):
    return summary_service.get_statistics(group=group, genre=genre, source=source, mine=mine)


@router.get("/export", summary="데이터 내보내기 (CSV/JSON 다운로드, 보너스)")
def export_data(
    format: Literal["csv", "json"] = "csv",
    genre: Optional[Genre] = None,
    source: Optional[str] = Query(None, max_length=30),
    mine: Optional[bool] = None,
):
    _, records = data_service.list_records(order="asc", limit=10**6, genre=genre, source=source, mine=mine)
    rows = [{k: r.get(k, "") for k in EXPORT_FIELDS} for r in records]
    stamp = datetime.now().strftime("%Y%m%d")
    if format == "json":
        body = json.dumps(rows, ensure_ascii=False, indent=1)
        media = "application/json; charset=utf-8"
    else:
        buf = io.StringIO()
        writer = csv.DictWriter(buf, fieldnames=EXPORT_FIELDS)
        writer.writeheader()
        writer.writerows(rows)
        body = "﻿" + buf.getvalue()  # BOM: 엑셀에서 한글이 깨지지 않도록
        media = "text/csv; charset=utf-8"
    return Response(
        content=body.encode("utf-8"),
        media_type=media,
        headers={"Content-Disposition": f'attachment; filename="writing-data-{stamp}.{format}"'},
    )


@router.get("/{record_id}", response_model=DataOut, summary="데이터 1건 조회")
def get_data(record_id: str):
    doc = data_service.get_record(record_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="해당 데이터를 찾을 수 없습니다.")
    return doc


@router.put("/{record_id}", response_model=DataOut, summary="데이터 수정 (보낸 필드만 변경)")
def update_data(record_id: str, payload: DataUpdate):
    doc = data_service.update_record(record_id, payload)
    if doc is None:
        raise HTTPException(status_code=404, detail="해당 데이터를 찾을 수 없습니다.")
    return doc


@router.delete("/{record_id}", summary="데이터 삭제")
def delete_data(record_id: str):
    if not data_service.delete_record(record_id):
        raise HTTPException(status_code=404, detail="해당 데이터를 찾을 수 없습니다.")
    return {"deleted": True, "id": record_id}
