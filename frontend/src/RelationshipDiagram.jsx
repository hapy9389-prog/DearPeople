import { relationEmoji, avatarColor } from './format'

const WIDTH = 320
const HEIGHT = 280
const CENTER_X = WIDTH / 2
const CENTER_Y = 132
const ORBIT_RADIUS = 92
const CENTER_NODE_RADIUS = 32

function RelationshipDiagram({ profile, characters, onOpenMemories }) {
  const nodeRadius = characters.length > 6 ? 20 : 26

  const positions = characters.map((c, i) => {
    const angle = (-90 + (360 / characters.length) * i) * (Math.PI / 180)
    return {
      character: c,
      x: CENTER_X + ORBIT_RADIUS * Math.cos(angle),
      y: CENTER_Y + ORBIT_RADIUS * Math.sin(angle),
    }
  })

  const familyChars = characters.filter((c) => c.grp === 'family')
  const familyPairs = []
  for (let i = 0; i < familyChars.length; i++) {
    for (let j = i + 1; j < familyChars.length; j++) {
      const a = positions.find((p) => p.character.id === familyChars[i].id)
      const b = positions.find((p) => p.character.id === familyChars[j].id)
      if (a && b) familyPairs.push([a, b])
    }
  }

  return (
    <svg className="relationship-diagram" viewBox={`0 0 ${WIDTH} ${HEIGHT}`} width="100%" height={HEIGHT}>
      {familyPairs.map(([a, b], i) => (
        <line
          key={`family-${i}`}
          x1={a.x} y1={a.y} x2={b.x} y2={b.y}
          stroke="var(--line)" strokeWidth="1"
        />
      ))}
      {positions.map(({ character, x, y }) => (
        <line
          key={`spoke-${character.id}`}
          x1={CENTER_X} y1={CENTER_Y} x2={x} y2={y}
          stroke="var(--line)" strokeWidth="1.5"
        />
      ))}
      <g>
        <circle cx={CENTER_X} cy={CENTER_Y} r={CENTER_NODE_RADIUS} fill="var(--accent)" />
        <text x={CENTER_X} y={CENTER_Y} textAnchor="middle" dominantBaseline="central" fontSize="20">
          {profile.emoji}
        </text>
        <text
          x={CENTER_X} y={CENTER_Y + CENTER_NODE_RADIUS + 14}
          textAnchor="middle" fontSize="12" fontWeight="bold" fill="var(--text)"
        >
          {profile.name}
        </text>
      </g>
      {positions.map(({ character, x, y }) => (
        <g
          key={character.id}
          className="relationship-diagram-node"
          onClick={() => onOpenMemories(character.id)}
        >
          <circle cx={x} cy={y} r={nodeRadius} fill={avatarColor(character.name)} />
          <text
            x={x} y={y} textAnchor="middle" dominantBaseline="central"
            fontSize={nodeRadius > 22 ? 16 : 13}
          >
            {relationEmoji(character.relation)}
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
