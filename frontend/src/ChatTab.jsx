import { useState, useEffect, useRef } from 'react'
import { apiRequest } from './api'
import { relationEmoji, avatarColor, formatTime } from './format'
import ChatRoom from './ChatRoom'
import RoomCreateSheet from './RoomCreateSheet'

function ChatTab({
  roomBadges, setRoomBadges, characters, openRoom, setOpenRoom,
  autoTickEnabled, onToggleAutoTick, tickVersion,
  animateRoomList, onRoomListAnimated,
}) {
  const [rooms, setRooms] = useState([])
  const [error, setError] = useState(null)
  const [loading, setLoading] = useState(true)
  const [ticking, setTicking] = useState(false)
  const [tickError, setTickError] = useState(null)
  const [roomCreateOpen, setRoomCreateOpen] = useState(false)
  const prevOpenRoomIdRef = useRef(null)
  const prevTickVersionRef = useRef(tickVersion)
  // 이 마운트 시점의 값만 캡처한다 — 이후 부모 상태가 바뀌어도 이번 렌더의 애니메이션 여부는 그대로 유지.
  const [shouldAnimateRooms] = useState(() => animateRoomList)

  useEffect(() => {
    if (animateRoomList) onRoomListAnimated()
  }, [])

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

  useEffect(() => {
    if (tickVersion !== prevTickVersionRef.current) {
      loadRooms(true) // 자동 시간 흐르기 결과 반영 (깜빡임 없이 조용히 갱신)
      prevTickVersionRef.current = tickVersion
    }
  }, [tickVersion])

  function handleEnterRoom(room) {
    setOpenRoom({ id: room.id, name: room.name, is_custom: room.is_custom })
    setRoomBadges((prev) => {
      if (!(room.id in prev)) return prev
      const next = { ...prev }
      delete next[room.id]
      return next
    })
  }

  function handleRoomCreated(room) {
    setRoomCreateOpen(false)
    setOpenRoom({ id: room.id, name: room.name, is_custom: true, justCreated: true })
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
      <ChatRoom roomId={openRoom.id} characters={characters} animateFirst={!!openRoom.justCreated} />
    )
  }

  if (loading) return <div className="placeholder">불러오는 중...</div>
  if (error) return <div className="error-banner">{error}</div>

  return (
    <div className="chat-tab">
      <div className="tick-row">
        <label className="auto-tick-toggle">
          <input
            type="checkbox"
            checked={autoTickEnabled}
            onChange={(e) => onToggleAutoTick(e.target.checked)}
          />
          <span className="auto-tick-switch" />
          <span>자동 시간 흐르기</span>
        </label>
        <button type="button" className="btn-primary tick-button" onClick={handleTick} disabled={ticking}>
          {ticking ? '시간이 흐르는 중...' : '시간 흐르기'}
        </button>
      </div>
      <div className="tick-hint">
        {autoTickEnabled
          ? '대화가 자동으로 이어지는 중입니다.'
          : '자동 시간 흐르기를 켜면 대화가 계속 이어집니다.'}
      </div>
      <div className="room-create-bar">
        <button type="button" className="btn-primary" onClick={() => setRoomCreateOpen(true)}>방 만들기</button>
      </div>
      {roomCreateOpen && (
        <RoomCreateSheet
          characters={characters}
          onClose={() => setRoomCreateOpen(false)}
          onCreated={handleRoomCreated}
        />
      )}
      {tickError && <div className="error-banner">{tickError}</div>}
      <ul className="room-list">
        {rooms.map((room, roomIdx) => (
          <li
            key={room.id}
            className={`room-item${!room.includes_me ? ' room-item-peek' : ''}${shouldAnimateRooms ? ' room-item-enter' : ''}`}
            style={shouldAnimateRooms ? { animationDelay: `${roomIdx * 0.15}s` } : undefined}
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
                  ? `${room.last_message.sender}: ${room.last_message.type === 'photo' ? '사진' : room.last_message.content}`
                  : '대화 없음'}
              </div>
            </div>
            <div className="room-item-meta">
              {room.last_message && (
                <span className="room-item-time">{formatTime(room.last_message.created_at)}</span>
              )}
              {!room.includes_me && <span className="room-item-badge">엿보기</span>}
              {room.is_custom && <span className="room-item-badge">직접 생성</span>}
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
