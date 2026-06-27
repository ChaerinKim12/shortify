// 백엔드 API 호출 레이어. 명세서의 엔드포인트 6개를 그대로 감쌌다.
//
// 호출 주소(BASE):
// - 기본값(빈 문자열)이면 vite proxy 를 통해 /api → http://localhost:8000 으로 전달된다.
//   (vite.config.js 의 server.proxy 설정. 개발 중 CORS 안 생김)
// - 백엔드를 다른 주소로 직접 부르고 싶으면 .env 에 VITE_API_BASE 를 지정한다.

const BASE = import.meta.env.VITE_API_BASE ?? ''
// ───────── 목업 모드 (백엔드 없을 때 화면 테스트용) ─────────
// 백엔드가 준비되면 아래 USE_MOCK 을 false 로 바꾸면 진짜 API 로 동작.
const USE_MOCK = false

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
  upload: async (onProgress) => {
    _mockProgress = 0
    // 업로드 진행률 흉내: 0 -> 100 (onProgress 가 있으면 단계적으로 호출)
    for (const pct of [20, 55, 85, 100]) { await wait(150); onProgress?.(pct) }
    return { task_id: 'mock-task-1', status: 'pending' }
  },
  status: async () => {
    await wait(400)
    _mockProgress = Math.min(100, _mockProgress + 30)
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

// 에러 객체 생성 (request() 와 동일한 형태: message + code + status)
function makeError(message, code, status) {
  const err = new Error(message)
  err.code = code
  err.status = status
  return err
}

// (1) 영상 올리기 + 분석 시작 → { task_id, status }
// categories: 백엔드 코드값 리스트(empathy/laughter/info/touching). 1~4개.
// onProgress(pct: 0~100): 업로드 진행률 콜백(선택). 진행률을 알려면 fetch 가 아닌 XHR 필요.
// onInit(xhr): 생성된 XHR 인스턴스를 호출측에 넘긴다(진행 중 업로드를 abort 할 수 있게).
export function uploadVideo({ file, youtubeUrl, categories, userPrompt, onProgress, onInit }) {
  if (USE_MOCK) return mock.upload(onProgress)
  const form = new FormData()
  if (file) form.append('file', file)
  if (youtubeUrl) form.append('youtube_url', youtubeUrl)
  // list[str] 계약: 같은 이름 'categories' 필드를 선택 개수만큼 반복 전송
  ;(categories ?? []).forEach((c) => form.append('categories', c))
  form.append('user_prompt', userPrompt ?? '')

  // XHR 사용 이유: fetch 는 업로드 진행률 이벤트를 제공하지 않는다.
  // FormData 사용 시 Content-Type 은 브라우저가 boundary 와 함께 자동 설정 (직접 넣지 말 것)
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest()
    xhr.open('POST', BASE + '/api/upload')
    // 호출측이 진행 중 업로드를 중단(abort)할 수 있게 xhr 인스턴스를 넘긴다.
    onInit?.(xhr)

    // 업로드(요청 본문 전송) 진행률. file 전송량 기준 0~100%.
    xhr.upload.onprogress = (e) => {
      if (onProgress && e.lengthComputable) {
        onProgress(Math.round((e.loaded / e.total) * 100))
      }
    }

    xhr.onload = () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        try { resolve(JSON.parse(xhr.responseText)) }
        catch { reject(makeError('응답을 해석할 수 없어요.', 'UNKNOWN', xhr.status)) }
        return
      }
      // 실패: request() 와 같은 { error: { code, message } } 규약을 읽어 throw
      let message = `요청에 실패했어요 (${xhr.status})`
      let code = 'UNKNOWN'
      try {
        const data = JSON.parse(xhr.responseText)
        if (data?.error) { message = data.error.message || message; code = data.error.code || code }
      } catch { /* JSON 아니면 기본 메시지 */ }
      reject(makeError(message, code, xhr.status))
    }

    xhr.onerror = () => reject(makeError('네트워크 오류로 업로드에 실패했어요.', 'NETWORK', 0))
    xhr.onabort = () => reject(makeError('업로드가 취소되었어요.', 'ABORTED', 0))
    xhr.send(form)
  })
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
// 스타일 옵션(bgColor/textColor/titlePosition/fontSize)도 함께 보낸다.
// 백엔드 RenderRequest 의 bg_color/text_color/title_position/font_size 와 1:1 매핑.
// (값이 undefined 면 JSON 에서 빠져 백엔드 기본값이 적용된다)
export function startRender({ taskId, startMs, endMs, title, bgColor, textColor, titlePosition, fontSize }) {
  if (USE_MOCK) return mock.upload()
  return requestJson('/api/render', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      task_id: taskId,
      start_ms: startMs,
      end_ms: endMs,
      title,
      bg_color: bgColor,
      text_color: textColor,
      title_position: titlePosition,
      font_size: fontSize,
    }),
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

// (7) 원본 미리보기 URL — <video src> 로 그대로 사용 (Range 지원, seek 가능)
export function previewUrl(taskId) {
  return `${BASE}/api/preview/${taskId}`
}

// 백엔드가 결과 JSON 으로 내려준 상대 경로(/api/...)에 BASE 를 붙여 절대 URL 로 만든다.
// 예: clip.thumbnail_url ("/api/thumbnail/{task_id}/{rank}") → <img src>
export function withApiBase(path) {
  return path ? `${BASE}${path}` : path
}