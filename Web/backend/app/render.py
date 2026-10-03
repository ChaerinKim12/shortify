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
import tempfile
from typing import Optional

from app import subtitles as subs_mod
from app.core import config

# 출력 캔버스(9:16) / 자막 스타일 상수
_OUT_W = 720
_OUT_H = 1280
_BORDER_W = 3          # 자막 외곽선 두께(px) - 가독성
_MARGIN = 120         # 자막을 화면 위/아래 가장자리에서 띄우는 여백(px)
_SIDE_MARGIN = 48     # 자막 좌우 안전 여백(px) - 이 폭 안으로 줄바꿈해 프레임 밖 잘림 방지
_LINE_SPACING = 12    # 자동 줄바꿈된 줄 사이 간격(px)

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


def _char_display_width(ch: str, font_size_px: int) -> float:
    """
    글자 1개의 대략적 렌더 폭(px) 추정.
    한글/가나/한자/전각은 약 font_size(정사각에 가까움), 그 외(라틴/숫자/공백)는 약 0.55배.
    실제 폰트 메트릭은 아니지만 줄바꿈 판단용으로 충분하고, 과대추정 쪽이라 잘림에 안전하다.
    """
    o = ord(ch)
    wide = (
        0xAC00 <= o <= 0xD7A3   # 한글 음절
        or 0x1100 <= o <= 0x11FF  # 한글 자모
        or 0x3040 <= o <= 0x30FF  # 가나
        or 0x3000 <= o <= 0x9FFF  # CJK 기호/한자
        or 0xFF00 <= o <= 0xFFEF  # 전각
    )
    return font_size_px * (1.0 if wide else 0.55)


def _wrap_title_to_lines(title: str, font_size_px: int, usable_px: float) -> list[str]:
    """
    제목을 usable_px 폭에 맞춰 자동 줄바꿈한다.
    - 공백이 있으면 단어 경계에서 끊는 것을 우선한다.
    - 한 단어(또는 공백 없는 한글)가 한 줄보다 길면 글자 단위로 강제 분할한다.
    각 줄의 추정 폭은 usable_px 이하라, 가운데 정렬해도 프레임 밖으로 나가지 않는다.
    """
    def width_of(s: str) -> float:
        return sum(_char_display_width(c, font_size_px) for c in s)

    out: list[str] = []
    for para in title.split("\n"):
        cur = ""
        cur_w = 0.0
        for ch in para:
            cw = _char_display_width(ch, font_size_px)
            if cur and cur_w + cw > usable_px:
                br = cur.rfind(" ")
                if br > 0:                 # 줄 안에 공백이 있으면 마지막 공백에서 끊고 나머지는 다음 줄로
                    out.append(cur[:br])
                    cur = cur[br + 1:]
                else:                      # 공백 없는 긴 텍스트(한글 등) -> 글자 단위 강제 분할
                    out.append(cur)
                    cur = ""
                cur_w = width_of(cur)
            cur += ch
            cur_w += cw
        out.append(cur)

    lines = [ln.strip() for ln in out]
    return lines if any(lines) else [title.strip()]


def _build_drawtext_filter(
    title: str,
    text_color: str,
    title_position: str,
    font_size_px: int,
) -> str:
    """한글 제목 자막(drawtext) 필터 문자열. title 이 비면 ""(자막 생략).

    긴 제목은 프레임 좌우 안전폭(_OUT_W - 2*_SIDE_MARGIN) 안으로 자동 줄바꿈해
    여러 줄로 그린다. 줄바꿈 후 각 줄 폭이 안전폭 이하이므로 x=(w-text_w)/2 도 음수가 되지 않는다.
    """
    if not title:
        return ""

    # Windows 경로(C:\...)의 역슬래시/콜론은 필터 파서가 먹으므로 escape (Linux 경로는 변화 없음)
    font_path = subs_mod.escape_filter_path(config.KOREAN_FONT_EXTRABOLD)
    usable_px = _OUT_W - 2 * _SIDE_MARGIN
    wrapped = "\n".join(_wrap_title_to_lines(title, font_size_px, usable_px))
    # 줄바꿈(개행) 문자는 escape 대상이 아니며 drawtext 가 그대로 줄바꿈으로 렌더한다.
    safe_title = escape_drawtext_text(wrapped)
    # 글씨색에 따라 외곽선은 반대색으로 (흰 글씨->검은 외곽선 / 검은 글씨->흰 외곽선)
    border_color = "black" if text_color == "white" else "white"
    # 위치: bottom = 아래에서 _MARGIN 위 / top = 위에서 _MARGIN 아래
    y_expr = f"h-text_h-{_MARGIN}" if title_position == "bottom" else str(_MARGIN)

    return (
        f"drawtext=fontfile='{font_path}':text='{safe_title}':"
        f"fontsize={font_size_px}:fontcolor={text_color}:"
        f"borderw={_BORDER_W}:bordercolor={border_color}:"
        f"line_spacing={_LINE_SPACING}:"
        f"x=(w-text_w)/2:y={y_expr}"
    )


def _title_top_y(title: str, title_position: str, font_size_px: int) -> Optional[float]:
    """하단 제목이 있으면 제목 윗선 y(px) 를 추정해 돌려준다 (자막이 제목과 겹치지 않게 하는 용도)."""
    if not title or title_position != "bottom":
        return None
    n = len(_wrap_title_to_lines(title, font_size_px, _OUT_W - 2 * _SIDE_MARGIN))
    text_h = n * font_size_px + (n - 1) * _LINE_SPACING
    return _OUT_H - _MARGIN - text_h


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
    subtitles: Optional[list[dict]] = None,
    subtitle_position: str = "letterbox",
    subtitle_size_px: int = 36,
) -> str:
    """
    원본 영상의 [start_ms, end_ms) 구간을 9:16 쇼츠로 합성해 output_path 에 저장한다.
    ffmpeg 를 subprocess 로 호출하며, 실패 시 stderr 일부를 담아 RuntimeError 를 raise 한다.
    """
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    start_sec = start_ms / 1000.0
    duration_sec = (end_ms - start_ms) / 1000.0

    # 레터박스 -> (선택) 대사 자막(ass) -> (선택) 제목(drawtext) 순으로 콤마로 이어 vf 구성
    vf = build_letterbox_filter(bg_color)

    # 대사 자막: 클립 기준 상대시간 .ass 를 임시 폴더에 만들어 ass 필터로 입힌다.
    # 자막이 없으면(꺼짐/빈 목록) vf 는 기존과 완전히 동일하다.
    tmp_dir = None
    ass_text = None
    if subtitles:
        ass_text = subs_mod.build_ass(
            subtitles, start_ms, end_ms, subtitle_position, subtitle_size_px,
            title_top_y=_title_top_y(title, title_position, font_size_px),
        )
    if ass_text:
        tmp_dir = tempfile.TemporaryDirectory(prefix="shortify_ass_")
        ass_path = os.path.join(tmp_dir.name, "subs.ass")
        with open(ass_path, "w", encoding="utf-8") as f:
            f.write(ass_text)
        vf = f"{vf},{subs_mod.build_ass_filter(ass_path)}"

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

    try:
        proc = subprocess.run(
            cmd, capture_output=True, text=True, encoding="utf-8", errors="replace"
        )
    finally:
        if tmp_dir is not None:
            tmp_dir.cleanup()
    if proc.returncode != 0:
        tail = (proc.stderr or "").strip()[-_STDERR_TAIL:]
        raise RuntimeError(f"ffmpeg 렌더 실패 (code={proc.returncode}): {tail}")

    return output_path
