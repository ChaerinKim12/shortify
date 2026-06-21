"""
===============================================================
오케스트레이터 (app/worker.py)
===============================================================
BackgroundTasks 가 백그라운드에서 실행하는 함수.
analyze() 를 감싸 작업 상태(jobs)를 갱신한다.

  pending(=upload 시점) -> processing(시작) -> done(성공) / failed(예외)

analyze() 가 더미든 실제 알고리즘이든 이 래퍼는 그대로 동작한다.
===============================================================
"""

from app.analyze import analyze
from app.core import jobs


def run_analysis_task(
    task_id: str,
    source: str,
    source_type: str,
    clip_count: int,
    category: str,
    user_prompt: str,
) -> None:
    """analyze() 를 실행하고 결과/에러를 jobs 에 기록한다."""
    jobs.update(task_id, status="processing", progress=10)

    try:
        result = analyze(
            source=source,
            source_type=source_type,
            clip_count=clip_count,
            category=category,
            user_prompt=user_prompt,
        )
        jobs.update(task_id, status="done", progress=100, result=result)
    except Exception as e:
        # MVP: 에러 메시지를 문자열로 보관 (status API 에서 노출)
        jobs.update(task_id, status="failed", error=str(e))
