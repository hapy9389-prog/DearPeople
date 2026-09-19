import { useState, useEffect, useRef } from 'react'
import { apiRequest } from './api'
import { avatarColor, formatTime } from './format'
import { AvatarInitial, ChatBubbleIcon } from './icons'
import ChatRoom from './ChatRoom'

const CLUSTER_POSITIONS = {
  1: [{ left: 12, top: 12 }],
  2: [{ left: 4, top: 4 }, { left: 16, top: 16 }],
  3: [{ left: 12, top: 1 }, { left: 5, top: 17 }, { left: 19, top: 17 }],
}

function ChatTab({
  roomBadges, setRoomBadges, openRoom, setOpenRoom,
  autoTickEnabled, onToggleAutoTick, tickVersion,
  animateRoomList, onRoomListAnimated, onOpenRoomCreate,
}) {
  const [rooms, setRooms] = useState([])
  const [error, setError] = useState(null)
  const [loading, setLoading] = useState(true)
  const [ticking, setTicking] = useState(false)
  const [tickError, setTickError] = useState(null)
  const prevOpenRoomIdRef = useRef(null)
  const prevTickVersionRef = useRef(tickVersion)
  // 이 마운트 시점의 값만 캡처한다 — 이후 부모 상태가 바뀌어도 이번 렌더의 애니메이션 여부는 그대로 유지.
  const [shouldAnimateRooms] = useState(() => animateRoomList)

  useEffect(() => {
    if (animateRoomList) onRoomListAnimated()
  }, [])

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
      <ChatRoom roomId={openRoom.id} animateFirst={!!openRoom.justCreated} />
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
          {ticking ? '대화를 이어 만드는 중... (최대 1분)' : '시간 흐르기'}
        </button>
      </div>
      <div className="tick-hint">
        {autoTickEnabled ? '켜져 있는 동안 5~20분마다 대화가 이어져요' : '앱을 다시 열면 그동안의 대화는 자동으로 채워져요'}
      </div>
      {rooms.some((room) => !room.includes_me) && (
        <div className="tick-hint">‘엿보기’ 방은 나 없이 캐릭터끼리 대화하는 방이에요</div>
      )}
      {tickError && <div className="error-banner">{tickError}</div>}
      {rooms.length === 0 ? (
        <div className="empty-state">
          <ChatBubbleIcon className="empty-state-icon" size={48} />
          <div className="empty-state-text">아직 방이 없어요</div>
          <button type="button" className="btn-primary" onClick={onOpenRoomCreate}>방 만들기</button>
        </div>
      ) : (
      <ul className="room-list">
        {rooms.map((room, roomIdx) => (
          <li
            key={room.id}
            className={`room-item${!room.includes_me ? ' room-item-peek' : ''}${shouldAnimateRooms ? ' room-item-enter' : ''}`}
            style={shouldAnimateRooms ? { animationDelay: `${roomIdx * 0.15}s` } : undefined}
            onClick={() => handleEnterRoom(room)}
          >
            <div className="room-item-avatars">
              {(() => {
                const total = room.members.length
                if (total === 1) {
                  const name = room.members[0]
                  return (
                    <div
                      className="room-cluster-avatar room-cluster-avatar-solo"
                      style={{ background: avatarColor(name) }}
                    >
                      <AvatarInitial name={name} size={40} />
                    </div>
                  )
                }
                const shownCount = Math.min(total, 3)
                const positions = CLUSTER_POSITIONS[shownCount] || CLUSTER_POSITIONS[1]
                return positions.map((pos, idx) => {
                  const isOverflowSlot = total > 3 && idx === 2
                  if (isOverflowSlot) {
                    return (
                      <div
                        key="overflow"
                        className="room-cluster-avatar room-cluster-avatar-more"
                        style={{ left: pos.left, top: pos.top, zIndex: shownCount - idx }}
                      >
                        +{total - 2}
                      </div>
                    )
                  }
                  const name = room.members[idx]
                  return (
                    <div
                      key={name + idx}
                      className="room-cluster-avatar"
                      style={{ left: pos.left, top: pos.top, background: avatarColor(name), zIndex: shownCount - idx }}
                    >
                      <AvatarInitial name={name} size={20} />
                    </div>
                  )
                })
              })()}
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
      )}
    </div>
  )
}

export default ChatTab
