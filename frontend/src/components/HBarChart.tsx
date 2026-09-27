import type { ReactNode } from 'react'
import { pct } from '../format'
import { ClubCrest } from './ClubCrest'
import { useTooltip } from './Tooltip'

export interface HBarDatum {
  key: string
  label: string
  value: number
  /** optional crest shown before the label */
  team?: string
  /** optional secondary text under/after the label (position, etc.) */
  meta?: string
  tooltip?: ReactNode
}

interface Props {
  data: HBarDatum[]
  tone: 'home' | 'away'
  /** shared scale max, so two charts side by side are comparable */
  max?: number
}

function Row({ d, tone, max }: { d: HBarDatum; tone: Props['tone']; max: number }) {
  const tip = useTooltip(
    d.tooltip ?? (
      <>
        <strong>{d.label}</strong>
        <span>{pct(d.value)}</span>
      </>
    ),
  )
  return (
    <li className="hbar-row" tabIndex={0} aria-label={`${d.label} : ${pct(d.value)}`} {...tip}>
      <span className="hbar-label">
        {d.team && <ClubCrest team={d.team} size={20} />}
        <span className="hbar-name">{d.label}</span>
        {d.meta && <span className="chip">{d.meta}</span>}
      </span>
      <span className="hbar-track">
        <span className={`hbar-fill hbar-fill-${tone}`} style={{ width: `${Math.max(0.6, (d.value / max) * 100)}%` }} />
      </span>
      <span className="hbar-value tabular">{pct(d.value)}</span>
    </li>
  )
}

/**
 * Single-series horizontal bars: one hue for every bar (never a value ramp
 * on nominal categories), thin rounded-end marks, value at the tip in ink.
 */
export function HBarChart({ data, tone, max }: Props) {
  const scaleMax = max ?? Math.max(...data.map((d) => d.value), 1e-9)
  return (
    <ul className="hbar">
      {data.map((d) => (
        <Row key={d.key} d={d} tone={tone} max={scaleMax} />
      ))}
    </ul>
  )
}
