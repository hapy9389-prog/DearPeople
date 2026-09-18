import { useState, useEffect } from 'react'
import { apiRequest } from './api'

function PeopleTab({ onOpenMemories }) {
  const [characters, setCharacters] = useState([])
  const [memoryCounts, setMemoryCounts] = useState({})
  const [expandedId, setExpandedId] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    apiRequest('/characters')
      .then(async (chars) => {
        if (cancelled) return
        setCharacters(chars)
        const counts = {}
        await Promise.all(chars.map(async (c) => {
          const memories = await apiRequest(`/characters/${c.id}/memories`)
          counts[c.id] = memories.length
        }))
        if (!cancelled) setMemoryCounts(counts)
      })
      .catch((e) => { if (!cancelled) setError(e.message) })
      .finally(() => { if (!cancelled) setLoading(false) })
    return () => { cancelled = true }
  }, [])

  if (loading) return <div className="placeholder">불러오는 중...</div>
  if (error) return <div className="error-banner">{error}</div>

  return (
    <div className="people-tab">
      <ul className="people-list">
        {characters.map((c) => (
          <li key={c.id} className="people-item">
            <div
              className="people-item-header"
              onClick={() => setExpandedId(expandedId === c.id ? null : c.id)}
            >
              <div className="people-item-main">
                <span className="people-item-name">{c.name}</span>
                <span className="people-item-relation">{c.relation}</span>
              </div>
              <div className="people-item-personality">{c.personality}</div>
              <button
                type="button"
                className="people-item-memory-count"
                onClick={(e) => { e.stopPropagation(); onOpenMemories(c.id) }}
              >
                기억 {memoryCounts[c.id] ?? 0}개
              </button>
            </div>
            {expandedId === c.id && (
              <div className="people-item-detail">
                <div><strong>성격</strong> {c.personality}</div>
                <div><strong>말투</strong> {c.speech_style}</div>
                <div><strong>나를 부르는 호칭</strong> {c.calls_me}</div>
              </div>
            )}
          </li>
        ))}
      </ul>
    </div>
  )
}

export default PeopleTab
