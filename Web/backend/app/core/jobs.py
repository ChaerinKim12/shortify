"""
===============================================================
인메모리 job 저장소 (app/core/jobs.py)
===============================================================
task_id 별 분석 작업의 상태/결과를 메모리(dict)에 보관한다.
MVP 라 DB 없이 dict 하나로 처리한다. (서버 재시작하면 사라짐)

BackgroundTasks 는 별도 스레드풀에서 실행되므로,
여러 스레드가 동시에 dict 를 건드려도 안전하도록 Lock 으로 보호한다.

상태 흐름: pending -> processing -> done / failed
===============================================================
"""

import threading
from typing import Optional

# task_id -> job dict
_jobs: dict = {}
_lock = threading.Lock()


def create(task_id: str, **fields) -> dict:
    """새 작업을 pending 상태로 등록한다."""
    job = {
        "task_id": task_id,
        "status": "pending",   # pending / processing / done / failed
        "progress": 0,         # 0~100
        "result": None,        # done 시 analyze() 반환값
        "error": None,         # failed 시 에러 메시지
    }
    job.update(fields)
    with _lock:
        _jobs[task_id] = job
    return job


def update(task_id: str, **fields) -> None:
    """기존 작업의 필드를 갱신한다 (status/progress/result/error 등)."""
    with _lock:
        job = _jobs.get(task_id)
        if job is not None:
            job.update(fields)


def get(task_id: str) -> Optional[dict]:
    """작업을 조회한다. 없으면 None."""
    with _lock:
        job = _jobs.get(task_id)
        # 호출 측이 실수로 내부 dict 를 수정하지 못하도록 사본 반환
        return dict(job) if job is not None else None
