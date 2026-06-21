# Shortify 백엔드 ↔ 알고리즘 인터페이스 계약

백엔드(A파트)와 알고리즘 담당이 맞춰야 할 **유일한 접점**은 `analyze()` 함수 하나다.
백엔드는 이 시그니처/반환형에만 의존하며, 현재는 `app/analyze.py` 에 **더미 스텁**으로 채워져 있다.
알고리즘 담당이 실제 함수를 주면 `app/analyze.py` 의 `analyze()` 만 교체하면 된다.

## `analyze()` 계약

```python
def analyze(
    source: str,        # source_type="file"이면 NFS에 저장된 파일 경로(/nfs/team/Shortify/{task_id}.mp4)
                        # source_type="url"이면 유튜브 URL 문자열 (다운로드는 analyze 내부 책임)
    source_type: str,   # "file" | "url"
    clip_count: int,    # 1~5
    category: str,      # 예: "empathy"
    user_prompt: str,   # 사용자 추가 요청 (없으면 "")
) -> dict:
    ...
```

함수 내부에서 **오디오추출 → STT → 음성힌트 → Claude 추천** 전 과정을 수행한다.

### 반환형 (확정)

```jsonc
{
  "video_duration_ms": 123456,        // 영상 길이. analyze가 영상을 다루며 함께 구함
  "clips": [
    {
      "rank": 1,
      "start_ms": 0,
      "end_ms": 45000,
      "duration_sec": 45.0,
      "reason": "...",
      "titles": ["...", "...", "..."]
      // score / score_reason 등 추가 필드는 넣어도 됨 (백엔드가 그대로 통과시켜 보존)
    }
  ]
}
```

- `video_duration_ms` 는 **반드시** 포함 (result API가 이 값을 내보냄).
- `clips` 의 필수 필드: `rank, start_ms, end_ms, duration_sec, reason, titles`.
- 예외/실패 시에는 예외를 raise 하면 됨 → 백엔드가 잡아서 status="failed" 로 기록.

## 백엔드 API (참고용 — 알고리즘 담당이 직접 쓸 일은 없음)

| 메서드 | 경로 | 설명 |
|---|---|---|
| POST | `/upload` | form-data: `file`(선택), `youtube_url`(선택), `clip_count`(1~5, 필수), `category`(empathy/laughter/info/sadness/twist, 필수), `user_prompt`(선택). file/youtube_url 중 **하나만** 보냄(자동 판단). → `{task_id, status:"pending"}`. file은 `{NFS}/{task_id}.mp4` 저장(5GB 초과 413, 둘 다 없거나 둘 다 있으면 400). 백엔드가 내부적으로 source_type(file/url)을 만들어 analyze에 전달 |
| GET | `/status/{task_id}` | `{task_id, status, progress, error}` (status: pending/processing/done/failed) |
| GET | `/result/{task_id}` | done일 때 `{task_id, status, video_duration_ms, clips}`. 미완료 409, 없음 404 |
