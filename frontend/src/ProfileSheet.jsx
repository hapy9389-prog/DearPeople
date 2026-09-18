import { useState, useEffect } from 'react'
import { apiRequest } from './api'
import { avatarColor } from './format'

const EMOJI_CHOICES = ['🙂', '😀', '😎', '🐱', '🐶', '🌸', '⭐', '🍀']

function ProfileSheet({ onClose, onSwitched, onCreated, onCleared }) {
  const [profiles, setProfiles] = useState([])
  const [currentProfileId, setCurrentProfileId] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(false)
  const [pickerForId, setPickerForId] = useState(null)

  function load() {
    setLoading(true)
    apiRequest('/profiles')
      .then((d) => {
        setProfiles(d.profiles)
        setCurrentProfileId(d.current_profile_id)
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false))
  }

  useEffect(() => { load() }, [])

  async function handleSwitch(profile) {
    if (profile.id === currentProfileId || busy) return
    setBusy(true)
    setError(null)
    try {
      await apiRequest('/profiles/current', { method: 'PUT', body: JSON.stringify({ id: profile.id }) })
      onSwitched()
    } catch (e) {
      setError(e.message)
      setBusy(false)
    }
  }

  async function handleCreate() {
    setBusy(true)
    setError(null)
    try {
      await apiRequest('/profiles', { method: 'POST', body: JSON.stringify({ name: '새 프로필' }) })
      onCreated()
    } catch (e) {
      setError(e.message)
      setBusy(false)
    }
  }

  async function handleEmojiSelect(profile, emoji) {
    if (busy) return
    setBusy(true)
    setError(null)
    try {
      await apiRequest(`/profiles/${profile.id}/emoji`, { method: 'PUT', body: JSON.stringify({ emoji }) })
      setProfiles((prev) => prev.map((p) => (p.id === profile.id ? { ...p, emoji } : p)))
      setPickerForId(null)
    } catch (e) {
      setError(e.message)
    } finally {
      setBusy(false)
    }
  }

  async function handleClear() {
    if (busy) return
    if (!window.confirm('모든 캐릭터와 대화가 삭제됩니다. 계속할까요?')) return
    setBusy(true)
    setError(null)
    try {
      await apiRequest('/reset', { method: 'POST' })
      onCleared()
    } catch (e) {
      setError(e.message)
      setBusy(false)
    }
  }

  async function handleDelete(profile) {
    if (busy) return
    if (!window.confirm('이 프로필과 모든 대화가 삭제됩니다. 계속할까요?')) return
    setBusy(true)
    setError(null)
    try {
      const wasCurrent = profile.id === currentProfileId
      await apiRequest(`/profiles/${profile.id}`, { method: 'DELETE' })
      if (wasCurrent) {
        onSwitched()
      } else {
        load()
        setBusy(false)
      }
    } catch (e) {
      setError(e.message)
      setBusy(false)
    }
  }

  function handleDeleteOrClear(profile) {
    if (profiles.length <= 1) {
      handleClear()
    } else {
      handleDelete(profile)
    }
  }

  return (
    <div className="profile-sheet-backdrop" onClick={onClose}>
      <div className="profile-sheet" onClick={(e) => e.stopPropagation()}>
        <div className="profile-sheet-handle" />
        <h2 className="profile-sheet-title">프로필</h2>
        {error && <div className="error-banner">{error}</div>}
        {loading ? (
          <div className="placeholder">불러오는 중...</div>
        ) : (
          <ul className="profile-sheet-list">
            {profiles.map((p) => (
              <li key={p.id} className="profile-sheet-item">
                <button
                  type="button"
                  className="avatar profile-sheet-avatar"
                  style={{ background: avatarColor(p.name) }}
                  onClick={(e) => { e.stopPropagation(); setPickerForId(pickerForId === p.id ? null : p.id) }}
                  disabled={busy}
                >
                  {p.emoji}
                </button>
                <div className="profile-sheet-row-wrap">
                  <button
                    type="button"
                    className={`profile-sheet-row${p.id === currentProfileId ? ' profile-sheet-row-current' : ''}`}
                    onClick={() => handleSwitch(p)}
                    disabled={busy}
                  >
                    <span className="profile-sheet-name">
                      {p.name}
                      {p.id === currentProfileId && <span className="profile-sheet-current-badge">현재</span>}
                    </span>
                    <span className="profile-sheet-count">캐릭터 {p.character_count}명</span>
                  </button>
                  {pickerForId === p.id && (
                    <div className="profile-sheet-emoji-picker">
                      {EMOJI_CHOICES.map((emoji) => (
                        <button
                          key={emoji}
                          type="button"
                          className="profile-sheet-emoji-option"
                          onClick={() => handleEmojiSelect(p, emoji)}
                          disabled={busy}
                        >
                          {emoji}
                        </button>
                      ))}
                    </div>
                  )}
                </div>
                <button
                  type="button"
                  className="profile-sheet-delete"
                  onClick={() => handleDeleteOrClear(p)}
                  disabled={busy}
                >
                  {profiles.length <= 1 ? '비우기' : '삭제'}
                </button>
              </li>
            ))}
          </ul>
        )}
        <button type="button" className="btn-primary profile-sheet-create" onClick={handleCreate} disabled={busy}>
          새 프로필 만들기
        </button>
      </div>
    </div>
  )
}

export default ProfileSheet
