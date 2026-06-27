// 의존성 없이 inline SVG 로 구성한 아이콘 세트.
// 사용: import { I } from './Icon'  →  I.upload, I.smile ...

export function Icon({ children, className = 'w-full h-full', stroke = 2, fill = 'none', viewBox = '0 0 24 24' }) {
  return (
    <svg
      viewBox={viewBox}
      fill={fill}
      stroke="currentColor"
      strokeWidth={stroke}
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
    >
      {children}
    </svg>
  )
}

export const I = {
  upload: (
    <Icon>
      <path d="M12 16V4" />
      <path d="m6 10 6-6 6 6" />
      <path d="M4 20h16" />
    </Icon>
  ),
  mic: (
    <Icon>
      <rect x="9" y="2" width="6" height="12" rx="3" />
      <path d="M5 10a7 7 0 0 0 14 0" />
      <path d="M12 17v4" />
    </Icon>
  ),
  target: (
    <Icon>
      <circle cx="12" cy="12" r="9" />
      <circle cx="12" cy="12" r="5" />
      <circle cx="12" cy="12" r="1.4" />
    </Icon>
  ),
  spark: (
    <Icon>
      <path d="M12 3v18M3 12h18" />
      <path d="m6 6 1.5 1.5M18 6l-1.5 1.5M6 18l1.5-1.5M18 18l-1.5-1.5" />
    </Icon>
  ),
  scissors: (
    <Icon>
      <circle cx="6" cy="6" r="3" />
      <circle cx="6" cy="18" r="3" />
      <path d="M20 4 8.12 15.88M14.47 14.48 20 20M8.12 8.12 12 12" />
    </Icon>
  ),
  palette: (
    <Icon>
      <path d="M12 22a10 10 0 1 1 0-20 8 8 0 0 1 0 16h-1.5a1.5 1.5 0 0 0-1 2.6A1 1 0 0 1 12 22z" />
      <circle cx="7.5" cy="10.5" r="1" />
      <circle cx="12" cy="7.5" r="1" />
      <circle cx="16.5" cy="10.5" r="1" />
    </Icon>
  ),
  phone: (
    <Icon>
      <rect x="7" y="2" width="10" height="20" rx="2" />
      <path d="M11 18h2" />
    </Icon>
  ),
  smile: (
    <Icon>
      <circle cx="12" cy="12" r="9" />
      <path d="M8 14s1.5 2 4 2 4-2 4-2" />
      <path d="M9 9h.01M15 9h.01" />
    </Icon>
  ),
  heart: (
    <Icon>
      <path d="M12 20s-7-4.5-9.5-9A5 5 0 0 1 12 6a5 5 0 0 1 9.5 5C19 15.5 12 20 12 20z" />
    </Icon>
  ),
  flip: (
    <Icon>
      <path d="M3 7a9 9 0 0 1 15-3l3 3M21 17a9 9 0 0 1-15 3l-3-3" />
      <path d="M21 4v3h-3M3 20v-3h3" />
    </Icon>
  ),
  bulb: (
    <Icon>
      <path d="M9 18h6M10 22h4" />
      <path d="M12 2a6 6 0 0 0-4 10.5c.8.8 1 1.5 1 2.5h6c0-1 .2-1.7 1-2.5A6 6 0 0 0 12 2z" />
    </Icon>
  ),
  sad: (
    <Icon>
      <circle cx="12" cy="12" r="9" />
      <path d="M16 16s-1.5-2-4-2-4 2-4 2" />
      <path d="M9 9h.01M15 9h.01" />
    </Icon>
  ),
  play: (
    <Icon fill="currentColor" stroke="none">
      <path d="M8 5v14l11-7z" />
    </Icon>
  ),
  check: (
    <Icon stroke={3}>
      <path d="m5 12 5 5L20 7" />
    </Icon>
  ),
  download: (
    <Icon>
      <path d="M12 4v12" />
      <path d="m6 12 6 6 6-6" />
      <path d="M4 20h16" />
    </Icon>
  ),
  refresh: (
    <Icon>
      <path d="M21 12a9 9 0 1 1-3-6.7L21 8" />
      <path d="M21 3v5h-5" />
    </Icon>
  ),
  plus: (
    <Icon stroke={2.5}>
      <path d="M12 5v14M5 12h14" />
    </Icon>
  ),
  bell: (
    <Icon>
      <path d="M6 9a6 6 0 0 1 12 0c0 5 2 6 2 6H4s2-1 2-6z" />
      <path d="M10 20a2 2 0 0 0 4 0" />
    </Icon>
  ),
  info: (
    <Icon>
      <circle cx="12" cy="12" r="9" />
      <path d="M12 11v5M12 8h.01" />
    </Icon>
  ),
  arrow: (
    <Icon className="w-4 h-4">
      <path d="M5 12h14M13 6l6 6-6 6" />
    </Icon>
  ),
  chevR: (
    <Icon className="w-5 h-5" stroke={2.5}>
      <path d="m9 6 6 6-6 6" />
    </Icon>
  ),
}
