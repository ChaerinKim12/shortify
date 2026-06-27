"""
===============================================================
STEP 2 - 오디오 추출 (extract_audio.py)
===============================================================
[이 파일이 하는 일]
  mp4 영상에서 "소리만" 뽑아 wav 파일로 저장한다.
  음성인식(STT)은 화면이 아니라 소리만 필요하기 때문.

  ffmpeg 로 변환할 때 두 가지를 맞춘다.
  - 모노(1채널): 다음 단계의 "화자 분리"를 켜려면 반드시 모노여야 함.
                  (스테레오/다중채널로 넘기면 화자 분리가 비활성화됨)
  - 16kHz: 리턴제로가 권장하는 샘플레이트. 음성인식에 충분하고 파일도 가벼움.

[입력]  {NFS_DOWNLOAD_DIR}/{영상이름}.mp4
[출력]  {AUDIO_DIR}/{영상이름}.wav  (모노 16kHz)
===============================================================
"""

import os
import subprocess

import config

NFS_DOWNLOAD_DIR = config.NFS_DOWNLOAD_DIR
AUDIO_DIR = config.AUDIO_DIR


def extract_audio(video_name: str) -> str:
    """
    mp4 영상에서 오디오를 추출하여 wav로 저장한다.
    리턴제로 STT + 화자 분리를 위해 모노(1채널) 16kHz로 변환한다.

    Args:
        video_name: 처리할 영상 파일명 (확장자 제외)

    Returns:
        저장된 wav 파일 경로

    Raises:
        RuntimeError: ffmpeg 변환 실패 시
    """
    input_path = f"{NFS_DOWNLOAD_DIR}/{video_name}.mp4"
    output_path = f"{AUDIO_DIR}/{video_name}.wav"

    # 출력 폴더 보장
    os.makedirs(AUDIO_DIR, exist_ok=True)

    command = [
        "ffmpeg",
        "-i", input_path,   # 입력 파일
        "-ac", "1",         # 모노 변환 (화자 분리 필수 조건)
        "-ar", "16000",     # 샘플레이트 16kHz (리턴제로 권장)
        "-y",               # 기존 파일 있으면 덮어쓰기
        output_path,
    ]

    print(f"[시작] {video_name} 오디오 추출 중...")
    result = subprocess.run(command, capture_output=True, text=True)

    # ffmpeg 는 실패 시 returncode 가 0이 아님
    if result.returncode != 0:
        print(f"[오류] {video_name} 오디오 추출 실패")
        print(result.stderr)
        # 서비스에서는 실패를 예외로 올려 백엔드가 failed 처리하게 한다
        raise RuntimeError(f"오디오 추출 실패: {video_name}")

    print(f"[완료] {video_name} -> {output_path}")
    return output_path