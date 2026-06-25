import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import FlowHeader from '../components/FlowHeader'
import PrimaryButton from '../components/PrimaryButton'
import { I } from '../components/Icon'
import { useShortify } from '../context/ShortifyContext'
import { CATEGORIES } from '../data/content'
import { uploadVideo } from '../api/client'

const CLIP_COUNT = 5 // AI가 최대 몇 개 추출할지 (명세서 clip_count)

export default function Options() {
  const navigate = useNavigate()
  const { state, update } = useShortify()
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState('')

  const toggleCategory = (key) => {
    const next = state.cats.includes(key)
      ? state.cats.filter((k) => k !== key)
      : [...state.cats, key]
    update({ cats: next })
    if (error) setError('')
  }

  const handleSubmit = async () => {
    // 입력 검증
    if (state.cats.length === 0) {
      setError('카테고리를 하나 이상 선택해주세요.')
      return
    }
    if (state.inputMode === 'file' && !state.file) {
      setError('영상 파일을 먼저 업로드해주세요.')
      return
    }
    if (state.inputMode === 'url' && !state.url.trim()) {
      setError('유튜브 URL을 먼저 입력해주세요.')
      return
    }

    setSubmitting(true)
    setError('')
    try {
      // 명세서: category 는 단수 → 현재는 첫 번째 선택 카테고리를 보냄 (팀 확정 필요)
      const category = CATEGORIES.find((c) => c.key === state.cats[0])?.apiKey

      const data = await uploadVideo({
        file: state.inputMode === 'file' ? state.file : null,
        youtubeUrl: state.inputMode === 'url' ? state.url.trim() : null,
        clipCount: CLIP_COUNT,
        category,
        userPrompt: state.extra,
      })

      // 이후로는 task_id 만 들고 다닌다
      update({ taskId: data.task_id })
      navigate('/analyzing')
    } catch (e) {
      setError(e.message || '업로드에 실패했어요. 잠시 후 다시 시도해주세요.')
      setSubmitting(false)
    }
  }

  return (
    <div className="animate-fadein min-h-screen">
      <FlowHeader step={1} onCancel={() => navigate('/')} cancelLabel="← 영상 다시 선택하기" />

      <main className="max-w-3xl mx-auto px-5 py-16">
        {/* 업로드된 입력 칩 */}
        <div className="flex items-center gap-3 rounded-xl bg-gray-100 px-4 py-3 mb-10">
          <div className="w-9 h-9 rounded-lg bg-white text-brand-600 flex items-center justify-center">{I.phone}</div>
          <div className="flex-1 min-w-0">
            <div className="font-semibold text-gray-800 text-sm truncate">
              {state.fileName || (state.inputMode === 'url' ? '유튜브 영상' : '선택된 파일 없음')}
            </div>
            <div className="text-xs text-gray-400">
              {state.inputMode === 'url' ? 'YouTube URL' : state.fileSize}
            </div>
          </div>
        </div>

        <h1 className="text-3xl font-extrabold text-gray-900">어떤 쇼츠를 만들까요?</h1>
        <p className="text-gray-500 mt-2">카테고리를 선택하면 AI가 더 정확하게 구간을 추출해드려요</p>

        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mt-8">
          {CATEGORIES.map((c) => {
            const active = state.cats.includes(c.key)
            return (
              <button
                key={c.key}
                onClick={() => toggleCategory(c.key)}
                className={
                  'rounded-2xl border-2 p-4 text-center transition ' +
                  (active ? 'border-brand-500 bg-brand-50' : 'border-gray-200 hover:border-gray-300 bg-white')
                }
              >
                <div className={'mx-auto w-7 h-7 mb-2 ' + (active ? 'text-brand-600' : 'text-gray-700')}>
                  {I[c.icon]}
                </div>
                <div className={'font-bold text-sm ' + (active ? 'text-brand-700' : 'text-gray-900')}>{c.label}</div>
                <div className="text-[11px] text-gray-400 mt-0.5">{c.desc}</div>
              </button>
            )
          })}
        </div>

        <div className="mt-8">
          <label className="text-sm font-semibold text-gray-700">추가 요청사항(선택)</label>
          <textarea
            value={state.extra}
            onChange={(e) => update({ extra: e.target.value })}
            rows={3}
            placeholder="예: 운전면허 시험 관련 구간 위주로 뽑아줘, 말이 빠른 구간은 제외해줘"
            className="mt-2 w-full rounded-2xl border border-gray-200 px-4 py-3 text-sm focus:outline-none focus:border-brand-400 focus:ring-2 focus:ring-brand-100 resize-none"
          />
        </div>

        {error && <p className="mt-4 text-sm text-red-500">{error}</p>}

        <div className="mt-6">
          <PrimaryButton onClick={handleSubmit} disabled={submitting || state.cats.length === 0}>
            {submitting ? '업로드 중...' : 'AI 분석 시작하기'}
          </PrimaryButton>
          <p className="text-center text-xs text-gray-400 mt-3">AI가 최대 {CLIP_COUNT}개 클립을 자동 추출합니다.</p>
        </div>
      </main>
    </div>
  )
}