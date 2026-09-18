import { useState, useEffect } from 'react'
import { apiRequest } from './api'
import CharacterForm from './CharacterForm'
import RelationshipDiagram from './RelationshipDiagram'
import RoomGenerateLoader from './RoomGenerateLoader'
import { RELATION_TO_GRP, resolveRelationAndGrp, isRelationValid } from './relation'

const BUILT_IN_RELATIONS = Object.keys(RELATION_TO_GRP)

function buildEditForm(c) {
  const isBuiltIn = BUILT_IN_RELATIONS.includes(c.relation)
  return {
    name: c.name,
    relationOption: isBuiltIn ? c.relation : '기타',
    customRelation: isBuiltIn ? '' : c.relation,
    customGrp: c.grp,
    personality: c.personality,
    speech_style: c.speech_style,
    calls_me: c.calls_me,
  }
}

function PeopleTab({ profile, onOpenMemories, onCharactersChanged, onRoomsRegenerated }) {
  const [characters, setCharacters] = useState([])
  const [memoryCounts, setMemoryCounts] = useState({})
  const [expandedId, setExpandedId] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [addingCharacter, setAddingCharacter] = useState(false)
  const [needsRoomRegen, setNeedsRoomRegen] = useState(false)
  const [regenerating, setRegenerating] = useState(false)
  const [regenerateError, setRegenerateError] = useState(null)
  const [editingId, setEditingId] = useState(null)
  const [editForm, setEditForm] = useState(null)
  const [savingEdit, setSavingEdit] = useState(false)
  const [editError, setEditError] = useState(null)
  const [toast, setToast] = useState(null)

  function loadCharacters() {
    setLoading(true)
    apiRequest('/characters')
      .then(async (chars) => {
        setCharacters(chars)
        const counts = {}
        await Promise.all(chars.map(async (c) => {
          const memories = await apiRequest(`/characters/${c.id}/memories`)
          counts[c.id] = memories.length
        }))
        setMemoryCounts(counts)
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    loadCharacters()
  }, [])

  function handleCharacterSaved() {
    setAddingCharacter(false)
    setNeedsRoomRegen(true)
    loadCharacters()
    onCharactersChanged()
  }

  async function handleRegenerateRooms() {
    setRegenerating(true)
    setRegenerateError(null)
    try {
      await apiRequest('/rooms/generate', { method: 'POST' })
      setNeedsRoomRegen(false)
      onRoomsRegenerated()
    } catch (e) {
      setRegenerateError(e.message)
    } finally {
      setRegenerating(false)
    }
  }

  function showToast() {
    setToast('다음 대화부터 반영됩니다')
    setTimeout(() => setToast(null), 2000)
  }

  function handleStartEdit(c) {
    setEditingId(c.id)
    setEditForm(buildEditForm(c))
    setEditError(null)
  }

  function handleCancelEdit() {
    setEditingId(null)
    setEditForm(null)
    setEditError(null)
  }

  async function handleSaveEdit() {
    const { relation, grp } = resolveRelationAndGrp(editForm)
    setSavingEdit(true)
    setEditError(null)
    try {
      await apiRequest(`/characters/${editingId}`, {
        method: 'PUT',
        body: JSON.stringify({
          name: editForm.name.trim(),
          relation,
          grp,
          personality: editForm.personality,
          speech_style: editForm.speech_style,
          calls_me: editForm.calls_me,
        }),
      })
      setEditingId(null)
      setEditForm(null)
      loadCharacters()
      onCharactersChanged()
      showToast()
    } catch (e) {
      setEditError(e.message)
    } finally {
      setSavingEdit(false)
    }
  }

  if (loading) return <div className="placeholder">불러오는 중...</div>
  if (error) return <div className="error-banner">{error}</div>

  return (
    <div className="people-tab">
      {toast && <div className="toast">{toast}</div>}

      <div className="people-top-bar">
        <button type="button" className="btn-primary" onClick={() => setAddingCharacter((v) => !v)}>
          {addingCharacter ? '취소' : '캐릭터 추가'}
        </button>
      </div>

      {addingCharacter && (
        <div className="people-add-form">
          <CharacterForm onSaved={handleCharacterSaved} />
        </div>
      )}

      {needsRoomRegen && (
        <div className="people-regen-banner">
          {regenerating ? (
            <RoomGenerateLoader characters={characters} profileName={profile.name} profileEmoji={profile.emoji} />
          ) : (
            <>
              <div>방을 다시 만들어야 새 캐릭터가 대화에 참여합니다. 기존 대화는 모두 지워집니다.</div>
              {regenerateError && <div className="error-banner">{regenerateError}</div>}
              <button type="button" className="btn-primary" onClick={handleRegenerateRooms}>
                방 다시 만들기
              </button>
            </>
          )}
        </div>
      )}

      {characters.length > 0 && (
        <RelationshipDiagram profile={profile} characters={characters} onOpenMemories={onOpenMemories} />
      )}

      <ul className="people-list">
        {characters.map((c) => {
          const isEditing = editingId === c.id
          let roomImpact = false
          if (isEditing) {
            const resolved = resolveRelationAndGrp(editForm)
            roomImpact = resolved.relation !== c.relation || resolved.grp !== c.grp
          }

          return (
            <li key={c.id} className="people-item">
              <div
                className="people-item-header"
                onClick={() => setExpandedId(expandedId === c.id ? null : c.id)}
              >
                <div className="people-item-main">
                  <span className="people-item-name">{c.name}</span>
                  <span className="people-item-relation">{c.relation}</span>
                </div>
                <div className="people-item-personality">{c.personality}</div>
                <button
                  type="button"
                  className="people-item-memory-count"
                  onClick={(e) => { e.stopPropagation(); onOpenMemories(c.id) }}
                >
                  기억 {memoryCounts[c.id] ?? 0}개
                </button>
              </div>

              {expandedId === c.id && !isEditing && (
                <div className="people-item-detail">
                  <div><strong>성격</strong> {c.personality}</div>
                  <div><strong>말투</strong> {c.speech_style}</div>
                  <div><strong>나를 부르는 호칭</strong> {c.calls_me}</div>
                  <button type="button" className="people-item-edit-button" onClick={() => handleStartEdit(c)}>
                    수정
                  </button>
                </div>
              )}

              {expandedId === c.id && isEditing && (
                <div className="people-item-edit">
                  {editError && <div className="error-banner">{editError}</div>}
                  <div className="field">
                    <label>이름</label>
                    <input
                      type="text"
                      value={editForm.name}
                      onChange={(e) => setEditForm({ ...editForm, name: e.target.value })}
                    />
                  </div>
                  <div className="field">
                    <label>관계</label>
                    <select
                      value={editForm.relationOption}
                      onChange={(e) => setEditForm({ ...editForm, relationOption: e.target.value })}
                    >
                      <option value="엄마">엄마</option>
                      <option value="아빠">아빠</option>
                      <option value="형제자매">형제자매</option>
                      <option value="친구">친구</option>
                      <option value="기타">기타</option>
                    </select>
                  </div>
                  {editForm.relationOption === '기타' && (
                    <>
                      <div className="field">
                        <label>관계 이름</label>
                        <input
                          type="text"
                          value={editForm.customRelation}
                          onChange={(e) => setEditForm({ ...editForm, customRelation: e.target.value })}
                          placeholder="예: 할머니, 선배, 동료"
                        />
                      </div>
                      <div className="field">
                        <label>그룹</label>
                        <select
                          value={editForm.customGrp}
                          onChange={(e) => setEditForm({ ...editForm, customGrp: e.target.value })}
                        >
                          <option value="family">가족</option>
                          <option value="friend">친구</option>
                        </select>
                      </div>
                    </>
                  )}
                  {roomImpact && (
                    <div className="field-hint">
                      방 구성이 달라질 수 있습니다. 방 다시 만들기를 하면 반영됩니다.
                    </div>
                  )}
                  <div className="field">
                    <label>성격</label>
                    <textarea
                      rows={3}
                      value={editForm.personality}
                      onChange={(e) => setEditForm({ ...editForm, personality: e.target.value })}
                    />
                  </div>
                  <div className="field">
                    <label>말투</label>
                    <textarea
                      rows={3}
                      value={editForm.speech_style}
                      onChange={(e) => setEditForm({ ...editForm, speech_style: e.target.value })}
                    />
                  </div>
                  <div className="field">
                    <label>나를 부르는 호칭</label>
                    <input
                      type="text"
                      value={editForm.calls_me}
                      onChange={(e) => setEditForm({ ...editForm, calls_me: e.target.value })}
                    />
                  </div>
                  <div className="people-item-edit-actions">
                    <button
                      type="button"
                      className="btn-primary"
                      onClick={handleSaveEdit}
                      disabled={savingEdit || !editForm.name.trim() || !isRelationValid(editForm)}
                    >
                      {savingEdit ? '저장 중...' : '저장'}
                    </button>
                    <button type="button" className="people-item-cancel" onClick={handleCancelEdit}>
                      취소
                    </button>
                  </div>
                </div>
              )}
            </li>
          )
        })}
      </ul>
    </div>
  )
}

export default PeopleTab
