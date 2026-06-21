"""
===============================================================
요청/응답 모델 (app/schemas.py)
===============================================================
팀장 명세에 맞춘 응답 스키마.
(요청은 multipart/form-data 라서 routes.py 의 Form/File 로 직접 받는다.)
===============================================================
"""

from typing import Optional

from pydantic import BaseModel

# 허용 카테고리 (API 명세 기준). upload 에서 이 집합으로 검증한다.
ALLOWED_CATEGORIES = {"empathy", "laughter", "info", "sadness", "twist"}


class UploadResponse(BaseModel):
    """POST /upload 응답: 작업 접수 확인."""
    task_id: str
    status: str               # 접수 직후 = "pending"


class StatusResponse(BaseModel):
    """GET /status/{task_id} 응답."""
    task_id: str
    status: str               # pending / processing / done / failed
    progress: int             # 0~100
    error: Optional[str] = None


class Clip(BaseModel):
    """
    result 응답의 클립 1개. 명세서 필드만 노출한다.
    analyze() 가 score/score_reason 등 추가 필드를 줘도(내부 저장엔 남음)
    이 모델로 직렬화되며 응답에서는 자동으로 제외된다.
    """
    rank: int
    start_ms: int
    end_ms: int
    duration_sec: float
    reason: str
    titles: list[str]


class ResultResponse(BaseModel):
    """GET /result/{task_id} 응답 (status=done 일 때만)."""
    task_id: str
    status: str               # "done"
    video_duration_ms: int
    clips: list[Clip]         # 명세 6개 필드만 (score 등은 응답에서 제외)
