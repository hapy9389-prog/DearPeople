import { useState } from 'react'
import { apiRequest } from './api'
import { resolveRelationAndGrp, isRelationValid } from './relation'
import { CloseIcon } from './icons'

const EMPTY_FORM = {
  relationOption: '엄마', customRelation: '', customGrp: 'family', name: '', description: '',
}

function CharacterForm({ onSaved, sheet = false, onClose }) {
  const [form, setForm] = useState(EMPTY_FORM)
  const [draft, setDraft] = useState(null)
  const [loading, setLoading] = useState('idle')
  const [error, setError] = useState(null)

  async function requestDraft() {
    setLoading('drafting')
    setError(null)
    try {
      const { relation, grp } = resolveRelationAndGrp(form)
      const result = await apiRequest('/characters/draft', {
        method: 'POST',
        body: JSON.stringify({
          relation,
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

  function handleDraft() {
    if (!form.name.trim() || !form.description.trim() || !isRelationValid(form)) return
    requestDraft()
  }

  async function handleSaveCharacter() {
    setLoading('saving')
    setError(null)
    try {
      const { relation, grp } = resolveRelationAndGrp(form)
      await apiRequest('/characters', {
        method: 'POST',
        body: JSON.stringify({ relation, grp, name: form.name, ...draft }),
      })
      const saved = { relation, name: form.name }
      setForm(EMPTY_FORM)
      setDraft(null)
      onSaved(saved)
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading('idle')
    }
  }

  function handleRedraft() {
    requestDraft()
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

  const fields = draft === null ? (
    <>
      <div className="field">
        <label>관계</label>
        <select
          value={form.relationOption}
          onChange={(e) => setForm({ ...form, relationOption: e.target.value })}
        >
          <option value="엄마">엄마</option>
          <option value="아빠">아빠</option>
          <option value="형제자매">형제자매</option>
          <option value="친구">친구</option>
          <option value="기타">기타</option>
        </select>
      </div>
      {form.relationOption === '기타' && (
        <>
          <div className="field">
            <label>관계 이름</label>
            <input
              type="text"
              value={form.customRelation}
              onChange={(e) => setForm({ ...form, customRelation: e.target.value })}
              placeholder="예: 할머니, 선배, 동료"
            />
          </div>
          <div className="field">
            <label>그룹</label>
            <select
              value={form.customGrp}
              onChange={(e) => setForm({ ...form, customGrp: e.target.value })}
            >
              <option value="family">가족</option>
              <option value="friend">친구</option>
            </select>
            <span className="field-hint">방을 자동으로 만들 때 쓰이는 분류예요</span>
          </div>
        </>
      )}
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
    </>
  ) : (
    <>
      <div className="character-draft-intro">이 사람이 맞나요? 필요하면 내용을 고쳐서 저장하세요.</div>
      <div className="field">
        <label>성격</label>
        <textarea
          rows={3}
          value={draft.personality}
          onChange={(e) => updateDraftField('personality', e.target.value)}
        />
      </div>
      <div className="field">
        <label>말투</label>
        <textarea
          rows={3}
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
        <label>서운하거나 화날 때</label>
        <textarea
          rows={2}
          value={draft.reaction_style}
          onChange={(e) => updateDraftField('reaction_style', e.target.value)}
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
    </>
  )

  const actions = draft === null ? (
    <button
      type="button"
      className="btn-primary"
      onClick={handleDraft}
      disabled={loading === 'drafting' || !form.name.trim()}
    >
      {loading === 'drafting' ? 'AI가 성격을 만드는 중...' : '초안 만들기'}
    </button>
  ) : (
    <div className="character-form-actions">
      <button
        type="button"
        className="btn-primary"
        onClick={handleSaveCharacter}
        disabled={loading !== 'idle' || !isRelationValid(form)}
      >
        {loading === 'saving' ? '저장 중...' : '저장'}
      </button>
      <button
        type="button"
        className="character-form-secondary-button"
        onClick={handleRedraft}
        disabled={loading !== 'idle'}
      >
        {loading === 'drafting' ? '다시 만드는 중...' : '다시 만들기'}
      </button>
    </div>
  )

  const body = (
    <div className={`character-form${draft !== null ? ' character-form-draft' : ''}`}>
      {error && <div className="error-banner">{error}</div>}
      {fields}
    </div>
  )

  if (!sheet) {
    return (
      <>
        {body}
        {actions}
      </>
    )
  }

  return (
    <div className="character-sheet-backdrop" onClick={onClose}>
      <div className="character-sheet" onClick={(e) => e.stopPropagation()}>
        <div className="character-sheet-header">
          <h2 className="character-sheet-title">캐릭터 추가</h2>
          <button type="button" className="character-sheet-close" onClick={onClose} aria-label="닫기">
            <CloseIcon size={18} />
          </button>
        </div>
        <div className="character-sheet-body">
          {body}
        </div>
        <div className="character-sheet-footer">
          {actions}
        </div>
      </div>
    </div>
  )
}

export default CharacterForm
