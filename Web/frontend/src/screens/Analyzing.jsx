import { Fragment, useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import FlowHeader from '../components/FlowHeader'
import { I } from '../components/Icon'
import { useShortify } from '../context/ShortifyContext'
import { CATEGORIES, ANALYZE_PHASES } from '../data/content'
import { getStatus, getResult } from '../api/client'

// 명세서는 10초(10000) 권장. 개발 중엔 빠르게 확인하려고 2초로 둠. 팀 합의대로 조정.
const POLL_INTERVAL_MS = 2000

export default function Analyzing() {
  const navigate = useNavigate()
  const { state, update } = useShortify()
  const [progress, setProgress] = useState(null) // 0~100 또는 null
  const [statusText, setStatusText] = useState('pending')
  const [done, setDone] = useState(false)
  const [error, setError] = useState('')
  const cancelledRef = useRef(false)

  useEffect(() => {
    // task_id 없이 직접 들어온 경우 옵션으로 되돌림
    if (!state.taskId) {
      navigate('/options')
      return
    }

    cancelledRef.current = false
    let timer

    const poll = async () => {
      try {
        const s = await getStatus(state.taskId)
        if (cancelledRef.current) return

        setStatusText(s.status)
        setProgress(typeof s.progress === 'number' ? s.progress : null)

        if (s.status === 'done') {
          const result = await getResult(state.taskId)
          if (cancelledRef.current) return
          update({
            clips: result.clips || [],
            videoDurationMs: result.video_duration_ms || 0,
          })
          setDone(true)
          setTimeout(() => {
            if (!cancelledRef.current) navigate('/results')
          }, 1000)
          return
        }

        if (s.status === 'failed') {
          setError('분석에 실패했어요. 다시 시도해주세요.')
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
  }, [state.taskId, navigate, update])

  const catLabels = state.cats.length
    ? CATEGORIES.filter((c) => state.cats.includes(c.key)).map((c) => c.label).join(', ')
    : ''

  // 진행 단계 계산: progress 가 있으면 4단계로 매핑, 없으면 status 기준
  const activePhase = done
    ? ANALYZE_PHASES.length
    : progress != null
      ? Math.min(ANALYZE_PHASES.length - 1, Math.floor((progress / 100) * ANALYZE_PHASES.length))
      : statusText === 'pending'
        ? 0
        : 1

  return (
    <div className="animate-fadein min-h-screen">
      <FlowHeader step={1} onCancel={() => navigate('/options')} cancelLabel="옵션 설정으로" />

      <main className="max-w-2xl mx-auto px-5 py-12">
        <div className="flex items-center gap-3 rounded-xl bg-gray-100 px-4 py-3 mb-10">
          <div className="w-9 h-9 rounded-lg bg-white text-brand-600 flex items-center justify-center">{I.phone}</div>
          <div className="min-w-0">
            <div className="font-semibold text-gray-800 text-sm truncate">
              {state.fileName || (state.inputMode === 'url' ? '유튜브 영상' : '영상')}
            </div>
            <div className="text-xs text-gray-400">
              {state.inputMode === 'url' ? 'YouTube URL' : state.fileSize}
            </div>
          </div>
        </div>

        <div className="bg-white rounded-3xl shadow-sm border border-gray-100 p-10 text-center">
          {error ? (
            <>
              <div className="mx-auto w-14 h-14 rounded-full bg-red-50 text-red-500 flex items-center justify-center mb-4">
                <span className="w-7 h-7">{I.info}</span>
              </div>
              <h2 className="text-2xl font-extrabold text-red-500">분석 실패</h2>
              <p className="text-gray-500 mt-1">{error}</p>
              <button
                onClick={() => navigate('/options')}
                className="mt-6 rounded-xl bg-brand-600 hover:bg-brand-700 text-white font-semibold px-6 py-3 transition"
              >
                다시 시도
              </button>
            </>
          ) : done ? (
            <>
              <div className="mx-auto w-14 h-14 rounded-full border-4 border-emerald-500 text-emerald-500 flex items-center justify-center mb-4 animate-pop">
                {I.check}
              </div>
              <h2 className="text-2xl font-extrabold text-emerald-500">분석 완료!</h2>
              <p className="text-gray-400 mt-1">결과를 확인하고 있습니다</p>
            </>
          ) : (
            <>
              <div className="mx-auto w-14 h-14 mb-4">
                <svg className="animate-spin text-brand-600" viewBox="0 0 24 24" fill="none">
                  <circle cx="12" cy="12" r="9" stroke="currentColor" strokeWidth="3" opacity="0.2" />
                  <path d="M21 12a9 9 0 0 0-9-9" stroke="currentColor" strokeWidth="3" strokeLinecap="round" />
                </svg>
              </div>
              <h2 className="text-2xl font-extrabold text-gray-900">AI 구간 분석 중...</h2>
              <p className="text-gray-400 mt-1">
                {catLabels && `카테고리: ${catLabels} · `}최대 {state.clips.length || 5}개 클립 추출
                {progress != null && ` · ${progress}%`}
              </p>
            </>
          )}

          {/* 단계 표시 (에러 아닐 때만) */}
          {!error && (
            <div className="flex items-start justify-between mt-10 px-2">
              {ANALYZE_PHASES.map((phase, i) => {
                const isDone = i < activePhase
                const isActive = i === activePhase && !done
                return (
                  <Fragment key={phase}>
                    <div className="flex flex-col items-center w-20">
                      <div
                        className={
                          'w-9 h-9 rounded-full flex items-center justify-center text-sm font-bold transition ' +
                          (isDone || done
                            ? 'bg-gray-400 text-white'
                            : isActive
                              ? 'bg-brand-600 text-white'
                              : 'bg-gray-200 text-gray-500')
                        }
                      >
                        {isDone || done ? <span className="w-4 h-4">{I.check}</span> : i + 1}
                      </div>
                      <div
                        className={
                          'text-[11px] mt-2 text-center leading-tight ' +
                          (isActive ? 'text-brand-600 font-semibold' : 'text-gray-400')
                        }
                      >
                        {phase}
                      </div>
                    </div>
                    {i < ANALYZE_PHASES.length - 1 && <div className="flex-1 h-px bg-gray-200 mt-4" />}
                  </Fragment>
                )
              })}
            </div>
          )}
        </div>

        {!done && !error && (
          <>
            <button className="w-full mt-4 rounded-2xl border border-gray-200 bg-white py-3.5 text-sm font-medium text-gray-600 flex items-center justify-center gap-2 hover:bg-gray-50">
              <span className="w-4 h-4">{I.bell}</span> 완료되면 알림 받기
            </button>
            <div className="mt-3 flex items-start gap-2 rounded-2xl border border-gray-100 bg-gray-50 px-4 py-3 text-xs text-gray-500">
              <span className="w-4 h-4 mt-0.5 shrink-0">{I.info}</span>
              다른 탭으로 이동해도 괜찮아요. 단, 창을 닫으면 처리가 중단될 수 있어요.
            </div>
          </>
        )}
      </main>
    </div>
  )
}