import { useRef } from 'react'

// 시작·종료 두 핸들을 가진 구간 슬라이더. 값은 ms 단위.
export default function DualRangeSlider({ min, max, start, end, onChange, step = 1000 }) {
  const trackRef = useRef(null)
  const span = Math.max(1, max - min)
  const startPct = ((start - min) / span) * 100
  const endPct = ((end - min) / span) * 100

  // 핸들 드래그 처리
  const drag = (which) => (e) => {
    e.preventDefault()
    const move = (clientX) => {
      const rect = trackRef.current.getBoundingClientRect()
      const ratio = Math.min(1, Math.max(0, (clientX - rect.left) / rect.width))
      let val = Math.round((min + ratio * span) / step) * step
      if (which === 'start') {
        val = Math.min(val, end - step) // 종료점 넘지 않게
        onChange({ start: Math.max(min, val), end })
      } else {
        val = Math.max(val, start + step) // 시작점 아래로 안 가게
        onChange({ start, end: Math.min(max, val) })
      }
    }
    const onMouseMove = (ev) => move(ev.clientX)
    const onTouchMove = (ev) => move(ev.touches[0].clientX)
    const stop = () => {
      window.removeEventListener('mousemove', onMouseMove)
      window.removeEventListener('mouseup', stop)
      window.removeEventListener('touchmove', onTouchMove)
      window.removeEventListener('touchend', stop)
    }
    window.addEventListener('mousemove', onMouseMove)
    window.addEventListener('mouseup', stop)
    window.addEventListener('touchmove', onTouchMove)
    window.addEventListener('touchend', stop)
  }

  return (
    <div ref={trackRef} className="relative h-2 bg-gray-200 rounded-full select-none">
      {/* 선택된 구간 */}
      <div
        className="absolute h-2 bg-brand-500 rounded-full"
        style={{ left: `${startPct}%`, width: `${endPct - startPct}%` }}
      />
      {/* 시작 핸들 */}
      <div
        onMouseDown={drag('start')}
        onTouchStart={drag('start')}
        style={{ left: `${startPct}%` }}
        className="absolute top-1/2 -translate-x-1/2 -translate-y-1/2 w-5 h-5 rounded-full bg-brand-600 border-2 border-white shadow cursor-grab active:cursor-grabbing"
      />
      {/* 종료 핸들 */}
      <div
        onMouseDown={drag('end')}
        onTouchStart={drag('end')}
        style={{ left: `${endPct}%` }}
        className="absolute top-1/2 -translate-x-1/2 -translate-y-1/2 w-5 h-5 rounded-full bg-brand-600 border-2 border-white shadow cursor-grab active:cursor-grabbing"
      />
    </div>
  )
}