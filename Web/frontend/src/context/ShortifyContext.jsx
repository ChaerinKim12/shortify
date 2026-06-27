import { createContext, useContext, useState } from 'react'

const ShortifyContext = createContext(null)

const INITIAL_STATE = {
  // 입력
  inputMode: 'file', // 'file' | 'url'
  url: '',
  file: null, // 실제 File 객체 (업로드 시점까지만 사용)
  fileName: '',
  fileSize: '',

  // 옵션
  cats: [], // 선택된 카테고리 key 목록 (다중 선택, API엔 categories 리스트로 전송)
  extra: '', // 추가 요청사항 (user_prompt)

  // 분석 (POST /api/upload → GET status → GET result)
  taskId: null,
  clips: [], // 추천 클립 목록 (result.clips)
  videoDurationMs: 0, // 원본 영상 길이

  // 결과 선택 / 편집
  selected: [], // 선택된 클립 rank 목록 (최대 5)
  editStart: null, // 편집에서 조정한 시작 (ms)
  editEnd: null, // 편집에서 조정한 종료 (ms)
  title: '', // 최종 제목
  titleInput: '',
  style: { bg: 'black', text: 'white', pos: 'bottom', size: 'md' },

  // 렌더 (POST /api/render → GET render/status → download)
  renderId: null,
}

export function ShortifyProvider({ children }) {
  const [state, setState] = useState(INITIAL_STATE)

  // 부분 업데이트
  const update = (patch) => setState((prev) => ({ ...prev, ...patch }))

  // 중첩된 style만 따로 갱신
  const updateStyle = (patch) =>
    setState((prev) => ({ ...prev, style: { ...prev.style, ...patch } }))

  const reset = () => setState(INITIAL_STATE)

  return (
    <ShortifyContext.Provider value={{ state, update, updateStyle, reset }}>
      {children}
    </ShortifyContext.Provider>
  )
}

export function useShortify() {
  const ctx = useContext(ShortifyContext)
  if (!ctx) throw new Error('useShortify must be used within ShortifyProvider')
  return ctx
}