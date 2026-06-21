"""
===============================================================
설정 (app/core/config.py)
===============================================================
백엔드(A파트)는 웹 레이어(upload/status/result)만 담당한다.
오디오추출/STT/추천은 알고리즘 담당의 analyze() 안에 들어있으므로
여기서는 "업로드 파일을 어디에 둘지" 정도만 설정한다.
===============================================================
"""

import os

from dotenv import load_dotenv

# .env 로드 (analyze 교체 시 알고리즘 담당이 쓸 키 등도 여기서 함께 로드됨)
load_dotenv()

# 이 파일 기준 backend/ 루트 자동 인식 (app/core/config.py -> 두 단계 위)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 업로드된 대용량 원본 영상은 서버 지침대로 NFS 에 저장
# 팀장 명세: source_type="file" 이면 {NFS_DIR}/{task_id}.mp4 로 저장
NFS_DIR = os.getenv("NFS_DIR", "/nfs/team/Shortify")
UPLOAD_DIR = NFS_DIR

# 기본 카테고리 (upload 에서 category 미지정 시)
DEFAULT_CATEGORY = "empathy"

# 업로드 파일 크기 상한 (5GB 초과 시 413). 테스트용으로 env 로 덮을 수 있음.
MAX_UPLOAD_BYTES = int(os.getenv("MAX_UPLOAD_BYTES", 5 * 1024 * 1024 * 1024))


def ensure_dirs() -> None:
    """업로드 저장 폴더를 미리 만든다 (서버 기동 시 1회 호출)."""
    os.makedirs(UPLOAD_DIR, exist_ok=True)
