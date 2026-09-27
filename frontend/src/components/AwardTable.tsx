import type { AwardRow } from '../api'
import { num1, pct } from '../format'
import { ClubCrest } from './ClubCrest'
import { useTooltip } from './Tooltip'

interface Props {
  rows: AwardRow[]
  tone: 'home' | 'away'
  /** "buts" or "passes" */
  unit: string
}

function Row({ r, tone, unit, max }: { r: AwardRow; tone: Props['tone']; unit: string; max: number }) {
  const tip = useTooltip(
    <>
      <strong>{r.player}</strong>
      <span>
        {r.current} {unit} aujourd'hui · {num1(r.expected_final)} attendus en fin de saison
      </span>
      <span>
        8 saisons simulées sur 10 entre {Math.round(r.p10)} et {Math.round(r.p90)}
      </span>
    </>,
  )
  return (
    <tr tabIndex={0} {...tip}>
      <td>
        <span className="team-cell">
          <ClubCrest team={r.team} size={20} />
          <span className="award-who">
            <span>{r.player}</span>
            <span className="award-team">{r.team}</span>
          </span>
        </span>
      </td>
      <td className="num tabular">{r.current}</td>
      <td className="num tabular">
        <span className="strong">{Math.round(r.expected_final)}</span>
        <span className="award-range">
          {' '}
          {Math.round(r.p10)}–{Math.round(r.p90)}
        </span>
      </td>
      <td className="award-p">
        <span className="award-bar" aria-hidden="true">
          <span className={`hbar-fill hbar-fill-${tone}`} style={{ width: `${Math.max(0.8, (r.p_top / max) * 100)}%` }} />
        </span>
        <span className="tabular">{pct(r.p_top)}</span>
      </td>
    </tr>
  )
}

/**
 * Season-long award race: goals/assists today, the projected final tally
 * (with its 10th-90th percentile range across simulations) and the
 * probability of finishing top.
 */
export function AwardTable({ rows, tone, unit }: Props) {
  if (rows.length === 0) {
    return (
      <p className="muted">
        Pas encore de données joueurs : lance <code>python scripts/download_player_data.py</code>.
      </p>
    )
  }
  const max = Math.max(...rows.map((r) => r.p_top), 1e-9)
  return (
    <div className="table-scroll">
      <table className="data-table award-table">
        <thead>
          <tr>
            <th>Joueur</th>
            <th className="num" title={`Nombre de ${unit} aujourd'hui`}>
              Actuel
            </th>
            <th className="num" title="Total attendu en fin de saison, et intervalle où tombent 8 saisons simulées sur 10">
              Projection
            </th>
            <th>Probabilité</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <Row key={`${r.player}-${r.team}`} r={r} tone={tone} unit={unit} max={max} />
          ))}
        </tbody>
      </table>
    </div>
  )
}
