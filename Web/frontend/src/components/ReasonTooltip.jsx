import { useEffect, useId, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import { Check, Info } from 'lucide-react'
import { humanizeReason } from '../utils/reason'

const SEP = ' · '
const REQUEST_LABEL = '요청 반영'

// "라벨 · 내용" 한 줄을 { label, content } 로 나눈다 (구분자가 없으면 통째로 내용)
function splitLine(line) {
  const i = line.indexOf(SEP)
  return i < 0 ? { label: '', content: line } : { label: line.slice(0, i), content: line.slice(i + SEP.length) }
}

// 선정 이유 ⓘ 툴팁. PC 는 hover/키보드 포커스, 모바일은 탭으로 열고 바깥 클릭/ESC 로 닫는다.
// display(reason_display 줄 목록)가 있으면 그것을, 없으면(변환 실패/기존 캐시) reason 의 태그 치환 문구를 보여준다.
// 아이콘 클릭이 카드 선택으로 번지지 않도록 stopPropagation.
export default function ReasonTooltip({ reason, display }) {
  const [open, setOpen] = useState(false)
  const rootRef = useRef(null)
  const btnRef = useRef(null)
  const [pos, setPos] = useState(null) // viewport 기준 위치. 카드 overflow-hidden 에 잘리지 않게 포털로 띄운다
  const id = useId()
  const lastPointer = useRef('') // 직전 포인터 종류: mouse 는 hover 로 열리므로 클릭으로 닫지 않는다

  useEffect(() => {
    if (!open) return
    const onDown = (e) => {
      if (rootRef.current && !rootRef.current.contains(e.target)) setOpen(false)
    }
    const onKey = (e) => e.key === 'Escape' && setOpen(false)
    const r = btnRef.current?.getBoundingClientRect()
    if (r) {
      const right = Math.max(12, window.innerWidth - r.right) // 툴팁 오른쪽 끝을 아이콘 오른쪽에 맞춤
      const centerX = r.left + r.width / 2
      setPos({
        top: r.bottom + 10,
        right,
        maxWidth: Math.min(320, r.right - 12),
        arrowRight: Math.max(8, window.innerWidth - right - centerX - 5), // 화살표가 아이콘 중심을 가리키게
      })
    }
    const close = () => setOpen(false)
    window.addEventListener('scroll', close, true)
    document.addEventListener('pointerdown', onDown)
    document.addEventListener('keydown', onKey)
    return () => {
      window.removeEventListener('scroll', close, true)
      document.removeEventListener('pointerdown', onDown)
      document.removeEventListener('keydown', onKey)
    }
  }, [open])

  const lines = Array.isArray(display) && display.length > 0 ? display.map(splitLine) : null
  if (!reason && !lines) return null

  return (
    <span
      ref={rootRef}
      className="relative shrink-0 inline-flex"
      onPointerEnter={(e) => e.pointerType === 'mouse' && setOpen(true)}
      onPointerLeave={(e) => e.pointerType === 'mouse' && setOpen(false)}
      onClick={(e) => e.stopPropagation()}
    >
      <button
        ref={btnRef}
        type="button"
        aria-label="선정 이유 보기"
        aria-describedby={open ? id : undefined}
        aria-expanded={open}
        onPointerDown={(e) => { lastPointer.current = e.pointerType }}
        onClick={(e) => {
          e.stopPropagation()
          // 마우스: 항상 열림 유지 / 터치·키보드: 토글
          if (lastPointer.current === 'mouse') setOpen(true)
          else setOpen((v) => !v)
          lastPointer.current = ''
        }}
        // 키보드 포커스일 때만 열림(터치/마우스 포커스는 클릭 처리와 겹쳐 바로 닫히므로 제외)
        onFocus={(e) => e.currentTarget.matches(':focus-visible') && setOpen(true)}
        onBlur={() => setOpen(false)}
        className="p-0.5 -m-0.5 rounded text-gray-400 hover:text-gray-600 focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-400"
      >
        <Info size={16} />
      </button>
      {open && pos && createPortal(
        <span
          id={id}
          role="tooltip"
          onClick={(e) => e.stopPropagation()}
          style={{ position: 'fixed', top: pos.top, right: pos.right, maxWidth: pos.maxWidth }}
          className="z-50 block w-max rounded-xl bg-brand-600 text-white text-xs leading-relaxed font-normal px-4 py-3 shadow-xl whitespace-normal break-keep"
        >
          {/* 화살표 (툴팁과 같은 보라색) */}
          <span
            aria-hidden="true"
            className="absolute -top-1 w-2.5 h-2.5 rotate-45 bg-brand-600"
            style={{ right: pos.arrowRight }}
          />
          {lines ? (
            <span className="block space-y-2">
              {lines.map(({ label, content }, i) => {
                const isRequest = label === REQUEST_LABEL
                return (
                  <span
                    key={i}
                    className={'block ' + (isRequest ? 'pt-2 border-t border-white/25' : '')}
                  >
                    <span className="inline-flex items-center gap-1 font-extrabold text-brand-200">
                      {isRequest && <Check size={12} strokeWidth={3} />}
                      {label}
                    </span>
                    {label && <span className="font-normal text-brand-300"> · </span>}
                    <span className="font-normal text-white">{content}</span>
                  </span>
                )
              })}
            </span>
          ) : (
            <span className="block">{humanizeReason(reason)}</span>
          )}
        </span>,
        document.body,
      )}
    </span>
  )
}
