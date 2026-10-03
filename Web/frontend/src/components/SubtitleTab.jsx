import { useEffect, useRef, useState } from 'react'
import StyleField from './StyleField'
import { previewUrl } from '../api/client'
import { msToClock } from '../utils/time'
import { OUT_W, MARGIN, LINE_SPACING, FONT_SIZE_PX, wrapTitleToLines } from '../utils/titleWrap'
import {
  OUT_H,
  VIDEO_TOP,
  VIDEO_H,
  OUTLINE_PX,
  SUBTITLE_SIZE_PX,
  subtitleAnchor,
  wrapCueText,
  lineFontScale,
  titleTopY,
} from '../utils/subtitle'

// 미리보기 프레임 폭(px). 렌더 프레임 OUT_W(720)에 대응.
const PREVIEW_W = 288

// 자막 탭: 9:16 프레임 안에서 영상 + 현재 시간 자막 오버레이를 보여주고, 자막 옵션/줄 목록을 편집한다.
export default function SubtitleTab({
  taskId, range, style, title,
  subs, loading, loadError,
  enabled, setEnabled, position, setPosition, size, setSize, lineCount, setLineCount,
  onEditText, onDelete,
}) {
  const videoRef = useRef(null)
  const [nowMs, setNowMs] = useState(range.start)

  // 구간이 바뀌면 시작점으로 이동
  useEffect(() => {
    const v = videoRef.current
    if (v) v.currentTime = range.start / 1000
  }, [range.start])

  const scale = PREVIEW_W / OUT_W
  const cur = enabled ? subs.find((s) => nowMs >= s.start_ms && nowMs < s.end_ms) : null
  const { anchor, y } = subtitleAnchor(position, titleTopY(title, style.pos, style.size))
  const subPx = SUBTITLE_SIZE_PX[size] * scale
  const titlePx = FONT_SIZE_PX[style.size] ?? FONT_SIZE_PX.md
  const titleLines = title && title.trim() ? wrapTitleToLines(title, titlePx) : []

  const seekTo = (ms) => {
    const v = videoRef.current
    if (v) v.currentTime = ms / 1000
  }

  return (
    <div className="grid md:grid-cols-2 gap-10 items-start">
      {/* 미리보기: 렌더와 같은 비율의 9:16 프레임 */}
      <div className="flex flex-col items-center">
        <div
          className={'relative rounded-3xl overflow-hidden ' + (style.bg === 'black' ? 'bg-black' : 'bg-white border border-gray-200')}
          style={{ width: PREVIEW_W, height: OUT_H * scale }}
        >
          <video
            ref={videoRef}
            src={previewUrl(taskId)}
            controls
            preload="metadata"
            onLoadedMetadata={() => seekTo(range.start)}
            onTimeUpdate={(e) => {
              const v = e.currentTarget
              if (v.currentTime >= range.end / 1000) v.currentTime = range.start / 1000
              setNowMs(v.currentTime * 1000)
            }}
            className="absolute left-0 bg-black"
            style={{ top: VIDEO_TOP * scale, width: PREVIEW_W, height: VIDEO_H * scale }}
          />
          {titleLines.length > 0 && (
            <div
              className="absolute inset-x-0 text-center font-extrabold pointer-events-none"
              style={{
                [style.pos === 'top' ? 'top' : 'bottom']: MARGIN * scale,
                color: style.text === 'white' ? '#fff' : '#000',
                fontSize: titlePx * scale,
                lineHeight: `${(titlePx + LINE_SPACING) * scale}px`,
                whiteSpace: 'nowrap',
              }}
            >
              {titleLines.map((ln, i) => <div key={i}>{ln || ' '}</div>)}
            </div>
          )}
          {cur && (
            <div
              className="absolute inset-x-0 text-center font-bold pointer-events-none"
              style={{
                top: y * scale,
                transform: anchor === 'center' ? 'translateY(-50%)' : 'translateY(-100%)',
                color: '#fff',
                // ASS 쪽은 정수 % 로 줄이므로 같은 반올림을 적용
                fontSize: subPx * (Math.round(lineFontScale(cur.text) * 100) / 100),
                lineHeight: 1.25,
                whiteSpace: 'pre',
                WebkitTextStroke: `${OUTLINE_PX * 2 * scale}px #000`,
                paintOrder: 'stroke fill',
              }}
            >
              {wrapCueText(cur.text)}
            </div>
          )}
        </div>
        <span className="text-xs text-gray-400 mt-2">미리보기 · 재생하면 자막이 시간에 맞춰 나와요</span>
      </div>

      {/* 옵션 + 자막 줄 목록 */}
      <div>
        <div className="flex items-center justify-between mb-5">
          <h3 className="font-bold text-gray-900">자막 표시</h3>
          <button
            role="switch"
            aria-checked={enabled}
            onClick={() => setEnabled(!enabled)}
            className={'relative w-12 h-7 rounded-full transition ' + (enabled ? 'bg-brand-600' : 'bg-gray-300')}
          >
            <span className={'absolute top-1 w-5 h-5 rounded-full bg-white transition-all ' + (enabled ? 'left-6' : 'left-1')} />
          </button>
        </div>

        <div className={'grid grid-cols-2 gap-x-8 gap-y-5 mb-8 ' + (enabled ? '' : 'opacity-40 pointer-events-none')}>
          <StyleField
            label="자막 위치"
            options={[['letterbox', '영상 아래'], ['overlay', '영상 위']]}
            value={position}
            onChange={setPosition}
          />
          <StyleField
            label="줄 수"
            options={[['1', '1줄'], ['2', '2줄']]}
            value={lineCount}
            onChange={setLineCount}
          />
          <StyleField
            label="자막 크기"
            options={[['sm', '소'], ['md', '중'], ['lg', '대']]}
            value={size}
            onChange={setSize}
          />
        </div>

        <h3 className="font-bold text-gray-900 mb-3">
          자막 줄 <span className="text-gray-400 font-medium text-sm">{subs.length}개</span>
        </h3>
        {loading ? (
          <p className="text-sm text-gray-400">자막을 불러오는 중이에요...</p>
        ) : loadError ? (
          <p className="text-sm text-gray-400">{loadError}</p>
        ) : subs.length === 0 ? (
          <p className="text-sm text-gray-400">이 구간에는 자막이 없어요.</p>
        ) : (
          <ul className={'space-y-2 max-h-[28rem] overflow-y-auto pr-1 ' + (enabled ? '' : 'opacity-40')}>
            {subs.map((s) => (
              <li key={s.key} className="flex items-start gap-3 bg-white rounded-xl border border-gray-100 p-3">
                <button
                  onClick={() => seekTo(s.start_ms)}
                  className="shrink-0 text-xs font-mono text-brand-600 hover:underline pt-1.5"
                  title="이 시간으로 이동"
                >
                  {msToClock(s.start_ms)}
                  <br />
                  {msToClock(s.end_ms)}
                </button>
                <textarea
                  value={s.text}
                  rows={2}
                  onChange={(e) => onEditText(s.key, e.target.value)}
                  className="flex-1 resize-none rounded-lg border border-gray-200 px-3 py-1.5 text-sm focus:outline-none focus:border-brand-400"
                />
                <button
                  onClick={() => onDelete(s.key)}
                  className="shrink-0 text-gray-300 hover:text-red-500 text-lg leading-none pt-1"
                  aria-label="자막 줄 삭제"
                >
                  ✕
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  )
}
