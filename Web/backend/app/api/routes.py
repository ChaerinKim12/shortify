"""
===============================================================
API 라우트 (app/api/routes.py)
===============================================================
POST /upload          분석 요청 접수 -> task_id 발급 + 백그라운드 분석 시작
GET  /status/{task_id} 진행 상태 조회
GET  /result/{task_id} 완료된 결과(클립) 조회

[upload 의 file/url 분기 - 알고리즘 계약]
- file 이 오면 파일 케이스, youtube_url 이 오면 URL 케이스로 자동 판단.
- analyze 는 항상 video_path={UPLOAD_DIR}/{task_id}.mp4 형태로 받는다(작업명 추출용).
  file 케이스: file 을 그 경로에 저장해 그대로 전달.
  url  케이스: 그 경로는 이름 운반용으로만 쓰고, 실제 다운로드는 youtube_url 로 알고리즘이 수행.
- file/youtube_url 둘 다 없으면 400, 둘 다 있으면 400 (모호 입력 방지)
- 파일 5GB 초과면 413

[카테고리 - 알고리즘 계약]
- categories(리스트, 1~4개) 로 받는다. 코드값: empathy/laughter/info/touching.
- 전환기 호환: 프론트가 아직 단수 category 를 보내면 [category] 로 감싸 처리한다.
- clip_count 는 더 이상 쓰지 않는다(목표 클립수는 카테고리 수로 자동 결정). 와도 무시.
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
from fastapi.responses import FileResponse

from app.core import config, jobs
from app.schemas import (
    ALLOWED_CATEGORIES,
    ResultResponse,
    StatusResponse,
    UploadResponse,
)
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
    user_prompt: str = Form(""),
    categories: list[str] | None = Form(None),     # 알고리즘 계약: 1~4개 리스트
    category: str | None = Form(None),             # legacy(단수) - 전환기 호환용
    clip_count: int | None = Form(None),           # deprecated - 받아도 무시
    file: UploadFile | None = File(None),
    youtube_url: str | None = Form(None),
) -> UploadResponse:
    # 1) 카테고리 정규화: categories(리스트) 우선, 없으면 legacy category 를 [category] 로
    cats = categories if categories else ([category] if category else [])
    if not cats:
        raise HTTPException(
            status_code=400,
            detail="categories 는 최소 1개 필요합니다.",
        )
    if len(cats) > len(ALLOWED_CATEGORIES):
        raise HTTPException(
            status_code=400,
            detail=f"categories 는 최대 {len(ALLOWED_CATEGORIES)}개까지 가능합니다.",
        )
    invalid = [c for c in cats if c not in ALLOWED_CATEGORIES]
    if invalid:
        raise HTTPException(
            status_code=400,
            detail=f"알 수 없는 카테고리 {invalid} (가능: {sorted(ALLOWED_CATEGORIES)}).",
        )

    # 2) file / youtube_url 자동 판단
    has_file = file is not None and bool(file.filename)
    has_url = bool(youtube_url)
    if has_file and has_url:
        raise HTTPException(
            status_code=400,
            detail="file 과 youtube_url 은 동시에 보낼 수 없습니다. 하나만 보내세요.",
        )
    if not has_file and not has_url:
        raise HTTPException(
            status_code=400,
            detail="file 또는 youtube_url 중 하나는 반드시 필요합니다.",
        )

    task_id = uuid.uuid4().hex
    # analyze 는 항상 이 경로(작업명 운반용)를 받는다. file 케이스에선 실제 저장 위치이기도 하다.
    nfs_mp4 = os.path.join(config.UPLOAD_DIR, f"{task_id}.mp4")

    # 3) 케이스별 분기
    if has_file:
        analyze_video_path = await _save_upload_to_nfs(file, task_id)  # == nfs_mp4
        analyze_youtube_url = None
        render_source = analyze_video_path        # B 가 찾을 실제 파일 경로(NFS)
    else:
        analyze_video_path = nfs_mp4              # 이름 운반용. 다운로드는 알고리즘이 수행.
        analyze_youtube_url = youtube_url
        render_source = youtube_url               # B 는 URL 원본 미지원 -> 렌더 단계에서 400

    # 4) 작업 등록(pending) 후 백그라운드 분석 시작
    jobs.create(
        task_id,
        video_path=render_source,  # B(예성)가 task_id 로 영상 위치 조회
    )
    background_tasks.add_task(
        run_analysis_task,
        task_id=task_id,
        video_path=analyze_video_path,
        categories=cats,
        user_prompt=user_prompt,
        youtube_url=analyze_youtube_url,
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


@router.get("/preview/{task_id}")
async def preview(task_id: str) -> FileResponse:
    """
    원본 영상(NFS mp4)을 스트리밍으로 반환한다. 구간조정 화면의 <video> 미리보기용.
    FileResponse 는 Range 요청을 자동 처리(206 + Content-Range)하므로 브라우저 seek 가능.
    """
    job = jobs.get(task_id)
    if job is None:
        raise HTTPException(status_code=404, detail="존재하지 않는 task_id 입니다.")

    path = job.get("video_path")
    if not path:
        raise HTTPException(status_code=404, detail="원본 영상 경로가 없습니다.")

    # URL(유튜브) 원본은 NFS 에 파일이 없으므로 미리보기 불가
    if path.startswith("http://") or path.startswith("https://"):
        raise HTTPException(
            status_code=404,
            detail="URL(유튜브) 원본은 미리보기를 지원하지 않습니다 (NFS 파일만 가능).",
        )
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="원본 영상 파일을 찾을 수 없습니다.")

    return FileResponse(path, media_type="video/mp4")


@router.get("/thumbnail/{task_id}/{rank}")
async def thumbnail(task_id: str, rank: int) -> FileResponse:
    """
    결과 화면 클립 카드용 대표 프레임(JPEG)을 반환한다.
    worker 가 분석 완료 시 {THUMBNAIL_DIR}/{task_id}_{rank}.jpg 로 미리 생성해 둔다.
    클립 result JSON 의 thumbnail_url 이 이 경로를 가리킨다.
    """
    path = os.path.join(config.THUMBNAIL_DIR, f"{task_id}_{rank}.jpg")
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="썸네일을 찾을 수 없습니다.")
    # 썸네일은 task_id+rank 로 불변이므로 캐시 허용
    return FileResponse(
        path,
        media_type="image/jpeg",
        headers={"Cache-Control": "public, max-age=86400"},
    )
