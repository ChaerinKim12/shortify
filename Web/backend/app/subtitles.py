"""
===============================================================
자막 (app/subtitles.py)
===============================================================
1) STT 결과(merged.json)에서 구간에 겹치는 발화를 뽑아 자막 줄로 쪼갠다.
2) 편집된 자막 목록으로 ffmpeg `ass` 필터용 .ass 파일을 만든다.

시간 단위는 전부 ms. load_subtitles 의 반환은 원본 영상 기준 시간이고,
build_ass 가 클립 시작 기준 상대시간으로 바꿔 쓴다.
===============================================================
"""

import json
import os
from typing import Optional

from app.core import config

LINE_CHARS = 18        # 자막 한 줄 최대 글자 수
DEFAULT_LINES = 1      # 자막 1개당 기본 줄 수 (1 또는 2)
MIN_CUE_MS = 700       # 자막 1개의 최소 표시 시간
MERGE_MAX_CHARS = 22   # 1줄 모드에서 짧은 자막을 합친 결과의 최대 글자 수(넘으면 합치지 않음)
BREAK_PUNCT = ",.?!"   # 이 뒤에서 끊는 것을 우선 (공백은 그 앞에서 끊는다)

# 렌더 캔버스(render.py 와 동일)
OUT_W = 720
OUT_H = 1280
VIDEO_H = round(OUT_W * 9 / 16)                 # 레터박스 안 16:9 영상 높이 (405)
VIDEO_TOP = (OUT_H - VIDEO_H) / 2
VIDEO_BOTTOM = VIDEO_TOP + VIDEO_H              # 영상 하단 y (≈842)

# 자막 크기(px). 18자 × 크기가 캔버스 폭 안에 들어오도록 잡았다.
SUBTITLE_SIZE_PX = {"small": 28, "medium": 32, "large": 36}
OUTLINE_PX = 3
OVERLAY_GAP = 28       # overlay: 영상 하단에서 위로 띄우는 간격

FONT_NAME = "Pretendard"
# libass 의 Fontsize 는 em 이 아니라 줄 높이(ascent+descent) 기준이라, em 기준 px(브라우저 CSS font-size 와 동일)로
# 맞추려면 (ascent+descent)/unitsPerEm 을 곱해야 한다. Pretendard: (1950+494)/2048 = 1.193
ASS_FONT_SCALE = 1.193


# ───────────────────────── 추출 ─────────────────────────

def _merged_path(task_id: str) -> str:
    return os.path.join(config.STT_RESULTS_DIR, f"{task_id}_merged.json")


def split_text_to_lines(text: str, line_chars: int = LINE_CHARS) -> list[str]:
    """
    줄당 최대 line_chars 자로 나눈다.
    끊는 위치: 18자 안에서 가장 뒤쪽의 쉼표/마침표 뒤 또는 공백 앞. 없으면 18자에서 자른다.
    (프론트 utils/subtitle.js 의 splitTextToLines 와 동일 규칙 - 함께 고칠 것)
    """
    s = " ".join(text.split())
    out: list[str] = []
    while len(s) > line_chars:
        cut = -1
        for i, ch in enumerate(s[: line_chars + 1]):
            if ch in BREAK_PUNCT and i + 1 <= line_chars:
                cut = i + 1
            elif ch == " " and 0 < i <= line_chars:
                cut = i
        if cut <= 0:
            cut = line_chars
        out.append(s[:cut].strip())
        s = s[cut:].lstrip()
    if s:
        out.append(s)
    return out


