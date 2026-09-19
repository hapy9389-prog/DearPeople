const BASE = import.meta.env.VITE_API_BASE || '/api'
const DEVICE_KEY_STORAGE = 'dearpeople_device_key'

// 처음 접속할 때 만든 무작위 기기 키. 서버가 기기별로 데이터를 나누는 데 쓴다.
function getDeviceKey() {
  try {
    let key = localStorage.getItem(DEVICE_KEY_STORAGE)
    if (!key) {
      key = crypto.randomUUID()
      localStorage.setItem(DEVICE_KEY_STORAGE, key)
    }
    return key
  } catch (e) {
    return 'local'
  }
}

export async function apiRequest(path, options = {}) {
  const isFormData = options.body instanceof FormData
  const headers = { 'X-Device-Key': getDeviceKey() }
  if (!isFormData) headers['Content-Type'] = 'application/json'
  const res = await fetch(`${BASE}${path}`, { ...options, headers })
  if (!res.ok) {
    // 서버 메시지는 그대로 보여주지 않는다. 원문은 콘솔에만 남긴다.
    try {
      console.error(`${path} ${res.status}`, await res.json())
    } catch (e) {
      // ignore
    }
    throw new Error(res.status === 429 ? '잠시 후 다시 시도해 주세요.' : '다시 시도해 주세요.')
  }
  if (res.status === 204) return null
  return res.json()
}
