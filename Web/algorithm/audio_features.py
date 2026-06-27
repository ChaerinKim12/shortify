"""
===============================================================
STEP 4 - 음성힌트 추출 + 자막 합치기 (audio_features.py)
===============================================================
[이 파일이 하는 일]
  자막은 "무슨 말"인지만 알지 "어떤 톤"인지는 모른다.
  그래서 librosa 로 오디오를 분석해 감정 신호(음성힌트)를 자막에 붙인다.
  Claude 가 "이 구간은 감정이 격했구나"를 텍스트로 읽을 수 있게 하는 단계.

  붙이는 태그 4종류:
   - [음량↑]/[음량↓] : 전체 평균 대비 크게/작게 말함
   - [피치↑]/[피치↓] : 목소리 높낮이 변화 (화자 baseline 대비)
   - [말빠름]/[말느림] : 단어수 / 시간
   - [무음]            : 발화 사이 1초 이상 정적

[개선 포인트 - 피치 baseline 을 "화자별"로 계산]
  STT가 나눠준 화자(p1/p2)별로 각자 baseline 을 계산해
  "그 사람 평소 톤 대비" 높였나/낮췄나를 판단한다.
  발화가 너무 적은 화자(MIN_UTTERANCES_FOR_BASELINE 미만)는
  baseline 이 불안정하므로 전체 baseline 으로 폴백한다.

[입력]  {AUDIO_DIR}/{영상이름}.wav, {RESULTS_DIR}/{영상이름}_stt.json
[출력]  {RESULTS_DIR}/{영상이름}_merged.json
        (segments: 힌트 포함 / formatted: Claude 입력용 한 줄 텍스트)
===============================================================
"""

import json
import os

import librosa
import numpy as np

import config

AUDIO_DIR = config.AUDIO_DIR
RESULTS_DIR = config.RESULTS_DIR

# 음성힌트 판단 임계값
VOLUME_HIGH_PERCENTILE = 80   # 음량 상위 20% -> 음량 높음
VOLUME_LOW_PERCENTILE = 20    # 음량 하위 20% -> 음량 낮음
PITCH_HIGH_RATIO = 1.6        # 화자 baseline 대비 60% 이상 높으면 피치 높음
PITCH_LOW_RATIO = 0.5         # 화자 baseline 대비 50% 이하면 피치 낮음
SPEECH_FAST_THRESHOLD = 5.0   # 단어/초 이상 -> 말빠름
SPEECH_SLOW_THRESHOLD = 2.0   # 단어/초 이하 -> 말느림
SILENCE_THRESHOLD_SEC = 1.0   # 1초 이상 묵음 -> [무음]

# 화자별 baseline 을 신뢰하려면 발화가 최소 이 개수 이상 있어야 함.
MIN_UTTERANCES_FOR_BASELINE = 5


def extract_rms(y: np.ndarray, sr: int, hop_sec: float = 0.5) -> tuple:
    """오디오 전체의 RMS 에너지(음량)를 0.5초 단위로 계산한다."""
    frame_length = int(hop_sec * sr)
    rms = librosa.feature.rms(
        y=y,
        frame_length=frame_length,
        hop_length=frame_length,
    )[0]
    rms_db = librosa.amplitude_to_db(rms)
    return rms_db, hop_sec


def extract_pitch(y: np.ndarray, sr: int, hop_sec: float = 0.5) -> tuple:
    """
    오디오 전체의 피치(Hz)를 0.5초 단위로 계산한다.
    pyin 대신 yin 알고리즘 사용 (안정적, 파라미터 충돌 없음).
    """
    hop_length = int(hop_sec * sr)

    f0 = librosa.yin(
        y,
        fmin=librosa.note_to_hz("C2"),   # 약 65Hz
        fmax=librosa.note_to_hz("C7"),   # 약 2093Hz
        hop_length=hop_length,
    )

    # yin 은 무성/오류 구간에서 0 을 반환하므로 0 을 nan 으로 바꿔 분석에서 제외
    f0 = f0.astype(float)
    f0[f0 == 0] = np.nan

    return f0, hop_sec


