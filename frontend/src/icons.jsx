import { initialLetter } from './format'

function IconBase({ size = 20, color = 'currentColor', children, ...rest }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke={color}
      strokeWidth="1.8"
      strokeLinecap="round"
      strokeLinejoin="round"
      {...rest}
    >
      {children}
    </svg>
  )
}

// 기능 아이콘

export function CameraIcon(props) {
  return (
    <IconBase {...props}>
      <path d="M8 7l1.2-2h5.6L16 7h2.5A1.5 1.5 0 0 1 20 8.5v9a1.5 1.5 0 0 1-1.5 1.5h-13A1.5 1.5 0 0 1 4 17.5v-9A1.5 1.5 0 0 1 5.5 7H8Z" />
      <circle cx="12" cy="13" r="3.4" />
    </IconBase>
  )
}

export function PlusIcon(props) {
  return (
    <IconBase {...props}>
      <path d="M12 5v14M5 12h14" />
    </IconBase>
  )
}

export function CloseIcon(props) {
  return (
    <IconBase {...props}>
      <path d="M6 6l12 12M18 6 6 18" />
    </IconBase>
  )
}

export function ArrowLeftIcon(props) {
  return (
    <IconBase {...props}>
      <path d="M14.5 5.5 8 12l6.5 6.5" />
    </IconBase>
  )
}

export function ChevronDownIcon(props) {
  return (
    <IconBase {...props}>
      <path d="M6 9.5 12 15.5 18 9.5" />
    </IconBase>
  )
}

export function SendIcon(props) {
  return (
    <IconBase {...props}>
      <path d="M20.5 3.5 3.8 10.2c-.6.24-.56 1.1.06 1.3l5.6 1.8 1.8 5.6c.2.62 1.06.66 1.3.06L19.3 3.5c.14-.5-.28-.86-.8-.72Z" />
      <path d="M10.4 13.3 15.3 8.4" />
    </IconBase>
  )
}

// 사람 아이콘 (프로필 아바타의 "사람" 옵션 전용)

export function PersonIcon(props) {
  return (
    <IconBase {...props}>
      <circle cx="12" cy="8.2" r="3.2" />
      <path d="M5.2 19c0-3.6 3-6.3 6.8-6.3s6.8 2.7 6.8 6.3" />
    </IconBase>
  )
}

// 캐릭터 아바타 (이름 첫 글자)

export function AvatarInitial({ name, size = 20, color = 'var(--text)' }) {
  return (
    <span style={{ fontSize: size * 0.4, fontWeight: 600, color, lineHeight: 1, userSelect: 'none' }}>
      {initialLetter(name)}
    </span>
  )
}

// 프로필 아바타 아이콘

export function HeartIcon(props) {
  return (
    <IconBase {...props}>
      <path d="M12 20.5c-.3 0-.6-.1-.8-.3C7.8 17.4 4.5 14.4 4.5 10.6 4.5 8 6.5 6 9 6c1.3 0 2.5.6 3 1.6.5-1 1.7-1.6 3-1.6 2.5 0 4.5 2 4.5 4.6 0 3.8-3.3 6.8-6.7 9.6-.2.2-.5.3-.8.3Z" />
    </IconBase>
  )
}

export function StarIcon(props) {
  return (
    <IconBase {...props}>
      <path d="M12 3.5l2.4 5 5.4.6-4 3.8 1 5.4L12 15.8 7.2 18.3l1-5.4-4-3.8 5.4-.6L12 3.5Z" />
    </IconBase>
  )
}

export function FlowerIcon(props) {
  return (
    <IconBase {...props}>
      <circle cx="12" cy="7.4" r="2" />
      <circle cx="16.6" cy="12" r="2" />
      <circle cx="12" cy="16.6" r="2" />
      <circle cx="7.4" cy="12" r="2" />
      <circle cx="12" cy="12" r="1.6" />
    </IconBase>
  )
}

export function CatIcon(props) {
  return (
    <IconBase {...props}>
      <path d="M6.5 10 5 5.5l3.8 2.6" />
      <path d="M17.5 10 19 5.5l-3.8 2.6" />
      <path d="M5 14.5c0-4 3.1-7 7-7s7 3 7 7-2.8 5-7 5-7-1-7-5Z" />
      <path d="M9.3 14.2h.4M14.3 14.2h.4" />
      <path d="M11 16.4c.3.3.7.3 1 0" />
    </IconBase>
  )
}

