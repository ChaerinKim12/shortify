"""
===============================================================
STEP 3 - 음성인식 STT (stt.py)
===============================================================
[이 파일이 하는 일]
  wav 오디오를 리턴제로(RTZR) STT API에 보내서
  "누가 / 언제 / 뭐라고" 말했는지 자막으로 받아온다.

  진행 순서:
   1) 인증     : .env 의 ID/시크릿으로 액세스 토큰 발급
   2) 업로드   : wav 전송. 이때 "화자 분리"를 켠다.
                 - 리턴제로가 목소리 음색(성문)으로 화자를 p1, p2 로 나눠줌.
   3) 폴링     : 인식이 끝날 때까지 10초마다 상태 확인
   4) 포맷 변환: 우리 파이프라인 형식으로 정리

[필요한 .env 항목]  RTZR_CLIENT_ID, RTZR_CLIENT_SECRET

[입력]  {AUDIO_DIR}/{영상이름}.wav
[출력]  {RESULTS_DIR}/{영상이름}_stt.json
        예) {"start_ms":12400,"end_ms":18700,"speaker":"p1","text":"진짜 이거 써보고"}
===============================================================
"""

import json
import os
import time

import requests
from dotenv import load_dotenv

import config

# .env 파일에서 리턴제로 자격증명 로드
load_dotenv()

RTZR_CLIENT_ID = os.getenv("RTZR_CLIENT_ID")
RTZR_CLIENT_SECRET = os.getenv("RTZR_CLIENT_SECRET")

AUDIO_DIR = config.AUDIO_DIR
RESULTS_DIR = config.RESULTS_DIR


def get_access_token() -> str:
    """
    리턴제로 API 인증 토큰을 발급받는다.

    Returns:
        액세스 토큰 문자열
    """
    url = "https://openapi.vito.ai/v1/authenticate"
    response = requests.post(
        url,
        data={
            "client_id": RTZR_CLIENT_ID,
            "client_secret": RTZR_CLIENT_SECRET,
        },
    )
    response.raise_for_status()
    token = response.json()["access_token"]
    print("[완료] 리턴제로 인증 토큰 발급 완료")
    return token


def request_transcription(token: str, audio_path: str) -> str:
    """
    오디오 파일을 리턴제로 STT API에 전송하고 작업 ID를 반환한다.
    화자 분리(diarization)를 활성화한다.
    (모노 오디오만 화자 분리 지원 -> STEP 2에서 모노로 변환한 이유)

    Args:
        token: 리턴제로 액세스 토큰
        audio_path: 오디오 파일 경로

    Returns:
        STT 작업 ID
    """
    url = "https://openapi.vito.ai/v1/transcribe"

    with open(audio_path, "rb") as f:
        response = requests.post(
            url,
            headers={"Authorization": f"Bearer {token}"},
            files={"file": f},
            data={
                "config": json.dumps({
                    "use_diarization": True,        # 화자 분리 활성화
                    "diarization": {
                        "spk_count": None,          # 화자 수 자동 감지
                    },
                    "use_itn": True,                # 숫자/단위 정규화 (예: 삼천원 -> 3000원)
                    "use_disfluency_filter": True,  # "음...", "어..." 등 군더더기 제거
                })
            },
        )

    response.raise_for_status()
    task_id = response.json()["id"]
    print(f"[완료] STT 요청 완료 / 작업 ID: {task_id}")
    return task_id


def poll_transcription(token: str, task_id: str) -> dict:
    """
    STT 작업이 끝날 때까지 10초마다 상태를 확인(폴링)한다.

    Args:
        token: 리턴제로 액세스 토큰
        task_id: STT 작업 ID

    Returns:
        STT 결과 딕셔너리
    """
    url = f"https://openapi.vito.ai/v1/transcribe/{task_id}"
    headers = {"Authorization": f"Bearer {token}"}

    while True:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        result = response.json()

        status = result.get("status")
        print(f"[대기] STT 상태: {status}")

        if status == "completed":
            print("[완료] STT 완료")
            return result
        elif status == "failed":
            raise Exception(f"STT 실패: {result}")

        # 아직 처리 중 -> 10초 후 다시 확인
        time.sleep(10)


def format_segments(stt_result: dict) -> list:
    """
    리턴제로 STT 결과를 우리 파이프라인용 세그먼트 포맷으로 변환한다.

    리턴제로는 "시작시각(start_at) + 길이(duration)"로 주는데,
    우리는 "시작ms ~ 끝ms"가 다루기 편해서 더해서 end_ms 를 만든다.
    화자 번호(spk)는 정수(0,1,..)로 오므로 p1, p2.. 형태로 바꾼다.

    Args:
        stt_result: 리턴제로 STT 결과 딕셔너리

    Returns:
        세그먼트 리스트
    """
    segments = []

    utterances = stt_result.get("results", {}).get("utterances", [])

    for utt in utterances:
        start_ms = utt.get("start_at", 0)
        duration_ms = utt.get("duration", 0)
        end_ms = start_ms + duration_ms
        speaker = utt.get("spk", "p1")
        text = utt.get("msg", "").strip()

        # 빈 발화는 제외
        if not text:
            continue

        segments.append({
            "start_ms": start_ms,
            "end_ms": end_ms,
            # spk 가 정수면 p1, p2.. 로 변환 (0 -> p1)
            "speaker": f"p{speaker + 1}" if isinstance(speaker, int) else speaker,
            "text": text,
        })

    return segments


def transcribe(audio_name: str) -> list:
    """
    오디오 1개에 대한 STT 전체 과정을 실행하고 결과를 JSON으로 저장한다.

    Args:
        audio_name: 오디오 파일명 (확장자 제외)

    Returns:
        세그먼트 리스트
    """
    audio_path = f"{AUDIO_DIR}/{audio_name}.wav"
    output_path = f"{RESULTS_DIR}/{audio_name}_stt.json"

    print(f"\n[시작] {audio_name} STT 시작...")

    token = get_access_token()                          # 1. 인증
    task_id = request_transcription(token, audio_path)  # 2. 요청
    result = poll_transcription(token, task_id)         # 3. 완료까지 대기
    segments = format_segments(result)                  # 4. 포맷 변환
    print(f"[완료] 총 {len(segments)}개 발화 추출")

    # 5. 결과 저장
    os.makedirs(RESULTS_DIR, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(segments, f, ensure_ascii=False, indent=2)
    print(f"[저장] {output_path}")

    return segments