def _median_baseline(values: np.ndarray) -> float:
    """
    피치 값 배열에서 이상치(하위10%/상위90%)를 제거한 뒤 중앙값을 구한다.
    (순간적으로 튀는 값에 baseline 이 휘둘리지 않도록)
    """
    valid = values[~np.isnan(values)]
    if len(valid) == 0:
        return 0.0
    lower = np.percentile(valid, 10)
    upper = np.percentile(valid, 90)
    filtered = valid[(valid >= lower) & (valid <= upper)]
    if len(filtered) == 0:
        return float(np.median(valid))
    return float(np.median(filtered))


def compute_pitch_baselines(
    segments: list,
    f0: np.ndarray,
    hop_sec: float,
    global_baseline: float,
) -> dict:
    """
    화자(speaker)별 피치 baseline 을 계산한다.
    발화 수가 MIN_UTTERANCES_FOR_BASELINE 미만인 화자는
    표본이 적어 불안정하므로 전체 baseline(global_baseline)으로 폴백한다.
    """
    # 1) 화자별로 피치 프레임 모으기
    speaker_frames = {}       # speaker -> 피치 값 리스트
    speaker_utter_count = {}  # speaker -> 발화 개수

    for seg in segments:
        speaker = seg["speaker"]
        start_frame = int((seg["start_ms"] / 1000) / hop_sec)
        end_frame = int((seg["end_ms"] / 1000) / hop_sec)
        seg_f0 = f0[start_frame:end_frame]

        speaker_frames.setdefault(speaker, []).append(seg_f0)
        speaker_utter_count[speaker] = speaker_utter_count.get(speaker, 0) + 1

    # 2) 화자별 baseline 계산 (발화 적으면 전체 baseline 폴백)
    baselines = {}
    for speaker, frame_list in speaker_frames.items():
        if speaker_utter_count.get(speaker, 0) < MIN_UTTERANCES_FOR_BASELINE:
            baselines[speaker] = global_baseline
            print(f"[정보] {speaker}: 발화 적음 -> 전체 baseline 사용 ({global_baseline:.1f}Hz)")
            continue

        combined = np.concatenate(frame_list)
        baseline = _median_baseline(combined)
        if baseline <= 0:
            baseline = global_baseline
        baselines[speaker] = baseline
        print(f"[정보] {speaker}: 화자별 baseline = {baseline:.1f}Hz")

    return baselines


def get_segment_hints(
    segment: dict,
    rms_db: np.ndarray,
    f0: np.ndarray,
    hop_sec: float,
    rms_high_threshold: float,
    rms_low_threshold: float,
    pitch_baseline: float,
) -> list:
    """
    하나의 발화 세그먼트에 대한 음성힌트 태그를 만든다.
    음량 -> 피치 -> 말속도 순으로 분석한다.
    (피치는 '해당 화자의 baseline' 을 기준으로 비교한다)
    """
    hints = []

    start_sec = segment["start_ms"] / 1000
    end_sec = segment["end_ms"] / 1000

    start_frame = int(start_sec / hop_sec)
    end_frame = int(end_sec / hop_sec)

    # 1. 음량 분석 (전체 분포 대비)
    seg_rms = rms_db[start_frame:end_frame]
    if len(seg_rms) > 0:
        avg_rms = np.nanmean(seg_rms)
        if avg_rms > rms_high_threshold:
            hints.append("[음량↑]")
        elif avg_rms < rms_low_threshold:
            hints.append("[음량↓]")

    # 2. 피치 분석 (화자 baseline 대비 상대값)
    seg_f0 = f0[start_frame:end_frame]
    valid_f0 = seg_f0[~np.isnan(seg_f0)]
    if len(valid_f0) > 0 and pitch_baseline > 0:
        avg_pitch = np.mean(valid_f0)
        ratio = avg_pitch / pitch_baseline
        if ratio > PITCH_HIGH_RATIO:
            hints.append("[피치↑]")
        elif ratio < PITCH_LOW_RATIO:
            hints.append("[피치↓]")

    # 3. 말속도 분석 (단어 수 / 구간 길이)
    duration_sec = end_sec - start_sec
    word_count = len(segment["text"].split())
    if duration_sec > 0:
        speech_rate = word_count / duration_sec
        if speech_rate > SPEECH_FAST_THRESHOLD:
            hints.append("[말빠름]")
        elif speech_rate < SPEECH_SLOW_THRESHOLD:
            hints.append("[말느림]")

    return hints


