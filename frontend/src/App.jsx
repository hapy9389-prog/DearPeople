import { useState, useEffect } from 'react'
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

function App() {
  const [phase, setPhase] = useState('loading')
  const [activeTab, setActiveTab] = useState('chat')
  const [roomBadges, setRoomBadges] = useState({})
  const [memoryTabCharacterId, setMemoryTabCharacterId] = useState(null)
  const [characters, setCharacters] = useState([])
  const [openRoom, setOpenRoom] = useState(null)
  const [myName, setMyName] = useState('나')

  function openMemoriesForCharacter(characterId) {
    setMemoryTabCharacterId(characterId)
    setActiveTab('memory')
  }

  function handleTabClick(key) {
    if (key !== 'chat') setOpenRoom(null)
    setActiveTab(key)
  }

  useEffect(() => {
    apiRequest('/rooms')
      .then((rooms) => setPhase(rooms.length === 0 ? 'onboarding' : 'main'))
      .catch(() => setPhase('main'))
    apiRequest('/characters').then(setCharacters).catch(() => {})
    apiRequest('/settings/me').then((d) => setMyName(d.name)).catch(() => {})
  }, [])

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
