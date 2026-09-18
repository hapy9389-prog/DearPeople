import { useState, useEffect, useRef } from 'react'
import Onboarding from './Onboarding'
import ChatTab from './ChatTab'
import PeopleTab from './PeopleTab'
import MemoryTab from './MemoryTab'
import ProfileSheet from './ProfileSheet'
import RoomCreateSheet from './RoomCreateSheet'
import { apiRequest } from './api'
import { avatarColor } from './format'
import { ArrowLeftIcon, ChevronDownIcon, PlusIcon, ProfileIcon, normalizeProfileIcon } from './icons'

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
  const [profile, setProfile] = useState({ id: null, name: '', emoji: '🙂' })
  const [profileSheetOpen, setProfileSheetOpen] = useState(false)
  const [roomCreateOpen, setRoomCreateOpen] = useState(false)
  const [profileVersion, setProfileVersion] = useState(0)
  const [autoTickEnabled, setAutoTickEnabled] = useState(() => {
    try { return localStorage.getItem(AUTO_TICK_STORAGE_KEY) === 'true' } catch (e) { return false }
  })
  const [tickVersion, setTickVersion] = useState(0)
  const [animateRoomList, setAnimateRoomList] = useState(false)
  const openRoomRef = useRef(openRoom)
  const autoTickRunningRef = useRef(false)

  function openMemoriesForCharacter(characterId) {
    setMemoryTabCharacterId(characterId)
    setActiveTab('memory')
  }

  function refreshCharacters() {
    apiRequest('/characters').then(setCharacters).catch(() => {})
  }

  function refreshProfile() {
    apiRequest('/profiles').then((d) => {
      const current = d.profiles.find((p) => p.id === d.current_profile_id)
      if (current) setProfile({ id: current.id, name: current.name, emoji: current.emoji })
    }).catch(() => {})
  }

  function applyProfileSwitchCommon() {
    setProfileSheetOpen(false)
    setRoomCreateOpen(false)
    setRoomBadges({})
    setOpenRoom(null)
    setMemoryTabCharacterId(null)
    setActiveTab('chat')
    setProfileVersion((v) => v + 1)
    refreshCharacters()
    refreshProfile()
  }

  function handleProfileSwitched() {
    applyProfileSwitchCommon()
    setPhase('main')
  }

  function handleProfileCreated() {
    applyProfileSwitchCommon()
    setPhase('onboarding')
  }

  function handleTabClick(key) {
    if (key !== 'chat') setOpenRoom(null)
    setActiveTab(key)
  }

  function handleRoomsRegenerated() {
    setAnimateRoomList(true)
  }

  function handleRoomCreated(room) {
    setRoomCreateOpen(false)
    setOpenRoom({ id: room.id, name: room.name, is_custom: true, justCreated: true })
  }

  async function handleDeleteRoom() {
    if (!openRoom) return
    const message = openRoom.is_custom
      ? '이 방과 모든 대화가 삭제됩니다. 계속할까요?'
      : '이 방과 모든 대화가 삭제됩니다. 계속할까요?\n다시 만들기를 해도 이 방은 생기지 않습니다.'
    if (!window.confirm(message)) return
    try {
      await apiRequest(`/rooms/${openRoom.id}`, { method: 'DELETE' })
      setOpenRoom(null)
    } catch (e) {
      window.alert(e.message)
    }
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
    refreshProfile()
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
    return (
      <Onboarding
        onComplete={() => {
          refreshCharacters()
          refreshProfile()
          setAnimateRoomList(true)
          setPhase('main')
          setActiveTab('chat')
        }}
        onExit={handleProfileSwitched}
      />
    )
  }

  return (
    <div className="app">
      <header className="app-header">
        {openRoom ? (
          <>
            <button type="button" className="app-header-back" onClick={() => setOpenRoom(null)}>
              <ArrowLeftIcon size={22} />
            </button>
            <span className="app-header-title">{openRoom.name}</span>
            <button type="button" className="app-header-delete" onClick={handleDeleteRoom}>삭제</button>
          </>
        ) : (
          <>
            <button type="button" className="app-header-profile-button" onClick={() => setProfileSheetOpen(true)}>
              <span className="avatar app-header-avatar" style={{ background: avatarColor(profile.name) }}>
                <ProfileIcon icon={normalizeProfileIcon(profile.emoji)} size={20} color="var(--text)" />
              </span>
              <span className="app-header-brand">
                <span className="app-header-logo">DearPeople</span>
                <span className="app-header-username">
                  {profile.name}
                  <ChevronDownIcon className="app-header-profile-indicator" size={14} />
                </span>
              </span>
            </button>
            {activeTab === 'chat' && (
              <button
                type="button"
                className="app-header-icon-button"
                onClick={() => setRoomCreateOpen(true)}
                aria-label="방 만들기"
              >
                <PlusIcon size={20} />
              </button>
            )}
          </>
        )}
      </header>
      <main className="screen">
        {activeTab === 'chat' && (
          <ChatTab
            key={profileVersion}
            roomBadges={roomBadges}
            setRoomBadges={setRoomBadges}
            characters={characters}
            openRoom={openRoom}
            setOpenRoom={setOpenRoom}
            autoTickEnabled={autoTickEnabled}
            onToggleAutoTick={toggleAutoTick}
            tickVersion={tickVersion}
            animateRoomList={animateRoomList}
            onRoomListAnimated={() => setAnimateRoomList(false)}
            onOpenRoomCreate={() => setRoomCreateOpen(true)}
          />
        )}
        {activeTab === 'people' && (
          <PeopleTab
            key={profileVersion}
            profile={profile}
            onOpenMemories={openMemoriesForCharacter}
            onCharactersChanged={refreshCharacters}
            onRoomsRegenerated={handleRoomsRegenerated}
          />
        )}
        {activeTab === 'memory' && (
          <MemoryTab
            key={profileVersion}
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
      {profileSheetOpen && (
        <ProfileSheet
          onClose={() => setProfileSheetOpen(false)}
          onSwitched={handleProfileSwitched}
          onCreated={handleProfileCreated}
          onCleared={handleProfileCreated}
        />
      )}
      {roomCreateOpen && (
        <RoomCreateSheet
          characters={characters}
          onClose={() => setRoomCreateOpen(false)}
          onCreated={handleRoomCreated}
        />
      )}
    </div>
  )
}

export default App
