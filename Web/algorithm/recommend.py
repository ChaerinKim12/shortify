"""
===============================================================
구간 추출 + 제목 생성 (recommend.py)
===============================================================
알고리즘의 엔진. Claude 를 호출해서 클립 구간과 제목을 뽑는다.
2단계로 나눠 작업마다 temperature 를 다르게 준다.
  1) 구간 추출 (temp=0.3): 카테고리별로 호출. 정확/일관 중요.   <- 이 파일 1부
  2) 제목 생성 (temp=1.0): 최종 클립에 제목 3개씩. 창의 중요.   <- 이 파일 2부(다음)

[이 파일의 책임 범위]
  "프롬프트 -> Claude 호출 -> JSON 파싱"에만 집중한다.
  히트맵 크롤링(yt-dlp), 영상 길이(ffprobe) 같은 외부 의존은 직접 하지 않고,
  상위(analyze.py)가 준비해서 heatmap_text / video_duration_ms 로 넘겨준다.
  -> recommend 가 순수해지고 테스트(모킹)가 쉬워진다.

[실패 정책 - (a) 실패 격리]
  카테고리별로 호출하되, 한 카테고리가 끝까지 실패해도
  그 카테고리만 건너뛰고 나머지는 계속한다(데모 안정성 우선).
  단, 모든 카테고리가 실패하면 그때는 예외를 던진다.
===============================================================
"""

import json
import re

from anthropic import Anthropic
from dotenv import load_dotenv

import config
from prompts import base
from prompts import get_category_prompt

# .env 에서 ANTHROPIC_API_KEY 자동 로드
load_dotenv()
client = Anthropic()

CLAUDE_MODEL = config.CLAUDE_MODEL


# ===============================================================
# JSON 추출 헬퍼 (마커 사이의 JSON 배열을 꺼냄)
# ===============================================================
def extract_json_between(text: str, start_re: str, end_re: str) -> list:
    """
    응답 텍스트에서 시작/끝 마커 사이의 JSON 배열을 꺼낸다.
    끝 마커가 없으면 첫 번째 대괄호 배열을 시도한다.
    """
    start_match = re.search(start_re, text)
    if not start_match:
        raise ValueError("START 마커 없음")

    after_start = text[start_match.end():].strip()

    end_match = re.search(end_re, after_start)
    if end_match:
        json_str = after_start[:end_match.start()].strip()
    else:
        bracket = re.search(r"\[.*\]", after_start, re.DOTALL)
        if not bracket:
            raise ValueError("JSON 배열 없음")
        json_str = bracket.group(0)

    return json.loads(json_str)


# ===============================================================
# 1차 응답 JSON 파싱 (실패 시 최대 2회 재요청)
# ===============================================================
def parse_segment_json(response_text: str, label: str, retry_count: int = 0) -> list:
    """
    1차(구간) 응답에서 FINAL_JSON 마커 사이 JSON 을 꺼낸다.
    파싱 실패 시 Claude 에게 JSON 만 다시 요청한다(최대 2회).

    Args:
        response_text: Claude 응답 원문
        label: 로그용 라벨 (예: "empathy")
        retry_count: 내부 재귀 카운터
    """
    try:
        return extract_json_between(
            response_text,
            r"=+FINAL_JSON_START=+",
            r"=+FINAL_JSON_END=+",
        )
    except Exception as e:
        if retry_count >= 2:
            print(f"[오류] {label} 구간 JSON 파싱 최종 실패: {e}")
            raise

        print(f"[경고] {label} 구간 JSON 파싱 실패 ({e}), 재시도 {retry_count + 1}/2...")

        retry_format = (
            "===FINAL_JSON_START===\n"
            "[{\"rank\":1,\"start_ms\":0,\"end_ms\":0,\"duration_sec\":0,"
            "\"score\":5,\"score_reason\":\"...\",\"reason\":\"...\"}]\n"
            "===FINAL_JSON_END==="
        )
        retry = client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=config.MAX_TOKENS,
            temperature=config.TEMP_SEGMENT,
            messages=[
                {"role": "user", "content": "이전 분석 결과를 바탕으로 아래 마커와 JSON만 출력하세요. 설명/백틱 금지.\n\n" + retry_format},
                {"role": "assistant", "content": response_text},
                {"role": "user", "content": "마커 사이에 JSON만 출력하세요."},
            ],
        )
        return parse_segment_json(retry.content[0].text, label, retry_count + 1)


