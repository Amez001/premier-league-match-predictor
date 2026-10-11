import { int, money } from '../format'
import { useTooltip } from './Tooltip'

interface SeasonProfit {
  season: number
  n_bets: number
  profit: number
}

const W = 720
const H = 170
const PAD = { top: 18, right: 8, bottom: 40, left: 8 }  // room below for the worst season's label

const seasonShort = (s: number) => `${String(s % 100).padStart(2, '0')}-${String((s + 1) % 100).padStart(2, '0')}`

/** A bar from the zero line to `v`: square at the baseline, 3px rounded at the data end. */
function barPath(x: number, w: number, y0: number, y1: number): string {
  const r = Math.min(3, w / 2, Math.abs(y1 - y0))
  if (y1 < y0) {
    return `M${x},${y0} V${y1 + r} Q${x},${y1} ${x + r},${y1} H${x + w - r} Q${x + w},${y1} ${x + w},${y1 + r} V${y0} Z`
  }
  return `M${x},${y0} V${y1 - r} Q${x},${y1} ${x + r},${y1} H${x + w - r} Q${x + w},${y1} ${x + w},${y1 - r} V${y0} Z`
}

function Bar({ d, x, w, y0, y1, stake }: { d: SeasonProfit; x: number; w: number; y0: number; y1: number; stake: number }) {
  const value = d.profit * stake
  const tip = useTooltip(
    <>
      <strong>Saison {d.season}-{String((d.season + 1) % 100).padStart(2, '0')}</strong>
      <span>
        {money(value)} sur {int(d.n_bets)} paris
      </span>
    </>,
  )
  return (
    <g tabIndex={0} {...tip} aria-label={`Saison ${d.season} : ${money(value)}`}>
      <rect x={x - 3} y={PAD.top} width={w + 6} height={H - PAD.top - PAD.bottom} fill="transparent" />
      <path d={barPath(x, w, y0, y1)} className={value >= 0 ? 'sb-gain' : 'sb-loss'} />
    </g>
  )
}

/**
 * Profit season by season for one strategy: one bar per season from the
 * zero line, gain above and loss below (diverging pair). Only the best and
 * worst seasons are labelled; every value is in the hover/focus tooltip.
 */
export function SeasonBars({ data, stake }: { data: SeasonProfit[]; stake: number }) {
  if (data.length === 0) return null
  const values = data.map((d) => d.profit * stake)
  const hi = Math.max(...values, 0)
  const lo = Math.min(...values, 0)
  const span = hi - lo || 1
  const y = (v: number) => PAD.top + ((hi - v) / span) * (H - PAD.top - PAD.bottom)
  const band = (W - PAD.left - PAD.right) / data.length
  const w = Math.min(28, band * 0.6)
  const best = values.indexOf(Math.max(...values))
  const worst = values.indexOf(Math.min(...values))

  return (
    <figure className="season-bars">
      <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label="Gain ou perte, saison par saison">
        <line x1={PAD.left} x2={W - PAD.right} y1={y(0)} y2={y(0)} className="pc-zero" />
        {data.map((d, i) => {
          const cx = PAD.left + band * i + band / 2
          const v = values[i]
          return (
            <g key={d.season}>
              <Bar d={d} x={cx - w / 2} w={w} y0={y(0)} y1={y(v)} stake={stake} />
              {(i === best || i === worst) && v !== 0 && (
                <text x={cx} y={v >= 0 ? y(v) - 6 : y(v) + 13} className="sb-label" textAnchor="middle">
                  {money(v)}
                </text>
              )}
              <text x={cx} y={H - 6} className="pc-tick" textAnchor="middle">
                {seasonShort(d.season)}
              </text>
            </g>
          )
        })}
      </svg>
    </figure>
  )
}
