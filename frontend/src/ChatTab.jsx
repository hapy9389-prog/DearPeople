import { useState, useEffect, useRef } from 'react'
import { apiRequest } from './api'
import { relationEmoji, avatarColor, formatTime } from './format'
import ChatRoom from './ChatRoom'

function ChatTab({ roomBadges, setRoomBadges, characters, openRoom, setOpenRoom }) {
  const [rooms, setRooms] = useState([])
  const [error, setError] = useState(null)
  const [loading, setLoading] = useState(true)
  const [ticking, setTicking] = useState(false)
  const [tickError, setTickError] = useState(null)
  const prevOpenRoomIdRef = useRef(null)

  const relationByName = Object.fromEntries(characters.map((c) => [c.name, c.relation]))

  function loadRooms(silent = false) {
    if (!silent) setLoading(true)
    apiRequest('/rooms')
      .then(setRooms)
      .catch((e) => setError(e.message))
      .finally(() => {
        if (!silent) setLoading(false)
      })
  }

  useEffect(() => {
    loadRooms()
  }, [])

  useEffect(() => {
    if (prevOpenRoomIdRef.current !== null && openRoom === null) loadRooms(true)
    prevOpenRoomIdRef.current = openRoom ? openRoom.id : null
  }, [openRoom])

  function handleEnterRoom(room) {
    setOpenRoom({ id: room.id, name: room.name })
    setRoomBadges((prev) => {
      if (!(room.id in prev)) return prev
      const next = { ...prev }
      delete next[room.id]
      return next
    })
  }

  async function handleTick() {
    setTicking(true)
    setTickError(null)
    try {
      const res = await apiRequest('/tick', { method: 'POST' })
      setRoomBadges((prev) => {
        const next = { ...prev }
        for (const [roomId, count] of Object.entries(res.counts)) {
          next[roomId] = (next[roomId] || 0) + count
        }
        return next
      })
      loadRooms(true) // 조용히 갱신 (버튼/목록 깜빡임 방지)
    } catch (e) {
      setTickError(e.message)
    } finally {
      setTicking(false)
    }
  }

  if (openRoom !== null) {
    return (
      <ChatRoom roomId={openRoom.id} characters={characters} />
    )
  }

  if (loading) return <div className="placeholder">불러오는 중...</div>
  if (error) return <div className="error-banner">{error}</div>

  return (
    <div className="chat-tab">
      <button type="button" className="btn-primary tick-button" onClick={handleTick} disabled={ticking}>
        {ticking ? '시간이 흐르는 중...' : '시간 흐르기'}
      </button>
      {tickError && <div className="error-banner">{tickError}</div>}
      <ul className="room-list">
        {rooms.map((room) => (
          <li
            key={room.id}
            className={`room-item${!room.includes_me ? ' room-item-peek' : ''}`}
            onClick={() => handleEnterRoom(room)}
          >
            <div className="room-item-avatars">
              {room.members.slice(0, 3).map((name, idx) => (
                <div key={name + idx} className="avatar avatar-small" style={{ background: avatarColor(name) }}>
                  {relationEmoji(relationByName[name])}
                </div>
              ))}
            </div>
            <div className="room-item-body">
              <span className="room-item-name">{room.name}</span>
              <div className="room-item-last">
                {room.last_message
                  ? `${room.last_message.sender}: ${room.last_message.content}`
                  : '대화 없음'}
              </div>
            </div>
            <div className="room-item-meta">
              {room.last_message && (
                <span className="room-item-time">{formatTime(room.last_message.created_at)}</span>
              )}
              {!room.includes_me && <span className="room-item-badge">엿보기</span>}
              {roomBadges[room.id] > 0 && (
                <span className="room-item-new-badge">{roomBadges[room.id]}</span>
              )}
            </div>
          </li>
        ))}
      </ul>
    </div>
  )
}

export default ChatTab
