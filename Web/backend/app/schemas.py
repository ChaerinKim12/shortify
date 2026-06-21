"""
===============================================================
요청/응답 모델 (app/schemas.py)
===============================================================
팀장 명세에 맞춘 응답 스키마.
(요청은 multipart/form-data 라서 routes.py 의 Form/File 로 직접 받는다.)
===============================================================
"""

from typing import Any, Optional

from pydantic import BaseModel


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


class ResultResponse(BaseModel):
    """GET /result/{task_id} 응답 (status=done 일 때만)."""
    task_id: str
    status: str               # "done"
    video_duration_ms: int
    # clips 는 analyze() 가 주는 형태를 그대로 통과시킨다.
    # (rank/start_ms/end_ms/duration_sec/reason/titles + score 등 추가필드 보존)
    clips: list[dict[str, Any]]