def detect_silence(segments: list) -> list:
    """
    발화 세그먼트 사이의 무음 구간을 감지한다.
    1초 이상 묵음이면 [무음] 세그먼트를 사이에 끼워 넣는다.
    """
    result = []

    for i, seg in enumerate(segments):
        result.append(seg)

        # 다음 세그먼트와의 간격 확인
        if i < len(segments) - 1:
            gap_ms = segments[i + 1]["start_ms"] - seg["end_ms"]
            gap_sec = gap_ms / 1000

            if gap_sec >= SILENCE_THRESHOLD_SEC:
                result.append({
                    "start_ms": seg["end_ms"],
                    "end_ms": segments[i + 1]["start_ms"],
                    "speaker": "none",
                    "text": "",
                    "hints": ["[무음]"],
                })

    return result


def merge_hints(audio_name: str) -> list:
    """
    STT 결과와 음성힌트를 합쳐 Claude 입력용 포맷을 만든다.

    출력 한 줄 예:
    "12400ms~18700ms / [p1] 진짜 이거 써보고 [음량↑] [말느림]"

    Returns:
        머지된 세그먼트 리스트
    """
    audio_path = f"{AUDIO_DIR}/{audio_name}.wav"
    stt_path = f"{RESULTS_DIR}/{audio_name}_stt.json"
    output_path = f"{RESULTS_DIR}/{audio_name}_merged.json"

    print(f"\n[시작] {audio_name} 음성힌트 추출 중...")

    # 1. 오디오 로드
    y, sr = librosa.load(audio_path, sr=16000)
    print(f"[완료] 오디오 로드 완료 / 길이: {len(y)/sr:.1f}초")

    # 2. RMS + 피치 추출
    rms_db, hop_sec = extract_rms(y, sr)
    f0, _ = extract_pitch(y, sr)

    # 3. 음량 임계값 계산 (전체 분포 기반)
    rms_high = np.percentile(rms_db, VOLUME_HIGH_PERCENTILE)
    rms_low = np.percentile(rms_db, VOLUME_LOW_PERCENTILE)

    # 4. 전체 피치 baseline 계산 (화자별 폴백용)
    global_baseline = _median_baseline(f0)
    print(f"[정보] 전체 피치 baseline: {global_baseline:.1f}Hz / 음량 기준: {rms_low:.1f}~{rms_high:.1f}dB")

    # 5. STT 세그먼트 로드
    with open(stt_path, "r", encoding="utf-8") as f:
        segments = json.load(f)

    # 6. 화자별 피치 baseline 계산 (개선 포인트)
    pitch_baselines = compute_pitch_baselines(segments, f0, hop_sec, global_baseline)

    # 7. 각 세그먼트에 음성힌트 추가 (피치는 해당 화자 baseline 사용)
    for seg in segments:
        speaker_baseline = pitch_baselines.get(seg["speaker"], global_baseline)
        seg["hints"] = get_segment_hints(
            seg, rms_db, f0, hop_sec,
            rms_high, rms_low, speaker_baseline,
        )

    # 8. 무음 구간 삽입
    segments_with_silence = detect_silence(segments)

    # 9. Claude 입력용 텍스트 한 줄씩 생성
    formatted_lines = []
    for seg in segments_with_silence:
        if seg["speaker"] == "none":
            formatted_lines.append(
                f"{seg['start_ms']}ms~{seg['end_ms']}ms / [무음]"
            )
        else:
            hints_str = " ".join(seg.get("hints", []))
            line = f"{seg['start_ms']}ms~{seg['end_ms']}ms / [{seg['speaker']}] {seg['text']}"
            if hints_str:
                line += f" {hints_str}"
            formatted_lines.append(line)

    # 10. 결과 저장
    result = {
        "audio_name": audio_name,
        "total_segments": len(segments_with_silence),
        "pitch_baseline_global_hz": float(global_baseline),
        "pitch_baselines_by_speaker_hz": {
            spk: float(val) for spk, val in pitch_baselines.items()
        },
        "segments": segments_with_silence,
        "formatted": formatted_lines,
    }

    os.makedirs(RESULTS_DIR, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"[저장] {output_path}")
    print(f"[완료] 총 {len(formatted_lines)}개 세그먼트 (무음 포함)")

    # 미리보기
    print(f"\n[미리보기] {audio_name} 첫 5개:")
    for line in formatted_lines[:5]:
        print(f"  {line}")

    return segments_with_silence