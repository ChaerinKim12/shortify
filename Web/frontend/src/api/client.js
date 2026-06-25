// 백엔드 API 호출 레이어. 명세서의 엔드포인트 6개를 그대로 감쌌다.
//
// 호출 주소(BASE):
// - 기본값(빈 문자열)이면 vite proxy 를 통해 /api → http://localhost:8000 으로 전달된다.
//   (vite.config.js 의 server.proxy 설정. 개발 중 CORS 안 생김)
// - 백엔드를 다른 주소로 직접 부르고 싶으면 .env 에 VITE_API_BASE 를 지정한다.

const BASE = import.meta.env.VITE_API_BASE ?? ''
// ───────── 목업 모드 (백엔드 없을 때 화면 테스트용) ─────────
// 백엔드가 준비되면 아래 USE_MOCK 을 false 로 바꾸면 진짜 API 로 동작.
const USE_MOCK = true

const wait = (ms) => new Promise((r) => setTimeout(r, ms))

const MOCK_RESULT = {
  video_duration_ms: 1320000,
  clips: [
    { rank: 1, start_ms: 192000, end_ms: 226000, duration_sec: 34, reason: '강사의 자신감 넘치는 말 직후 갑자기 눈이 내리자 분노하는 모습이 압권이에요',
      titles: ['운전면허 시험 직전 멘탈 나간 이유', '추억의 장소에서 터진 대참사', '혼자 여행 중 생긴 역대급 위기'] },
    { rank: 2, start_ms: 502000, end_ms: 530000, duration_sec: 28, reason: '순간적으로 당황하며 표정이 일그러지는 장면과 리액션이 자연스럽고 재미있어요',
      titles: ['중딩 때 못 했던 혼코노 드디어 해냈다', '드디어 도전한 첫 혼코노', '10년 묵은 버킷리스트 클리어'] },
    { rank: 3, start_ms: 1335000, end_ms: 1376000, duration_sec: 41, reason: '긴박한 상황을 재미있게 설명하며 몰입도가 높고 공감 가는 에피소드예요',
      titles: ['옛날 동네에서 똥 지릴 뻔한 썰', '모두가 겪어봤을 그 위기의 순간', '웃픈 어린 시절 흑역사'] },
  ],
}

let _mockProgress = 0

const mock = {
  upload: async () => { _mockProgress = 0; await wait(500); return { task_id: 'mock-task-1', status: 'pending' } },
  status: async () => {
    await wait(400)
    _mockProgress = Math.min(100, _mockProgress + 35)
    return { status: _mockProgress >= 100 ? 'done' : 'processing', progress: _mockProgress }
  },
  result: async () => { await wait(300); return MOCK_RESULT },
  render: async () => { await wait(500); return { render_id: 'mock-render-1', status: 'pending' } },
  renderStatus: (() => { let n = 0; return async () => { await wait(500); n += 1; return { status: n >= 2 ? 'done' : 'processing' } } })(),
}
// ──────────────────────────────────────────────────────────

// 공통 요청 처리: 실패하면 명세서의 에러 형식 { error: { code, message } } 을 읽어 throw
async function request(path, options = {}) {
  const res = await fetch(BASE + path, options)
  if (!res.ok) {
    let message = `요청에 실패했어요 (${res.status})`
    let code = 'UNKNOWN'
    try {
      const data = await res.json()
      if (data?.error) {
        message = data.error.message || message
        code = data.error.code || code
      }
    } catch {
      // 에러 본문이 JSON 이 아니면 기본 메시지 사용
    }
    const err = new Error(message)
    err.code = code
    err.status = res.status
    throw err
  }
  return res
}

async function requestJson(path, options) {
  const res = await request(path, options)
  return res.json()
}

// (1) 영상 올리기 + 분석 시작 → { task_id, status }
export function uploadVideo({ file, youtubeUrl, clipCount, category, userPrompt }) {
  if (USE_MOCK) return mock.upload()
  const form = new FormData()
  if (file) form.append('file', file)
  if (youtubeUrl) form.append('youtube_url', youtubeUrl)
  form.append('clip_count', String(clipCount))
  form.append('category', category)
  form.append('user_prompt', userPrompt ?? '')
  // FormData 사용 시 Content-Type 은 브라우저가 boundary 와 함께 자동 설정 (직접 넣지 말 것)
  return requestJson('/api/upload', { method: 'POST', body: form })
}

// (2) 분석 상태 확인 → { status, progress }
export function getStatus(taskId) {
  if (USE_MOCK) return mock.status()
  return requestJson(`/api/status/${taskId}`)
}

// (3) 추천 결과 → { video_duration_ms, clips[] }
export function getResult(taskId) {
  if (USE_MOCK) return mock.upload()
  return requestJson(`/api/result/${taskId}`)
}

// (4) 영상 만들기 시작 → { render_id, status }
export function startRender({ taskId, startMs, endMs, title }) {
  if (USE_MOCK) return mock.upload()
  return requestJson('/api/render', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ task_id: taskId, start_ms: startMs, end_ms: endMs, title }),
  })
}

// (5) 만들기 상태 확인 → { status }
export function getRenderStatus(renderId) {
  if (USE_MOCK) return mock.upload()
  return requestJson(`/api/render/status/${renderId}`)
}

// (6) 다운로드 URL — <a href> 로 그대로 사용 (mp4 파일이 응답으로 옴)
export function downloadUrl(renderId) {
  return `${BASE}/api/download/${renderId}`
}