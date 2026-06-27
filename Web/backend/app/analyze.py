"""
===============================================================
analyze() 연결 레이어 (app/analyze.py)
===============================================================
알고리즘 담당이 만든 실제 분석 함수(Web/algorithm/analyze.py)를 끌어와
백엔드가 부르는 단일 진입점 analyze() 로 노출한다.

[계약 - Web/algorithm 레퍼런스 기준 확정]
입력:
  video_path   : 분석 대상 영상 경로. URL 케이스에서도 작업명(name) 추출에 쓰이므로
                 항상 {UPLOAD_DIR}/{task_id}.mp4 형태로 넘긴다.
  categories   : ["empathy","laughter","info","touching"] 중 1~4개 리스트
  user_prompt  : 사용자 추가 요청 (없으면 "")
  youtube_url  : URL 업로드일 때만. 있으면 알고리즘이 다운로드 + 히트맵 사용.
  (clip_count 는 더 이상 받지 않는다 — 목표 클립수는 len(categories)로 자동 결정)

반환(dict):
  {
    "video_duration_ms": int,
    "clips": [
      { "rank", "category": [...], "start_ms", "end_ms",
        "duration_sec"(int), "reason", "titles": [...] }, ...
    ]
  }

[import 경로]
  Web/algorithm/ 은 backend/app 밖(형제 폴더)에 있고, 그 안의 모듈들이
  `import config` 같은 top-level import 를 쓰므로 해당 폴더를 sys.path 에 올려야 한다.
  실제 모듈/의존성(anthropic, librosa, ffmpeg 등)이 아직 없으면 import 가 실패할 수 있어
  그 경우 더미 결과로 폴백한다 (_USE_REAL=False). 환경이 갖춰지면 자동으로 실제 분석을 탄다.
===============================================================
"""

import os
import sys

# Web/algorithm 디렉토리: backend/app -> backend -> Web -> Web/algorithm
_ALGO_DIR = os.path.normpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "algorithm")
)
if _ALGO_DIR not in sys.path:
    sys.path.insert(0, _ALGO_DIR)

# 실제 알고리즘 모듈 연결 시도. 실패하면 더미 폴백.
try:
    import analyze as _algo  # Web/algorithm/analyze.py (top-level module)

    _USE_REAL = True
    _IMPORT_ERROR = None
except Exception as e:  # ImportError 외에 의존성 로드 실패 등도 폴백 처리
    _algo = None
    _USE_REAL = False
    _IMPORT_ERROR = e


def _dummy_analyze(video_path: str, categories: list, user_prompt: str) -> dict:
    """
    [더미] 실제 분석 없이 계약 형태의 가짜 결과를 반환한다.
    실제 algorithm 모듈을 import 하지 못했을 때만 쓰인다 (환경 미구성).
    계약 7필드(category 리스트 / duration_sec 정수 포함)를 그대로 지킨다.
    """
    cats = list(categories) or ["empathy"]
    fake_clip = {
        "rank": 1,
        "category": cats,
        "start_ms": 0,
        "end_ms": 45000,
        "duration_sec": 45,
        "reason": (
            f"[더미 클립] video_path={video_path!r}, categories={cats}, "
            f"user_prompt={user_prompt!r} 로 호출됨. 실제 분석 결과 아님 — "
            f"algorithm 모듈 미연결({_IMPORT_ERROR!r}). 환경 구성되면 자동 전환."
        ),
        "titles": ["[더미] 제목 후보 1", "[더미] 제목 후보 2", "[더미] 제목 후보 3"],
    }
    return {
        "video_duration_ms": 60000,
        "clips": [fake_clip],
    }


def analyze(
    video_path: str,
    categories: list,
    user_prompt: str = "",
    youtube_url: str = None,
    on_progress=None,
) -> dict:
    """
    백엔드가 부르는 단일 진입점. 실제 algorithm.analyze() 로 위임하고,
    모듈이 없으면 더미로 폴백한다. (반환 계약은 양쪽 동일)
    on_progress: 단계별 진행률 콜백(선택). 실제 algorithm.analyze() 로 그대로 전달.
    """
    if _USE_REAL:
        return _algo.analyze(
            video_path=video_path,
            categories=categories,
            user_prompt=user_prompt,
            youtube_url=youtube_url,
            on_progress=on_progress,
        )
    return _dummy_analyze(video_path, categories, user_prompt)
