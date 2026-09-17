const BASE = '/api'

export async function apiRequest(path, options = {}) {
  const res = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  })
  if (!res.ok) {
    let detail = '요청에 실패했습니다.'
    try {
      const body = await res.json()
      if (body && body.detail) detail = body.detail
    } catch (e) {
      // ignore
    }
    throw new Error(detail)
  }
  if (res.status === 204) return null
  return res.json()
}
