# Shortify (web)

AI 기반 한국어 쇼츠 자동 추출 — 프론트엔드 (Vite + React + Tailwind)

## 실행

```bash
npm install
npm run dev      # 개발 서버 (http://localhost:5173)
npm run build    # 프로덕션 빌드 (dist/)
npm run preview  # 빌드 결과 미리보기
```

## 구조

```
src/
├── main.jsx                  # 엔트리 (Router + Context Provider)
├── App.jsx                   # 라우트 정의
├── index.css                 # Tailwind + 슬라이더 스타일
├── context/
│   └── ShortifyContext.jsx   # 위저드 전역 상태 (cats, selected, title, style ...)
├── data/
│   └── content.js            # 화면 콘텐츠 데이터 (카테고리·기능·클립 등)
├── components/
│   ├── Icon.jsx              # inline SVG 아이콘 세트 (I.xxx)
│   ├── Logo.jsx
│   ├── FlowHeader.jsx        # 단계 표시 헤더
│   ├── PrimaryButton.jsx
│   └── StyleField.jsx        # 스타일 토글 그룹
└── screens/
    ├── Landing.jsx           # /         랜딩
    ├── Options.jsx           # /options  카테고리 선택
    ├── Analyzing.jsx         # /analyzing 분석 진행
    ├── Results.jsx           # /results  클립 추천 결과
    ├── Edit.jsx              # /edit     구간 조정 / 제목·스타일
    └── Done.jsx              # /done     완료·다운로드
```

## 수정 포인트

- 더미 클립/문구는 `src/data/content.js` 한 곳에서 관리됩니다.
- 색상·폰트·애니메이션 토큰은 `tailwind.config.js` 의 `theme.extend`.
- 화면 흐름(전역 상태)은 `src/context/ShortifyContext.jsx`.
- 실제 API 연동 시 `Analyzing.jsx` 의 setTimeout 진행을 실제 요청으로,
  `Results.jsx` 의 `CLIPS` 를 응답 데이터로 교체하면 됩니다.
