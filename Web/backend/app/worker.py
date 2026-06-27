"""
===============================================================
오케스트레이터 (app/worker.py)
===============================================================
BackgroundTasks 가 백그라운드에서 실행하는 함수.
analyze() 를 감싸 작업 상태(jobs)를 갱신한다.

  pending(=upload 시점) -> processing(시작) -> done(성공) / failed(예외)

analyze() 가 더미든 실제 알고리즘이든 이 래퍼는 그대로 동작한다.
===============================================================
"""

import logging
import os
import subprocess

from app.analyze import analyze
from app.core import config, jobs
from app.render import render_clip
from app.thumbnail import generate_thumbnail

logger = logging.getLogger("shortify.faststart")

# ffmpeg stderr 중 로그에 실어 보낼 최대 길이
_STDERR_TAIL = 800


def _faststart_inplace(video_path: str) -> bool:
    """
    mp4 의 moov atom 을 파일 앞으로 옮긴다(faststart) → 브라우저 미리보기 빠른 시작.
    재인코딩 없이 -c copy 로 재먹싱한 뒤 원본을 원자적으로 덮어쓴다(경로 유지).
    실패하면 원본을 그대로 두고 False 반환(최적화일 뿐, 분석/미리보기는 계속).
    """
    if not video_path or not os.path.exists(video_path):
        logger.warning("[faststart] 원본 없음, 스킵: %s", video_path)
        return False

    tmp_path = f"{video_path}.faststart.tmp.mp4"
    cmd = [
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
        "-i", video_path,
        "-c", "copy", "-movflags", "+faststart",
        tmp_path,
    ]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True)
        if proc.returncode != 0:
            tail = (proc.stderr or "").strip()[-_STDERR_TAIL:]
            logger.warning(
                "[faststart] 변환 실패(code=%s), 원본 유지: %s | %s",
                proc.returncode, video_path, tail,
            )
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
            return False
        os.replace(tmp_path, video_path)  # 같은 디렉터리 -> 원자적 덮어쓰기, 경로 유지
        logger.info("[faststart] 변환 성공: %s", video_path)
        return True
    except Exception as e:
        logger.warning("[faststart] 변환 예외, 원본 유지: %s | %s", video_path, e)
        if os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except OSError:
                pass
        return False


def _attach_thumbnails(task_id: str, result: dict, source_path: str) -> None:
    """
    각 클립 구간의 대표 프레임을 뽑아 {THUMBNAIL_DIR}/{task_id}_{rank}.jpg 로 저장하고,
    클립 dict 에 thumbnail_url(=/api/thumbnail/{task_id}/{rank}) 을 채운다.
    추출 실패(또는 원본 없음)면 thumbnail_url=None → 프론트가 그라데이션으로 폴백.
    """
    clips = result.get("clips") or []
    have_source = bool(source_path) and os.path.exists(source_path)
    for clip in clips:
        rank = clip.get("rank")
        if not have_source or rank is None:
            clip["thumbnail_url"] = None
            continue
        out_path = os.path.join(config.THUMBNAIL_DIR, f"{task_id}_{rank}.jpg")
        ok = generate_thumbnail(
            source_path, out_path, clip.get("start_ms", 0), clip.get("end_ms", 0)
        )
        clip["thumbnail_url"] = f"/api/thumbnail/{task_id}/{rank}" if ok else None


def run_analysis_task(
    task_id: str,
    video_path: str,
    categories: list,
    user_prompt: str,
    youtube_url: str = None,
) -> None:
    """analyze() 를 실행하고 결과/에러를 jobs 에 기록한다 (알고리즘 계약 시그니처)."""
    jobs.update(task_id, status="processing", progress=10)

    # analyze 가 단계별로 부르는 진행률 콜백. jobs 에 percent 를 그대로 반영한다.
    # 콜백 예외가 분석을 깨지 않도록 방어적으로 감싼다.
    def _on_progress(percent: int, message: str = None) -> None:
        try:
            jobs.update(task_id, progress=int(percent))
        except Exception as e:  # noqa: BLE001 - 진행률 보고 실패는 무시(분석 지속)
            logger.warning("[progress] 갱신 실패: %s", e)

    try:
        result = analyze(
            video_path=video_path,
            categories=categories,
            user_prompt=user_prompt,
            youtube_url=youtube_url,
            on_progress=_on_progress,
        )

        # 미리보기용: analyze 가 알려준 실제 mp4 경로로 video_path 를 갱신한다.
        # (URL 케이스면 다운로드본, 로컬이면 NFS 복사본) + faststart 재먹싱.
        # done 으로 바꾸기 전에 처리해, 클라이언트가 갱신 전 경로로 preview 하지 않게 한다.
        source_path = result.get("source_path")
        if source_path and os.path.exists(source_path):
            _faststart_inplace(source_path)               # 최적화(실패해도 무방)
            jobs.update(task_id, video_path=source_path)  # preview 가 이 파일을 보게

        # 클립별 대표 프레임 썸네일 생성 → 각 clip 에 thumbnail_url 추가.
        # (faststart 적용본 기준으로 뽑는다. 실패해도 done 으로 진행)
        _attach_thumbnails(task_id, result, source_path)

        jobs.update(task_id, status="done", progress=100, result=result)
    except Exception as e:
        # MVP: 에러 메시지를 문자열로 보관 (status API 에서 노출)
        jobs.update(task_id, status="failed", error=str(e))


def run_render_task(
    render_id: str,
    input_path: str,
    output_path: str,
    start_ms: int,
    end_ms: int,
    title: str,
    bg_color: str,
    text_color: str,
    title_position: str,
    font_size_px: int,
) -> None:
    """
    render_clip() 을 실행하고 결과/에러를 renders 에 기록한다.
    run_analysis_task 와 동일 패턴:
      pending(=render 접수 시점) -> processing(시작) -> done(성공) / failed(예외)
    """
    jobs.update_render(render_id, status="processing")

    try:
        render_clip(
            input_path=input_path,
            output_path=output_path,
            start_ms=start_ms,
            end_ms=end_ms,
            title=title,
            bg_color=bg_color,
            text_color=text_color,
            title_position=title_position,
            font_size_px=font_size_px,
        )
        jobs.update_render(render_id, status="done", output_path=output_path)
    except Exception as e:
        # 실패 메시지를 renders.error 에 보관 (render status API 에서 노출)
        jobs.update_render(render_id, status="failed", error=str(e))
