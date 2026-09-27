import { ClubCrest } from './ClubCrest'

export interface LeaderRow {
  key: string
  player: string
  team: string
  value: number
  /** secondary figure shown under the name, e.g. "2 passes" next to goals */
  note?: string
}

interface Props {
  rows: LeaderRow[]
  tone: 'home' | 'away'
  /** accessible unit for the value, e.g. "buts" */
  unit: string
  /** players level with the last row but not listed */
  moreTied?: number
}

/**
 * Ranked leaderboard of a real count (goals, assists). Players level on the
 * count share a rank ("=") - the leaderboard never invents an order the data
 * doesn't have. Bars share one scale so the gaps read at a glance.
 */
export function LeaderList({ rows, tone, unit, moreTied = 0 }: Props) {
  if (rows.length === 0) {
    return (
      <p className="muted">
        Pas encore de données joueurs : lance <code>python scripts/download_player_data.py</code>.
      </p>
    )
  }
  const max = Math.max(...rows.map((r) => r.value), 1)
  const last = rows[rows.length - 1].value

  return (
    <>
      <ol className="leaders">
        {rows.map((r, i) => {
          const rank = rows.findIndex((o) => o.value === r.value) + 1
          const tied = i > 0 && rows[i - 1].value === r.value
          return (
            <li key={r.key} className="leader" aria-label={`${rank === 1 ? '1er' : `${rank}e`}, ${r.player} (${r.team}) : ${r.value} ${unit}`}>
              <span className="leader-rank tabular">{tied ? '=' : rank}</span>
              <ClubCrest team={r.team} size={22} />
              <span className="leader-who">
                <span className="leader-name">{r.player}</span>
                <span className="leader-team">
                  {r.team}
                  {r.note && <> · {r.note}</>}
                </span>
              </span>
              <span className="leader-bar" aria-hidden="true">
                <span className={`leader-bar-fill leader-bar-${tone}`} style={{ width: `${(r.value / max) * 100}%` }} />
              </span>
              <span className="leader-value tabular">{r.value}</span>
            </li>
          )
        })}
      </ol>
      {moreTied > 0 && (
        <p className="leaders-more">
          Et {moreTied} autre{moreTied > 1 ? 's' : ''} joueur{moreTied > 1 ? 's' : ''} à {last} {unit}.
        </p>
      )}
    </>
  )
}
