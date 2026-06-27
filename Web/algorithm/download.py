"""
===============================================================
STEP 1 - 유튜브 영상 다운로드 (download.py)
===============================================================
[이 파일이 하는 일]
  유튜브 URL 을 받아 mp4 로 다운로드한다.
  원본 영상은 용량이 크므로 서버 지침에 따라 NFS(/nfs/team)에 저장한다.
  URL 업로드 케이스에서 analyze.py 가 호출한다.

[mp4 강제 변환]
  영상에 따라 webm/mkv 로 떨어질 수 있는데, 다음 단계(extract_audio)가
  항상 {name}.mp4 를 찾으므로, 어떤 포맷으로 받든 mp4 로 합쳐서 저장한다.
  (merge_output_format="mp4" + ffmpeg 필요)

[입력]  url, output_name (analyze.py 가 넘김)
[출력]  {NFS_DOWNLOAD_DIR}/{output_name}.mp4
===============================================================
"""

import yt_dlp

import config

NFS_DOWNLOAD_DIR = config.NFS_DOWNLOAD_DIR


def download_video(url: str, output_name: str) -> str:
    """
    유튜브 URL에서 영상을 다운로드하여 NFS 경로에 mp4로 저장한다.

    Args:
        url: 유튜브 영상 URL
        output_name: 저장할 파일명 (확장자 제외). 보통 task_id.

    Returns:
        저장된 mp4 파일 경로
    """
    output_path = f"{NFS_DOWNLOAD_DIR}/{output_name}.%(ext)s"

    ydl_opts = {
        # mp4 비디오 + m4a 오디오 우선, 없으면 mp4, 그것도 없으면 최고화질
        "format": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
        # 어떤 포맷으로 받든 mp4 로 합쳐서 저장 (extract_audio 가 .mp4 를 찾으므로)
        "merge_output_format": "mp4",
        "outtmpl": output_path,
        "quiet": False,  # 다운로드 진행상황 출력
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])

    saved_path = f"{NFS_DOWNLOAD_DIR}/{output_name}.mp4"
    print(f"[완료] {output_name} 다운로드 완료 -> {saved_path}")
    return saved_path