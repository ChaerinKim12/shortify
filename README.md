# Shortify

> 긴 유튜브 영상에서 쇼츠로 만들 구간을 AI가 찾아 주는 서비스

Shortify는 10분 이상의 한국어 영상을 넣으면 **웃음·감동·공감 같은 카테고리별로 쇼츠가 될 만한 구간을 추천**하고, 세로형 쇼츠 영상(720×1280)으로 바로 만들어 줍니다.
크리에이터가 긴 영상을 처음부터 다시 보며 구간을 고르고 자르는 반복 작업을 줄이는 것이 목표입니다.

---

## 주요 기능

| 기능 | 설명 |
| --- | --- |
| AI 구간 추천 | 자막(STT)과 음성 특징을 함께 분석해 카테고리별 하이라이트 구간 추천 |
| 선정 이유 공개 | 클립마다 "포인트 / 반응 신호 / 첫 3초" 형식으로 왜 골랐는지 설명 |
| 사용자 요청 반영 | "먹방 장면 위주로"처럼 원하는 방향을 입력하면 추천 우선순위에 참고 |
| 자동 자막 | 분석에 쓴 STT 결과를 재사용해 추가 비용 없이 자막 생성, 줄 단위 수정 가능 |
| 웹 편집기 | 구간 조정 → 자막 → 제목·스타일 순서로 편집 후 다운로드 |
| 완료 알림 | 분석이 끝나면 브라우저 알림으로 안내 |

---

## 동작 방식

```
영상 업로드 / 유튜브 URL
        ↓
① 오디오 추출 (ffmpeg)
        ↓
② 음성 인식 + 화자 분리 (리턴제로 STT)
        ↓
③ 음성 특징 태깅 (librosa: 음량 · 피치 · 말 속도 · 무음)
        ↓
④ 카테고리별 구간 추천 (Claude Sonnet 4.5)
        ↓
⑤ 중복 제거 · 개수 조정 → 제목 생성
        ↓
⑥ 세로형 쇼츠 렌더링 (제목 · 자막 합성)
```

- **자막만이 아니라 "어떻게 말했는지"까지 봅니다.** 목소리가 커지거나 톤이 올라가는 구간처럼 텍스트에 드러나지 않는 반응을 태그로 붙여 함께 판단합니다.
- **카테고리마다 따로 분석합니다.** 웃음과 감동은 좋은 장면의 기준이 달라 카테고리별 기준으로 각각 추천합니다.

---

## 기술 스택

| 구분 | 사용 기술 |
| --- | --- |
| Frontend | React, Vite, React Router, Tailwind CSS |
| Backend | FastAPI (BackgroundTasks) |
| AI / 분석 | Claude Sonnet 4.5 (구간 추천), Claude Haiku 4.5 (선정 이유 정리), 리턴제로 STT, librosa |
| 영상 처리 | ffmpeg (libass 자막), yt-dlp |

---

## 폴더 구조

```
Web/
├── algorithm/   # 구간 추천 알고리즘 (STT, 음성 특징, 프롬프트, 후처리)
├── backend/     # FastAPI 서버 (업로드, 분석 작업, 자막, 렌더링 API)
└── frontend/    # React 웹 (업로드 → 옵션 → 결과 → 편집·다운로드)
```

---

## 로컬 실행

### 1. 준비물
- Python 3.10 이상, Node.js 18 이상
- ffmpeg (libass 포함 빌드), yt-dlp
- API 키: Anthropic, 리턴제로(RTZR)

### 2. 환경 변수
`Web/.env` 파일을 만들고 아래 값을 채웁니다. (`.env`는 git에 올리지 않습니다)

```
ANTHROPIC_API_KEY=
RTZR_CLIENT_ID=
RTZR_CLIENT_SECRET=
```

### 3. 백엔드
```bash
cd Web/backend
python -m venv .venv
# Windows: .\.venv\Scripts\Activate.ps1   /   macOS·Linux: source .venv/bin/activate
pip install -r requirements.txt -r ../algorithm/requirements.txt
uvicorn app.main:app --reload --port 8000
```
> `anthropic` 패키지가 없는 환경에서 실행하면 알고리즘 대신 예시 결과가 표시됩니다.

### 4. 프론트엔드
```bash
cd Web/frontend
npm install
npm run dev
```
브라우저에서 `http://localhost:5173` 접속

---

## 팀

**미래내일 일경험 프로젝트형 · 모바일앱개발협동조합**

| 이름 | 역할 |
| --- | --- |
| 김채린 | 팀장, 알고리즘 설계 |
| 김지연 | 알고리즘 설계, 백엔드 |
| 김예성 | 알고리즘 설계, 백엔드 |
| 양세은 | 알고리즘 설계, 프론트앤드 |
