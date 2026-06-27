// ===============================================================
// 자막 줄바꿈 포팅 (titleWrap.js) — 방식 A
// ===============================================================
// 백엔드 render.py 의 _wrap_title_to_lines / _char_display_width 를
// 그대로 JS 로 포팅했다. 편집 미리보기의 줄 수·줄 끊는 위치를 실제
// 다운로드 영상과 1:1로 맞추기(WYSIWYG) 위함.
//
// render.py 상수 동기화:
//   _OUT_W = 720, _SIDE_MARGIN = 48, _LINE_SPACING = 12, _MARGIN = 120
//   usable_px = _OUT_W - 2*_SIDE_MARGIN = 624
//   font_size_px: small=36, medium=48, large=64  (api/render.py _FONT_SIZE_PX)
//
// 이 값/규칙을 바꿀 땐 render.py 와 함께 고쳐야 미리보기가 어긋나지 않는다.
// ===============================================================

export const OUT_W = 720
export const SIDE_MARGIN = 48
export const LINE_SPACING = 12
export const MARGIN = 120
export const USABLE_PX = OUT_W - 2 * SIDE_MARGIN // 624

// 프론트 size(sm/md/lg) → 백엔드 실제 자막 px (render.py 와 동일 값)
export const FONT_SIZE_PX = { sm: 36, md: 48, lg: 64 }

// render.py _char_display_width 포팅.
// 한글/한자/가나/전각 ≈ font_size, 그 외(라틴/숫자/공백) ≈ font_size*0.55.
export function charDisplayWidth(ch, fontSizePx) {
  const o = ch.codePointAt(0)
  const wide =
    (o >= 0xac00 && o <= 0xd7a3) || // 한글 음절
    (o >= 0x1100 && o <= 0x11ff) || // 한글 자모
    (o >= 0x3040 && o <= 0x30ff) || // 가나
    (o >= 0x3000 && o <= 0x9fff) || // CJK 기호/한자
    (o >= 0xff00 && o <= 0xffef)    // 전각
  return fontSizePx * (wide ? 1.0 : 0.55)
}

// render.py _wrap_title_to_lines 포팅 (줄 끊는 순서/조건 동일).
// - 공백이 있으면 마지막 공백(단어 경계)에서 우선 끊는다.
// - 공백 없는 긴 텍스트(한글 등)는 글자 단위로 강제 분할한다.
export function wrapTitleToLines(title, fontSizePx, usablePx = USABLE_PX) {
  const widthOf = (s) => {
    let sum = 0
    for (const c of s) sum += charDisplayWidth(c, fontSizePx)
    return sum
  }

  const out = []
  for (const para of String(title).split('\n')) {
    let cur = ''
    let curW = 0
    // for...of 는 코드포인트 단위 순회 (파이썬 str 순회와 동일)
    for (const ch of para) {
      const cw = charDisplayWidth(ch, fontSizePx)
      if (cur && curW + cw > usablePx) {
        const br = cur.lastIndexOf(' ')
        if (br > 0) {
          // 줄 안에 공백이 있으면 마지막 공백에서 끊고 나머지는 다음 줄로
          out.push(cur.slice(0, br))
          cur = cur.slice(br + 1)
        } else {
          // 공백 없는 긴 텍스트 → 글자 단위 강제 분할
          out.push(cur)
          cur = ''
        }
        curW = widthOf(cur)
      }
      cur += ch
      curW += cw
    }
    out.push(cur)
  }

  const lines = out.map((ln) => ln.trim())
  return lines.some((l) => l) ? lines : [String(title).trim()]
}
