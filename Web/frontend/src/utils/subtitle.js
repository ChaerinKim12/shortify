// ===============================================================
// 자막 미리보기 기하 (subtitle.js)
// ===============================================================
// 백엔드 app/subtitles.py 와 동일한 값/규칙. 바꿀 땐 함께 고쳐야
// 미리보기가 실제 렌더와 어긋나지 않는다.
//   캔버스 720x1280, 영상 16:9 → 높이 405 (위 437.5 ~ 아래 842.5)
//   자막 크기 px: small=28, medium=32, large=36 / 외곽선 3px
//   분할: 줄당 최대 18자, 기본 1줄(옵션 2줄) — splitTextToLines/wrapCueText 는 subtitles.py 와 동일 규칙
//   letterbox : 영상 아래 여백 세로 중앙 (하단 제목이 있으면 제목 윗선까지의 중앙)
//   overlay   : 영상 하단에서 28px 위, 하단 정렬
// ===============================================================
import { OUT_W, MARGIN, LINE_SPACING, FONT_SIZE_PX, USABLE_PX, wrapTitleToLines } from './titleWrap'

export const OUT_H = 1280
export const VIDEO_H = Math.round((OUT_W * 9) / 16) // 405
export const VIDEO_TOP = (OUT_H - VIDEO_H) / 2
export const VIDEO_BOTTOM = VIDEO_TOP + VIDEO_H
export const OVERLAY_GAP = 28
export const OUTLINE_PX = 3

export const SUBTITLE_SIZE_PX = { sm: 28, md: 32, lg: 36 }
// 프론트 size → 백엔드 subtitle_size
export const SUBTITLE_SIZE_API = { sm: 'small', md: 'medium', lg: 'large' }

// 렌더 캔버스 기준 하단 제목의 윗선 y (render.py _title_top_y 포팅). 하단 제목이 없으면 null.
export function titleTopY(title, titlePos, titleSize) {
  if (!title || !title.trim() || titlePos !== 'bottom') return null
  const px = FONT_SIZE_PX[titleSize] ?? FONT_SIZE_PX.md
  const n = wrapTitleToLines(title, px, USABLE_PX).length
  return OUT_H - MARGIN - (n * px + (n - 1) * LINE_SPACING)
}

// { anchor: 'center' | 'bottom', y } — y 는 렌더 캔버스(720x1280) 기준
export function subtitleAnchor(position, topOfTitle) {
  if (position === 'overlay') return { anchor: 'bottom', y: VIDEO_BOTTOM - OVERLAY_GAP }
  const bottom = topOfTitle ?? OUT_H
  return { anchor: 'center', y: (VIDEO_BOTTOM + bottom) / 2 }
}

export const LINE_CHARS = 18
export const MERGE_MAX_CHARS = 22
const BREAK_PUNCT = ',.?!'

// subtitles.py split_text_to_lines 포팅: 18자 안에서 가장 뒤쪽의 쉼표/마침표 뒤 또는 공백 앞에서 끊고,
// 없으면 18자에서 자른다.
export function splitTextToLines(text, lineChars = LINE_CHARS) {
  let s = String(text).split(/\s+/).filter(Boolean).join(' ')
  const out = []
  while ([...s].length > lineChars) {
    const chars = [...s]
    let cut = -1
    chars.slice(0, lineChars + 1).forEach((ch, i) => {
      if (BREAK_PUNCT.includes(ch) && i + 1 <= lineChars) cut = i + 1
      else if (ch === ' ' && i > 0 && i <= lineChars) cut = i
    })
    if (cut <= 0) cut = lineChars
    out.push(chars.slice(0, cut).join('').trim())
    s = chars.slice(cut).join('').trimStart()
  }
  if (s) out.push(s)
  return out
}

// subtitles.py wrap_cue_text 포팅: { } \ 제거, 줄바꿈 유지, 18자 넘는 줄은 같은 규칙으로 다시 나눔.
// 렌더가 실제로 그리는 줄과 동일하다 (미리보기에 이 결과를 그대로 쓴다).
export function wrapCueText(text) {
  const t = String(text).replace(/\{/g, '(').replace(/\}/g, ')').replace(/\\/g, '')
  const out = []
  for (const ln of t.split('\n')) {
    const clean = ln.split(/\s+/).filter(Boolean).join(' ')
    if (!clean) continue
    // 합쳐진 자막(최대 22자)은 그대로 두고, 그보다 긴 줄만 18자 규칙으로 다시 나눈다
    if ([...clean].length <= MERGE_MAX_CHARS) out.push(clean)
    else out.push(...splitTextToLines(clean))
  }
  return out.join('\n')
}

// subtitles.py line_font_scale 포팅: 19~22자 줄은 18자 줄과 같은 폭이 되도록 글자를 줄인다.
export function lineFontScale(text) {
  const longest = Math.max(0, ...wrapCueText(text).split('\n').map((l) => [...l].length))
  return longest ? Math.min(1, LINE_CHARS / longest) : 1
}
