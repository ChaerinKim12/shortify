// 배경색 / 글씨색 / 제목 위치 / 글씨 크기 등 토글 버튼 그룹
export default function StyleField({ label, options, value, onChange }) {
  return (
    <div>
      <div className="text-xs font-semibold text-gray-500 mb-2">{label}</div>
      <div className="flex gap-2">
        {options.map(([key, text]) => {
          const active = value === key
          const isDark = (label === '배경색' && key === 'black') || (label === '글씨색' && key === 'black')
          const isLightFill =
            (label === '배경색' && key === 'white') || (label === '글씨색' && key === 'white')

          let cls = 'flex-1 rounded-xl border-2 px-3 py-2 text-sm font-semibold transition '
          if (active) {
            cls += 'border-brand-500 '
            cls += isDark ? 'bg-black text-white' : isLightFill ? 'bg-white text-gray-900' : 'bg-brand-50 text-brand-700'
          } else {
            cls += 'border-gray-200 '
            cls += isDark ? 'bg-black text-white' : 'bg-white text-gray-700'
          }

          return (
            <button key={key} onClick={() => onChange(key)} className={cls}>
              {text}
            </button>
          )
        })}
      </div>
    </div>
  )
}
