// 화면에 들어가는 정적 콘텐츠. icon 값은 components/Icon.jsx 의 I[key] 로 매핑된다.
// apiKey 는 백엔드로 보낼 카테고리 값 (empathy/laughter/info/touching). key == apiKey 로 통일.

export const CATEGORIES = [
  { key: 'laughter', apiKey: 'laughter', label: '웃음', desc: '웃긴 장면과 유머', icon: 'smile' },
  { key: 'empathy', apiKey: 'empathy', label: '공감', desc: '공감되는 순간', icon: 'heart' },
  { key: 'info', apiKey: 'info', label: '정보', desc: '유용한 정보와 팁', icon: 'bulb' },
  { key: 'touching', apiKey: 'touching', label: '감동', desc: '뭉클한 감동 순간', icon: 'heart' },
]

export const FEATURES = [
  { icon: 'mic', title: '한국어 특화 STT', desc: '리얼타임 AI 기반 정확한 한국어 음성 인식 및 자막 추출' },
  { icon: 'target', title: '카테고리 선택', desc: '웃음, 공감, 정보·팁, 감동 중 원하는 분위기 선택' },
  { icon: 'spark', title: 'AI 제목 추천', desc: '클립을 분석하여 쇼츠 제목 3개를 자동으로 추천' },
  { icon: 'scissors', title: '구간 직접 조정', desc: 'AI 추천 구간을 슬라이더로 더 세밀하게 조정 가능' },
  { icon: 'palette', title: '스타일 설정', desc: '배경색, 글씨색, 제목 위치, 글씨 크기를 간편하게 설정' },
  { icon: 'phone', title: '9:16 자동 변환', desc: '쇼츠 최적 비율로 변환 후 즉시 다운로드' },
]

export const STEPS = [
  { num: 1, icon: 'upload', title: '영상 업로드', desc: '파일 또는 유튜브 URL 입력' },
  { num: 2, icon: 'target', title: '카테고리 선택', desc: '원하는 분위기 선택' },
  { num: 3, icon: 'scissors', title: 'AI 구간 편집', desc: 'AI 추천 구간 선택 및 조정' },
  { num: 4, icon: 'download', title: '다운로드', desc: '9:16 쇼츠 완성' },
]

// 히어로 미리보기 카드. img 파일을 public/landing/ 에 넣으면 사진이 뜨고, 없으면 그라데이션.
export const HERO_CARDS = [
  { label: '웃음', time: '00:34', rank: '1위 추천', grad: 'from-brand-600 to-fuchsia-500', headline: '웃참하다 결국 터져버림', sub: 'ㅋㅋㅋ', img: '/landing/humor.webp' },
  { label: '감동', time: '00:28', rank: '2위 추천', grad: 'from-teal-600 to-emerald-500', headline: '엄마 손잡고 걷던 게 언제였더라', img: '/landing/touching.webp' },
  { label: '공감', time: '00:41', rank: '3위 추천', grad: 'from-slate-800 to-slate-600', headline: '카페에서 5분만 쉬려다 기절', sub: 'ㅋㅋㅋ', img: '/landing/empathy.webp' },
]

// 결과 카드 배경 그라데이션 (순위 순서대로 돌려 씀)
export const CLIP_GRADIENTS = [
  'from-brand-600 to-fuchsia-500',
  'from-teal-600 to-emerald-500',
  'from-slate-800 to-slate-600',
  'from-rose-500 to-orange-400',
  'from-sky-600 to-indigo-500',
]

// 분석 단계 라벨 (진행 표시용)
export const ANALYZE_PHASES = ['오디오 추출중', '음성인식(STT) 처리중', 'AI 구간 분석중', '결과 준비']