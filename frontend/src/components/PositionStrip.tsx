import { pct } from '../format'
import { useTooltip } from './Tooltip'

const TOP_ZONE = 4
const RELEGATION_ZONE = 3

function Cell({ team, position, p, n }: { team: string; position: number; p: number; n: number }) {
  // Sequential, absolute scale (same for every row) so rows are comparable:
  // full opacity at >= 50% to finish in one given position.
  const alpha = p === 0 ? 0 : 0.08 + 0.92 * Math.min(1, p / 0.5)
  const zone = position <= TOP_ZONE ? ' zone-top' : position > n - RELEGATION_ZONE ? ' zone-releg' : ''
  const tip = useTooltip(
    <>
      <strong>
        {team} · {position}
        <sup>{position === 1 ? 'er' : 'e'}</sup>
      </strong>
      <span>{pct(p)} des simulations</span>
    </>,
  )
  return (
    <span
      className={`pos-cell${zone}`}
      style={{ background: alpha ? `rgba(var(--seq-rgb), ${alpha.toFixed(3)})` : undefined }}
      tabIndex={0}
      aria-label={`${team} termine ${position}e : ${pct(p)}`}
      {...tip}
    />
  )
}

/** One team's distribution of final league positions (1st -> 20th). */
export function PositionStrip({ team, probs }: { team: string; probs: number[] }) {
  return (
    <span className="pos-strip" role="group" aria-label={`Distribution des positions finales de ${team}`}>
      {probs.map((p, i) => (
        <Cell key={i} team={team} position={i + 1} p={p} n={probs.length} />
      ))}
    </span>
  )
}

export function PositionStripHeader({ n }: { n: number }) {
  return (
    <span className="pos-strip pos-strip-header" aria-hidden="true">
      {Array.from({ length: n }, (_, i) => (
        <span key={i} className="pos-cell-label">
          {i === 0 || i === TOP_ZONE - 1 || i === n - RELEGATION_ZONE || i === n - 1 ? i + 1 : ''}
        </span>
      ))}
    </span>
  )
}
