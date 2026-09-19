import { useState, useEffect } from 'react'
import { apiRequest } from './api'
import { avatarColor } from './format'
import { NoteIcon, AvatarInitial, MoreIcon, PlusIcon } from './icons'

function MemoryTab({ selectedCharacterId, onSelectCharacter }) {
  const [characters, setCharacters] = useState([])
  const [memories, setMemories] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [editingId, setEditingId] = useState(null)
  const [editingText, setEditingText] = useState('')
  const [menuOpenId, setMenuOpenId] = useState(null)
  const [newMemoryText, setNewMemoryText] = useState('')
  const [toast, setToast] = useState(null)
  const [suggestions, setSuggestions] = useState([])
  const [finding, setFinding] = useState(false)

  useEffect(() => {
    apiRequest('/characters')
      .then((chars) => {
        setCharacters(chars)
        if (selectedCharacterId === null && chars.length > 0) {
          onSelectCharacter(chars[0].id)
        }
      })
      .catch((e) => setError(e.message))
  }, [])

  useEffect(() => {
    apiRequest('/memories/suggestions')
      .then(setSuggestions)
      .catch((e) => setError(e.message))
  }, [])

  useEffect(() => {
    if (selectedCharacterId === null) return
    setLoading(true)
    setEditingId(null)
    setMenuOpenId(null)
    apiRequest(`/characters/${selectedCharacterId}/memories`)
      .then(setMemories)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false))
  }, [selectedCharacterId])

  function showToast() {
    setToast('다음 대화부터 반영됩니다')
    setTimeout(() => setToast(null), 2000)
  }

  async function handleAdd() {
    const content = newMemoryText.trim()
    if (!content) return
    try {
      const created = await apiRequest(`/characters/${selectedCharacterId}/memories`, {
        method: 'POST',
        body: JSON.stringify({ content }),
      })
      setMemories((prev) => [...prev, created])
      setNewMemoryText('')
      showToast()
    } catch (e) {
      setError(e.message)
    }
  }

  async function handleSaveEdit(memoryId) {
    const content = editingText.trim()
    if (!content) return
    try {
      await apiRequest(`/memories/${memoryId}`, {
        method: 'PUT',
        body: JSON.stringify({ content }),
      })
      setMemories((prev) => prev.map((m) => (m.id === memoryId ? { ...m, content } : m)))
      setEditingId(null)
      showToast()
    } catch (e) {
      setError(e.message)
    }
  }

  async function handleDelete(memoryId) {
    try {
      await apiRequest(`/memories/${memoryId}`, { method: 'DELETE' })
      setMemories((prev) => prev.filter((m) => m.id !== memoryId))
      showToast()
    } catch (e) {
      setError(e.message)
    }
  }

  async function handleFindSuggestions() {
    setFinding(true)
    try {
      const created = await apiRequest('/memories/suggest', { method: 'POST' })
      setSuggestions((prev) => [...prev, ...created])
    } catch (e) {
      setError(e.message)
    } finally {
      setFinding(false)
    }
  }

  function handleSuggestionEdit(id, value) {
    setSuggestions((prev) => prev.map((s) => (s.id === id ? { ...s, content: value } : s)))
  }

  async function handleAcceptSuggestion(suggestion) {
    const content = suggestion.content.trim()
    if (!content) return
    try {
      const memory = await apiRequest(`/memories/suggestions/${suggestion.id}/accept`, {
        method: 'POST',
        body: JSON.stringify({ content }),
      })
      setSuggestions((prev) => prev.filter((s) => s.id !== suggestion.id))
      if (suggestion.character_id === selectedCharacterId) {
        setMemories((prev) => [...prev, memory])
      }
      showToast()
    } catch (e) {
      setError(e.message)
    }
  }

  async function handleRejectSuggestion(id) {
    try {
      await apiRequest(`/memories/suggestions/${id}/reject`, { method: 'POST' })
      setSuggestions((prev) => prev.filter((s) => s.id !== id))
    } catch (e) {
      setError(e.message)
    }
  }

  return (
    <div className="memory-tab">
      <div className="memory-character-strip">
        {characters.map((c) => (
          <button
            key={c.id}
            type="button"
            className={`memory-character-chip${c.id === selectedCharacterId ? ' memory-character-chip-active' : ''}`}
            onClick={() => onSelectCharacter(c.id)}
          >
            <span className="avatar avatar-small memory-character-avatar" style={{ background: avatarColor(c.name) }}>
              <AvatarInitial name={c.name} size={32} />
            </span>
            <span className="memory-character-chip-name">{c.name}</span>
          </button>
        ))}
      </div>

      <div className="memory-suggest-bar">
        <button
          type="button"
          className="memory-suggest-button"
          onClick={handleFindSuggestions}
          disabled={finding}
        >
          {finding ? '최근 대화를 읽는 중... (최대 30초)' : '대화에서 찾기'}
        </button>
      </div>

      <div className="memory-tab-body">
        {error && <div className="error-banner">{error}</div>}
        {toast && <div className="toast">{toast}</div>}

        {suggestions.length > 0 && (
          <ul className="memory-suggestion-list">
            {suggestions.map((s) => (
              <li key={s.id} className="memory-suggestion-card">
                <div className="memory-suggestion-character">{s.character_name}</div>
                <textarea
                  className="memory-suggestion-content"
                  rows={2}
                  value={s.content}
                  onChange={(e) => handleSuggestionEdit(s.id, e.target.value)}
                />
                <div className="character-form-actions">
                  <button type="button" className="btn-primary" onClick={() => handleAcceptSuggestion(s)}>
                    추가
                  </button>
                  <button
                    type="button"
                    className="character-form-secondary-button"
                    onClick={() => handleRejectSuggestion(s.id)}
                  >
                    무시
                  </button>
                </div>
              </li>
            ))}
          </ul>
        )}

        {loading ? (
          <div className="placeholder">불러오는 중...</div>
        ) : memories.length === 0 ? (
          <div className="empty-state">
            <NoteIcon className="empty-state-icon" size={48} />
            <div className="empty-state-text">이 사람에 대한 기억이 아직 없어요</div>
          </div>
        ) : (
          <ul className="memory-card-list">
            {memories.map((m) => (
              <li key={m.id} className="memory-card">
                {editingId === m.id ? (
                  <div className="memory-card-edit">
                    <input
                      type="text"
                      value={editingText}
                      onChange={(e) => setEditingText(e.target.value)}
                    />
                    <div className="memory-card-edit-actions">
                      <button type="button" className="btn-primary" onClick={() => handleSaveEdit(m.id)}>저장</button>
                      <button type="button" className="memory-card-cancel" onClick={() => setEditingId(null)}>취소</button>
                    </div>
                  </div>
                ) : (
                  <>
                    <div className="memory-card-content">{m.content}</div>
                    <div className="memory-card-menu-wrap">
                      <button
                        type="button"
                        className="memory-card-more"
                        onClick={() => setMenuOpenId(menuOpenId === m.id ? null : m.id)}
                        aria-label="더보기"
                      >
                        <MoreIcon size={16} />
                      </button>
                      {menuOpenId === m.id && (
                        <div className="memory-card-menu">
                          <button
                            type="button"
                            onClick={() => { setEditingId(m.id); setEditingText(m.content); setMenuOpenId(null) }}
                          >
                            수정
                          </button>
                          <button type="button" onClick={() => { handleDelete(m.id); setMenuOpenId(null) }}>삭제</button>
                        </div>
                      )}
                    </div>
                  </>
                )}
              </li>
            ))}
          </ul>
        )}
      </div>

      <div className="memory-add-bar">
        <div className="memory-add-input-wrap">
          <textarea
            rows={2}
            value={newMemoryText}
            onChange={(e) => setNewMemoryText(e.target.value)}
            placeholder="새 기억 추가"
          />
          <button
            type="button"
            className="memory-add-submit"
            onClick={handleAdd}
            disabled={!newMemoryText.trim()}
            aria-label="추가"
          >
            <PlusIcon size={16} />
          </button>
        </div>
      </div>
    </div>
  )
}

export default MemoryTab