def split_utterance(start_ms: int, end_ms: int, text: str, lines_per_cue: int = DEFAULT_LINES) -> list[dict]:
    """
    발화 1개를 자막들로 쪼갠다(lines_per_cue 줄 단위). 시간은 발화 구간 안에서 글자 수 비율로 배분하고,
    표시 시간이 MIN_CUE_MS 미만인 자막은 다음 자막과 합친다(마지막이 짧으면 앞 자막과 합침).
    """
    lines = split_text_to_lines(text)
    if not lines:
        return []
    n = 2 if lines_per_cue == 2 else 1
    chunks = [lines[i:i + n] for i in range(0, len(lines), n)]
    weights = [max(1, sum(len(ln) for ln in c)) for c in chunks]
    total = sum(weights)
    dur = end_ms - start_ms

    cues = []
    acc = 0
    for chunk, w in zip(chunks, weights):
        s = start_ms + round(dur * acc / total)
        acc += w
        e = start_ms + round(dur * acc / total)
        cues.append({"start_ms": s, "end_ms": e, "text": "\n".join(chunk)})

    def can_join(a: str, b: str) -> bool:
        # 1줄 모드: 공백으로 이어 붙이되 결과가 22자를 넘으면 합치지 않는다 / 2줄 모드: 줄바꿈으로 이어 붙임
        return n == 2 or len(a) + 1 + len(b) <= MERGE_MAX_CHARS

    def join_text(a: str, b: str) -> str:
        return a + ("\n" if n == 2 else " ") + b

    merged: list[dict] = []
    i = 0
    while i < len(cues):
        cur = dict(cues[i])
        i += 1
        while (cur["end_ms"] - cur["start_ms"] < MIN_CUE_MS and i < len(cues)
               and can_join(cur["text"], cues[i]["text"])):
            nxt = cues[i]
            i += 1
            cur["end_ms"] = nxt["end_ms"]
            cur["text"] = join_text(cur["text"], nxt["text"])
        merged.append(cur)
    if (len(merged) > 1 and merged[-1]["end_ms"] - merged[-1]["start_ms"] < MIN_CUE_MS
            and can_join(merged[-2]["text"], merged[-1]["text"])):
        last = merged.pop()
        merged[-1]["end_ms"] = last["end_ms"]
        merged[-1]["text"] = join_text(merged[-1]["text"], last["text"])
    return merged


def load_subtitles(task_id: str, start_ms: int, end_ms: int, lines_per_cue: int = DEFAULT_LINES) -> Optional[list[dict]]:
    """
    merged.json 의 segments(speaker != "none") 중 [start_ms, end_ms] 와 겹치는 발화를 자막으로 만든다.
    merged.json 이 없으면 None. 발화를 쪼갠 뒤 구간과 겹치는 자막 줄만 남긴다.
    """
    path = _merged_path(task_id)
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as f:
        data = json.load(f)

    subs: list[dict] = []
    for seg in data.get("segments", []):
        if seg.get("speaker") == "none" or not (seg.get("text") or "").strip():
            continue
        if seg["end_ms"] <= start_ms or seg["start_ms"] >= end_ms:
            continue
        for cue in split_utterance(seg["start_ms"], seg["end_ms"], seg["text"], lines_per_cue):
            if cue["end_ms"] > start_ms and cue["start_ms"] < end_ms:
                subs.append(cue)
    return subs


# ───────────────────────── ASS 생성 ─────────────────────────

def _ass_time(ms: int) -> str:
    cs = round(ms / 10)                          # centisecond
    h, rem = divmod(cs, 360000)
    m, rem = divmod(rem, 6000)
    s, cs = divmod(rem, 100)
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


def wrap_cue_text(text: str) -> str:
    """
    자막 본문 정리(렌더/미리보기 공통): { } 역슬래시 제거, 줄바꿈 유지, 18자 넘는 줄은 같은 규칙으로 다시 나눔.
    (프론트 utils/subtitle.js 의 wrapCueText 와 동일)
    """
    text = text.replace("{", "(").replace("}", ")").replace("\\", "")
    out: list[str] = []
    for ln in text.split("\n"):
        ln = " ".join(ln.split())
        if not ln:
            continue
        # 합쳐진 자막(최대 22자)은 그대로 두고, 그보다 긴 줄만 18자 규칙으로 다시 나눈다
        out.extend([ln] if len(ln) <= MERGE_MAX_CHARS else split_text_to_lines(ln))
    return "\n".join(out)