# ===============================================================
# 단일 카테고리 구간 추출 (1차 호출, temp=0.3)
# ===============================================================
def extract_segments_for_category(
    merged_data: dict,
    category_code: str,
    video_duration_ms: int,
    user_prompt: str = "",
    heatmap_text: str = "",
) -> list:
    """
    한 카테고리에 대해 Claude 를 1번 호출해 구간 후보를 추출한다.
    뽑힌 각 클립에는 어느 카테고리에서 나왔는지 category 꼬리표를 단다.
    (병합을 대비해 처음부터 리스트로: category = [category_code])

    Returns:
        clip 딕셔너리 리스트. 추천 없으면 빈 리스트.
    """
    category_name = config.CATEGORIES[category_code]
    category_prompt = get_category_prompt(category_code)

    # merged.json 에서 자막/발화수 뽑기
    formatted_lines = merged_data.get("formatted", [])
    subtitle_text = "\n".join(formatted_lines)
    segment_count = len([
        s for s in merged_data.get("segments", [])
        if s.get("speaker") != "none"
    ])

    prompt = base.build_segment_prompt(
        subtitle_text=subtitle_text,
        segment_count=segment_count,
        video_duration_ms=video_duration_ms,
        category_name=category_name,
        category_prompt=category_prompt,
        per_category_max=config.PER_CATEGORY_MAX,
        user_prompt=user_prompt,
        heatmap_text=heatmap_text,
    )

    print(f"[정보] [{category_code}] 구간 추출 호출 / 프롬프트 {len(prompt)}자 / temp={config.TEMP_SEGMENT}")

    resp = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=config.MAX_TOKENS,
        temperature=config.TEMP_SEGMENT,
        messages=[{"role": "user", "content": prompt}],
    )
    text = resp.content[0].text

    if resp.stop_reason in ("max_tokens", "model_context_window_exceeded"):
        print(f"[경고] [{category_code}] 출력이 잘렸을 수 있음 (stop_reason={resp.stop_reason})")

    clips = parse_segment_json(text, category_code)

    # category 꼬리표 부착 (병합 대비 리스트)
    for clip in clips:
        clip["category"] = [category_code]

    print(f"[완료] [{category_code}] 구간 {len(clips)}개 추출")
    return clips


# ===============================================================
# 전체 카테고리 구간 추출 ((a) 실패 격리 정책)
# ===============================================================
def extract_all_segments(
    merged_data: dict,
    categories: list,
    video_duration_ms: int,
    user_prompt: str = "",
    heatmap_text: str = "",
) -> list:
    """
    사용자가 고른 카테고리 전부에 대해 구간을 추출해 한 리스트로 합친다.

    실패 정책 (a):
      - 한 카테고리가 끝까지 실패하면 그 카테고리만 건너뛰고 계속.
      - 단, 모든 카테고리가 실패하면 예외를 던진다.

    Returns:
        모든 카테고리에서 뽑힌 clip 들을 합친 리스트 (아직 dedup/캡 전).
    """
    all_clips = []
    failures = []

    for code in categories:
        try:
            clips = extract_segments_for_category(
                merged_data=merged_data,
                category_code=code,
                video_duration_ms=video_duration_ms,
                user_prompt=user_prompt,
                heatmap_text=heatmap_text,
            )
            all_clips.extend(clips)
        except Exception as e:
            failures.append(code)
            print(f"[경고] [{code}] 카테고리 추출 실패 -> 건너뜀: {e}")

    # 모든 카테고리가 실패한 경우에만 전체 실패로 처리
    if failures and len(failures) == len(categories):
        raise RuntimeError(f"모든 카테고리 구간 추출 실패: {failures}")

    print(f"[완료] 전체 구간 추출: {len(all_clips)}개 "
          f"(성공 {len(categories) - len(failures)}/{len(categories)} 카테고리)")
    return all_clips


# ===============================================================
# ===============================================================
# 2부: 제목 생성 (2차 호출, temp=1.0)
# ===============================================================
# 구간이 확정된 뒤, 각 클립에 클릭을 부르는 제목 3개씩을 단다.
# 호출은 1번만 한다(모든 클립을 한 번에). 카테고리별로 톤이 다르므로,
# 프롬프트 안에서 각 클립의 category 에 따라 톤을 분기한다.
# 제목은 없어도 치명적이지 않으므로(프론트가 직접입력/건너뛰기 제공),
# 파싱이 끝까지 실패하면 예외 대신 "제목 없이 진행"한다.
# ===============================================================

# 카테고리별 제목 톤 가이드 (touching 에서 분리해온 감동 톤 포함)
TITLE_TONE_BY_CATEGORY = {
    "empathy": "공감 직격형. 20대가 '어 나도' 하게. 자기 경험을 건드리는 톤.",
    "laughter": "웃음 유발형. 피식하게 만드는 톤. 어이없음/예상 뒤집힘을 살림.",
    "info": "정보 호기심형. '이거 몰랐다' 싶게. 단, 낚시 금지(내용과 일치).",
    "touching": (
        "감동/뭉클형. 구체적 디테일(숫자/인물/행동)을 활용한 자연스러운 톤. "
        "'눈물 주의', '충격', 괄호 강조 같은 옛날 자극 문법 금지. "
        "'감동' 단어 직접 사용 금지(보여주기). 예: '23년 만에 제일 축하 많이 받은 생일'"
    ),
}


