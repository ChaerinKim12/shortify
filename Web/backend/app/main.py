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

from fastapi import FastAPI

from app.api.routes import router
from app.core.config import ensure_dirs


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 기동 시 업로드 저장 폴더 보장
    ensure_dirs()
    yield


app = FastAPI(title="Shortify Backend (A파트)", lifespan=lifespan)
# 명세서가 /api/ 기준이므로 모든 API 경로에 /api prefix 부여
# (/health 는 라우터가 아니라 아래 앱에 직접 달려 루트에 그대로 둔다)
app.include_router(router, prefix="/api")


@app.get("/health")
async def health():
    """헬스체크."""
    return {"ok": True}