def line_font_scale(text: str) -> float:
    """19~22자 줄은 18자 줄과 같은 폭이 되도록 글자를 줄인다(화면 폭 초과 방지). 프론트 lineFontScale 와 동일."""
    longest = max((len(ln) for ln in wrap_cue_text(text).split("\n")), default=0)
    return min(1.0, LINE_CHARS / longest) if longest else 1.0


def _ass_text(text: str) -> str:
    return wrap_cue_text(text).replace("\n", "\\N")


def subtitle_center_y(position: str, title_top_y: Optional[float]) -> tuple[int, int]:
    """
    (정렬 코드, y) 를 돌려준다.
      letterbox : 영상 아래 검은 여백의 세로 중앙 (\\an5).
                  제목이 하단이면 제목 윗선까지의 여백 중앙으로 올려 겹침을 피한다.
      overlay   : 영상 하단 바로 위에 하단 정렬 (\\an2).
    """
    if position == "overlay":
        return 2, round(VIDEO_BOTTOM - OVERLAY_GAP)
    bottom = title_top_y if title_top_y is not None else OUT_H
    return 5, round((VIDEO_BOTTOM + bottom) / 2)


def build_ass(
    subtitles: list[dict],
    clip_start_ms: int,
    clip_end_ms: int,
    position: str,
    size_px: int,
    title_top_y: Optional[float] = None,
) -> Optional[str]:
    """
    원본 기준 자막 목록을 클립 상대시간으로 바꿔 .ass 문자열을 만든다.
    표시할 자막이 하나도 없으면 None.
    """
    clip_dur = clip_end_ms - clip_start_ms
    align, y = subtitle_center_y(position, title_top_y)

    events = []
    for sub in sorted(subtitles, key=lambda s: s["start_ms"]):
        s = max(0, sub["start_ms"] - clip_start_ms)
        e = min(clip_dur, sub["end_ms"] - clip_start_ms)
        raw = sub.get("text") or ""
        text = _ass_text(raw)
        k = line_font_scale(raw)
        if k < 1.0 and text:
            text = f"{{\\fscx{round(k * 100)}\\fscy{round(k * 100)}}}" + text
        if e <= s or not text:
            continue
        events.append(
            f"Dialogue: 0,{_ass_time(s)},{_ass_time(e)},Sub,,0,0,0,,"
            f"{{\\an{align}\\pos({OUT_W // 2},{y})}}{text}"
        )
    if not events:
        return None

    header = (
        "[Script Info]\n"
        "ScriptType: v4.00+\n"
        f"PlayResX: {OUT_W}\n"
        f"PlayResY: {OUT_H}\n"
        "WrapStyle: 2\n"                       # 자동 줄바꿈 끔(\N 만 사용)
        "ScaledBorderAndShadow: yes\n\n"
        "[V4+ Styles]\n"
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, "
        "Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, "
        "Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\n"
        # 흰 글씨(&H00FFFFFF) + 검은 외곽선(&H00000000), 그림자 없음
        f"Style: Sub,{FONT_NAME},{round(size_px * ASS_FONT_SCALE)},&H00FFFFFF,&H00FFFFFF,&H00000000,&H00000000,"
        f"-1,0,0,0,100,100,0,0,1,{OUTLINE_PX},0,2,20,20,20,1\n\n"
        "[Events]\n"
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
    )
    return header + "\n".join(events) + "\n"


def escape_filter_path(path: str) -> str:
    """
    ffmpeg 필터 옵션값에 경로를 넣기 위한 escape.
    Windows 경로의 역슬래시는 '/' 로 바꾸고, 드라이브 콜론(C:)과 필터 구분 문자를 escape 한다.
    (Linux 경로는 그대로 통과)
    """
    p = path.replace("\\", "/")
    for ch in (":", "'", ",", "[", "]", ";"):
        p = p.replace(ch, "\\" + ch)
    return p


def build_ass_filter(ass_path: str) -> str:
    """ass 필터 문자열. 폰트는 app/fonts 의 Pretendard 를 fontsdir 로 지정한다."""
    return (
        f"ass=filename='{escape_filter_path(ass_path)}':"
        f"fontsdir='{escape_filter_path(config.FONTS_DIR)}'"
    )
