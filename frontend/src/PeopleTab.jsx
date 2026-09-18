import { useState, useEffect } from 'react'
import { apiRequest } from './api'
import CharacterForm from './CharacterForm'
import RelationshipDiagram from './RelationshipDiagram'

function PeopleTab({ profile, onOpenMemories, onCharactersChanged }) {
  const [characters, setCharacters] = useState([])
  const [memoryCounts, setMemoryCounts] = useState({})
  const [expandedId, setExpandedId] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [addingCharacter, setAddingCharacter] = useState(false)
  const [needsRoomRegen, setNeedsRoomRegen] = useState(false)
  const [regenerating, setRegenerating] = useState(false)
  const [regenerateError, setRegenerateError] = useState(null)

  function loadCharacters() {
    setLoading(true)
    apiRequest('/characters')
      .then(async (chars) => {
        setCharacters(chars)
        const counts = {}
        await Promise.all(chars.map(async (c) => {
          const memories = await apiRequest(`/characters/${c.id}/memories`)
          counts[c.id] = memories.length
        }))
        setMemoryCounts(counts)
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    loadCharacters()
  }, [])

  function handleCharacterSaved() {
    setAddingCharacter(false)
    setNeedsRoomRegen(true)
    loadCharacters()
    onCharactersChanged()
  }

  async function handleRegenerateRooms() {
    setRegenerating(true)
    setRegenerateError(null)
    try {
      await apiRequest('/rooms/generate', { method: 'POST' })
      setNeedsRoomRegen(false)
    } catch (e) {
      setRegenerateError(e.message)
    } finally {
      setRegenerating(false)
    }
  }

  if (loading) return <div className="placeholder">불러오는 중...</div>
  if (error) return <div className="error-banner">{error}</div>

  return (
    <div className="people-tab">
      <div className="people-top-bar">
        <button type="button" className="btn-primary" onClick={() => setAddingCharacter((v) => !v)}>
          {addingCharacter ? '취소' : '캐릭터 추가'}
        </button>
      </div>

      {addingCharacter && (
        <div className="people-add-form">
          <CharacterForm onSaved={handleCharacterSaved} />
        </div>
      )}

      {needsRoomRegen && (
        <div className="people-regen-banner">
          <div>방을 다시 만들어야 새 캐릭터가 대화에 참여합니다. 기존 대화는 모두 지워집니다.</div>
          {regenerateError && <div className="error-banner">{regenerateError}</div>}
          <button type="button" className="btn-primary" onClick={handleRegenerateRooms} disabled={regenerating}>
            {regenerating ? '방 만드는 중...' : '방 다시 만들기'}
          </button>
        </div>
      )}

      {characters.length > 0 && (
        <RelationshipDiagram profile={profile} characters={characters} onOpenMemories={onOpenMemories} />
      )}

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
