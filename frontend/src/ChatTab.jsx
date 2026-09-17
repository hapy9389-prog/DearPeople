import { useState, useEffect } from 'react'
import { apiRequest } from './api'

function ChatTab() {
  const [rooms, setRooms] = useState([])
  const [error, setError] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    apiRequest('/rooms')
      .then(setRooms)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false))
  }, [])

  if (loading) return <div className="placeholder">불러오는 중...</div>
  if (error) return <div className="error-banner">{error}</div>

  return (
    <ul className="room-list">
      {rooms.map((room) => (
        <li key={room.id} className="room-item">
          <div className="room-item-header">
            <span className="room-item-name">{room.name}</span>
            {!room.includes_me && <span className="room-item-badge">엿보기</span>}
          </div>
          <div className="room-item-last">
            {room.last_message
              ? `${room.last_message.sender}: ${room.last_message.content}`
              : '대화 없음'}
          </div>
        </li>
      ))}
    </ul>
  )
}

export default ChatTab
