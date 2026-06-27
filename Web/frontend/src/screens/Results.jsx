import { useNavigate } from 'react-router-dom'
import FlowHeader from '../components/FlowHeader'
import { I } from '../components/Icon'
import { useShortify } from '../context/ShortifyContext'
import { CATEGORIES, CLIP_GRADIENTS } from '../data/content'
import { msToClock } from '../utils/time'

const MAX_SELECT = 5

export default function Results() {
  const navigate = useNavigate()
  const { state, update } = useShortify()

  const toggleClip = (rank) => {
    if (state.selected.includes(rank)) {
      update({ selected: state.selected.filter((r) => r !== rank) })
    } else if (state.selected.length < MAX_SELECT) {
      update({ selected: [...state.selected, rank] })
    }
  }

  const count = state.selected.length
  const clips = state.clips || []

  // 선택한 카테고리 라벨 (배지용). 명세서가 단수라 첫 번째 기준.
  const catLabel = CATEGORIES.find((c) => c.key === state.cats[0])?.label || ''

  return (
    <div className="animate-fadein min-h-screen pb-24">
      <FlowHeader step={2} onCancel={() => navigate('/options')} />

      <main className="max-w-6xl mx-auto px-5 py-12">
        <h1 className="text-3xl font-extrabold text-gray-900">AI가 추천한 클립이에요</h1>
        <p className="text-gray-500 mt-2">
          원하는 클립을 선택해 주세요 · <span className="text-brand-600 font-semibold">{count}개 선택됨</span> · 최대 5개
        </p>

        {clips.length === 0 ? (
          <div className="mt-16 text-center text-gray-400">
            <div className="mx-auto w-12 h-12 text-gray-300 mb-3">{I.info}</div>
            <p className="font-medium text-gray-500">추천할 만한 구간을 찾지 못했어요.</p>
            <p className="text-sm mt-1">다른 카테고리나 영상으로 다시 시도해보세요.</p>
            <button
              onClick={() => navigate('/options')}
              className="mt-6 rounded-xl bg-brand-600 hover:bg-brand-700 text-white font-semibold px-6 py-3 transition"
            >
              옵션 다시 설정하기
            </button>
          </div>
        ) : (
          <div className="grid md:grid-cols-3 gap-5 mt-8">
            {clips.map((clip, idx) => {
              const active = state.selected.includes(clip.rank)
              const grad = CLIP_GRADIENTS[idx % CLIP_GRADIENTS.length]
              const headline = clip.titles?.[0] || `추천 클립 ${clip.rank}`
              return (
                <div
                  key={clip.rank}
                  onClick={() => toggleClip(clip.rank)}
                  className={
                    'cursor-pointer rounded-2xl bg-white border-2 transition overflow-hidden shadow-sm hover:shadow-md ' +
                    (active ? 'border-brand-500' : 'border-transparent')
                  }
                >
                  <div className={'relative aspect-[16/10] bg-gradient-to-br ' + grad}>
                    <span className="absolute top-3 left-3 text-xs font-bold text-white bg-black/25 rounded-md px-2 py-1">
                      {clip.rank}위
                    </span>
                    {catLabel && (
                      <span className="absolute top-3 right-3 text-xs font-semibold text-gray-700 bg-white/90 rounded-md px-2 py-1">
                        {catLabel}
                      </span>
                    )}
                    <div className="absolute inset-0 flex items-center justify-center">
                      {active ? (
                        <div className="w-12 h-12 rounded-full bg-brand-600 text-white flex items-center justify-center animate-pop">
                          <span className="w-6 h-6">{I.check}</span>
                        </div>
                      ) : (
                        <div className="w-12 h-12 rounded-full bg-white/30 text-white flex items-center justify-center">
                          {I.play}
                        </div>
                      )}
                    </div>
                  </div>
                  <div className="p-4">
                    <h3 className="font-bold text-gray-900 leading-snug">{headline}</h3>
                    <div className="text-sm text-gray-500 mt-2">
                      ⏱ {clip.duration_sec}초 · {msToClock(clip.start_ms)} ~ {msToClock(clip.end_ms)}
                    </div>
                    <p className="text-xs text-gray-400 mt-2 leading-relaxed line-clamp-2">{clip.reason}</p>
                  </div>
                </div>
              )
            })}
          </div>
        )}
      </main>

      {/* 하단 고정 바 */}
      <div className="fixed bottom-0 inset-x-0 bg-white/95 backdrop-blur border-t border-gray-100">
        <div className="max-w-6xl mx-auto px-5 h-20 flex items-center justify-between">
          <span className="text-sm text-gray-500">{count}개 클립 선택됨</span>
          <button
            onClick={() => count > 0 && navigate('/edit')}
            disabled={count === 0}
            className={
              'rounded-2xl font-bold px-6 py-3.5 transition flex items-center gap-2 ' +
              (count > 0
                ? 'bg-brand-600 hover:bg-brand-700 text-white shadow-lg shadow-brand-600/25'
                : 'bg-gray-200 text-gray-400 cursor-not-allowed')
            }
          >
            선택한 클립 편집하기 {I.arrow}
          </button>
        </div>
      </div>
    </div>
  )
}