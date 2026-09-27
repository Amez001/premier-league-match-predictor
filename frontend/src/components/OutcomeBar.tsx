import { pct } from '../format'
import { useTooltip } from './Tooltip'

interface Props {
  home: string
  away: string
  pHome: number
  pDraw: number
  pAway: number
}

interface Segment {
  key: 'home' | 'draw' | 'away'
  label: string
  value: number
}

function BarSegment({ seg, isFirst, isLast }: { seg: Segment; isFirst: boolean; isLast: boolean }) {
  const tip = useTooltip(
    <>
      <strong>{seg.label}</strong>
      <span>{pct(seg.value)}</span>
    </>,
  )
  return (
    <div
      className={`outcome-seg outcome-seg-${seg.key}${isFirst ? ' is-first' : ''}${isLast ? ' is-last' : ''}`}
      style={{ flexGrow: seg.value }}
      tabIndex={0}
      aria-label={`${seg.label} : ${pct(seg.value)}`}
      {...tip}
    />
  )
}

/**
 * Part-to-whole of three outcomes: one stacked bar (2px surface gaps between
 * segments, no strokes) with the three numbers as large direct labels above
 * it - each paired with its swatch, so identity never rests on color alone.
 */
export function OutcomeBar({ home, away, pHome, pDraw, pAway }: Props) {
  const segs: Segment[] = [
    { key: 'home', label: `Victoire ${home}`, value: pHome },
    { key: 'draw', label: 'Match nul', value: pDraw },
    { key: 'away', label: `Victoire ${away}`, value: pAway },
  ]
  const favourite = segs.reduce((a, b) => (b.value > a.value ? b : a))

  return (
    <div className="outcome">
      <div className="outcome-figures">
        {segs.map((s) => (
          <div key={s.key} className={`outcome-figure outcome-figure-${s.key}${s === favourite ? ' is-favourite' : ''}`}>
            <span className="outcome-figure-label">
              <i className={`swatch swatch-${s.key}`} aria-hidden="true" />
              {s.label}
            </span>
            <span className="outcome-figure-value">{pct(s.value)}</span>
          </div>
        ))}
      </div>
      <div className="outcome-bar" role="img" aria-label={segs.map((s) => `${s.label} ${pct(s.value)}`).join(', ')}>
        {segs.map((s, i) => (
          <BarSegment key={s.key} seg={s} isFirst={i === 0} isLast={i === segs.length - 1} />
        ))}
      </div>
    </div>
  )
}
