"""
===============================================================
클립 썸네일 추출 (app/thumbnail.py)
===============================================================
결과 화면의 클립 카드에 쓸 대표 프레임 1장을 ffmpeg 로 뽑는다.
  - 각 클립(start_ms~end_ms) 구간 안쪽의 한 프레임을 추출
  - 시작점 + 2초 지점을 기본으로 하되, 짧은 클립은 구간 중앙으로 보정
  - 가로 640px 로 축소(JPEG)해 카드 썸네일로 가볍게 서빙

[계약]
입력:
  input_path  : NFS 에 저장된 원본 영상 경로(source_path, faststart 적용본)
  output_path : 썸네일 저장 경로 ({THUMBNAIL_DIR}/{task_id}_{rank}.jpg)
  start_ms/end_ms : 해당 클립 구간 (밀리초)
반환:
  True(성공) / False(실패). 실패해도 분석 자체는 done 으로 진행한다
  (프론트는 thumbnail_url 이 없으면 기존 그라데이션으로 폴백).
===============================================================
"""

import logging
import os
import subprocess

logger = logging.getLogger("shortify.thumbnail")

# 썸네일 가로 폭(px). 세로는 비율 유지(-2 로 짝수 보정).
_THUMB_W = 640
# 기본 추출 지점: 클립 시작 + 2초
_DEFAULT_OFFSET_MS = 2000
# ffmpeg stderr 중 로그에 실어 보낼 최대 길이
_STDERR_TAIL = 800


def _pick_frame_ms(start_ms: int, end_ms: int) -> int:
    """
    추출할 프레임의 절대 위치(ms)를 고른다.
    기본은 start+2초. 단 구간이 짧으면 끝을 넘어가지 않도록 구간 중앙으로 보정.
    """
    start_ms = max(0, int(start_ms or 0))
    end_ms = int(end_ms or 0)
    duration = end_ms - start_ms
    if duration <= 0:
        return start_ms
    # 구간이 넉넉하면 +2초, 짧으면 절반 지점 (항상 구간 내부)
    offset = _DEFAULT_OFFSET_MS if duration > 2 * _DEFAULT_OFFSET_MS else duration // 2
    return start_ms + offset


def generate_thumbnail(input_path: str, output_path: str, start_ms: int, end_ms: int) -> bool:
    """클립 구간 대표 프레임 1장을 JPEG 로 추출한다. 성공 시 True."""
    if not input_path or not os.path.exists(input_path):
        logger.warning("[thumbnail] 원본 없음, 스킵: %s", input_path)
        return False

    seek_sec = _pick_frame_ms(start_ms, end_ms) / 1000.0
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    # -ss 를 -i 앞에 두어 빠른 입력 시킹(썸네일이라 정밀도보다 속도 우선).
    # -frames:v 1 한 장만, -an 오디오 무시, scale 로 가로 640 축소.
    cmd = [
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
        "-ss", f"{seek_sec:.3f}",
        "-i", input_path,
        "-frames:v", "1",
        "-an",
        "-vf", f"scale={_THUMB_W}:-2",
        "-q:v", "3",
        output_path,
    ]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True)
        if proc.returncode != 0 or not os.path.exists(output_path):
            tail = (proc.stderr or "").strip()[-_STDERR_TAIL:]
            logger.warning(
                "[thumbnail] 추출 실패(code=%s): %s | %s",
                proc.returncode, output_path, tail,
            )
            return False
        logger.info("[thumbnail] 추출 성공: %s (@%.3fs)", output_path, seek_sec)
        return True
    except Exception as e:  # noqa: BLE001 - 썸네일 실패는 분석을 깨지 않음
        logger.warning("[thumbnail] 추출 예외: %s | %s", output_path, e)
        return False
