import { useState } from 'react'

const TABS = [
  { key: 'chat', label: '채팅' },
  { key: 'people', label: '사람' },
  { key: 'memory', label: '기억' },
]

function App() {
  const [activeTab, setActiveTab] = useState('chat')

  return (
    <div className="app">
      <main className="screen">
        <div className="placeholder">
          {TABS.find((t) => t.key === activeTab)?.label} 화면
        </div>
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
