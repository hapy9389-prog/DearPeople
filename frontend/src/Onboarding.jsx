import { useState, useEffect } from 'react'
import { apiRequest } from './api'

const RELATION_TO_GRP = {
  엄마: 'family',
  아빠: 'family',
  형제자매: 'family',
  친구: 'friend',
}

const EMPTY_FORM = { relation: '엄마', name: '', description: '' }

function Onboarding({ onComplete }) {
  const [myName, setMyName] = useState('')
  const [step, setStep] = useState('name')
  const [form, setForm] = useState(EMPTY_FORM)
  const [draft, setDraft] = useState(null)
  const [savedCharacters, setSavedCharacters] = useState([])
  const [loading, setLoading] = useState('idle')
  const [error, setError] = useState(null)

  useEffect(() => {
    apiRequest('/characters')
      .then((chars) => setSavedCharacters(chars.map((c) => ({ relation: c.relation, name: c.name }))))
      .catch(() => {})
  }, [])

  function handleNameNext() {
    if (myName.trim()) setStep('character-form')
  }

  async function handleDraft() {
    if (!form.name.trim() || !form.description.trim()) return
    setLoading('drafting')
    setError(null)
    try {
      const grp = RELATION_TO_GRP[form.relation]
      const result = await apiRequest('/characters/draft', {
        method: 'POST',
        body: JSON.stringify({
          relation: form.relation,
          grp,
          name: form.name,
          description: form.description,
        }),
      })
      setDraft(result)
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading('idle')
    }
  }

  async function handleSaveCharacter() {
    setLoading('saving')
    setError(null)
    try {
      const grp = RELATION_TO_GRP[form.relation]
      await apiRequest('/characters', {
        method: 'POST',
        body: JSON.stringify({ relation: form.relation, grp, name: form.name, ...draft }),
      })
      setSavedCharacters((prev) => [...prev, { relation: form.relation, name: form.name }])
      setForm(EMPTY_FORM)
      setDraft(null)
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading('idle')
    }
  }

  async function handleStart() {
    setLoading('starting')
    setError(null)
    try {
      await apiRequest('/settings/me', { method: 'PUT', body: JSON.stringify({ name: myName }) })
      await apiRequest('/rooms/generate', { method: 'POST' })
      onComplete()
    } catch (e) {
      setError(e.message)
      setLoading('idle')
    }
  }

  function updateDraftField(field, value) {
    setDraft((prev) => ({ ...prev, [field]: value }))
  }

  function updateDraftMemory(index, value) {
    setDraft((prev) => {
      const memories = [...prev.memories]
      memories[index] = value
      return { ...prev, memories }
    })
  }

  return (
    <div className="onboarding">
      <h1 className="onboarding-title">DearPeople</h1>
      {error && <div className="error-banner">{error}</div>}

      {step === 'name' && (
        <>
          <div className="field">
            <label>내 이름</label>
            <input
              type="text"
              value={myName}
              onChange={(e) => setMyName(e.target.value)}
              placeholder="이름을 입력하세요"
            />
          </div>
          <button type="button" className="btn-primary" onClick={handleNameNext} disabled={!myName.trim()}>
            다음
          </button>
        </>
      )}

      {step === 'character-form' && (
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
                {loading === 'starting' ? '방 만드는 중...' : '시작하기'}
              </button>
            </div>
          )}

          {draft === null && (
            <>
              <div className="field">
                <label>관계</label>
                <select
                  value={form.relation}
                  onChange={(e) => setForm({ ...form, relation: e.target.value })}
                >
                  <option value="엄마">엄마</option>
                  <option value="아빠">아빠</option>
                  <option value="형제자매">형제자매</option>
                  <option value="친구">친구</option>
                </select>
              </div>
              <div className="field">
                <label>이름</label>
                <input
                  type="text"
                  value={form.name}
                  onChange={(e) => setForm({ ...form, name: e.target.value })}
                  placeholder="예: 민수"
                />
              </div>
              <div className="field">
                <label>한 줄 설명</label>
                <input
                  type="text"
                  value={form.description}
                  onChange={(e) => setForm({ ...form, description: e.target.value })}
                  placeholder="이 사람은 어떤 사람인가요?"
                />
              </div>
              <button type="button" className="btn-primary" onClick={handleDraft} disabled={loading === 'drafting'}>
                {loading === 'drafting' ? '생성 중...' : '초안 만들기'}
              </button>
            </>
          )}

          {draft !== null && (
            <>
              <div className="field">
                <label>성격</label>
                <input
                  type="text"
                  value={draft.personality}
                  onChange={(e) => updateDraftField('personality', e.target.value)}
                />
              </div>
              <div className="field">
                <label>말투</label>
                <input
                  type="text"
                  value={draft.speech_style}
                  onChange={(e) => updateDraftField('speech_style', e.target.value)}
                />
              </div>
              <div className="field">
                <label>나를 부르는 호칭</label>
                <input
                  type="text"
                  value={draft.calls_me}
                  onChange={(e) => updateDraftField('calls_me', e.target.value)}
                />
              </div>
              <div className="field">
                <label>기억</label>
                <ul className="memory-list">
                  {draft.memories.map((m, i) => (
                    <li key={i} className="memory-item">
                      <input type="text" value={m} onChange={(e) => updateDraftMemory(i, e.target.value)} />
                    </li>
                  ))}
                </ul>
              </div>
              <button
                type="button"
                className="btn-primary"
                onClick={handleSaveCharacter}
                disabled={loading === 'saving'}
              >
                {loading === 'saving' ? '저장 중...' : '저장'}
              </button>
            </>
          )}
        </>
      )}
    </div>
  )
}

export default Onboarding
