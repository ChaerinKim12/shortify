// 선정 이유(reason)에 섞여 오는 분석 태그를 사용자용 문구로 바꿔 보여준다. (표시 전용 — 원본 데이터는 그대로)
const TAG_LABELS = {
  '[음량↑]': '목소리 커짐',
  '[음량↓]': '목소리 작아짐',
  '[피치↑]': '톤 올라감',
  '[피치↓]': '톤 낮아짐',
  '[말빠름]': '말 빨라짐',
  '[말느림]': '말 느려짐',
  '[무음]': '정적',
}

const TAG_RE = new RegExp(Object.keys(TAG_LABELS).map((t) => t.replace(/[[\]]/g, '\\$&')).join('|'), 'g')

export function humanizeReason(reason) {
  return String(reason ?? '').replace(TAG_RE, (m) => TAG_LABELS[m])
}
