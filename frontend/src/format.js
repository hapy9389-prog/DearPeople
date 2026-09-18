const KST = 'Asia/Seoul'

function toDate(createdAt) {
  if (!createdAt) return new Date()
  return new Date(createdAt.replace(' ', 'T') + 'Z')
}

export function kstDateKey(createdAt) {
  return new Intl.DateTimeFormat('en-CA', { timeZone: KST }).format(toDate(createdAt))
}

export function kstMinuteKey(createdAt) {
  return new Intl.DateTimeFormat('en-GB', {
    timeZone: KST, hour: '2-digit', minute: '2-digit', hour12: false,
  }).format(toDate(createdAt))
}

export function formatTime(createdAt) {
  return new Intl.DateTimeFormat('ko-KR', {
    timeZone: KST, hour: 'numeric', minute: '2-digit', hour12: true,
  }).format(toDate(createdAt))
}

export function formatDateDivider(createdAt) {
  if (kstDateKey(createdAt) === kstDateKey(null)) return '오늘'
  return new Intl.DateTimeFormat('ko-KR', {
    timeZone: KST, year: 'numeric', month: 'long', day: 'numeric', weekday: 'long',
  }).format(toDate(createdAt))
}

const RELATION_EMOJI = { '엄마': '👩', '아빠': '👨', '형제자매': '🧒', '친구': '🧑' }
export function relationEmoji(relation) {
  return RELATION_EMOJI[relation] || '🙂'
}

const AVATAR_PALETTE = ['#FADADD', '#FDE7C8', '#FFF3B0', '#D7F0D1', '#CDE7F0', '#D9D3F0', '#F0D9E8', '#E4D6C4']
export function avatarColor(name) {
  let hash = 0
  for (let i = 0; i < (name || '').length; i++) hash += name.charCodeAt(i)
  return AVATAR_PALETTE[hash % AVATAR_PALETTE.length]
}
