import { useState } from 'react'
import { apiRequest } from './api'

function RoomCreateSheet({ characters, onClose, onCreated }) {
  const [name, setName] = useState('')
  const [selectedIds, setSelectedIds] = useState([])
  const [includesMe, setIncludesMe] = useState(true)
  const [creating, setCreating] = useState(false)
  const [error, setError] = useState(null)

  function toggleMember(id) {
    setSelectedIds((prev) => (prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]))
  }

  async function handleCreate() {
    if (selectedIds.length === 0 || creating) return
    setCreating(true)
    setError(null)
    try {
      const room = await apiRequest('/rooms', {
        method: 'POST',
        body: JSON.stringify({ name: name.trim(), member_ids: selectedIds, includes_me: includesMe }),
      })
      onCreated(room)
    } catch (e) {
      setError(e.message)
      setCreating(false)
    }
  }

  return (
    <div className="room-sheet-backdrop" onClick={onClose}>
      <div className="room-sheet" onClick={(e) => e.stopPropagation()}>
        <div className="room-sheet-handle" />
        <h2 className="room-sheet-title">방 만들기</h2>
        {error && <div className="error-banner">{error}</div>}

        <div className="field">
          <label>방 이름</label>
          <input
            type="text"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="비워두면 멤버 이름으로 자동 지정됩니다"
          />
        </div>

        <div className="field">
          <label>멤버 선택</label>
          <ul className="room-sheet-member-list">
            {characters.map((c) => (
              <li key={c.id} className="room-sheet-member-item">
                <label className="room-sheet-member-label">
                  <input
                    type="checkbox"
                    checked={selectedIds.includes(c.id)}
                    onChange={() => toggleMember(c.id)}
                  />
                  <span>{c.name}</span>
                  <span className="room-sheet-member-relation">{c.relation}</span>
                </label>
              </li>
            ))}
          </ul>
        </div>

        <label className="room-sheet-includes-me">
          <input type="checkbox" checked={includesMe} onChange={(e) => setIncludesMe(e.target.checked)} />
          <span>내가 참여하는 방</span>
        </label>

        <button
          type="button"
          className="btn-primary room-sheet-submit"
          onClick={handleCreate}
          disabled={selectedIds.length === 0 || creating}
        >
          {creating ? '만드는 중...' : '방 만들기'}
        </button>
      </div>
    </div>
  )
}

export default RoomCreateSheet
