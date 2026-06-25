"""
===============================================================
영상 렌더링 (app/render.py)
===============================================================
원본 영상의 한 구간을 잘라 9:16 세로 쇼츠로 합성한다.
  - 가로 16:9 영상을 720x1280 캔버스 중앙에 배치(레터박스)
  - 한글 제목 자막을 ffmpeg drawtext 로 합성 (Pretendard ExtraBold)

검증 완료한 ffmpeg 명령을 그대로 함수화했다 (config.KOREAN_FONT_EXTRABOLD 사용).
실제 합성은 run_render_task(worker.py) 가 백그라운드에서 이 함수를 호출한다.

[계약]
입력:
  input_path     : NFS 에 저장된 원본 영상 경로
  output_path    : 결과 mp4 저장 경로 ({RENDER_DIR}/{render_id}.mp4)
  start_ms/end_ms: 자를 구간 (밀리초)
  title          : 자막 제목 (없으면 "" -> 자막 생략)
  bg_color       : 레터박스 배경색 "black" | "white"
  text_color     : 자막 글씨색 "white" | "black"
  title_position : 자막 위치 "top" | "bottom"
  font_size_px   : 자막 크기 (px)
반환:
  output_path (성공). 실패 시 RuntimeError 를 raise -> worker 가 failed 로 기록.
===============================================================
"""

import os
import subprocess

from app.core import config

# 출력 캔버스(9:16) / 자막 스타일 상수
_OUT_W = 720
_OUT_H = 1280
_BORDER_W = 3          # 자막 외곽선 두께(px) - 가독성
_MARGIN = 120         # 자막을 화면 가장자리에서 띄우는 여백(px)

# ffmpeg stderr 중 예외에 실어 보낼 최대 길이
_STDERR_TAIL = 800


def escape_drawtext_text(text: str) -> str:
    """
    사용자 제목을 drawtext text='...' 안에 안전하게 넣기 위한 escape.
    ffmpeg 필터 파서가 특수 취급하는 문자(\\ : ' %)를 escape 한다.
    (역슬래시를 가장 먼저 처리해야 이후 escape 가 중복되지 않는다.)
    """
    text = text.replace("\\", "\\\\")
    text = text.replace(":", "\\:")
    text = text.replace("'", "\\'")
    text = text.replace("%", "\\%")
    return text


def build_letterbox_filter(bg_color: str) -> str:
    """
    16:9 영상을 720x1280(9:16) 캔버스 중앙에 배치하는 레터박스 필터 문자열.
      - scale=720:-2  : 가로 720 고정, 세로는 비율 유지(짝수 보정)
      - pad           : 9:16 캔버스에 중앙 배치 + 위아래 배경색 채움
    """
    return (
        f"scale={_OUT_W}:-2,"
        f"pad={_OUT_W}:{_OUT_H}:(ow-iw)/2:(oh-ih)/2:color={bg_color}"
    )


def _build_drawtext_filter(
    title: str,
    text_color: str,
    title_position: str,
    font_size_px: int,
) -> str:
    """한글 제목 자막(drawtext) 필터 문자열. title 이 비면 ""(자막 생략)."""
    if not title:
        return ""

    font_path = config.KOREAN_FONT_EXTRABOLD
    safe_title = escape_drawtext_text(title)
    # 글씨색에 따라 외곽선은 반대색으로 (흰 글씨->검은 외곽선 / 검은 글씨->흰 외곽선)
    border_color = "black" if text_color == "white" else "white"
    # 위치: bottom = 아래에서 _MARGIN 위 / top = 위에서 _MARGIN 아래
    y_expr = f"h-text_h-{_MARGIN}" if title_position == "bottom" else str(_MARGIN)

    return (
        f"drawtext=fontfile='{font_path}':text='{safe_title}':"
        f"fontsize={font_size_px}:fontcolor={text_color}:"
        f"borderw={_BORDER_W}:bordercolor={border_color}:"
        f"x=(w-text_w)/2:y={y_expr}"
    )


def render_clip(
    input_path: str,
    output_path: str,
    start_ms: int,
    end_ms: int,
    title: str = "",
    bg_color: str = "black",
    text_color: str = "white",
    title_position: str = "bottom",
    font_size_px: int = 48,
) -> str:
    """
    원본 영상의 [start_ms, end_ms) 구간을 9:16 쇼츠로 합성해 output_path 에 저장한다.
    ffmpeg 를 subprocess 로 호출하며, 실패 시 stderr 일부를 담아 RuntimeError 를 raise 한다.
    """
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    start_sec = start_ms / 1000.0
    duration_sec = (end_ms - start_ms) / 1000.0

    # 레터박스 + (선택) 자막 을 콤마로 이어 vf 구성
    vf = build_letterbox_filter(bg_color)
    drawtext = _build_drawtext_filter(title, text_color, title_position, font_size_px)
    if drawtext:
        vf = f"{vf},{drawtext}"

    # 검증한 명령 그대로: 입력 앞 -ss 로 빠른 seek
    cmd = [
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
        "-ss", f"{start_sec}", "-t", f"{duration_sec}", "-i", input_path,
        "-vf", vf,
        "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart",
        output_path,
    ]

    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        tail = (proc.stderr or "").strip()[-_STDERR_TAIL:]
        raise RuntimeError(f"ffmpeg 렌더 실패 (code={proc.returncode}): {tail}")

    return output_path
