"""
===============================================================
job 저장소 - SQLite (app/core/jobs.py)
===============================================================
task_id 별 분석 작업 상태/결과를 SQLite DB 에 보관한다.
인메모리 dict 에서 전환했지만, 기존 인터페이스(create/get/update)는
그대로 유지하므로 routes.py / worker.py / API 는 수정할 필요가 없다.

[DB 파일]  /nfs/team/Shortify/shortify.db  (config.NFS_DIR 기준)
  - 백엔드 A/B 가 같은 파일을 공유한다 (NFS 위치).

[테이블 - JSON구조 PDF 그대로]
  tasks   : task_id, status, video_path, result_json   (A 가 사용)
  renders : render_id, task_id, status, output_path     (B 가 사용 - 스키마만 생성)

[인터페이스 매핑 - 4컬럼에 기존 dict 인터페이스를 얹는다]
  - status      -> status 컬럼
  - result(dict)-> result_json 컬럼 (JSON 문자열)
  - error(str)  -> 실패 시 result_json 에 {"error": "..."} 로 저장
  - progress    -> 컬럼 없음. get() 에서 status 로부터 파생해서 돌려줌
  - video_path  -> 컬럼 있음. 현재 routes 가 안 넘겨주므로 NULL
                   (routes 에서 create 시 video_path=... 한 줄 추가하면 채워짐)

[동시성]  BackgroundTasks 스레드풀 + 요청 핸들러가 동시에 접근하므로
  WAL 모드 + 쓰기 Lock + 호출마다 새 커넥션으로 안전하게 처리.
===============================================================
"""

import json
import os
import sqlite3
import threading
from typing import Optional

from app.core import config

DB_PATH = os.path.join(config.NFS_DIR, "shortify.db")

# 쓰기 직렬화용 (SQLite 'database is locked' 회피)
_lock = threading.Lock()

# status -> progress(0~100) 파생 규칙 (progress 컬럼이 없으므로)
_PROGRESS_BY_STATUS = {
    "pending": 0,
    "processing": 50,
    "done": 100,
    "failed": 100,
}


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """DB 파일/테이블을 보장한다 (없으면 생성). import 시 1회 호출."""
    os.makedirs(config.NFS_DIR, exist_ok=True)
    with _lock:
        with _connect() as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS tasks (
                    task_id     TEXT PRIMARY KEY,
                    status      TEXT NOT NULL,
                    video_path  TEXT,
                    result_json TEXT
                )
                """
            )
            # 백엔드 B 용 렌더 작업 테이블.
            #   error 컬럼은 실패 메시지 보관용 (tasks 와 달리 result_json 이 없어 전용 컬럼을 둠).
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS renders (
                    render_id   TEXT PRIMARY KEY,
                    task_id     TEXT,
                    status      TEXT,
                    output_path TEXT,
                    error       TEXT
                )
                """
            )
            # 이미 4컬럼으로 만들어진 DB 호환: error 컬럼이 없으면 추가한다.
            cols = {r["name"] for r in conn.execute("PRAGMA table_info(renders)")}
            if "error" not in cols:
                conn.execute("ALTER TABLE renders ADD COLUMN error TEXT")


def create(task_id: str, **fields) -> Optional[dict]:
    """
    새 작업을 등록한다 (기본 status=pending).
    tasks 4컬럼에 없는 kwargs(source_type/clip_count/category/progress 등)는 무시한다.
    """
    status = fields.get("status", "pending")
    video_path = fields.get("video_path")
    result = fields.get("result")
    result_json = (
        json.dumps(result, ensure_ascii=False) if result is not None else None
    )

    with _lock:
        with _connect() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO tasks (task_id, status, video_path, result_json) "
                "VALUES (?, ?, ?, ?)",
                (task_id, status, video_path, result_json),
            )
    return get(task_id)


