// 밀리초 → "mm:ss" (1시간 이상이면 "h:mm:ss")
export function msToClock(ms) {
  const total = Math.max(0, Math.round((ms ?? 0) / 1000))
  const h = Math.floor(total / 3600)
  const m = Math.floor((total % 3600) / 60)
  const s = total % 60
  const pad = (n) => String(n).padStart(2, '0')
  return h > 0 ? `${h}:${pad(m)}:${pad(s)}` : `${pad(m)}:${pad(s)}`
}