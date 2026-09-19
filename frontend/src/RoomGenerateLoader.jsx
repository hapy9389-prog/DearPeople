import { useState, useEffect } from 'react'
import { avatarColor } from './format'
import { AvatarInitial, ProfileIcon, normalizeProfileIcon } from './icons'

const PHRASES = ['방을 만들고 있어요', '서로를 소개하는 중', '첫 대화를 나누는 중']
const ORBIT_RADIUS = 60

function RoomGenerateLoader({ characters, profileName, profileEmoji }) {
  const [phraseIndex, setPhraseIndex] = useState(0)

  useEffect(() => {
    const intervalId = setInterval(() => {
      setPhraseIndex((i) => (i + 1) % PHRASES.length)
    }, 8000)
    return () => clearInterval(intervalId)
  }, [])

  if (characters.length === 0) {
    return <div className="placeholder">불러오는 중...</div>
  }

  return (
    <div className="room-loader">
      <div className="room-loader-stage">
        <div className="room-loader-orbit">
          {characters.map((c, i) => {
            const angle = (360 / characters.length) * i
            return (
              <div
                key={c.id ?? i}
                className="room-loader-satellite"
                style={{ transform: `rotate(${angle}deg) translate(${ORBIT_RADIUS}px)` }}
              >
                <div className="avatar avatar-small" style={{ background: avatarColor(c.name) }}>
                  <AvatarInitial name={c.name} size={32} />
                </div>
              </div>
            )
          })}
        </div>
        <div className="avatar room-loader-center" style={{ background: avatarColor(profileName) }}>
          <ProfileIcon icon={normalizeProfileIcon(profileEmoji)} size={22} color="var(--text)" />
        </div>
      </div>
      <div className="room-loader-text">{PHRASES[phraseIndex]}</div>
      <div className="room-loader-hint">캐릭터가 대화를 만들고 있어요. 30초~1분 정도 걸려요</div>
    </div>
  )
}

export default RoomGenerateLoader
