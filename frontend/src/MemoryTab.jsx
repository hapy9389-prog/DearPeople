import { useState, useEffect } from 'react'
import { apiRequest } from './api'

function MemoryTab({ selectedCharacterId, onSelectCharacter }) {
  const [characters, setCharacters] = useState([])
  const [memories, setMemories] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [editingId, setEditingId] = useState(null)
  const [editingText, setEditingText] = useState('')
  const [newMemoryText, setNewMemoryText] = useState('')
  const [toast, setToast] = useState(null)

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
    if (selectedCharacterId === null) return
    setLoading(true)
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

  return (
    <div className="memory-tab">
      <div className="field">
        <label>사람 선택</label>
        <select
          value={selectedCharacterId ?? ''}
          onChange={(e) => onSelectCharacter(Number(e.target.value))}
        >
          {characters.map((c) => (
            <option key={c.id} value={c.id}>{c.name}</option>
          ))}
        </select>
      </div>

      {error && <div className="error-banner">{error}</div>}
      {toast && <div className="toast">{toast}</div>}

      {loading ? (
        <div className="placeholder">불러오는 중...</div>
      ) : (
        <ul className="memory-card-list">
          {memories.map((m) => (
            <li key={m.id} className="memory-card">
              {editingId === m.id ? (
                <>
                  <input
                    type="text"
                    value={editingText}
                    onChange={(e) => setEditingText(e.target.value)}
                  />
                  <div className="memory-card-actions">
                    <button type="button" onClick={() => handleSaveEdit(m.id)}>저장</button>
                    <button type="button" onClick={() => setEditingId(null)}>취소</button>
                  </div>
                </>
              ) : (
                <>
                  <div className="memory-card-content">{m.content}</div>
                  <div className="memory-card-actions">
                    <button type="button" onClick={() => { setEditingId(m.id); setEditingText(m.content) }}>수정</button>
                    <button type="button" onClick={() => handleDelete(m.id)}>삭제</button>
                  </div>
                </>
              )}
            </li>
          ))}
        </ul>
      )}

      <div className="memory-add-bar">
        <textarea
          rows={3}
          value={newMemoryText}
          onChange={(e) => setNewMemoryText(e.target.value)}
          placeholder="새 기억 추가"
        />
        <button type="button" className="btn-primary" onClick={handleAdd} disabled={!newMemoryText.trim()}>
          추가
        </button>
      </div>
    </div>
  )
}

export default MemoryTab
