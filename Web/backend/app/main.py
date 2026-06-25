"""
===============================================================
FastAPI 앱 진입점 (app/main.py)
===============================================================
실행:
  uvicorn app.main:app --host 0.0.0.0 --port 8000
(장시간 실행이므로 서버 지침에 따라 screen 안에서 띄운다.)
===============================================================
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.routes import router
from app.api import render as render_routes
from app.core.config import ensure_dirs


# 프론트(Vite dev 서버) 연동용 CORS 허용 origin. 배포/추가 시 여기에 한 줄씩 추가.
ALLOWED_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 기동 시 업로드 저장 폴더 보장
    ensure_dirs()
    yield


app = FastAPI(title="Shortify Backend (A파트)", lifespan=lifespan)

# CORS: 브라우저에서 프론트(다른 origin)가 API 를 호출할 수 있도록 허용
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 명세서가 /api/ 기준이므로 모든 API 경로에 /api prefix 부여
# (/health 는 라우터가 아니라 아래 앱에 직접 달려 루트에 그대로 둔다)
app.include_router(router, prefix="/api")
# 백엔드 B - 렌더 라우터
app.include_router(render_routes.router, prefix="/api", tags=["render"])


# ===============================================================
# 에러 응답 형식 통일 (PDF 명세)
#   {"error": {"code": "...", "message": "..."}}
# ===============================================================
_CODE_BY_STATUS = {
    400: "INVALID_REQUEST",
    404: "NOT_FOUND",
    409: "NOT_READY",
    413: "FILE_TOO_LARGE",
    422: "VALIDATION_ERROR",
}


def _error_body(code: str, message) -> dict:
    return {"error": {"code": code, "message": message}}


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    """routes 에서 raise 한 HTTPException(및 기본 404 등)을 통일 형식으로 변환."""
    code = _CODE_BY_STATUS.get(exc.status_code, "ERROR")
    return JSONResponse(
        status_code=exc.status_code,
        content=_error_body(code, exc.detail),
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """필수값 누락/타입 오류(FastAPI 기본 422)도 같은 형식으로."""
    # loc 경로 + 메시지를 사람이 읽기 쉽게 요약
    parts = [
        f"{'.'.join(str(loc) for loc in e['loc'])}: {e['msg']}"
        for e in exc.errors()
    ]
    return JSONResponse(
        status_code=422,
        content=_error_body("VALIDATION_ERROR", "; ".join(parts)),
    )


@app.get("/health")
async def health():
    """헬스체크."""
    return {"ok": True}
