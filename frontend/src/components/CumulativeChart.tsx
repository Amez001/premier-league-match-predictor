import { useTooltip } from './Tooltip'
import { num1, pct } from '../format'

export interface CumulativePoint {
  week: number
  hits: number
  n: number
  expected: number
  expected_low: number
  expected_high: number
}

interface Props {
  title: string
  points: CumulativePoint[]
  /** top of the y axis, as a rate (e.g. 1 for 100%) */
  yMax: number
}

const W = 320
const H = 170
const PAD = { top: 12, right: 44, bottom: 26, left: 34 }

function Dot({ x, y, p, title }: { x: number; y: number; p: CumulativePoint; title: string }) {
  const tip = useTooltip(
    <>
      <strong>
        {title}, après la journée {p.week}
      </strong>
      <span>
        {p.hits} sur {p.n} ({pct(p.hits / p.n)})
      </span>
      <span>
        attendu {num1(p.expected)} (entre {Math.round(p.expected_low)} et {Math.round(p.expected_high)})
      </span>
    </>,
  )
  return (
    <g tabIndex={0} {...tip} aria-label={`Journée ${p.week} : ${p.hits} sur ${p.n}`}>
      <circle cx={x} cy={y} r={12} fill="transparent" />
      <circle cx={x} cy={y} r={4} className="cum-dot" />
    </g>
  )
}

/**
 * Cumulative hit rate after each matchweek (line) against the 80% range our
 * own probabilities predicted (band). One series + one reference band on a
 * single axis; the legend lives with the small multiples (RecordPage).
 */
export function CumulativeChart({ title, points, yMax }: Props) {
  const usable = points.filter((p) => p.n > 0)
  if (usable.length === 0) {
    return (
      <figure className="cum-chart">
        <figcaption>{title}</figcaption>
        <p className="muted small-note">Pas encore de données.</p>
      </figure>
    )
  }

  const weeks = usable.map((p) => p.week)
  const minW = Math.min(...weeks)
  const maxW = Math.max(...weeks)
  const x = (w: number) =>
    maxW === minW ? PAD.left + (W - PAD.left - PAD.right) / 2 : PAD.left + ((w - minW) / (maxW - minW)) * (W - PAD.left - PAD.right)
  const y = (rate: number) => PAD.top + (1 - Math.min(rate, yMax) / yMax) * (H - PAD.top - PAD.bottom)

  const band =
    usable.map((p) => `${x(p.week)},${y(p.expected_high / p.n)}`).join(' ') +
    ' ' +
    [...usable].reverse().map((p) => `${x(p.week)},${y(p.expected_low / p.n)}`).join(' ')
  const expectedLine = usable.map((p) => `${x(p.week)},${y(p.expected / p.n)}`).join(' ')
  const actualLine = usable.map((p) => `${x(p.week)},${y(p.hits / p.n)}`).join(' ')
  const last = usable[usable.length - 1]
  const ticks = [0, yMax / 2, yMax]

  return (
    <figure className="cum-chart">
      <figcaption>{title}</figcaption>
      <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label={`${title} : ${last.hits} sur ${last.n}, attendu ${num1(last.expected)}`}>
        {ticks.map((t) => (
          <g key={t}>
            <line x1={PAD.left} x2={W - PAD.right} y1={y(t)} y2={y(t)} className="cum-grid" />
            <text x={PAD.left - 6} y={y(t)} className="cum-tick" textAnchor="end" dominantBaseline="middle">
              {Math.round(t * 100)} %
            </text>
          </g>
        ))}
        {weeks.map((w) => (
          <text key={w} x={x(w)} y={H - 8} className="cum-tick" textAnchor="middle">
            J{w}
          </text>
        ))}
        {usable.length > 1 ? (
          <polygon points={band} className="cum-band" />
        ) : (
          // a single matchweek has no width to draw a band across: show the range as a bar
          <rect
            x={x(last.week) - 10}
            width={20}
            y={y(last.expected_high / last.n)}
            height={y(last.expected_low / last.n) - y(last.expected_high / last.n)}
            className="cum-band"
          />
        )}
        <polyline points={expectedLine} className="cum-expected" />
        <polyline points={actualLine} className="cum-actual" />
        {usable.map((p) => (
          <Dot key={p.week} x={x(p.week)} y={y(p.hits / p.n)} p={p} title={title} />
        ))}
        <text x={x(last.week) + 9} y={y(last.hits / last.n)} className="cum-end-label" dominantBaseline="middle">
          {Math.round((last.hits / last.n) * 100)} %
        </text>
      </svg>
    </figure>
  )
}
