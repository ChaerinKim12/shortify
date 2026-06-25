"""
===============================================================
렌더 API 라우트 (app/api/render.py) - 백엔드 B
===============================================================
POST /api/render                  렌더 요청 접수 -> render_id 발급 + 백그라운드 합성 시작
GET  /api/render/status/{render_id} 렌더 진행 상태 조회
GET  /api/download/{render_id}      완료된 결과 mp4 다운로드

[흐름 - A 의 upload/status/result 와 같은 패턴]
- render 접수 시 renders 테이블에 pending 으로 등록 후 즉시 render_id 반환
- 실제 ffmpeg 합성은 BackgroundTasks 가 run_render_task 로 비동기 실행
- 원본 위치(input_path)는 task_id 로 tasks.video_path 를 조회해서 얻는다
  (A 가 upload 시 video_path 에 NFS 경로/URL 을 저장해 둠)
- B 는 NFS 파일만 처리한다. video_path 가 URL 이면 아직 미지원 -> 400
===============================================================
"""

import os
import uuid
from typing import Literal, Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from app.core import config, jobs
from app.worker import run_render_task

router = APIRouter()

# 자막 크기 옵션 -> px 매핑
_FONT_SIZE_PX = {"small": 36, "medium": 48, "large": 64}

# 구간 길이 제한 (밀리초): 5초 이상 90초 이하
_MIN_DURATION_MS = 5_000
_MAX_DURATION_MS = 90_000


class RenderRequest(BaseModel):
    """POST /api/render 요청 바디."""
    task_id: str
    start_ms: int = Field(..., ge=0)
    end_ms: int = Field(..., gt=0)
    title: str = ""
    bg_color: Literal["black", "white"] = "black"
    text_color: Literal["white", "black"] = "white"
    title_position: Literal["top", "bottom"] = "bottom"
    font_size: Literal["small", "medium", "large"] = "medium"


class RenderResponse(BaseModel):
    """POST /api/render 응답: 렌더 접수 확인."""
    render_id: str
    status: str               # 접수 직후 = "pending"


class RenderStatusResponse(BaseModel):
    """GET /api/render/status/{render_id} 응답."""
    render_id: str
    status: str               # pending / processing / done / failed
    error: Optional[str] = None


@router.post("/render", response_model=RenderResponse)
async def render(
    req: RenderRequest,
    background_tasks: BackgroundTasks,
) -> RenderResponse:
    # 1) 구간 검증
    if req.start_ms >= req.end_ms:
        raise HTTPException(
            status_code=400,
            detail="start_ms 는 end_ms 보다 작아야 합니다.",
        )
    duration_ms = req.end_ms - req.start_ms
    if not (_MIN_DURATION_MS <= duration_ms <= _MAX_DURATION_MS):
        raise HTTPException(
            status_code=400,
            detail="구간 길이는 5초 이상 90초 이하여야 합니다.",
        )

    # 2) task 조회 (원본 위치 확보)
    task = jobs.get(req.task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="존재하지 않는 task_id 입니다.")

    input_path = task.get("video_path")
    if not input_path:
        raise HTTPException(
            status_code=404,
            detail="해당 task 에 원본 영상 경로가 없습니다.",
        )
    # B 는 NFS 파일만 처리한다. URL 원본은 아직 미지원.
    if input_path.startswith("http://") or input_path.startswith("https://"):
        raise HTTPException(
            status_code=400,
            detail="URL 원본 렌더는 아직 지원하지 않습니다 (NFS 파일만 가능).",
        )

    # 3) render 작업 등록(pending) 후 백그라운드 합성 시작
    render_id = uuid.uuid4().hex
    output_path = os.path.join(config.RENDER_DIR, f"{render_id}.mp4")

    jobs.create_render(render_id, req.task_id)
    background_tasks.add_task(
        run_render_task,
        render_id=render_id,
        input_path=input_path,
        output_path=output_path,
        start_ms=req.start_ms,
        end_ms=req.end_ms,
        title=req.title,
        bg_color=req.bg_color,
        text_color=req.text_color,
        title_position=req.title_position,
        font_size_px=_FONT_SIZE_PX[req.font_size],
    )

    return RenderResponse(render_id=render_id, status="pending")


@router.get("/render/status/{render_id}", response_model=RenderStatusResponse)
async def render_status(render_id: str) -> RenderStatusResponse:
    job = jobs.get_render(render_id)
    if job is None:
        raise HTTPException(status_code=404, detail="존재하지 않는 render_id 입니다.")
    return RenderStatusResponse(
        render_id=render_id,
        status=job["status"],
        error=job.get("error"),
    )


@router.get("/download/{render_id}")
async def download(render_id: str) -> FileResponse:
    job = jobs.get_render(render_id)
    if job is None:
        raise HTTPException(status_code=404, detail="존재하지 않는 render_id 입니다.")

    if job["status"] != "done":
        # 아직 처리 중 / 실패 -> 409 + 현재 상태 안내
        raise HTTPException(
            status_code=409,
            detail=f"아직 다운로드할 수 없습니다 (status={job['status']}).",
        )

    output_path = job.get("output_path")
    if not output_path or not os.path.exists(output_path):
        # done 인데 파일이 없으면 서버 내부 문제
        raise HTTPException(status_code=500, detail="렌더 결과 파일을 찾을 수 없습니다.")

    short_id = render_id[:8]
    return FileResponse(
        output_path,
        media_type="video/mp4",
        filename=f"shortify_{short_id}.mp4",
    )
