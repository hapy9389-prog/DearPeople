import { avatarColor, initialLetter } from './format'
import { ProfileIcon, normalizeProfileIcon } from './icons'

const WIDTH = 320
const HEIGHT = 280
const CENTER_X = WIDTH / 2
const CENTER_Y = 132
const ORBIT_RADIUS = 92
const CENTER_NODE_RADIUS = 32

const NODE_BASE_DELAY = 0.1
const NODE_DURATION = 0.15
const LINE_DURATION = 0.1

function RelationshipDiagram({ profile, characters, onOpenMemories }) {
  const nodeRadius = characters.length > 6 ? 20 : 26
  const stagger = characters.length > 1 ? Math.min(0.1, 0.44 / (characters.length - 1)) : 0.1

  function nodeDelay(i) {
    return NODE_BASE_DELAY + i * stagger
  }

  const positions = characters.map((c, i) => {
    const angle = (-90 + (360 / characters.length) * i) * (Math.PI / 180)
    return {
      character: c,
      x: CENTER_X + ORBIT_RADIUS * Math.cos(angle),
      y: CENTER_Y + ORBIT_RADIUS * Math.sin(angle),
      delay: nodeDelay(i),
    }
  })

  const familyChars = characters.filter((c) => c.grp === 'family')
  const familyPairs = []
  for (let i = 0; i < familyChars.length; i++) {
    for (let j = i + 1; j < familyChars.length; j++) {
      const ai = positions.findIndex((p) => p.character.id === familyChars[i].id)
      const bi = positions.findIndex((p) => p.character.id === familyChars[j].id)
      if (ai !== -1 && bi !== -1) {
        familyPairs.push({
          a: positions[ai], b: positions[bi],
          delay: nodeDelay(Math.max(ai, bi)) + NODE_DURATION,
        })
      }
    }
  }

  return (
    <svg className="relationship-diagram" viewBox={`0 0 ${WIDTH} ${HEIGHT}`} width="100%" height={HEIGHT}>
      {familyPairs.map((pair, i) => (
        <line
          key={`family-${i}`}
          className="relationship-diagram-line"
          style={{ animationDelay: `${pair.delay}s`, animationDuration: `${LINE_DURATION}s` }}
          x1={pair.a.x} y1={pair.a.y} x2={pair.b.x} y2={pair.b.y}
          stroke="var(--line)" strokeWidth="1"
        />
      ))}
      {positions.map(({ character, x, y, delay }) => (
        <line
          key={`spoke-${character.id}`}
          className="relationship-diagram-line"
          style={{ animationDelay: `${delay + NODE_DURATION}s`, animationDuration: `${LINE_DURATION}s` }}
          x1={CENTER_X} y1={CENTER_Y} x2={x} y2={y}
          stroke="var(--line)" strokeWidth="1.5"
        />
      ))}
      <g className="relationship-diagram-center">
        <circle cx={CENTER_X} cy={CENTER_Y} r={CENTER_NODE_RADIUS} fill="var(--accent)" />
        <ProfileIcon
          icon={normalizeProfileIcon(profile.emoji)}
          size={22}
          color="var(--surface)"
          x={CENTER_X - 11}
          y={CENTER_Y - 11}
        />
        <text
          x={CENTER_X} y={CENTER_Y + CENTER_NODE_RADIUS + 14}
          textAnchor="middle" fontSize="12" fontWeight="bold" fill="var(--text)"
        >
          {profile.name}
        </text>
      </g>
      {positions.map(({ character, x, y, delay }) => (
        <g
          key={character.id}
          className="relationship-diagram-node"
          style={{ animationDelay: `${delay}s`, animationDuration: `${NODE_DURATION}s` }}
          onClick={() => onOpenMemories(character.id)}
        >
          <circle cx={x} cy={y} r={nodeRadius} fill={avatarColor(character.name)} />
          <text
            x={x} y={y} textAnchor="middle" dominantBaseline="central"
            fontSize={nodeRadius * 0.8} fontWeight="600" fill="var(--text)"
          >
            {initialLetter(character.name)}
          </text>
          <text x={x} y={y + nodeRadius + 12} textAnchor="middle" fontSize="11" fill="var(--text)">
            {character.name}
          </text>
        </g>
      ))}
    </svg>
  )
}

export default RelationshipDiagram
