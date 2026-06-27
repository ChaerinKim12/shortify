"""
===============================================================
진입점 (analyze.py)
===============================================================
백엔드가 부르는 단 하나의 함수 analyze() 를 제공한다.
지금까지 만든 조각(prompts / recommend / postprocess)과
기존 전처리 모듈(download / extract_audio / stt / audio_features)을
순서대로 엮어 최종 결과 JSON 을 만든다.

[백엔드 사용법]
  result = analyze(
      video_path="/nfs/team/.../영상.mp4",
      categories=["empathy", "laughter"],   # 1~4개
      user_prompt="감동적인 부분 위주로",      # 없으면 ""
      youtube_url=None,                       # URL 업로드면 채움
  )
  -> {"video_duration_ms": 1320000, "clips": [...]}

실패 시 예외(Exception)를 던진다. 백엔드가 try/except 로 받아
task 상태를 failed 로 처리한다.

[전처리 4개 모듈 인터페이스 - 가정]
  실제 파일을 아직 확인하지 않았으므로 run_all.py 호출 방식 기준으로 가정한다.
  실제 시그니처가 다르면 _run_preprocess() 안의 호출만 고치면 된다.
    download.download_video(youtube_url, name)  -> NFS 에 {name}.mp4 저장
    extract_audio.extract_audio(name)           -> 오디오 wav 생성
    stt.transcribe(name)                        -> STT 결과 생성
    audio_features.merge_hints(name)            -> {RESULTS_DIR}/{name}_merged.json 생성
  merged.json 구조(가정):
    {
      "formatted": ["12400ms~18700ms / [p1] 발화 [음량↑]", ...],
      "segments":  [{"start_ms":.., "end_ms":.., "speaker":"p1"}, ...]
    }
===============================================================
"""

import json
import os
import shutil
import subprocess

import config
import recommend
import postprocess

# 전처리 모듈 (기존 파이프라인)
import download
import extract_audio
import stt
import audio_features


# ===============================================================
# 헬퍼: 진행률 콜백 안전 호출
# ===============================================================
def _report(on_progress, percent: int, message: str = None) -> None:
    """
    백엔드가 넘긴 진행률 콜백을 안전하게 호출한다.
    콜백이 없거나(None) 콜백에서 예외가 나도 분석은 계속되어야 한다.
    """
    if on_progress is None:
        return
    try:
        on_progress(percent, message)
    except Exception as e:  # noqa: BLE001 - 진행률 보고 실패는 무시
        print(f"[경고] 진행률 콜백 실패: {e}")


# ===============================================================
# 헬퍼: 영상 경로에서 작업 이름(name) 뽑기
# ===============================================================
def _derive_name(video_path: str) -> str:
    """
    영상 파일 경로에서 확장자를 뗀 파일명을 작업 이름으로 쓴다.
    (전처리 모듈들이 이 name 으로 중간 파일을 찾고 쓰므로 일관돼야 한다)
    """
    return os.path.splitext(os.path.basename(video_path))[0]


# ===============================================================
# 헬퍼: 영상 길이 (ffprobe). 실패 시 0
# ===============================================================
def _get_video_duration_ms(video_path: str) -> int:
    """ffprobe 로 영상 길이를 ms 로 반환한다. 실패하면 0."""
    command = [
        "ffprobe", "-v", "quiet",
        "-show_entries", "format=duration",
        "-of", "csv=p=0",
        video_path,
    ]
    try:
        result = subprocess.run(command, capture_output=True, text=True)
        return int(float(result.stdout.strip()) * 1000)
    except Exception as e:
        print(f"[경고] ffprobe 실패, 세그먼트 기반 추정으로 대체: {e}")
        return 0


def _resolve_duration_ms(merged_data: dict, video_path: str) -> int:
    """영상 길이를 구한다. ffprobe 실패 시 마지막 세그먼트 end_ms 로 폴백."""
    duration = _get_video_duration_ms(video_path)
    if duration == 0:
        segments = merged_data.get("segments", [])
        duration = max((s.get("end_ms", 0) for s in segments), default=0)
    return duration