def update(task_id: str, **fields) -> None:
    """
    작업 필드를 갱신한다. 4컬럼으로 매핑:
      status -> status / video_path -> video_path
      result(dict) -> result_json / error(str) -> result_json={"error": ...}
      progress 등 컬럼 없는 값은 무시.
    """
    sets = []
    params: list = []

    if "status" in fields:
        sets.append("status = ?")
        params.append(fields["status"])
    if "video_path" in fields:
        sets.append("video_path = ?")
        params.append(fields["video_path"])
    if "result" in fields:
        sets.append("result_json = ?")
        params.append(json.dumps(fields["result"], ensure_ascii=False))
    if "error" in fields:
        # error 전용 컬럼이 없어 result_json 에 보존
        sets.append("result_json = ?")
        params.append(json.dumps({"error": fields["error"]}, ensure_ascii=False))

    if not sets:
        return  # 갱신할 컬럼이 없으면(예: progress 만) 그냥 통과

    params.append(task_id)
    with _lock:
        with _connect() as conn:
            conn.execute(
                f"UPDATE tasks SET {', '.join(sets)} WHERE task_id = ?",
                params,
            )


def get(task_id: str) -> Optional[dict]:
    """
    작업을 조회한다. 없으면 None.
    기존 인메모리 dict 와 같은 형태로 돌려준다:
      {task_id, status, progress, result, error, video_path}
    """
    with _connect() as conn:
        row = conn.execute(
            "SELECT task_id, status, video_path, result_json FROM tasks WHERE task_id = ?",
            (task_id,),
        ).fetchone()

    if row is None:
        return None

    status = row["status"]
    parsed = json.loads(row["result_json"]) if row["result_json"] else None

    # result_json 은 done 이면 분석결과, failed 면 {"error": ...} 로 해석
    if status == "done":
        result, error = parsed, None
    elif status == "failed":
        result = None
        error = parsed.get("error") if isinstance(parsed, dict) else None
    else:
        result, error = None, None

    return {
        "task_id": row["task_id"],
        "status": status,
        "progress": _PROGRESS_BY_STATUS.get(status, 0),
        "result": result,
        "error": error,
        "video_path": row["video_path"],
    }


# ===============================================================
# renders 테이블 (백엔드 B - 렌더 작업)
#   tasks 의 create/get/update 와 같은 패턴.
#   render_id 별 렌더 상태/결과경로/에러를 보관한다.
# ===============================================================
def create_render(render_id: str, task_id: str) -> Optional[dict]:
    """새 렌더 작업을 등록한다 (status=pending)."""
    with _lock:
        with _connect() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO renders "
                "(render_id, task_id, status, output_path, error) "
                "VALUES (?, ?, ?, ?, ?)",
                (render_id, task_id, "pending", None, None),
            )
    return get_render(render_id)


def update_render(
    render_id: str,
    status: Optional[str] = None,
    output_path: Optional[str] = None,
    error: Optional[str] = None,
) -> None:
    """렌더 작업 필드를 갱신한다 (None 인 인자는 건드리지 않음)."""
    sets = []
    params: list = []

    if status is not None:
        sets.append("status = ?")
        params.append(status)
    if output_path is not None:
        sets.append("output_path = ?")
        params.append(output_path)
    if error is not None:
        sets.append("error = ?")
        params.append(error)

    if not sets:
        return  # 갱신할 값이 없으면 통과

    params.append(render_id)
    with _lock:
        with _connect() as conn:
            conn.execute(
                f"UPDATE renders SET {', '.join(sets)} WHERE render_id = ?",
                params,
            )


def get_render(render_id: str) -> Optional[dict]:
    """렌더 작업을 조회한다. 없으면 None."""
    with _connect() as conn:
        row = conn.execute(
            "SELECT render_id, task_id, status, output_path, error "
            "FROM renders WHERE render_id = ?",
            (render_id,),
        ).fetchone()

    if row is None:
        return None

    return {
        "render_id": row["render_id"],
        "task_id": row["task_id"],
        "status": row["status"],
        "output_path": row["output_path"],
        "error": row["error"],
    }


# import 시 DB/테이블 보장 (main.py 등 다른 파일을 건드리지 않기 위해 여기서 초기화)
init_db()
