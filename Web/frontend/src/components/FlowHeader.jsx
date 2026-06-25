import { Fragment } from 'react'
import Logo from './Logo'

const STEP_NAMES = ['업로드', '옵션 설정', '결과 확인', '편집·다운로드']

export default function FlowHeader({ step, onCancel, cancelLabel = '취소' }) {
  return (
    <header className="sticky top-0 z-20 bg-white/90 backdrop-blur border-b border-gray-100">
      <div className="max-w-6xl mx-auto px-5 h-16 flex items-center justify-between">
        <Logo />
        <nav className="hidden md:flex items-center gap-2 text-sm">
          {STEP_NAMES.map((name, i) => (
            <Fragment key={name}>
              <span className={i === step ? 'text-brand-600 font-bold' : 'text-gray-400'}>{name}</span>
              {i < STEP_NAMES.length - 1 && <span className="text-gray-300">•</span>}
            </Fragment>
          ))}
        </nav>
        <button onClick={onCancel} className="text-sm text-gray-500 hover:text-gray-800">
          {cancelLabel}
        </button>
      </div>
    </header>
  )
}
