import { useState, useEffect } from 'react'
import { apiRequest } from './api'
import CharacterForm from './CharacterForm'
import RoomGenerateLoader from './RoomGenerateLoader'

function Onboarding({ onComplete, onExit }) {
  const [myName, setMyName] = useState('')
  const [step, setStep] = useState('name')
  const [savedCharacters, setSavedCharacters] = useState([])
  const [loading, setLoading] = useState('idle')
  const [error, setError] = useState(null)
  const [profilesInfo, setProfilesInfo] = useState({ profiles: [], current_profile_id: null })
  const [exiting, setExiting] = useState(false)

  useEffect(() => {
    apiRequest('/characters')
      .then((chars) => setSavedCharacters(chars.map((c) => ({ relation: c.relation, name: c.name }))))
      .catch(() => {})
    apiRequest('/profiles').then(setProfilesInfo).catch(() => {})
  }, [])

  async function handleExit() {
    const message = savedCharacters.length > 0
      ? `만들던 프로필과 지금까지 추가한 캐릭터 ${savedCharacters.length}명이 함께 삭제됩니다. 나가시겠어요?`
      : '만들던 프로필이 삭제됩니다. 나가시겠어요?'
    if (!window.confirm(message)) return
    setExiting(true)
    setError(null)
    try {
      await apiRequest(`/profiles/${profilesInfo.current_profile_id}`, { method: 'DELETE' })
      onExit()
    } catch (e) {
      setError(e.message)
      setExiting(false)
    }
  }

  async function handleNameNext() {
    if (!myName.trim()) return
    setLoading('naming')
    setError(null)
    try {
      await apiRequest('/profiles/current/name', {
        method: 'PUT',
        body: JSON.stringify({ name: myName.trim() }),
      })
      setStep('character-form')
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading('idle')
    }
  }

  function handleCharacterSaved(saved) {
    setSavedCharacters((prev) => [...prev, saved])
  }

  async function handleStart() {
    setLoading('starting')
    setError(null)
    try {
      await apiRequest('/rooms/generate', { method: 'POST' })
      onComplete(myName)
    } catch (e) {
      setError(e.message)
      setLoading('idle')
    }
  }

  return (
    <div className="onboarding">
      {profilesInfo.profiles.length > 1 && (
        <button type="button" className="onboarding-back" onClick={handleExit} disabled={exiting}>
          {exiting ? '나가는 중...' : '‹ 뒤로'}
        </button>
      )}
      <h1 className="onboarding-title">DearPeople</h1>
      {error && <div className="error-banner">{error}</div>}

      {step === 'name' && (
        <>
          <p className="onboarding-intro">
            가족과 친구를 AI 캐릭터로 만들어 두면, 카카오톡 단톡방처럼 서로 대화하고 사진도 나눠요.
            내가 없는 방에서 오가는 이야기를 엿보거나, 직접 말을 걸 수도 있어요.
            캐릭터의 기억을 고치면 이후의 말이 달라져요.
          </p>
          <div className="field">
            <label>내 이름</label>
            <input
              type="text"
              value={myName}
              onChange={(e) => setMyName(e.target.value)}
              placeholder="이름을 입력하세요"
            />
          </div>
          <button
            type="button"
            className="btn-primary"
            onClick={handleNameNext}
            disabled={!myName.trim() || loading === 'naming'}
          >
            {loading === 'naming' ? '처리 중...' : '다음'}
          </button>
        </>
      )}

      {step === 'character-form' && (
        loading === 'starting' ? (
          <RoomGenerateLoader characters={savedCharacters} profileName={myName} profileEmoji="user" />
        ) : (
          <>
            {savedCharacters.length > 0 && (
              <ul className="saved-character-list">
                {savedCharacters.map((c, i) => (
                  <li key={i} className="saved-character-item">
                    {c.relation} · {c.name}
                  </li>
                ))}
              </ul>
            )}

            {savedCharacters.length >= 2 && (
              <div className="start-button-wrap">
                <button type="button" className="btn-primary" onClick={handleStart} disabled={loading === 'starting'}>
                  시작하기
                </button>
              </div>
            )}

            <CharacterForm onSaved={handleCharacterSaved} />
          </>
        )
      )}
    </div>
  )
}

export default Onboarding
