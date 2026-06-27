import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import FlowHeader from '../components/FlowHeader'
import { I } from '../components/Icon'
import { useShortify } from '../context/ShortifyContext'
import { CLIP_GRADIENTS } from '../data/content'
import { getRenderStatus, downloadUrl, withApiBase } from '../api/client'

const POLL_INTERVAL_MS = 2000

export default function Done() {
  const navigate = useNavigate()
  const { state, update, reset } = useShortify()
  const [status, setStatus] = useState('pending')
  const [error, setError] = useState('')
  const [downloaded, setDownloaded] = useState(false)
  const cancelledRef = useRef(false)
  const fileInputRef = useRef(null)

  // 새 영상 업로드: 파일 탐색기만 (드래그 없음) → 고르면 상태 갱신 후 옵션 설정으로
  const handleNewFile = (e) => {
    const file = e.target.files?.[0]
    if (!file) return
    const sizeMB = (file.size / (1024 * 1024)).toFixed(0) + 'MB'
    reset() // 이전 작업 상태 초기화 (일회성 서비스)
    update({ inputMode: 'file', file, fileName: file.name, fileSize: sizeMB })
    navigate('/options')
  }

  const clip = (state.clips || []).find((c) => c.rank === state.selected[0])
  const title = state.title?.trim() ? state.title : clip?.titles?.[0] || '완성된 쇼츠'
  const grad = clip ? CLIP_GRADIENTS[(clip.rank - 1) % CLIP_GRADIENTS.length] : CLIP_GRADIENTS[0]

  useEffect(() => {
    if (!state.renderId) {
      navigate('/results')
      return
    }
    cancelledRef.current = false
    let timer

    const poll = async () => {
      try {
        const s = await getRenderStatus(state.renderId)
        if (cancelledRef.current) return
        setStatus(s.status)
        if (s.status === 'done') return
        if (s.status === 'failed') {
          setError('영상 만들기에 실패했어요. 다시 시도해주세요.')
          return
        }
        timer = setTimeout(poll, POLL_INTERVAL_MS)
      } catch (e) {
        if (cancelledRef.current) return
        setError(e.message || '상태 확인 중 오류가 발생했어요.')
      }
    }

    poll()
    return () => {
      cancelledRef.current = true
      clearTimeout(timer)
    }
  }, [state.renderId, navigate])

  const startOver = () => {
    reset()
    navigate('/')
  }

  const isReady = status === 'done'

  return (
    <div className="animate-fadein min-h-screen">
      <FlowHeader step={3} onCancel={startOver} cancelLabel="처음으로" />

      <main className="max-w-2xl mx-auto px-5 py-16">
        {error ? (
          <div className="bg-white rounded-3xl shadow-sm border border-gray-100 p-10 text-center">
            <div className="mx-auto w-14 h-14 rounded-full bg-red-50 text-red-500 flex items-center justify-center mb-4">
              <span className="w-7 h-7">{I.info}</span>
            </div>
            <h2 className="text-2xl font-extrabold text-red-500">만들기 실패</h2>
            <p className="text-gray-500 mt-1">{error}</p>
            <button onClick={() => navigate('/edit')} className="mt-6 rounded-xl bg-brand-600 hover:bg-brand-700 text-white font-semibold px-6 py-3 transition">
              편집으로 돌아가기
            </button>
          </div>
        ) : !isReady ? (
          <div className="bg-white rounded-3xl shadow-sm border border-gray-100 p-10 text-center">
            <div className="mx-auto w-14 h-14 mb-4">
              <svg className="animate-spin text-brand-600" viewBox="0 0 24 24" fill="none">
                <circle cx="12" cy="12" r="9" stroke="currentColor" strokeWidth="3" opacity="0.2" />
                <path d="M21 12a9 9 0 0 0-9-9" stroke="currentColor" strokeWidth="3" strokeLinecap="round" />
              </svg>
            </div>
            <h2 className="text-2xl font-extrabold text-gray-900">쇼츠 만드는 중...</h2>
            <p className="text-gray-400 mt-1">9:16 영상으로 변환하고 있어요</p>
          </div>
        ) : (
          <>
            <div className="flex items-center justify-center gap-4 mb-3">
              <div className="w-14 h-14 rounded-full bg-emerald-500 text-white flex items-center justify-center animate-pop">
                <span className="w-7 h-7">{I.check}</span>
              </div>
              <h1 className="text-3xl font-extrabold text-gray-900">쇼츠가 완성됐어요!</h1>
            </div>
            <p className="text-center text-gray-400 mb-10">아래에서 다운로드하세요</p>

            <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-4 flex gap-4">
              <div className={'rounded-xl w-24 aspect-[9/16] bg-gradient-to-br ' + grad + ' relative flex items-end justify-center p-2 shrink-0 overflow-hidden'}>
                {/* 클립 대표 프레임 썸네일. 없거나 로드 실패하면 뒤의 그라데이션이 그대로 보인다. */}
                {clip?.thumbnail_url && (
                  <img
                    src={withApiBase(clip.thumbnail_url)}
                    alt={title}
                    onError={(e) => { e.currentTarget.style.display = 'none' }}
                    className="absolute inset-0 w-full h-full object-cover"
                  />
                )}
                <div className="absolute inset-0 flex items-center justify-center">
                  <div className="w-10 h-10 rounded-full bg-white/30 text-white flex items-center justify-center">{I.play}</div>
                </div>
                <span className="text-[10px] text-white font-semibold relative z-10 text-center leading-tight">{title.slice(0, 8)}</span>
              </div>
              <div className="flex-1">
                <h3 className="font-bold text-gray-900">{title}</h3>
                {clip && <p className="text-xs text-gray-400 mt-1">{clip.duration_sec}초 · 9:16 · mp4</p>}
                <div className="mt-3 space-y-2">
                  <a href={downloadUrl(state.renderId)} download onClick={() => setDownloaded(true)} className={'w-full rounded-xl py-2.5 text-sm font-bold flex items-center justify-center gap-2 transition ' + (downloaded ? 'bg-emerald-500 text-white' : 'border-2 border-brand-500 text-brand-600 hover:bg-brand-50')}>
                    <span className="w-4 h-4">{downloaded ? I.check : I.download}</span>
                    {downloaded ? '다운로드 완료' : '다운로드'}
                  </a>
                  <button
                    onClick={() => {
                      // 다른 구간으로 다시 만들기 → 결과 확인(/results)에서 클립/구간을 다시 고른다.
                      // 이전 선택·제목·스타일·렌더 state 는 초기화하되 clips/taskId 는 유지한다.
                      // (clips 가 비어 있어도 /results 가 taskId 로 다시 불러온다)
                      update({
                        selected: [],
                        title: '',
                        titleInput: '',
                        editStart: null,
                        editEnd: null,
                        style: { bg: 'black', text: 'white', pos: 'bottom', size: 'md' },
                        renderId: null,
                      })
                      navigate('/results')
                    }}
                    className="w-full rounded-xl border border-gray-200 py-2.5 text-sm font-medium text-gray-600 flex items-center justify-center gap-2 hover:bg-gray-50"
                  >
                    <span className="w-4 h-4">{I.refresh}</span> 다른 구간으로 다시 만들기
                  </button>
                </div>
              </div>
            </div>

            <input
              ref={fileInputRef}
              type="file"
              accept="video/mp4,video/quicktime,.mp4,.mov"
              className="hidden"
              onChange={handleNewFile}
            />
            <button
              onClick={() => fileInputRef.current?.click()}
              className="w-full mt-6 rounded-2xl bg-brand-600 hover:bg-brand-700 text-white font-bold py-4 flex items-center justify-center gap-2 transition shadow-lg shadow-brand-600/25"
            >
              <span className="w-5 h-5">{I.plus}</span> 새 영상 업로드
            </button>

            {downloaded && (
              <div className="mt-6 rounded-2xl bg-gradient-to-br from-brand-600 to-fuchsia-500 text-white text-center p-8 animate-fadein">
                <div className="mx-auto w-12 h-12 rounded-full bg-white/20 flex items-center justify-center mb-3">
                  <span className="w-6 h-6">{I.check}</span>
                </div>
                <p className="font-bold text-lg">다운로드했어요!</p>
                <p className="text-sm text-white/80 mt-1">이제 쇼츠를 업로드해보세요</p>
              </div>
            )}
          </>
        )}
      </main>
    </div>
  )
}
