"""
===============================================================
후처리 (postprocess.py)
===============================================================
recommend.py 가 뽑은 후보들(카테고리별 최대 3개씩, category 꼬리표가 달린)을
받아서 최종 클립 목록으로 다듬는다. Claude 호출은 하지 않는 순수 코드.

처리 순서 (analyze.py 가 이 순서로 호출):
  1) dedup_clips      : 시간이 많이 겹치는 후보 병합 (category 합침)
  2) cap_clips        : 목표 개수로 라운드로빈 캡 (카테고리 공평 분배)
  -- (이 사이에 제목 생성: recommend.generate_titles) --
  3) validate_clips   : duration_sec 재계산, end_ms 보정
  4) strip_to_contract: 내부 필드 제거, 계약 7필드만 남김

[왜 dedup 을 먼저, 캡을 나중에]
  웃음에서도 공감에서도 뽑힌 같은 구간을 먼저 합쳐야(병합),
  목표 개수를 셀 때 같은 순간을 두 번 세지 않는다.
===============================================================
"""

import config


# 백엔드로 나가는 계약 필드 (이 외의 내부 필드는 전부 제거)
CONTRACT_FIELDS = [
    "rank",
    "category",
    "start_ms",
    "end_ms",
    "duration_sec",
    "reason",
    "titles",
]


# ===============================================================
# 1) dedup - 많이 겹치는 후보 병합
# ===============================================================
def _overlap_ratio(a: dict, b: dict) -> float:
    """
    두 구간의 겹침 비율을 반환한다.
    비율 = 겹친 시간 / 두 구간 중 짧은 쪽 길이.
    (같은 순간을 두 카테고리가 잡은 경우를 잘 잡아내기 위해 '짧은 쪽 기준')
    """
    start = max(a["start_ms"], b["start_ms"])
    end = min(a["end_ms"], b["end_ms"])
    overlap = max(0, end - start)
    if overlap == 0:
        return 0.0
    len_a = a["end_ms"] - a["start_ms"]
    len_b = b["end_ms"] - b["start_ms"]
    shorter = min(len_a, len_b)
    if shorter <= 0:
        return 0.0
    return overlap / shorter


def _merge_categories(target: dict, source: dict) -> None:
    """source 의 category 들을 target 에 합친다 (중복 제거, 정렬)."""
    merged = set(target.get("category", [])) | set(source.get("category", []))
    target["category"] = sorted(merged)


def dedup_clips(clips: list, overlap_ratio: float = None) -> list:
    """
    시간이 많이 겹치는 후보들을 하나로 병합한다.

    방법:
      - score 내림차순으로 정렬해 점수 높은 후보를 '기준'으로 삼는다.
      - 새 후보가 기존 결과 중 하나와 overlap_ratio 이상 겹치면,
        경계/점수/이유는 기준(높은 점수) 것을 유지하고 category 만 합친다.
      - 겹치지 않으면 새 클립으로 추가한다.

    Returns:
        병합된 clip 리스트 (category 가 여러 개일 수 있음).
    """
    if overlap_ratio is None:
        overlap_ratio = config.DEDUP_OVERLAP_RATIO

    # 점수 높은 것부터 (점수 없으면 0 취급)
    ordered = sorted(clips, key=lambda c: c.get("score", 0), reverse=True)

    merged_list = []
    for clip in ordered:
        hit = None
        for m in merged_list:
            if _overlap_ratio(clip, m) >= overlap_ratio:
                hit = m
                break
        if hit is not None:
            # 기존(높은 점수) 기준 유지, category 만 합침
            _merge_categories(hit, clip)
        else:
            merged_list.append(dict(clip))  # 원본 보호용 복사

    return merged_list


# ===============================================================
# 2) cap - 라운드로빈으로 목표 개수만큼만
# ===============================================================
def _reorder_by_score(clips: list) -> list:
    """score 내림차순으로 정렬하고 rank 를 1부터 다시 매긴다."""
    ordered = sorted(clips, key=lambda c: c.get("score", 0), reverse=True)
    for i, clip in enumerate(ordered, start=1):
        clip["rank"] = i
    return ordered


def cap_clips(clips: list, categories: list, target: int) -> list:
    """
    목표 개수(target)를 넘으면 라운드로빈으로 카테고리를 공평하게 뽑는다.

    라운드로빈:
      - 카테고리별 버킷을 만들고 각 버킷을 score 내림차순 정렬.
      - 카테고리 순서대로 돌며 각 버킷에서 아직 안 뽑힌 최고 점수 1개씩 선택.
      - 병합 클립은 여러 버킷에 있지만 id 로 중복 선택을 막는다.
      - target 을 채우거나 더 뽑을 게 없으면 종료.

    target 이하면 라운드로빈 없이 그대로 두되 rank 만 다시 매긴다.
    """
    if len(clips) <= target:
        return _reorder_by_score(clips)

    # 카테고리별 버킷 (클립이 여러 카테고리면 각 버킷에 모두 들어감)
    buckets = {cat: [] for cat in categories}
    for clip in clips:
        for cat in clip.get("category", []):
            if cat in buckets:
                buckets[cat].append(clip)
    for cat in buckets:
        buckets[cat].sort(key=lambda c: c.get("score", 0), reverse=True)

    selected = []
    selected_ids = set()
    idx = {cat: 0 for cat in categories}

    while len(selected) < target:
        progressed = False
        for cat in categories:
            if len(selected) >= target:
                break
            # 이 카테고리 버킷에서 아직 안 뽑힌 다음 클립 찾기
            while idx[cat] < len(buckets[cat]):
                cand = buckets[cat][idx[cat]]
                idx[cat] += 1
                if id(cand) not in selected_ids:
                    selected.append(cand)
                    selected_ids.add(id(cand))
                    progressed = True
                    break
        if not progressed:
            break  # 모든 버킷 소진

    return _reorder_by_score(selected)


# ===============================================================
# 3) validate - 코드로 값 재검증/보정
# ===============================================================
def validate_clips(clips: list, video_duration_ms: int) -> list:
    """
    LLM 이 준 값을 코드로 다시 점검/보정한다.
      - end_ms 가 영상 길이를 넘으면 잘라서 보정
      - start_ms > end_ms 뒤집힘은 swap
      - duration_sec 은 모델 값 대신 (end-start)/1000 으로 직접 재계산 (정수)
    """
    for clip in clips:
        start = int(clip.get("start_ms", 0))
        end = int(clip.get("end_ms", 0))

        # 뒤집힘 보정
        if end < start:
            start, end = end, start

        # 영상 길이 초과 보정
        if video_duration_ms > 0 and end > video_duration_ms:
            end = video_duration_ms

        clip["start_ms"] = start
        clip["end_ms"] = end
        # 계약상 duration_sec 는 정수
        clip["duration_sec"] = round((end - start) / 1000)

    return clips


# ===============================================================
# 4) strip - 계약 필드만 남기기
# ===============================================================
def strip_to_contract(clips: list) -> list:
    """
    내부 전용 필드(score, score_reason 등)를 제거하고
    백엔드로 나갈 계약 7필드만 남긴다.
    titles 가 없으면 빈 리스트로 채운다.
    """
    out = []
    for clip in clips:
        out.append({
            "rank": clip.get("rank"),
            "category": clip.get("category", []),
            "start_ms": clip.get("start_ms"),
            "end_ms": clip.get("end_ms"),
            "duration_sec": clip.get("duration_sec"),
            "reason": clip.get("reason", ""),
            "titles": clip.get("titles", []),
        })
    return out