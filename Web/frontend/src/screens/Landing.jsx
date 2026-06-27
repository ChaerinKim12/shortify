import { Fragment, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { I } from '../components/Icon'
import { useShortify } from '../context/ShortifyContext'
import { FEATURES, STEPS, HERO_CARDS } from '../data/content'

const ACCEPTED = ['video/mp4', 'video/quicktime'] // mp4, mov
const ACCEPTED_EXT = ['.mp4', '.mov']

export default function Landing() {
  const navigate = useNavigate()
  const { state, update } = useShortify()
  const fileInputRef = useRef(null)
  const [dragging, setDragging] = useState(false)
  const [error, setError] = useState('')

  // mp4 / mov 인지 확인 (타입이 비어도 확장자로 한 번 더 검사)
  const isVideoFile = (file) => {
    if (ACCEPTED.includes(file.type)) return true
    const name = file.name.toLowerCase()
    return ACCEPTED_EXT.some((ext) => name.endsWith(ext))
  }

  const acceptFile = (file) => {
    if (!file) return
    if (!isVideoFile(file)) {
      setError('MP4 또는 MOV 파일만 업로드할 수 있어요.')
      return
    }
    const sizeMB = (file.size / (1024 * 1024)).toFixed(0) + 'MB'
    update({ file, fileName: file.name, fileSize: sizeMB, cats: [], extra: '', selected: [], clips: [], taskId: null })
    setError('')
    navigate('/options')
  }

  // 유튜브 링크 형식 검사 (youtube.com/watch?v=, youtu.be/, shorts 등 허용)
  const isValidYoutubeUrl = (value) => {
    const pattern =
      /^(https?:\/\/)?(www\.)?(youtube\.com\/(watch\?v=|shorts\/|live\/)|youtu\.be\/)[\w-]{11}.*$/
    return pattern.test(value.trim())
  }

const handleUrlSubmit = () => {
    if (!isValidYoutubeUrl(state.url)) {
      setError('올바른 유튜브 링크를 입력해주세요.')
      return
    }
    setError('')
    // URL 분석이므로 이전에 고른 로컬 파일 정보는 비우고, 표시용 정보를 URL로 교체
    update({ file: null, fileName: state.url.trim(), fileSize: 'YouTube', cats: [], extra: '', selected: [], clips: [], taskId: null })
    navigate('/options')
  }

  const handleFileChange = (e) => {
    acceptFile(e.target.files?.[0])
  }

  const handleDrop = (e) => {
    e.preventDefault()
    setDragging(false)
    acceptFile(e.dataTransfer.files?.[0])
  }

  return (
    <div className="animate-fadein">
      {/* 상단 바 */}
      <header className="border-b border-gray-100 bg-white">
        <div className="max-w-6xl mx-auto px-5 h-16 flex items-center justify-between">
          <button onClick={() => navigate('/')} className="text-2xl font-extrabold text-brand-600 tracking-tight">
            Shortify
          </button>
        </div>
      </header>

      {/* 히어로 */}
      <section className="max-w-6xl mx-auto px-5 pt-14 pb-20 grid lg:grid-cols-2 gap-12 items-center">
        <div>
          <span className="inline-block rounded-full bg-brand-50 text-brand-600 text-xs font-semibold px-3 py-1.5 mb-6">
            AI 기반 한국어 쇼츠 자동 추출
          </span>
          <h1 className="text-4xl sm:text-5xl font-extrabold leading-tight text-gray-900">
            긴 영상을 쇼츠로,
            <br />
            10분이면 충분합니다.
          </h1>
          <p className="mt-5 text-gray-500 leading-relaxed">
            한국어 특화 AI가 영상에서 핵심 구간을 자동으로 찾아드려요.
            <br />
            카테고리를 선택하면 더 정확하게 추출합니다.
          </p>

          {/* 입력 방식 탭 */}
          <div className="mt-7 inline-flex rounded-xl bg-gray-100 p-1">
            {[
              ['file', '파일 업로드'],
              ['url', '유튜브 URL'],
            ].map(([key, label]) => (
              <button
                key={key}
                onClick={() => { update({ inputMode: key }); setError('') }}
                className={
                  'px-4 py-2 rounded-lg text-sm font-semibold transition ' +
                  (state.inputMode === key ? 'bg-brand-600 text-white shadow' : 'text-gray-600')
                }
              >
                {label}
              </button>
            ))}
          </div>

          {state.inputMode === 'file' ? (
            <>
              <div
                onClick={() => fileInputRef.current?.click()}
                onDragOver={(e) => {
                  e.preventDefault()
                  setDragging(true)
                }}
                onDragLeave={() => setDragging(false)}
                onDrop={handleDrop}
                className={
                  'mt-4 cursor-pointer rounded-2xl border-2 border-dashed transition p-10 text-center ' +
                  (dragging
                    ? 'border-brand-500 bg-brand-50'
                    : 'border-gray-200 hover:border-brand-300 hover:bg-brand-50/40')
                }
              >
                <input
                  ref={fileInputRef}
                  type="file"
                  accept="video/mp4,video/quicktime,.mp4,.mov"
                  className="hidden"
                  onChange={handleFileChange}
                />
                <div className="mx-auto w-12 h-12 rounded-xl bg-brand-50 text-brand-600 flex items-center justify-center mb-3 pointer-events-none">
                  {I.upload}
                </div>
                <p className="text-gray-700 font-medium pointer-events-none">
                  {dragging ? '여기에 파일을 놓으세요' : 'MP4, MOV 파일을 드래그하거나 클릭하여 업로드'}
                </p>
                <p className="text-xs text-gray-400 mt-1 pointer-events-none">최대 5GB · MP4, MOV 지원</p>
                <span className="inline-block mt-4 rounded-xl bg-brand-600 text-white text-sm font-semibold px-5 py-2.5 pointer-events-none">
                  파일 선택
                </span>
              </div>
              {error && <p className="mt-2 text-sm text-red-500">{error}</p>}
            </>
          ) : (
            <>
              <div className="mt-4 flex gap-2">
                <input
                  value={state.url ?? ''}
                  onChange={(e) => {
                    update({ url: e.target.value })
                    if (error) setError('')
                  }}
                  onKeyDown={(e) => e.key === 'Enter' && state.url.trim() && handleUrlSubmit()}
                  placeholder="https://youtube.com/watch?v=..."
                  className="flex-1 rounded-xl border border-gray-200 px-4 py-3 text-sm focus:outline-none focus:border-brand-400 focus:ring-2 focus:ring-brand-100"
                />
                <button
                  onClick={handleUrlSubmit}
                  disabled={!state.url.trim()}
                  className={
                    'rounded-xl text-sm font-semibold px-5 transition whitespace-nowrap ' +
                    (state.url.trim()
                      ? 'bg-brand-600 hover:bg-brand-700 text-white'
                      : 'bg-gray-200 text-gray-400 cursor-not-allowed')
                  }
                >
                  분석 시작
                </button>
              </div>
              {error && <p className="mt-2 text-sm text-red-500">{error}</p>}
            </>
          )}
        </div>

        {/* 미리보기 카드 */}
        <div className="grid grid-cols-3 gap-3">
          {HERO_CARDS.map((card, i) => (
            <div key={i} className="animate-pop" style={{ animationDelay: `${i * 80}ms` }}>
              {/* 검은 카드 */}
              <div className="rounded-2xl aspect-[9/16] bg-black relative overflow-hidden shadow-xl flex flex-col items-center justify-center">
                {/* 영상 위 검은 여백: 제목 */}
                <div className="px-2 mb-4 text-center">
                  <p className="text-white font-extrabold text-xs sm:text-sm leading-snug">{card.headline}</p>
                </div>

                {/* 가운데 영상 (가로 꽉, 16:9) */}
                <div className={'w-full aspect-video bg-gradient-to-br ' + card.grad + ' relative overflow-hidden'}>
                  {card.img && (
                    <img
                      src={card.img}
                      alt={card.label}
                      onError={(e) => { e.currentTarget.style.display = 'none' }}
                      className="absolute inset-0 w-full h-full object-cover"
                    />
                  )}
                  <div className="absolute inset-0 flex items-center justify-center">
                    <div className="w-10 h-10 rounded-full bg-white/25 backdrop-blur flex items-center justify-center">
                      <div className="w-5 h-5 text-white">{I.play}</div>
                    </div>
                  </div>
                </div>
                <div className="absolute bottom-3 left-3 text-white">
                  <div className="text-sm font-bold leading-none">{card.label}</div>
                  <div className="text-xs opacity-80 mt-1">{card.time}</div>
                </div>
              </div>
              <div className="text-xs text-gray-500 mt-2 font-medium">{card.rank}</div>
            </div>
          ))}
        </div>
      </section>

      {/* 기능 소개 */}
      <section className="bg-gray-50 py-20">
        <div className="max-w-6xl mx-auto px-5">
          <h2 className="text-3xl font-extrabold text-center text-gray-900">AI가 이렇게 추천해드려요</h2>
          <p className="text-center text-gray-400 mt-2">카테고리별로 최적의 구간을 선별합니다</p>
          <div className="grid md:grid-cols-3 gap-5 mt-10">
            {FEATURES.map((f, i) => (
              <div key={i} className="bg-white rounded-2xl p-6 shadow-sm border border-gray-100 hover:shadow-md transition">
                <div className="w-10 h-10 text-brand-600 mb-4">{I[f.icon]}</div>
                <h3 className="font-bold text-gray-900">{f.title}</h3>
                <p className="text-sm text-gray-500 mt-1.5 leading-relaxed">{f.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* 사용 방법 */}
      <section className="py-20">
        <div className="max-w-5xl mx-auto px-5">
          <h2 className="text-3xl font-extrabold text-center text-gray-900 mb-12">사용 방법</h2>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-y-10 gap-x-4">
            {STEPS.map((s) => (
              <div key={s.num} className="flex flex-col items-center text-center">
                <div className="w-12 h-12 rounded-full bg-brand-600 text-white flex items-center justify-center font-bold text-lg mb-3">
                  {s.num}
                </div>
                <div className="w-12 h-9 flex items-center justify-center text-brand-600 mb-2">
                  <div className="w-6 h-6">{I[s.icon]}</div>
                </div>
                <div className="font-bold text-gray-900 text-sm">{s.title}</div>
                <div className="text-xs text-gray-400 mt-1">{s.desc}</div>
              </div>
            ))}
          </div>

        </div>
      </section>

      {/* 푸터 */}
      <footer className="border-t border-gray-100 bg-white">
        <div className="max-w-6xl mx-auto px-5 py-10 flex flex-col sm:flex-row items-center justify-between gap-4">
          <div className="text-center sm:text-left">
            <div className="text-lg font-extrabold text-brand-600">Shortify</div>
            <p className="text-xs text-gray-400 mt-1">AI 기반 한국어 쇼츠 자동 추출</p>
          </div>
          <p className="text-xs text-gray-400">© 2026 Shortify. All rights reserved.</p>
        </div>
      </footer>
    </div>
  )
}