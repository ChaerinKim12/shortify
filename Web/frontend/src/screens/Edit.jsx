import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import FlowHeader from '../components/FlowHeader'
import StyleField from '../components/StyleField'
import { I } from '../components/Icon'
import { useShortify } from '../context/ShortifyContext'
import { CLIP_GRADIENTS } from '../data/content'
import { msToClock } from '../utils/time'
import { startRender } from '../api/client'

const TITLE_SIZE = { sm: 'text-base', md: 'text-xl', lg: 'text-3xl' }

export default function Edit() {
  const navigate = useNavigate()
  const { state, update, updateStyle } = useShortify()
  const [tab, setTab] = useState('trim') // 'trim' | 'style'
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState('')

  // 선택한 첫 번째 클립
  const clip = (state.clips || []).find((c) => c.rank === state.selected[0])

  // 선택 클립이 없으면 결과로 되돌림
  useEffect(() => {
    if (!clip) navigate('/results')
  }, [clip, navigate])

  if (!clip) return null

  const grad = CLIP_GRADIENTS[(clip.rank - 1) % CLIP_GRADIENTS.length]
  const { style } = state
  const currentTitle = state.title || clip.titles?.[0] || ''

  const handleRender = async () => {
    setSubmitting(true)
    setError('')
    try {
      const title = state.title?.trim() ? state.title : clip.titles?.[0] || ''
      const data = await startRender({
        taskId: state.taskId,
        startMs: clip.start_ms, // TODO: 구간 슬라이더 조정값 연동 (지금은 추천 구간 그대로)
        endMs: clip.end_ms,
        title,
      })
      update({ renderId: data.render_id, title })
      navigate('/done')
    } catch (e) {
      setError(e.message || '영상 만들기 시작에 실패했어요.')
      setSubmitting(false)
    }
  }

  return (
    <div className="animate-fadein min-h-screen pb-24 bg-gray-50">
      <FlowHeader step={3} onCancel={() => navigate('/results')} cancelLabel="← 목록으로" />

      {/* 탭 */}
      <div className="bg-white border-b border-gray-100">
        <div className="max-w-5xl mx-auto px-5 py-3 font-bold text-gray-900">클립 1</div>
        <div className="max-w-5xl mx-auto px-5 flex gap-6">
          {[
            ['trim', '구간 조정', I.scissors],
            ['style', '제목·스타일', I.palette],
          ].map(([key, label, icon]) => (
            <button
              key={key}
              onClick={() => setTab(key)}
              className={
                'flex items-center gap-2 pb-3 text-sm font-semibold border-b-2 transition ' +
                (tab === key ? 'border-brand-600 text-brand-600' : 'border-transparent text-gray-400')
              }
            >
              <span className="w-4 h-4">{icon}</span>
              {label}
            </button>
          ))}
        </div>
      </div>

      <main className="max-w-5xl mx-auto px-5 py-8">
        {tab === 'trim' ? (
          <>
            <p className="text-center text-gray-700 font-medium mb-3">{currentTitle}</p>
            <div className={'relative rounded-2xl aspect-video bg-gradient-to-br ' + grad + ' overflow-hidden'}>
              <div className="absolute inset-0 flex items-center justify-center">
                <div className="w-16 h-16 rounded-full bg-white/30 text-white flex items-center justify-center">{I.play}</div>
              </div>
              <div className="absolute bottom-4 left-4 right-4 bg-black/40 rounded-lg px-4 py-2 text-white text-sm font-mono">
                {msToClock(clip.start_ms)} / {msToClock(clip.end_ms)}
              </div>
            </div>

            <div className="bg-white rounded-2xl border border-gray-100 p-6 mt-6">
              <p className="text-xs text-gray-400 mb-4">앞뒤 1분 포함 구간 표시</p>
              <input type="range" min="0" max="100" defaultValue="60" className="rng w-full" />
              <div className="flex items-center justify-center gap-3 mt-6 flex-wrap">
                <div className="rounded-xl bg-gray-100 px-4 py-2 text-sm">
                  <span className="text-gray-400">시작점: </span>
                  <b className="text-gray-800">{msToClock(clip.start_ms)}</b>
                </div>
                <span className="text-gray-300">{I.arrow}</span>
                <div className="rounded-xl bg-gray-100 px-4 py-2 text-sm">
                  <span className="text-gray-400">종료점: </span>
                  <b className="text-gray-800">{msToClock(clip.end_ms)}</b>
                </div>
                <div className="rounded-xl bg-brand-50 px-4 py-2 text-sm">
                  <span className="text-brand-500">길이: </span>
                  <b className="text-brand-700">{clip.duration_sec}초</b>
                </div>
              </div>
            </div>
          </>
        ) : (
          <div className="grid md:grid-cols-2 gap-10 items-start">
            {/* 미리보기 */}
            <div className="flex flex-col items-center">
              <div
                className={
                  'rounded-3xl aspect-[9/16] w-64 flex justify-center p-5 ' +
                  (style.bg === 'black' ? 'bg-black' : 'bg-white border border-gray-200') +
                  ' ' +
                  (style.pos === 'top' ? 'items-start' : 'items-end')
                }
              >
                <p
                  className={
                    'text-center font-extrabold leading-snug ' +
                    TITLE_SIZE[style.size] +
                    ' ' +
                    (style.text === 'white' ? 'text-white' : 'text-black')
                  }
                >
                  {currentTitle}
                </p>
              </div>
              <span className="text-xs text-gray-400 mt-2">미리보기</span>
            </div>

            {/* 제목 + 스타일 컨트롤 */}
            <div>
              <h3 className="font-bold text-gray-900 mb-3">제목 설정</h3>
              <div className="space-y-2">
                {(clip.titles || []).map((t, i) => (
                  <button
                    key={i}
                    onClick={() => update({ title: t, titleInput: '' })}
                    className={
                      'block text-left w-full text-sm font-medium px-1 py-1 rounded ' +
                      (currentTitle === t ? 'text-brand-600 font-bold' : 'text-gray-700 hover:text-gray-900')
                    }
                  >
                    {t}
                  </button>
                ))}
                <input
                  value={state.titleInput}
                  onChange={(e) => update({ titleInput: e.target.value, title: e.target.value })}
                  placeholder="직접 입력하기"
                  className="w-full mt-2 rounded-xl border border-gray-200 px-4 py-2.5 text-sm focus:outline-none focus:border-brand-400"
                />
                <button
                  onClick={() => update({ title: ' ', titleInput: '' })}
                  className="text-xs text-gray-400 hover:text-gray-600"
                >
                  건너뛰기 (제목 없이)
                </button>
              </div>

              <h3 className="font-bold text-gray-900 mt-8 mb-3">스타일 설정</h3>
              <div className="grid grid-cols-2 gap-x-8 gap-y-5">
                <StyleField
                  label="배경색"
                  options={[['black', '검정'], ['white', '흰색']]}
                  value={style.bg}
                  onChange={(v) => updateStyle({ bg: v })}
                />
                <StyleField
                  label="글씨색"
                  options={[['white', '흰색'], ['black', '검정']]}
                  value={style.text}
                  onChange={(v) => updateStyle({ text: v })}
                />
                <StyleField
                  label="제목 위치"
                  options={[['top', '상단'], ['bottom', '하단']]}
                  value={style.pos}
                  onChange={(v) => updateStyle({ pos: v })}
                />
                <StyleField
                  label="글씨 크기"
                  options={[['sm', '소'], ['md', '중'], ['lg', '대']]}
                  value={style.size}
                  onChange={(v) => updateStyle({ size: v })}
                />
              </div>

              <label className="flex items-center gap-2 mt-6 text-sm text-gray-500">
                <input type="checkbox" className="accent-brand-600 w-4 h-4" /> 이 스타일을 다른 클립에도 동일하게 적용
              </label>
            </div>
          </div>
        )}

        {error && <p className="mt-4 text-sm text-red-500 text-center">{error}</p>}
      </main>

      {/* 하단 고정 바 */}
      <div className="fixed bottom-0 inset-x-0 bg-white/95 backdrop-blur border-t border-gray-100">
        <div className="max-w-5xl mx-auto px-5 h-20 flex items-center justify-between">
          <span className="text-sm text-gray-500">클립 1/1 편집 중</span>
          <button
            onClick={handleRender}
            disabled={submitting}
            className={
              'rounded-2xl font-bold px-6 py-3.5 transition flex items-center gap-2 ' +
              (submitting
                ? 'bg-gray-200 text-gray-400 cursor-not-allowed'
                : 'bg-brand-600 hover:bg-brand-700 text-white shadow-lg shadow-brand-600/25')
            }
          >
            {submitting ? '준비 중...' : '저장 후 다운로드'} {!submitting && I.arrow}
          </button>
        </div>
      </div>
    </div>
  )
}