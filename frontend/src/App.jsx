import { useState, useEffect, useRef } from 'react'
import Onboarding from './Onboarding'
import ChatTab from './ChatTab'
import PeopleTab from './PeopleTab'
import MemoryTab from './MemoryTab'
import { apiRequest } from './api'

const TABS = [
  { key: 'chat', label: '채팅' },
  { key: 'people', label: '사람' },
  { key: 'memory', label: '기억' },
]

const AUTO_TICK_STORAGE_KEY = 'dearpeople_auto_tick_enabled'
const LAST_AUTO_TICK_KEY = 'dearpeople_last_auto_tick_at'
const AUTO_TICK_INTERVAL_MS = 3 * 60 * 1000
const AUTO_TICK_MIN_GAP_MS = 60 * 1000

function App() {
  const [phase, setPhase] = useState('loading')
  const [activeTab, setActiveTab] = useState('chat')
  const [roomBadges, setRoomBadges] = useState({})
  const [memoryTabCharacterId, setMemoryTabCharacterId] = useState(null)
  const [characters, setCharacters] = useState([])
  const [openRoom, setOpenRoom] = useState(null)
  const [myName, setMyName] = useState('나')
  const [autoTickEnabled, setAutoTickEnabled] = useState(() => {
    try { return localStorage.getItem(AUTO_TICK_STORAGE_KEY) === 'true' } catch (e) { return false }
  })
  const [tickVersion, setTickVersion] = useState(0)
  const openRoomRef = useRef(openRoom)
  const autoTickRunningRef = useRef(false)

  function openMemoriesForCharacter(characterId) {
    setMemoryTabCharacterId(characterId)
    setActiveTab('memory')
  }

  function handleTabClick(key) {
    if (key !== 'chat') setOpenRoom(null)
    setActiveTab(key)
  }

  function toggleAutoTick(enabled) {
    setAutoTickEnabled(enabled)
    try { localStorage.setItem(AUTO_TICK_STORAGE_KEY, String(enabled)) } catch (e) { /* ignore */ }
  }

  async function runAutoTick() {
    if (autoTickRunningRef.current || openRoomRef.current) return
    autoTickRunningRef.current = true
    try {
      const res = await apiRequest('/tick', { method: 'POST' })
      setRoomBadges((prev) => {
        const next = { ...prev }
        for (const [roomId, count] of Object.entries(res.counts)) {
          next[roomId] = (next[roomId] || 0) + count
        }
        return next
      })
      try { localStorage.setItem(LAST_AUTO_TICK_KEY, String(Date.now())) } catch (e) { /* ignore */ }
      setTickVersion((v) => v + 1)
    } catch (e) {
      // 자동 호출 실패는 화면에 방해되지 않게 조용히 무시한다.
    } finally {
      autoTickRunningRef.current = false
    }
  }

  useEffect(() => {
    apiRequest('/rooms')
      .then((rooms) => setPhase(rooms.length === 0 ? 'onboarding' : 'main'))
      .catch(() => setPhase('main'))
    apiRequest('/characters').then(setCharacters).catch(() => {})
    apiRequest('/settings/me').then((d) => setMyName(d.name)).catch(() => {})
  }, [])

  useEffect(() => {
    openRoomRef.current = openRoom
  }, [openRoom])

  useEffect(() => {
    if (!autoTickEnabled) return
    let lastAt = 0
    try { lastAt = Number(localStorage.getItem(LAST_AUTO_TICK_KEY)) || 0 } catch (e) { /* ignore */ }
    if (Date.now() - lastAt >= AUTO_TICK_MIN_GAP_MS) runAutoTick()
    const intervalId = setInterval(runAutoTick, AUTO_TICK_INTERVAL_MS)
    return () => clearInterval(intervalId)
  }, [autoTickEnabled])

  if (phase === 'loading') {
    return (
      <div className="app">
        <main className="screen">
          <div className="placeholder">불러오는 중...</div>
        </main>
      </div>
    )
  }

  if (phase === 'onboarding') {
    return <Onboarding onComplete={() => { setPhase('main'); setActiveTab('chat') }} />
  }

  return (
    <div className="app">
      <header className="app-header">
        {openRoom ? (
          <>
            <button type="button" className="app-header-back" onClick={() => setOpenRoom(null)}>‹</button>
            <span className="app-header-title">{openRoom.name}</span>
          </>
        ) : (
          <div className="app-header-brand">
            <span className="app-header-logo">DearPeople</span>
            <span className="app-header-username">{myName}</span>
          </div>
        )}
      </header>
      <main className="screen">
        {activeTab === 'chat' && (
          <ChatTab
            roomBadges={roomBadges}
            setRoomBadges={setRoomBadges}
            characters={characters}
            openRoom={openRoom}
            setOpenRoom={setOpenRoom}
            autoTickEnabled={autoTickEnabled}
            onToggleAutoTick={toggleAutoTick}
            tickVersion={tickVersion}
          />
        )}
        {activeTab === 'people' && <PeopleTab onOpenMemories={openMemoriesForCharacter} />}
        {activeTab === 'memory' && (
          <MemoryTab
            selectedCharacterId={memoryTabCharacterId}
            onSelectCharacter={setMemoryTabCharacterId}
          />
        )}
      </main>
      <nav className="tab-bar">
        {TABS.map((tab) => (
          <button
            key={tab.key}
            type="button"
            className={`tab${activeTab === tab.key ? ' active' : ''}`}
            onClick={() => handleTabClick(tab.key)}
          >
            {tab.label}
          </button>
        ))}
      </nav>
    </div>
  )
}

export default App
