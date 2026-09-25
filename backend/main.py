"""글벗 API — 데이터 기반 AI 글쓰기 코치 (FastAPI 진입점).

실행: uvicorn main:app --reload
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from google.api_core.exceptions import GoogleAPIError

from app.config import settings
from app.firebase import FirebaseNotConfigured
from app.mcp_remote import build_routes as mcp_routes, mcp
from app.routers import books, catalog, chat, conversations, data, library

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("writing-assistant")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("storage=%s model=%s origins=%s", settings.storage_backend, settings.openai_model,
                settings.allowed_origins)
    if settings.storage_backend == "memory":
        from app.seed import seed
        from app.storage import get_store

        logger.info("메모리 저장소 시드: %s", seed(get_store()))
    async with mcp.session_manager.run():  # 원격 MCP(/mcp) 요청 처리기
        yield


app = FastAPI(
    title="글벗 API — 데이터 기반 AI 글쓰기 코치",
    description=(
        "주제 선정 → 구상·개요 → 초고 → 퇴고까지, 장르에 상관없이 글쓰기를 돕는 AI 비서의 백엔드입니다.\n\n"
        "- **data**: 날짜별 글쓰기 기록(date, value=글자 수, memo) CRUD + 요약/통계/내보내기\n"
        "- **conversations**: 대화 기록 저장·목록·불러오기·삭제\n"
        "- **chat**: 데이터 요약을 시스템 프롬프트에 주입한 GPT 대화 (Function Calling 포함)\n"
        "- **MCP**: `POST /mcp` — 같은 기능을 외부 MCP 클라이언트용 도구로 노출 (Streamable HTTP)\n\n"
        "※ 무료 서버(Render)는 15분간 요청이 없으면 잠들어 첫 요청이 30~60초 걸릴 수 있습니다."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_origin_regex=r"https://.*\.vercel\.app" if "*.vercel.app" in settings.allowed_origins else None,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type"],
    expose_headers=["Content-Disposition"],
)


@app.exception_handler(RequestValidationError)
async def validation_handler(request: Request, exc: RequestValidationError):
    errors = exc.errors()
    readable = "; ".join(
        f"{'.'.join(str(p) for p in e['loc'] if p != 'body')}: {e['msg']}" for e in errors
    )
    return JSONResponse(
        status_code=422,
        content={"detail": f"입력값을 확인해 주세요 — {readable}",
                 "errors": [{"loc": e["loc"], "msg": e["msg"]} for e in errors]},
    )


@app.exception_handler(FirebaseNotConfigured)
async def firebase_handler(request: Request, exc: FirebaseNotConfigured):
    return JSONResponse(status_code=503, content={"detail": str(exc)})


@app.exception_handler(GoogleAPIError)
async def firestore_handler(request: Request, exc: GoogleAPIError):
    logger.exception("Firestore 오류")
    return JSONResponse(status_code=503, content={"detail": "데이터베이스 요청이 실패했습니다. 잠시 후 다시 시도해 주세요."})


@app.get("/", tags=["health"], summary="서비스 정보")
def root():
    return {"service": "글벗 API", "docs": "/docs", "health": "/health"}


@app.get("/health", tags=["health"], summary="헬스 체크 (콜드스타트 깨우기용)")
def health():
    from app.services import data_service

    if settings.storage_backend == "firestore":
        data_service.all_records()  # 깨울 때 미리 읽어 두고(캐시), Firestore 이상 여부를 degraded 로 알린다
    return {"status": "ok", "storage": settings.storage_backend, "ai_ready": bool(settings.openai_api_key),
            "degraded": data_service.degraded}


app.include_router(data.router)
app.include_router(conversations.router)
app.include_router(library.router)
app.include_router(books.router)
app.include_router(catalog.router)
app.include_router(chat.router)

# 원격 MCP 서버: /mcp (MCP 프로토콜 엔드포인트라 Swagger 에는 나타나지 않는다)
app.router.routes.extend(mcp_routes())