export function DogIcon(props) {
  return (
    <IconBase {...props}>
      <path d="M6.5 8.5c-1.8.4-2.8 2.2-2.3 4.4l1.3 3.8" />
      <path d="M17.5 8.5c1.8.4 2.8 2.2 2.3 4.4l-1.3 3.8" />
      <path d="M6 13.8c0-4.3 2.9-7.3 6-7.3s6 3 6 7.3c0 3.6-2.6 5.7-6 5.7s-6-2.1-6-5.7Z" />
      <path d="M9.4 13.6h.4M14.2 13.6h.4" />
      <path d="M10.6 17c.5.4 1.3.4 1.8 0" />
    </IconBase>
  )
}

export function MoonIcon(props) {
  return (
    <IconBase {...props}>
      <path d="M16.8 14.2A7.6 7.6 0 0 1 9.3 4.2a8 8 0 1 0 7.5 10Z" />
    </IconBase>
  )
}

export function LeafIcon(props) {
  return (
    <IconBase {...props}>
      <path d="M6 18c-1-5.5 2-11 11-12 1 6.5-2.5 11.5-9 12-1 .1-1.7.1-2 0Z" />
      <path d="M7 17c2-3 4.5-6 9-9" />
    </IconBase>
  )
}

export const PROFILE_ICON_OPTIONS = ['user', 'heart', 'star', 'flower', 'cat', 'dog', 'moon', 'leaf']

const PROFILE_ICON_MAP = {
  user: PersonIcon,
  heart: HeartIcon,
  star: StarIcon,
  flower: FlowerIcon,
  cat: CatIcon,
  dog: DogIcon,
  moon: MoonIcon,
  leaf: LeafIcon,
}

export function normalizeProfileIcon(value) {
  return PROFILE_ICON_MAP[value] ? value : 'user'
}

export function ProfileIcon({ icon, size = 20, color = 'currentColor', ...rest }) {
  const Cmp = PROFILE_ICON_MAP[icon] || PersonIcon
  return <Cmp size={size} color={color} {...rest} />
}

// 작은 UI 아이콘

export function TrashIcon(props) {
  return (
    <IconBase {...props}>
      <path d="M5 7h14" />
      <path d="M9.5 7V5.2c0-.7.5-1.2 1.2-1.2h2.6c.7 0 1.2.5 1.2 1.2V7" />
      <path d="M7.5 7l.7 11.2c.05.9.8 1.6 1.7 1.6h4.2c.9 0 1.65-.7 1.7-1.6L16.5 7" />
      <path d="M10.3 10.5v6M13.7 10.5v6" />
    </IconBase>
  )
}

export function MoreIcon(props) {
  return (
    <IconBase {...props}>
      <circle cx="12" cy="6" r="1.1" fill="currentColor" stroke="none" />
      <circle cx="12" cy="12" r="1.1" fill="currentColor" stroke="none" />
      <circle cx="12" cy="18" r="1.1" fill="currentColor" stroke="none" />
    </IconBase>
  )
}

// 빈 화면 아이콘

export function ChatBubbleIcon(props) {
  return (
    <IconBase {...props}>
      <path d="M4 12.2C4 7.7 7.8 4 12.4 4s8.4 3.7 8.4 8.2-3.8 8.2-8.4 8.2c-1.1 0-2.1-.2-3-.5L5 21l1.3-3.7C4.9 16 4 14.2 4 12.2Z" />
    </IconBase>
  )
}

export function PeopleIcon(props) {
  return (
    <IconBase {...props}>
      <circle cx="9" cy="8.3" r="3" />
      <path d="M3.6 19c0-3 2.4-5.4 5.4-5.4s5.4 2.4 5.4 5.4" />
      <circle cx="16.3" cy="9.2" r="2.3" />
      <path d="M14.2 13.4c2.5.3 4.4 2.3 4.6 5.2" />
    </IconBase>
  )
}

export function NoteIcon(props) {
  return (
    <IconBase {...props}>
      <rect x="5" y="3.5" width="14" height="17" rx="2.6" />
      <path d="M8.3 9h7.4M8.3 12.6h7.4M8.3 16.2h4.4" />
    </IconBase>
  )
}

export function ThoughtBubbleIcon(props) {
  return (
    <IconBase {...props}>
      <path d="M8.3 15.4c-2.3 0-4.1-1.8-4.1-4s1.6-3.7 3.5-4c.5-2.5 2.7-4.4 5.3-4.4 2.7 0 4.9 2 5.3 4.5 2 .2 3.6 1.9 3.6 4s-1.8 4-4.1 4H8.3Z" />
      <circle cx="7" cy="19.2" r="1.1" />
      <circle cx="10.2" cy="21.4" r="0.75" />
    </IconBase>
  )
}