# ===============================================================
# 헬퍼: 유튜브 히트맵 (URL 업로드일 때만)
# ===============================================================
def _get_youtube_heatmap(url: str) -> list:
    """yt-dlp 로 히트맵(Most Replayed) 데이터를 추출한다. 실패하면 빈 리스트."""
    try:
        result = subprocess.run(
            ["yt-dlp", "--dump-json", url],
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode != 0:
            print(f"[경고] yt-dlp 실행 실패: {result.stderr[:100]}")
            return []
        data = json.loads(result.stdout)
        raw = data.get("heatmap", [])
        if not raw:
            print("[정보] 히트맵 데이터 없음")
            return []
        return [
            {
                "time_range_start_ms": int(m["start_time"] * 1000),
                "intensity": float(m["value"]),
            }
            for m in raw
        ]
    except Exception as e:
        print(f"[경고] 히트맵 추출 실패: {e}")
        return []


def _format_heatmap(heatmap: list) -> str:
    """히트맵을 프롬프트용 텍스트로 변환한다. 상위 20% 구간만(토큰 절약)."""
    if not heatmap:
        return ""
    intensities = sorted((m["intensity"] for m in heatmap), reverse=True)
    threshold = intensities[max(0, len(heatmap) // 5)]
    hot = [m for m in heatmap if m["intensity"] >= threshold]
    lines = ["[히트맵 데이터 - 시청자 반복 재생 구간 (상위 20%)]"]
    for m in hot:
        sec = m["time_range_start_ms"] // 1000
        lines.append(f"  {m['time_range_start_ms']}ms ({sec}초) / 강도 {m['intensity']:.2f}")
    return "\n".join(lines)


# ===============================================================
# 전처리: 영상 -> merged.json
# ===============================================================
def _run_preprocess(name: str, video_path: str, youtube_url: str = None,
                    on_progress=None) -> tuple[dict, str]:
    """
    영상 1개를 전처리해서 (merged_data, source_path)를 돌려준다.
    URL 이면 download 로 받고, 로컬이면 백엔드가 준 video_path 를 그대로 쓴다.
    source_path 는 전처리에 실제로 사용한 NFS mp4 경로(미리보기/렌더가 볼 파일).
    on_progress: 단계별 진행률 콜백(선택). 오디오추출(10) -> STT(40) 경계에서 보고.
    """
    if youtube_url:
        print(f"[정보] 유튜브 URL -> 다운로드 시작: {name}")
        source_path = download.download_video(youtube_url, name)
    else:
        # 로컬 업로드: 하위 모듈들이 NFS/{name}.mp4 를 기대하므로 그 위치로 모아준다.
        # (백엔드가 어디에 저장했든 진입점에서 경로를 일원화한다)
        dst = os.path.join(config.NFS_DOWNLOAD_DIR, f"{name}.mp4")
        if os.path.abspath(video_path) != os.path.abspath(dst):
            os.makedirs(config.NFS_DOWNLOAD_DIR, exist_ok=True)
            shutil.copy(video_path, dst)
            print(f"[정보] 로컬 파일 -> NFS 복사: {video_path} -> {dst}")
        else:
            print(f"[정보] 로컬 파일이 이미 NFS 위치에 있음: {dst}")
        source_path = dst

    _report(on_progress, 10, "오디오 추출중")
    extract_audio.extract_audio(name)   # mp4 -> wav

    _report(on_progress, 40, "음성인식(STT) 처리중")
    stt.transcribe(name)                # STT + 화자분리
    audio_features.merge_hints(name)    # 음성힌트 머지 -> merged.json

    merged_path = os.path.join(config.RESULTS_DIR, f"{name}_merged.json")
    if not os.path.exists(merged_path):
        raise RuntimeError(f"전처리 결과 파일 없음: {merged_path}")
    with open(merged_path, "r", encoding="utf-8") as f:
        merged_data = json.load(f)
    return merged_data, source_path


# ===============================================================
# 메인 진입점
# ===============================================================
def analyze(
    video_path: str,
    categories: list,
    user_prompt: str = "",
    youtube_url: str = None,
    on_progress=None,
) -> dict:
    """
    백엔드가 부르는 단 하나의 함수.
    영상 1개를 분석해 추천 클립 목록(계약 JSON)을 반환한다.

    Args:
        video_path: 영상 파일 경로 (로컬 업로드면 백엔드가 저장해둔 경로)
        categories: ["empathy","laughter","info","touching"] 중 1~4개
        user_prompt: 사용자 자유 입력 (없으면 "")
        youtube_url: URL 업로드일 때만. 있으면 다운로드 + 히트맵.
        on_progress: 단계별 진행률 콜백(선택). on_progress(percent:int, message:str=None).
                     없으면(None) 아무 것도 하지 않는다(기존 동작 그대로).

    Returns:
        {"video_duration_ms": int, "clips": [...계약 7필드...],
         "source_path": str}  # 미리보기/렌더가 볼 실제 mp4 경로 (백엔드가 video_path로 사용)

    Raises:
        ValueError: 카테고리 입력이 잘못된 경우
        RuntimeError/Exception: 전처리/추천 실패 (모든 카테고리 실패 등)
    """
    # 0) 입구 검사
    config.validate_categories(categories)
    name = _derive_name(video_path)
    print(f"\n{'='*55}\n  분석 시작: {name} / 카테고리 {categories}\n{'='*55}")

    # 1) 전처리 -> merged.json (오디오추출 10 / STT 40 진행률 보고는 내부에서)
    merged_data, source_path = _run_preprocess(
        name, video_path, youtube_url=youtube_url, on_progress=on_progress,
    )

    # 2) 영상 길이 (프롬프트/검증 양쪽에서 쓰므로 한 번만)
    video_duration_ms = _resolve_duration_ms(merged_data, video_path)

    # 3) 히트맵 (URL 케이스만)
    heatmap_text = ""
    if youtube_url:
        heatmap_text = _format_heatmap(_get_youtube_heatmap(youtube_url))

    # 4) 카테고리별 구간 추출 (temp 0.3, 실패 격리)
    _report(on_progress, 65, "AI 구간 분석중")
    clips = recommend.extract_all_segments(
        merged_data=merged_data,
        categories=categories,
        video_duration_ms=video_duration_ms,
        user_prompt=user_prompt,
        heatmap_text=heatmap_text,
    )

    # 5) 후처리: 병합 -> 라운드로빈 캡
    _report(on_progress, 90, "결과 준비")
    clips = postprocess.dedup_clips(clips)
    target = config.get_target_clip_count(len(categories))
    clips = postprocess.cap_clips(clips, categories, target)
    print(f"[정보] dedup+캡 후 클립 수: {len(clips)} (목표 {target})")

    # 6) 제목 생성 (temp 1.0)
    clips = recommend.generate_titles(clips, merged_data)

    # 7) 검증 + 계약 필드 정리
    clips = postprocess.validate_clips(clips, video_duration_ms)
    clips = postprocess.strip_to_contract(clips)

    result = {
        "video_duration_ms": video_duration_ms,
        "clips": clips,
        "source_path": source_path,   # 미리보기/렌더가 볼 실제 mp4 경로(백엔드가 video_path 로 사용)
    }
    print(f"[완료] 분석 종료: {name} / 최종 클립 {len(clips)}개")
    return result