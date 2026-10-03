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

# 허용 카테고리 (알고리즘 계약 기준 — Web/algorithm/config.py 의 CATEGORIES 와 일치).
# upload 에서 이 집합으로 검증한다. (구 sadness/twist 폐기, touching 추가)
ALLOWED_CATEGORIES = {"empathy", "laughter", "info", "touching"}


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
    result 응답의 클립 1개. 알고리즘 계약 7필드만 노출한다
    (Web/algorithm/postprocess.py 의 CONTRACT_FIELDS 와 일치).
    analyze() 가 score/score_reason 등 추가 필드를 줘도(내부 저장엔 남음)
    이 모델로 직렬화되며 응답에서는 자동으로 제외된다.
    """
    rank: int
    category: list[str]       # 이 구간이 속한 카테고리(들). dedup 으로 여러 개일 수 있음.
    start_ms: int
    end_ms: int
    duration_sec: int         # 계약상 정수 (postprocess.validate_clips 가 round 처리)
    reason: str
    titles: list[str]
    # 클립 대표 프레임 썸네일 URL (/api/thumbnail/{task_id}/{rank}).
    # worker 가 analyze() 결과에 덧붙인다. 추출 실패 시 None → 프론트가 그라데이션 폴백.
    thumbnail_url: Optional[str] = None
    # 사용자용 선정 이유 3~4줄("라벨 · 내용"). 변환 실패/기존 캐시 결과에는 없음 -> None.
    reason_display: Optional[list[str]] = None


class ResultResponse(BaseModel):
    """GET /result/{task_id} 응답 (status=done 일 때만)."""
    task_id: str
    status: str               # "done"
    video_duration_ms: int
    clips: list[Clip]         # 명세 6개 필드만 (score 등은 응답에서 제외)