TITLE_PROMPT = """
[역할]
당신은 유튜브 쇼츠 제목 카피라이터입니다.
이미 선정된 클립 구간마다, 클릭을 부르는 제목 3개를 짓습니다.

[공통 제목 기준]
- 30자 이내
- 20대 시청자 클릭 유발
- 한 클립당 제목 3개, 서로 다른 패턴:
  제목1: 궁금증 유발형
  제목2: 공감/감정 직격형
  제목3: 반전/감정 자극형
- 금지: 단순 요약형, 낚시성(내용과 무관한 자극)

[카테고리별 톤 - 각 클립의 카테고리에 맞춰 적용]
{tone_guide}

[선정된 클립들]
아래 각 클립의 카테고리/자막/선정 이유를 참고해 제목을 지으세요.

{clips_block}

[출력 형식]
아래 마커와 JSON만 출력하세요. 설명/백틱 금지.
===TITLES_JSON_START===
[
  {{"rank": 1, "titles": ["제목1", "제목2", "제목3"]}}
]
===TITLES_JSON_END===
"""


def get_subtitles_for_range(formatted_lines: list, start_ms: int, end_ms: int) -> list:
    """[start_ms, end_ms] 구간과 겹치는 자막 줄만 골라낸다 (제목 생성용)."""
    picked = []
    for line in formatted_lines:
        m = re.match(r"^(\d+)ms~(\d+)ms", line)
        if not m:
            continue
        s, e = int(m.group(1)), int(m.group(2))
        if e >= start_ms and s <= end_ms:  # 조금이라도 겹치면 포함
            picked.append(line)
    return picked


def build_title_prompt(clips: list, formatted_lines: list) -> str:
    """선정된 구간들 + 각 구간 자막 + 카테고리로 제목 프롬프트를 조립한다."""
    # 이번 클립들에 실제 등장하는 카테고리의 톤만 모아서 안내
    used_codes = set()
    for clip in clips:
        for code in clip.get("category", []):
            used_codes.add(code)
    tone_lines = [
        f"- {config.CATEGORIES.get(code, code)}: {TITLE_TONE_BY_CATEGORY.get(code, '')}"
        for code in used_codes
    ]
    tone_guide = "\n".join(tone_lines) if tone_lines else "(해당 없음)"

    blocks = []
    for clip in clips:
        subs = get_subtitles_for_range(
            formatted_lines, clip["start_ms"], clip["end_ms"]
        )
        subs_text = "\n".join(subs) if subs else "(자막 없음)"
        cat_names = ", ".join(
            config.CATEGORIES.get(c, c) for c in clip.get("category", [])
        )
        blocks.append(
            f"[클립 rank {clip['rank']}] 카테고리: {cat_names}\n"
            f"선정 이유: {clip.get('reason', '')}\n"
            f"자막:\n{subs_text}"
        )
    clips_block = "\n\n".join(blocks)

    return TITLE_PROMPT.format(tone_guide=tone_guide, clips_block=clips_block)


def parse_title_json(response_text: str, retry_count: int = 0) -> list:
    """
    2차(제목) 응답에서 제목 JSON 을 꺼낸다.
    실패 시 1회 재요청, 그래도 실패하면 빈 리스트(제목 없이 진행).
    """
    try:
        return extract_json_between(
            response_text,
            r"=+TITLES_JSON_START=+",
            r"=+TITLES_JSON_END=+",
        )
    except Exception as e:
        if retry_count >= 1:
            print(f"[경고] 제목 JSON 파싱 실패, 제목 없이 진행: {e}")
            return []
        print(f"[경고] 제목 JSON 파싱 실패 ({e}), 재시도 1/1...")
        retry = client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=2000,
            temperature=config.TEMP_TITLE,
            messages=[
                {"role": "user", "content": "이전 응답에서 제목 JSON이 누락되었습니다. ===TITLES_JSON_START=== 와 ===TITLES_JSON_END=== 마커 사이에 JSON만 출력하세요."},
                {"role": "assistant", "content": response_text},
                {"role": "user", "content": "마커 사이에 JSON만 출력하세요."},
            ],
        )
        return parse_title_json(retry.content[0].text, retry_count + 1)


def generate_titles(clips: list, merged_data: dict) -> list:
    """
    [2차 호출] 최종 클립들에 제목 3개씩 생성해 붙인다 (temp=1.0).
    제목 생성이 실패해도 clips 자체는 그대로 반환(titles 빈 리스트).
    """
    if not clips:
        return clips

    formatted_lines = merged_data.get("formatted", [])
    prompt = build_title_prompt(clips, formatted_lines)
    print(f"[정보] 제목 생성 호출 / 프롬프트 {len(prompt)}자 / temp={config.TEMP_TITLE}")

    try:
        resp = client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=2000,
            temperature=config.TEMP_TITLE,
            messages=[{"role": "user", "content": prompt}],
        )
        title_list = parse_title_json(resp.content[0].text)
    except Exception as e:
        print(f"[경고] 제목 생성 호출 실패, 제목 없이 진행: {e}")
        title_list = []

    # rank 를 열쇠로 각 클립에 제목을 붙인다
    title_map = {t.get("rank"): t.get("titles", []) for t in title_list}
    for clip in clips:
        clip["titles"] = title_map.get(clip["rank"], [])

    filled = sum(1 for c in clips if c.get("titles"))
    print(f"[완료] 제목 생성: {filled}/{len(clips)}개 클립에 제목 부착")
    return clips