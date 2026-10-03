import { useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import FlowHeader from '../components/FlowHeader'
import StyleField from '../components/StyleField'
import { I } from '../components/Icon'
import { useShortify } from '../context/ShortifyContext'
import { CLIP_GRADIENTS } from '../data/content'
import { msToClock } from '../utils/time'
import { startRender, getSubtitles, previewUrl, withApiBase } from '../api/client'
import DualRangeSlider from '../components/DualRangeSlider'
import SubtitleTab from '../components/SubtitleTab'
import { SUBTITLE_SIZE_API } from '../utils/subtitle'
import {
  OUT_W,
  MARGIN,
  LINE_SPACING,
  FONT_SIZE_PX,
  wrapTitleToLines,
} from '../utils/titleWrap'

// 프론트 스타일 size(sm/md/lg) → 백엔드 render font_size(small/medium/large) 매핑
const FONT_SIZE_MAP = { sm: 'small', md: 'medium', lg: 'large' }

// 미리보기 프레임 폭(px). 실제 렌더 프레임 OUT_W(720px)에 대응시켜 비율을 맞춘다.
const PREVIEW_W = 256

export default function Edit() {
  const navigate = useNavigate()
  const { state, update, updateStyle } = useShortify()
  const [tab, setTab] = useState('trim') // 'trim' | 'subtitle' | 'style'
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState('')
  // 구간 조정값 (ms). 처음엔 추천 구간으로 시작.
  const [range, setRange] = useState({ start: 0, end: 0 })
  const videoRef = useRef(null)

  // 자막: 슬라이더 최대 범위(앞뒤 1분 포함)를 한 번 받아 두고, 구간이 바뀌면 그 안에서 다시 필터한다.
  // 사용자가 고친 텍스트/삭제는 구간을 움직여도 유지되도록 key(시작-끝) 기준으로 따로 보관한다.
  const [allSubs, setAllSubs] = useState([])
  const [subsLoading, setSubsLoading] = useState(false)
  const [subsError, setSubsError] = useState('')
  const [subEdits, setSubEdits] = useState({})
  const [subDeleted, setSubDeleted] = useState({})
  const [subEnabled, setSubEnabled] = useState(true)
  const [subPos, setSubPos] = useState('letterbox')
  const [subSize, setSubSize] = useState('md')
  const [subLines, setSubLines] = useState('1') // 자막 1개당 줄 수 '1' | '2'

  // 선택한 첫 번째 클립
  const clip = (state.clips || []).find((c) => c.rank === state.selected[0])

  useEffect(() => {
    if (clip) setRange({ start: clip.start_ms, end: clip.end_ms })
  }, [clip])

  useEffect(() => {
    if (!clip || !state.taskId) return
    let cancelled = false
    setSubsLoading(true)
    setSubsError('')
    getSubtitles(state.taskId, Math.max(0, clip.start_ms - 60000), clip.end_ms + 60000, Number(subLines))
      .then((list) => {
        if (cancelled) return
        setAllSubs(list.map((s) => ({ ...s, key: `${s.start_ms}-${s.end_ms}` })))
        setSubEdits({})
        setSubDeleted({})
      })
      .catch((e) => {
        if (cancelled) return
        setAllSubs([])
        setSubsError(e.status === 404 ? '이 영상은 자막 데이터가 없어요.' : '자막을 불러오지 못했어요.')
      })
      .finally(() => !cancelled && setSubsLoading(false))
    return () => { cancelled = true }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [clip?.rank, state.taskId, subLines]) // 줄 수를 바꾸면 새 규칙으로 다시 받는다(수정/삭제는 초기화)

  // 현재 구간과 겹치는 자막만 + 사용자 수정/삭제 반영
  const subs = useMemo(
    () =>
      allSubs
        .filter((s) => s.end_ms > range.start && s.start_ms < range.end && !subDeleted[s.key])
        .map((s) => (s.key in subEdits ? { ...s, text: subEdits[s.key] } : s)),
    [allSubs, range.start, range.end, subEdits, subDeleted],
  )

  // (2) 슬라이더로 시작점(range.start)을 바꾸면 영상 재생 위치도 따라간다.
  useEffect(() => {
    const v = videoRef.current
    if (v) v.currentTime = range.start / 1000
  }, [range.start])

  // 선택한 클립이 바뀌거나 비어 있으면 제목을 그 클립의 추천 제목으로 세팅한다.
  // (이전 클립 제목 잔존 방지. 사용자가 이미 정한 제목이 있으면 유지)
  useEffect(() => {
    if (clip && !state.title) update({ title: clip.titles?.[0] || '' })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [clip?.rank])

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
        startMs: range.start,
        endMs: range.end,
        title,
        // 제목·스타일 설정값을 렌더에 반영 (배경/글씨색/위치/크기)
        bgColor: style.bg,
        textColor: style.text,
        titlePosition: style.pos,
        fontSize: FONT_SIZE_MAP[style.size] || 'medium',
        // 자막: 꺼져 있거나 줄이 없으면 백엔드가 기존 렌더와 동일하게 처리
        subtitleEnabled: subEnabled,
        subtitles: subs.filter((s) => s.text.trim()).map(({ start_ms, end_ms, text }) => ({ start_ms, end_ms, text })),
        subtitlePosition: subPos,
        subtitleSize: SUBTITLE_SIZE_API[subSize] || 'medium',
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
      <FlowHeader
        step={3}
        onCancel={() => {
          // 다른 클립을 다시 고르므로 이전 클립의 제목·스타일·선택/편집 state 를 초기화한다.
          update({
            selected: [],
            title: '',
            titleInput: '',
            editStart: null,
            editEnd: null,
            style: { bg: 'black', text: 'white', pos: 'bottom', size: 'md' }, // INITIAL_STATE.style 와 동일
          })
          navigate('/results')
        }}
        cancelLabel="클립 다시 선택하기"
      />

      {/* 탭 */}
      <div className="bg-white border-b border-gray-100">
        <div className="max-w-5xl mx-auto px-5 py-3 font-bold text-gray-900">클립 1</div>
        <div className="max-w-5xl mx-auto px-5 flex gap-6">
          {[
            ['trim', '구간 조정', I.scissors],
            ['subtitle', '자막', I.mic],
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
              {state.taskId ? (
                <video
                  ref={videoRef}
                  src={previewUrl(state.taskId)}
                  poster={clip.thumbnail_url ? withApiBase(clip.thumbnail_url) : undefined}
                  controls
                  preload="metadata"
                  // (1) 메타데이터 로드되면 AI 추천 구간 시작점으로 점프
                  onLoadedMetadata={() => {
                    const v = videoRef.current
                    if (v) v.currentTime = clip.start_ms / 1000
                  }}
                  // (3) 추천 구간 끝(range.end)을 넘으면 시작점으로 되돌려 구간만 미리보기
                  onTimeUpdate={(e) => {
                    const v = e.currentTarget
                    if (v.currentTime >= range.end / 1000) v.currentTime = range.start / 1000
                  }}
                  className="absolute inset-0 w-full h-full object-contain bg-black/60"
                />
              ) : (
                <div className="absolute inset-0 flex items-center justify-center">
                  {clip.thumbnail_url && (
                    <img
                      src={withApiBase(clip.thumbnail_url)}
                      alt={currentTitle}
                      onError={(e) => { e.currentTarget.style.display = 'none' }}
                      className="absolute inset-0 w-full h-full object-cover"
                    />
                  )}
                  <div className="w-16 h-16 rounded-full bg-white/30 text-white flex items-center justify-center">{I.play}</div>
                </div>
              )}
              <div className="absolute top-3 left-3 bg-black/50 rounded-lg px-3 py-1.5 text-white text-xs font-mono pointer-events-none">
                {msToClock(range.start)} / {msToClock(range.end)}
              </div>
            </div>

            <div className="bg-white rounded-2xl border border-gray-100 p-6 mt-6">
              <p className="text-xs text-gray-400 mb-4">앞뒤 1분을 포함해 구간을 조정할 수 있어요</p>
              <DualRangeSlider
                min={Math.max(0, clip.start_ms - 60000)}
                max={clip.end_ms + 60000}
                start={range.start}
                end={range.end}
                onChange={setRange}
              />
              <div className="flex items-center justify-center gap-3 mt-6 flex-wrap">
                <div className="rounded-xl bg-gray-100 px-4 py-2 text-sm">
                  <span className="text-gray-400">시작점: </span>
                  <b className="text-gray-800">{msToClock(range.start)}</b>
                </div>
                <span className="text-gray-300">{I.arrow}</span>
                <div className="rounded-xl bg-gray-100 px-4 py-2 text-sm">
                  <span className="text-gray-400">종료점: </span>
                  <b className="text-gray-800">{msToClock(range.end)}</b>
                </div>
                <div className="rounded-xl bg-brand-50 px-4 py-2 text-sm">
                  <span className="text-brand-500">길이: </span>
                  <b className="text-brand-700">{Math.round((range.end - range.start) / 1000)}초</b>
                </div>
              </div>
            </div>
          </>
        ) : tab === 'subtitle' ? (
          state.taskId ? (
            <SubtitleTab
              taskId={state.taskId}
              range={range}
              style={style}
              title={currentTitle}
              subs={subs}
              loading={subsLoading}
              loadError={subsError}
              enabled={subEnabled}
              setEnabled={setSubEnabled}
              position={subPos}
              setPosition={setSubPos}
              size={subSize}
              setSize={setSubSize}
              lineCount={subLines}
              setLineCount={(v) => {
                if (v === subLines) return
                // 줄 수를 바꾸면 자막을 새 규칙으로 다시 받아 수정/삭제가 사라지므로 수정한 게 있을 때만 확인
                const edited = Object.keys(subEdits).length > 0 || Object.keys(subDeleted).length > 0
                if (edited && !window.confirm('줄 수를 바꾸면 수정한 자막이 초기화됩니다.\n계속할까요?')) return
                setSubLines(v)
              }}
              onEditText={(key, text) => setSubEdits((m) => ({ ...m, [key]: text }))}
              onDelete={(key) => setSubDeleted((m) => ({ ...m, [key]: true }))}
            />
          ) : (
            <p className="text-center text-sm text-gray-400">영상 정보가 없어 자막을 편집할 수 없어요.</p>
          )
        ) : (
          <div className="grid md:grid-cols-2 gap-10 items-start">
            {/* 미리보기 — 줄바꿈/글자폭/여백을 render.py 와 동일 규칙으로 계산해 WYSIWYG.
                줄바꿈은 wrapTitleToLines()가 결정하고, 각 줄은 white-space:nowrap 으로
                고정해 CSS 자동 줄바꿈에 의존하지 않는다. (CSS가 다시 끊으면 어긋남) */}
            <div className="flex flex-col items-center">
              {(() => {
                const scale = PREVIEW_W / OUT_W                 // 미리보기 폭 / 720
                const fontPx = FONT_SIZE_PX[style.size] ?? FONT_SIZE_PX.md
                const lines = wrapTitleToLines(currentTitle, fontPx) // 백엔드와 동일 폭(624) 기준
                const previewFont = fontPx * scale              // 환산된 글씨 px
                const lineHeight = (fontPx + LINE_SPACING) * scale
                const vPad = MARGIN * scale                     // 위/아래 여백(_MARGIN 환산)
                return (
                  <div
                    className={
                      'rounded-3xl aspect-[9/16] flex flex-col overflow-hidden ' +
                      (style.bg === 'black' ? 'bg-black' : 'bg-white border border-gray-200') +
                      ' ' +
                      (style.pos === 'top' ? 'justify-start' : 'justify-end')
                    }
                    style={{ width: PREVIEW_W, paddingTop: vPad, paddingBottom: vPad }}
                  >
                    <div className="w-full text-center font-extrabold">
                      {lines.map((ln, i) => (
                        <div
                          key={i}
                          style={{
                            whiteSpace: 'nowrap',
                            fontSize: `${previewFont}px`,
                            lineHeight: `${lineHeight}px`,
                            color: style.text === 'white' ? '#fff' : '#000',
                          }}
                        >
                          {ln === '' ? ' ' : ln}
                        </div>
                      ))}
                    </div>
                  </div>
                )
              })()}
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