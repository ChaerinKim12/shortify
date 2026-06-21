"""
===============================================================
analyze() 더미 스텁 (app/analyze.py)
===============================================================
⬅ 알고리즘 담당이 제공할 함수의 "끼울 자리".

실제 함수는 이 시그니처 그대로, 내부에서
  오디오추출 -> STT -> 음성힌트 -> Claude 추천
전 과정을 수행하고 결과를 돌려준다.

지금은 그 함수가 없으므로, 같은 시그니처로 가짜 결과 1개를 반환해
API 가 end-to-end 로 돌아가는지 확인할 수 있게만 해 둔다.
나중에 알고리즘 담당 함수로 이 파일의 analyze() 만 교체하면 된다.

[계약 - 알고리즘 담당과 합의 필요]
입력:
  source       : 분석 대상. source_type="file"이면 NFS에 저장된 파일 경로,
                 source_type="url"이면 유튜브 URL 문자열.
  source_type  : "file" 또는 "url"
  clip_count   : 뽑을 클립 개수 (1~5)
  category     : 카테고리 키 (예: "empathy")
  user_prompt  : 사용자 추가 요청 (없으면 "")

반환(dict):
  {
    "video_duration_ms": int,
    "clips": [
      { "rank", "start_ms", "end_ms", "duration_sec", "reason", "titles": [...],
        # score 등 추가 필드는 있어도 됨 (result에서 같이 실어 나중에 추림)
      }, ...
    ]
  }
===============================================================
"""


def analyze(
    source: str,
    source_type: str,
    clip_count: int,
    category: str,
    user_prompt: str,
) -> dict:
    """[더미] 입력을 받되 실제 분석은 하지 않고 가짜 clips 1개를 반환한다."""
    fake_clip = {
        "rank": 1,
        "start_ms": 0,
        "end_ms": 45000,
        "duration_sec": 45.0,
        "score": 5,
        "score_reason": "[더미] 스텁 고정값",
        "reason": (
            f"[더미 클립] source_type={source_type}, category={category}, "
            f"clip_count={clip_count}, user_prompt={user_prompt!r} 로 호출됨. "
            "실제 분석 결과 아님 — 알고리즘 담당 analyze()로 교체 예정."
        ),
        "titles": ["[더미] 제목 후보 1", "[더미] 제목 후보 2", "[더미] 제목 후보 3"],
    }

    return {
        "video_duration_ms": 60000,
        "clips": [fake_clip],
    }
