import { useState, useEffect, useRef } from 'react'
import { apiRequest } from './api'

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms))
}

function ChatRoom({ roomId, onBack }) {
  const [room, setRoom] = useState(null)
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [sending, setSending] = useState(false)
  const [typing, setTyping] = useState(false)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const bottomRef = useRef(null)

  useEffect(() => {
    apiRequest(`/rooms/${roomId}/messages`)
      .then((data) => { setRoom(data.room); setMessages(data.messages) })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false))
  }, [roomId])

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, typing])

  async function revealReplies(replies) {
    if (replies.length === 0) {
      setTyping(false)
      return
    }
    for (let i = 0; i < replies.length; i++) {
      await sleep(1000)
      setMessages((prev) => [...prev, replies[i]])
      setTyping(i < replies.length - 1) // 마지막 메시지를 보여준 뒤에는 "입력 중..."을 끈다
    }
  }

  async function handleSend() {
    const text = input.trim()
    if (!text || sending) return
    setMessages((prev) => [...prev, {
      id: `temp-${Date.now()}`, sender: '나', sender_character_id: null, content: text,
    }])
    setInput('')
    setSending(true)
    setError(null)
    setTyping(true) // 보내자마자 바로 "입력 중..." 표시
    try {
      const replies = await apiRequest(`/rooms/${roomId}/messages`, {
        method: 'POST',
        body: JSON.stringify({ content: text }),
      })
      await revealReplies(replies)
    } catch (e) {
      setError(e.message)
      setTyping(false)
    } finally {
      setSending(false)
    }
  }

  if (loading) return <div className="placeholder">불러오는 중...</div>
  if (!room) return <div className="error-banner">{error || '채팅방을 찾을 수 없습니다.'}</div>

  return (
    <div className="chat-room">
      <div className="chat-room-header">
        <button type="button" className="chat-room-back" onClick={onBack}>‹</button>
        <span className="chat-room-title">{room.name}</span>
      </div>
      {!room.includes_me && <div className="peek-banner">엿보는 중</div>}
      {error && <div className="error-banner">{error}</div>}
      <div className="chat-room-messages">
        {messages.map((m) => (
          <div key={m.id} className={`bubble-row${m.sender_character_id === null ? ' mine' : ''}`}>
            {m.sender_character_id !== null && <div className="bubble-sender">{m.sender}</div>}
            <div className="bubble">{m.content}</div>
          </div>
        ))}
        {typing && (
          <div className="bubble-row">
            <div className="bubble bubble-typing">입력 중...</div>
          </div>
        )}
        <div ref={bottomRef} />
      </div>
      {room.includes_me && (
        <div className="chat-room-input-bar">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => { if (e.key === 'Enter' && !e.nativeEvent.isComposing) handleSend() }}
            placeholder="메시지 보내기"
            disabled={sending}
          />
          <button type="button" className="btn-primary" onClick={handleSend} disabled={sending || !input.trim()}>
            전송
          </button>
        </div>
      )}
    </div>
  )
}

export default ChatRoom
