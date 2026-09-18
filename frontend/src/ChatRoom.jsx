import { useState, useEffect, useRef } from 'react'
import { apiRequest } from './api'
import { relationEmoji, avatarColor, formatTime, formatDateDivider, kstDateKey, kstMinuteKey } from './format'

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms))
}

const ALLOWED_PHOTO_TYPES = ['image/png', 'image/jpeg', 'image/webp']
const MAX_PHOTO_BYTES = 5 * 1024 * 1024

function withDisplayFlags(messages) {
  let prevSenderId, prevDateKey
  return messages.map((m, i) => {
    const dateKey = kstDateKey(m.created_at)
    const showDateDivider = dateKey !== prevDateKey
    const isFirstOfRun = m.sender_character_id !== prevSenderId || showDateDivider
    const next = messages[i + 1]
    const sameRunAsNext = next
      && next.sender_character_id === m.sender_character_id
      && kstDateKey(next.created_at) === dateKey
      && kstMinuteKey(next.created_at) === kstMinuteKey(m.created_at)
    prevSenderId = m.sender_character_id
    prevDateKey = dateKey
    return {
      ...m,
      showDateDivider,
      showAvatar: isFirstOfRun && m.sender_character_id !== null,
      showTimestamp: !sameRunAsNext,
    }
  })
}

function ChatRoom({ roomId, characters, animateFirst }) {
  const [room, setRoom] = useState(null)
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [sending, setSending] = useState(false)
  const [typing, setTyping] = useState(false)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [photoFile, setPhotoFile] = useState(null)
  const [photoPreviewUrl, setPhotoPreviewUrl] = useState(null)
  const [photoCaption, setPhotoCaption] = useState('')
  const bottomRef = useRef(null)
  const fileInputRef = useRef(null)

  const relationById = Object.fromEntries(characters.map((c) => [c.id, c.relation]))

  useEffect(() => {
    apiRequest(`/rooms/${roomId}/messages`)
      .then(async (data) => {
        setRoom(data.room)
        setLoading(false)
        if (animateFirst && data.messages.length > 0) {
          setTyping(true)
          await revealReplies(data.messages)
        } else {
          setMessages(data.messages)
        }
      })
      .catch((e) => { setError(e.message); setLoading(false) })
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
    if (photoFile) return handleSendPhoto()
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

  function handleFileSelect(e) {
    const file = e.target.files[0]
    e.target.value = '' // 같은 파일을 다시 선택해도 onChange가 발생하도록 초기화
    if (!file) return
    if (!ALLOWED_PHOTO_TYPES.includes(file.type)) {
      setError('png, jpg, webp 파일만 보낼 수 있습니다.')
      return
    }
    if (file.size > MAX_PHOTO_BYTES) {
      setError('5MB 이하 파일만 보낼 수 있습니다.')
      return
    }
    setError(null)
    setPhotoFile(file)
    setPhotoPreviewUrl(URL.createObjectURL(file))
    setPhotoCaption('')
  }

  function handleCancelPhoto() {
    setPhotoFile(null)
    setPhotoPreviewUrl(null)
    setPhotoCaption('')
  }

  async function handleSendPhoto() {
    if (!photoFile || sending) return
    const file = photoFile
    const caption = photoCaption.trim()
    setMessages((prev) => [...prev, {
      id: `temp-${Date.now()}`, sender: '나', sender_character_id: null,
      type: 'photo', image_path: photoPreviewUrl, caption: caption || null,
    }])
    setPhotoFile(null)
    setPhotoPreviewUrl(null)
    setPhotoCaption('')
    setSending(true)
    setError(null)
    setTyping(true)
    try {
      const formData = new FormData()
      formData.append('file', file)
      formData.append('caption', caption)
      const replies = await apiRequest(`/rooms/${roomId}/photo`, { method: 'POST', body: formData })
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
      {!room.includes_me && <div className="peek-banner">엿보는 중</div>}
      {error && <div className="error-banner">{error}</div>}
      <div className="chat-room-messages">
        {withDisplayFlags(messages).map((m) => (
          <div key={m.id} className="message-block">
            {m.showDateDivider && (
              <div className="chat-date-divider"><span>{formatDateDivider(m.created_at)}</span></div>
            )}
            <div className={`bubble-row${m.sender_character_id === null ? ' mine' : ''}`}>
              {m.sender_character_id !== null && m.showAvatar && (
                <div className="bubble-header">
                  <div className="avatar avatar-small" style={{ background: avatarColor(m.sender) }}>
                    {relationEmoji(relationById[m.sender_character_id])}
                  </div>
                  <span className="bubble-sender">{m.sender}</span>
                </div>
              )}
              <div className={`bubble-line${m.sender_character_id !== null ? ' bubble-line-indent' : ''}`}>
                {m.sender_character_id === null && m.showTimestamp && (
                  <span className="bubble-time">{formatTime(m.created_at)}</span>
                )}
                {m.type === 'photo' ? (
                  <div className="photo-card">
                    {m.image_path ? (
                      <img src={m.image_path} alt={m.content} className="photo-card-image" />
                    ) : (
                      <div className="photo-card-placeholder">
                        <span className="photo-card-icon">📷</span>
                        <span className="photo-card-desc">{m.content}</span>
                      </div>
                    )}
                    {m.caption && <div className="photo-card-caption">{m.caption}</div>}
                  </div>
                ) : (
                  <div className="bubble">{m.content}</div>
                )}
                {m.sender_character_id !== null && m.showTimestamp && (
                  <span className="bubble-time">{formatTime(m.created_at)}</span>
                )}
              </div>
            </div>
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
        <>
          {photoFile && (
            <div className="chat-room-photo-preview">
              <img src={photoPreviewUrl} alt="첨부한 사진 미리보기" className="chat-room-photo-preview-thumb" />
              <input
                type="text"
                className="chat-room-photo-preview-caption"
                value={photoCaption}
                onChange={(e) => setPhotoCaption(e.target.value)}
                placeholder="캡션 (선택)"
                disabled={sending}
              />
              <button
                type="button"
                className="chat-room-photo-preview-cancel"
                onClick={handleCancelPhoto}
                disabled={sending}
              >
                ×
              </button>
            </div>
          )}
          <div className="chat-room-input-bar">
            <input
              type="file"
              accept="image/png,image/jpeg,image/webp"
              ref={fileInputRef}
              onChange={handleFileSelect}
              hidden
            />
            <button
              type="button"
              className="chat-room-attach-button"
              onClick={() => fileInputRef.current.click()}
              disabled={sending}
            >
              📷
            </button>
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => { if (e.key === 'Enter' && !e.nativeEvent.isComposing) handleSend() }}
              placeholder={photoFile ? '사진을 보낼 준비가 됐어요' : '메시지 보내기'}
              disabled={sending || !!photoFile}
            />
            <button
              type="button"
              className="btn-primary"
              onClick={handleSend}
              disabled={sending || (photoFile ? false : !input.trim())}
            >
              전송
            </button>
          </div>
        </>
      )}
    </div>
  )
}

export default ChatRoom
