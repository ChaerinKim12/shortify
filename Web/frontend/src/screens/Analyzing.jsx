import { Fragment, useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import FlowHeader from '../components/FlowHeader'
import { I } from '../components/Icon'
import { useShortify } from '../context/ShortifyContext'
import { CATEGORIES, ANALYZE_PHASES } from '../data/content'
import { getStatus, getResult, uploadVideo } from '../api/client'

// 명세서는 10초(10000) 권장. 개발 중엔 빠르게 확인하려고 2초로 둠. 팀 합의대로 조정.
const POLL_INTERVAL_MS = 2500

export default function Analyzing() {
  const navigate = useNavigate()
  const { state, update } = useShortify()
  const [progress, setProgress] = useState(null) // 0~100 또는 null
  const [statusText, setStatusText] = useState('pending')
  const [done, setDone] = useState(false)
  const [error, setError] = useState('')
  const [phase, setPhase] = useState(state.taskId ? 'polling' : 'uploading') // 'uploading' | 'polling'
  const [uploadPct, setUploadPct] = useState(0)
  // 브라우저 알림(Web Notification). 작업(task) 단위: 항상 꺼진 상태로 시작하고(브라우저 권한이
  // 허용돼 있어도 켜진 것으로 보지 않는다), 완료/실패 알림을 1회 보내면 자동으로 꺼진다.
  // 아무 곳에도 저장하지 않으므로 새 업로드/분석(컴포넌트 새 마운트)은 늘 꺼짐에서 시작한다.
  const [notifyOn, setNotifyOn] = useState(false)
  const notifiedTaskRef = useRef(null) // 알림을 이미 보낸 task_id (같은 작업에 중복 발송 방지)
  const cancelledRef = useRef(false)
  const uploadStartedRef = useRef(false) // StrictMode 이중 마운트 시 업로드 1회만 보장
  const uploadXhrRef = useRef(null)      // 진행 중 업로드 XHR (cleanup 에서 abort)
  const abortTimerRef = useRef(null)     // StrictMode remount 와 실제 unmount 구분용 지연 abort

  useEffect(() => {
    // taskId 도 없고 업로드할 입력(file/url)도 없으면 옵션으로 되돌림
    if (!state.taskId && !state.file && !state.url) {
      navigate('/options')
      return
    }

    cancelledRef.current = false
    clearTimeout(abortTimerRef.current) // StrictMode remount: 직전 cleanup 이 예약한 abort 취소
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

    const doUpload = async () => {
      try {
        setPhase('uploading')
        setUploadPct(0)
        // 선택된 카테고리 key → 백엔드 코드값(apiKey) 리스트로 변환 (1~4개)
        const categories = state.cats
          .map((k) => CATEGORIES.find((c) => c.key === k)?.apiKey)
          .filter(Boolean)
        const data = await uploadVideo({
          file: state.inputMode === 'file' ? state.file : null,
          youtubeUrl: state.inputMode === 'url' ? state.url.trim() : null,
          categories,
          userPrompt: state.extra,
          onProgress: (pct) => { if (!cancelledRef.current) setUploadPct(pct) },
          onInit: (xhr) => { uploadXhrRef.current = xhr },
        })
        uploadXhrRef.current = null
        if (cancelledRef.current) return
        update({ taskId: data.task_id }) // taskId 가 채워지면 effect 재실행 → 폴링 시작
      } catch (e) {
        uploadXhrRef.current = null
        if (cancelledRef.current) return // 언마운트/abort 로 인한 취소면 조용히 무시
        setError(e.message || '업로드에 실패했어요. 다시 시도해주세요.')
      }
    }

    if (state.taskId) {
      setPhase('polling')
      poll()
    } else if (!uploadStartedRef.current) {
      uploadStartedRef.current = true
      doUpload()
    }

    return () => {
      cancelledRef.current = true
      clearTimeout(timer)
      // 진행 중 업로드 abort. 단 StrictMode 의 mount→cleanup→remount 동기 사이클에서는
      // 곧바로 remount(effect 재실행) 되어 위에서 이 타이머를 취소하므로 실제로 abort 되지 않는다.
      // 진짜 unmount 면 remount 가 없어 타이머가 살아남아 abort 된다.
      const xhr = uploadXhrRef.current
      if (xhr) {
        abortTimerRef.current = setTimeout(() => xhr.abort(), 0)
      }
    }
  }, [state.taskId, navigate, update])

  // "알림받기" 클릭 → 브라우저 알림 권한 요청. 미지원/거부 브라우저는 조용히 무시.
  const handleEnableNotify = async () => {
    if (typeof Notification === 'undefined') return        // 미지원 브라우저
    if (Notification.permission === 'granted') { setNotifyOn(true); return }
    if (Notification.permission === 'denied') return       // 거부 상태면 재요청 불가
    try {
      const perm = await Notification.requestPermission()
      setNotifyOn(perm === 'granted')
    } catch {
      // 일부 구형 브라우저의 콜백형 API 등 예외 — 조용히 무시
    }
  }

  // 분석 완료/실패 시, 알림을 켜 둔 경우에만 1회 발송하고 곧바로 끈다.
  // (업로드 단계 실패처럼 task_id 가 아직 없는 오류는 "분석" 실패가 아니므로 보내지 않는다)
  const finished = done ? 'done' : error && state.taskId ? 'failed' : null
  useEffect(() => {
    if (!finished || !notifyOn) return
    if (notifiedTaskRef.current === state.taskId) return
    notifiedTaskRef.current = state.taskId
    setNotifyOn(false)
    if (typeof Notification === 'undefined' || Notification.permission !== 'granted') return
    try {
      new Notification(
        finished === 'done' ? '분석 완료!' : '분석에 실패했어요',
        {
          body:
            finished === 'done'
              ? '쇼츠 추천 구간이 준비됐어요. 결과를 확인해 보세요.'
              : '다시 시도해 주세요.',
        },
      )
    } catch {
      // 발송 실패(권한 변동/모바일 제약 등) — 조용히 무시
    }
  }, [finished, notifyOn, state.taskId])

  const catLabels = state.cats.length
    ? CATEGORIES.filter((c) => state.cats.includes(c.key)).map((c) => c.label).join(', ')
    : ''

  // 진행 단계 계산: progress 가 있으면 4단계로 매핑, 없으면 status 기준
  const activePhase = done
    ? ANALYZE_PHASES.length
    : phase === 'uploading'
      ? 0 // 업로드는 분석 1단계 이전 단계
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
              {phase === 'uploading' ? (
                <>
                  <h2 className="text-2xl font-extrabold text-gray-900">영상 업로드 중...</h2>
                  <p className="text-gray-400 mt-1">업로드 중 {uploadPct}% · 완료되면 분석을 시작해요</p>
                </>
              ) : (
                <>
                  <h2 className="text-2xl font-extrabold text-gray-900">AI 구간 분석 중...</h2>
                  <p className="text-gray-400 mt-1">
                    {catLabels && `카테고리: ${catLabels} · `}선택 카테고리에 따라 클립 추출
                    {progress != null && ` · ${progress}%`}
                  </p>
                </>
              )}
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
            <button
              onClick={handleEnableNotify}
              disabled={notifyOn}
              className={
                'w-full mt-4 rounded-2xl border py-3.5 text-sm font-medium flex items-center justify-center gap-2 transition ' +
                (notifyOn
                  ? 'border-brand-200 bg-brand-50 text-brand-700 cursor-default'
                  : 'border-gray-200 bg-white text-gray-600 hover:bg-gray-50')
              }
            >
              <span className="w-4 h-4">{notifyOn ? I.check : I.bell}</span>
              {notifyOn ? '완료되면 알림 받기 (켜짐)' : '완료되면 알림 받기'}
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