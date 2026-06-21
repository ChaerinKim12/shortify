"""
===============================================================
API 라우트 (app/api/routes.py)
===============================================================
POST /upload          분석 요청 접수 -> task_id 발급 + 백그라운드 분석 시작
GET  /status/{task_id} 진행 상태 조회
GET  /result/{task_id} 완료된 결과(클립) 조회

[upload 의 file/url 분기 - 팀장 명세]
- source_type="file": file 을 {NFS_DIR}/{task_id}.mp4 로 저장 후 그 경로를 source 로 analyze 에 전달
- source_type="url" : video_url 을 그대로 source 로 analyze 에 전달 (다운로드는 analyze 내부)
- file/url 둘 다 없으면 400
- 파일 5GB 초과면 413
===============================================================
"""

import os
import uuid

from fastapi import (
    APIRouter,
    BackgroundTasks,
    File,
    Form,
    HTTPException,
    UploadFile,
)

from app.core import config, jobs
from app.schemas import ResultResponse, StatusResponse, UploadResponse
from app.worker import run_analysis_task

router = APIRouter()

# 스트리밍 저장 청크 크기 (1MB)
_CHUNK = 1024 * 1024


async def _save_upload_to_nfs(file: UploadFile, task_id: str) -> str:
    """
    업로드 파일을 {NFS_DIR}/{task_id}.mp4 로 스트리밍 저장한다.
    Content-Length 를 못 믿으므로 직접 바이트를 세어 5GB 초과 시 413.

    Returns:
        저장된 파일 경로
    """
    os.makedirs(config.UPLOAD_DIR, exist_ok=True)  # NFS 폴더 보장 (방어적)
    dest = os.path.join(config.UPLOAD_DIR, f"{task_id}.mp4")
    size = 0

    try:
        with open(dest, "wb") as out:
            while True:
                chunk = await file.read(_CHUNK)
                if not chunk:
                    break
                size += len(chunk)
                if size > config.MAX_UPLOAD_BYTES:
                    raise HTTPException(
                        status_code=413,
                        detail="업로드 파일이 5GB를 초과했습니다.",
                    )
                out.write(chunk)
    except HTTPException:
        # 한도 초과 등 -> 부분 저장 파일 정리 후 재발생
        if os.path.exists(dest):
            os.remove(dest)
        raise

    return dest


@router.post("/upload", response_model=UploadResponse)
async def upload(
    background_tasks: BackgroundTasks,
    source_type: str = Form(...),
    clip_count: int = Form(3),
    category: str = Form(config.DEFAULT_CATEGORY),
    user_prompt: str = Form(""),
    file: UploadFile | None = File(None),
    video_url: str | None = Form(None),
) -> UploadResponse:
    # 1) 기본 검증
    if source_type not in ("file", "url"):
        raise HTTPException(status_code=400, detail="source_type 은 'file' 또는 'url' 이어야 합니다.")
    if not (1 <= clip_count <= 5):
        raise HTTPException(status_code=400, detail="clip_count 는 1~5 사이여야 합니다.")

    task_id = uuid.uuid4().hex

    # 2) source_type 분기 -> analyze 에 넘길 source 결정
    if source_type == "file":
        if file is None:
            raise HTTPException(status_code=400, detail="source_type='file' 인데 file 이 없습니다.")
        source = await _save_upload_to_nfs(file, task_id)
    else:  # url
        if not video_url:
            raise HTTPException(status_code=400, detail="source_type='url' 인데 video_url 이 없습니다.")
        source = video_url

    # 3) 작업 등록(pending) 후 백그라운드 분석 시작
    jobs.create(
        task_id,
        source_type=source_type,
        clip_count=clip_count,
        category=category,
    )
    background_tasks.add_task(
        run_analysis_task,
        task_id=task_id,
        source=source,
        source_type=source_type,
        clip_count=clip_count,
        category=category,
        user_prompt=user_prompt,
    )

    return UploadResponse(task_id=task_id, status="pending")


@router.get("/status/{task_id}", response_model=StatusResponse)
async def status(task_id: str) -> StatusResponse:
    job = jobs.get(task_id)
    if job is None:
        raise HTTPException(status_code=404, detail="존재하지 않는 task_id 입니다.")
    return StatusResponse(
        task_id=task_id,
        status=job["status"],
        progress=job["progress"],
        error=job.get("error"),
    )


@router.get("/result/{task_id}", response_model=ResultResponse)
async def result(task_id: str) -> ResultResponse:
    job = jobs.get(task_id)
    if job is None:
        raise HTTPException(status_code=404, detail="존재하지 않는 task_id 입니다.")

    if job["status"] == "failed":
        raise HTTPException(status_code=409, detail=f"분석 실패: {job.get('error')}")
    if job["status"] != "done":
        # 아직 처리 중 -> 409 + 현재 상태 안내
        raise HTTPException(status_code=409, detail=f"아직 완료되지 않았습니다 (status={job['status']}).")

    data = job["result"]
    return ResultResponse(
        task_id=task_id,
        status="done",
        video_duration_ms=data["video_duration_ms"],
        clips=data["clips"],
    )
