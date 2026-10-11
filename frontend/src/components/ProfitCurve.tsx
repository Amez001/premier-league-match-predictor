import { useEffect, useId, useMemo, useRef, useState } from 'react'
import { longDate, money } from '../format'
import { useTooltipApi } from './Tooltip'

interface Props {
  /** cumulative profit in stakes after each round: [date, profit] */
  curve: [string, number][]
  stake: number
  label: string
  /** label the x axis by year (many seasons) rather than by date */
  byYear: boolean
}

const W = 720
const H = 240
const PAD = { top: 16, right: 70, bottom: 28, left: 58 }

/** 1, 2 or 5 times a power of ten, giving about `target` intervals. */
function niceStep(range: number, target = 4): number {
  if (range <= 0) return 1
  const raw = range / target
  const magnitude = 10 ** Math.floor(Math.log10(raw))
  const r = raw / magnitude
  return (r > 5 ? 10 : r > 2 ? 5 : r > 1 ? 2 : 1) * magnitude
}

const SHORT_MONTH = new Intl.DateTimeFormat('fr-FR', { day: 'numeric', month: 'short' })

/**
 * Cumulative profit of one strategy over time. One series on one axis: the
 * line, with the area to zero shaded by sign (diverging pair: gain above the
 * zero line, loss below), and the final value labelled at the end. A
 * crosshair (mouse or arrow keys) reads any round's running total.
 */
export function ProfitCurve({ curve, stake, label, byYear }: Props) {
  const clipId = useId()
  const dotRef = useRef<SVGCircleElement>(null)
  // show/hide are stable callbacks; the context object itself changes on every tooltip update
  const { show, hide } = useTooltipApi()
  const [active, setActive] = useState<number | null>(null)

  const points = useMemo(() => {
    if (curve.length === 0) return []
    // start from zero a few days before the first settled round
    const start = Date.parse(curve[0][0]) - 4 * 86_400_000
    return [{ t: start, date: null as string | null, v: 0 }, ...curve.map(([d, v]) => ({ t: Date.parse(d), date: d, v: v * stake }))]
  }, [curve, stake])

  const geometry = useMemo(() => {
    if (points.length < 2) return null
    const t0 = points[0].t
    const t1 = points[points.length - 1].t
    const values = points.map((p) => p.v)
    const step = niceStep(Math.max(...values, 0) - Math.min(...values, 0) || 1)
    const lo = Math.floor(Math.min(...values, 0) / step) * step
    const hi = Math.ceil(Math.max(...values, 0) / step) * step || step
    const x = (t: number) => PAD.left + ((t - t0) / (t1 - t0 || 1)) * (W - PAD.left - PAD.right)
    const y = (v: number) => PAD.top + ((hi - v) / (hi - lo || 1)) * (H - PAD.top - PAD.bottom)
    const yTicks: number[] = []
    for (let v = lo; v <= hi + step / 2; v += step) yTicks.push(v)

    const xTicks: { x: number; text: string }[] = []
    if (byYear) {
      const first = new Date(t0).getFullYear()
      const last = new Date(t1).getFullYear()
      const every = last - first > 8 ? 2 : 1
      for (let year = first + 1; year <= last; year += every) xTicks.push({ x: x(new Date(year, 0, 1).getTime()), text: String(year) })
    } else {
      const settled = points.slice(1)
      const every = Math.max(1, Math.ceil(settled.length / 6))
      settled.forEach((p, i) => i % every === 0 && xTicks.push({ x: x(p.t), text: SHORT_MONTH.format(new Date(p.t)) }))
    }

    const line = points.map((p) => `${x(p.t).toFixed(1)},${y(p.v).toFixed(1)}`).join(' ')
    const area = `${x(t0)},${y(0)} ${line} ${x(t1)},${y(0)}`
    return { x, y, yTicks, xTicks, line, area, zero: y(0) }
  }, [points, byYear])

  useEffect(() => {
    if (active === null || !dotRef.current) return
    const p = points[active]
    show(
      <>
        <strong>{p.date ? longDate(p.date) : 'Départ'}</strong>
        <span>{money(p.v)} au total</span>
      </>,
      dotRef.current,
    )
  }, [active, points, show])

  if (!geometry) return <p className="muted small-note">Pas assez de paris pour tracer une courbe.</p>
  const { x, y, yTicks, xTicks, line, area, zero } = geometry
  const last = points[points.length - 1]

  const nearest = (clientX: number, svg: SVGSVGElement) => {
    const box = svg.getBoundingClientRect()
    const vx = ((clientX - box.left) / box.width) * W
    let best = 0
    points.forEach((p, i) => {
      if (Math.abs(x(p.t) - vx) < Math.abs(x(points[best].t) - vx)) best = i
    })
    return best
  }
  const clear = () => {
    setActive(null)
    hide()
  }

  return (
    <figure className="profit-curve">
      <svg
        viewBox={`0 0 ${W} ${H}`}
        role="img"
        aria-label={`${label} : ${money(last.v)} au total. Flèches gauche et droite pour parcourir.`}
        tabIndex={0}
        onMouseMove={(e) => setActive(nearest(e.clientX, e.currentTarget))}
        onMouseLeave={clear}
        onFocus={() => setActive(points.length - 1)}
        onBlur={clear}
        onKeyDown={(e) => {
          if (e.key === 'ArrowLeft') setActive((i) => Math.max(0, (i ?? points.length) - 1))
          if (e.key === 'ArrowRight') setActive((i) => Math.min(points.length - 1, (i ?? -1) + 1))
        }}
      >
        <defs>
          <clipPath id={`${clipId}-above`}>
            <rect x={0} y={0} width={W} height={zero} />
          </clipPath>
          <clipPath id={`${clipId}-below`}>
            <rect x={0} y={zero} width={W} height={H - zero} />
          </clipPath>
        </defs>

        {yTicks.map((v) => (
          <g key={v}>
            <line x1={PAD.left} x2={W - PAD.right} y1={y(v)} y2={y(v)} className={v === 0 ? 'pc-zero' : 'pc-grid'} />
            <text x={PAD.left - 8} y={y(v)} className="pc-tick" textAnchor="end" dominantBaseline="middle">
              {v === 0 ? '0 $' : money(v)}
            </text>
          </g>
        ))}
        {xTicks.map((t) => (
          <text key={t.text + t.x} x={t.x} y={H - 8} className="pc-tick" textAnchor="middle">
            {t.text}
          </text>
        ))}

        <polygon points={area} className="pc-area-gain" clipPath={`url(#${clipId}-above)`} />
        <polygon points={area} className="pc-area-loss" clipPath={`url(#${clipId}-below)`} />
        <polyline points={line} className="pc-line" />

        <text x={x(last.t) + 8} y={y(last.v)} className="pc-end" dominantBaseline="middle">
          {money(last.v)}
        </text>

        {active !== null && (
          <g pointerEvents="none">
            <line x1={x(points[active].t)} x2={x(points[active].t)} y1={PAD.top} y2={H - PAD.bottom} className="pc-cross" />
            <circle ref={dotRef} cx={x(points[active].t)} cy={y(points[active].v)} r={4.5} className="pc-dot" />
          </g>
        )}
      </svg>
    </figure>
  )
}
