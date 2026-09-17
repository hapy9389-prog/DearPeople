import { useState, useEffect } from 'react'
import Onboarding from './Onboarding'
import ChatTab from './ChatTab'
import { apiRequest } from './api'

const TABS = [
  { key: 'chat', label: '채팅' },
  { key: 'people', label: '사람' },
  { key: 'memory', label: '기억' },
]

function App() {
  const [phase, setPhase] = useState('loading')
  const [activeTab, setActiveTab] = useState('chat')

  useEffect(() => {
    apiRequest('/rooms')
      .then((rooms) => setPhase(rooms.length === 0 ? 'onboarding' : 'main'))
      .catch(() => setPhase('main'))
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
      <main className="screen">
        {activeTab === 'chat' && <ChatTab />}
        {activeTab === 'people' && <div className="placeholder">사람 화면</div>}
        {activeTab === 'memory' && <div className="placeholder">기억 화면</div>}
      </main>
      <nav className="tab-bar">
        {TABS.map((tab) => (
          <button
            key={tab.key}
            type="button"
            className={`tab${activeTab === tab.key ? ' active' : ''}`}
            onClick={() => setActiveTab(tab.key)}
          >
            {tab.label}
          </button>
        ))}
      </nav>
    </div>
  )
}

export default App
