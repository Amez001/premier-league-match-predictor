import { pct } from '../format'
import { useTooltip } from './Tooltip'

interface Props {
  home: string
  away: string
  matrix: number[][] // matrix[i][j] = P(home scores i, away scores j)
}

/** Only label cells above this, so the grid never turns into a wall of numbers. */
const LABEL_THRESHOLD = 0.04

function Cell({ i, j, p, max, home, away }: { i: number; j: number; p: number; max: number; home: string; away: string }) {
  // Sequential: one hue, opacity grows monotonically with probability.
  const alpha = 0.05 + 0.95 * (p / max)
  const outcome = i > j ? `Victoire ${home}` : i < j ? `Victoire ${away}` : 'Match nul'
  const tip = useTooltip(
    <>
      <strong>
        {home} {i} – {j} {away}
      </strong>
      <span>
        {pct(p)} · {outcome}
      </span>
    </>,
  )
  return (
    <div
      className={`score-cell${p === max ? ' is-max' : ''}${i === j ? ' is-draw' : ''}`}
      style={{ background: `rgba(var(--seq-rgb), ${alpha.toFixed(3)})` }}
      tabIndex={0}
      aria-label={`${home} ${i}, ${away} ${j} : ${pct(p)}`}
      {...tip}
    >
      {p >= LABEL_THRESHOLD && <span className="tabular">{Math.round(p * 100)}</span>}
    </div>
  )
}

export function ScoreHeatmap({ home, away, matrix }: Props) {
  const max = Math.max(...matrix.flat())
  const n = matrix.length

  return (
    <figure className="score-heatmap">
      <div className="score-heatmap-body">
        <div className="score-axis-y">
          <span>Buts {home}</span>
        </div>
        <div className="score-grid-wrap">
          <div className="score-axis-x-label">Buts {away}</div>
          <div className="score-grid" style={{ gridTemplateColumns: `28px repeat(${n}, 1fr)` }}>
            <div />
            {matrix[0].map((_, j) => (
              <div key={`x${j}`} className="score-tick">
                {j}
              </div>
            ))}
            {matrix.map((row, i) => (
              <div key={`row${i}`} className="score-grid-row">
                <div className="score-tick">{i}</div>
                {row.map((p, j) => (
                  <Cell key={j} i={i} j={j} p={p} max={max} home={home} away={away} />
                ))}
              </div>
            ))}
          </div>
        </div>
      </div>
      <figcaption className="scale-legend">
        <span>0 %</span>
        <span className="scale-legend-ramp" aria-hidden="true" />
        <span>{Math.round(max * 100)} %</span>
        <span className="muted">· valeurs en % affichées au-dessus de {LABEL_THRESHOLD * 100} %</span>
      </figcaption>
    </figure>
  )
}
