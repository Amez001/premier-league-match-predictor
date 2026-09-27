import type { Scorer } from '../api'

interface Props {
  team: string
  scorers: Scorer[]
}

export function ScorersList({ team, scorers }: Props) {
  if (scorers.length === 0) {
    return (
      <div className="scorers-list">
        <h4>{team}</h4>
        <p className="muted">
          No player data yet - run <code>python scripts/download_player_data.py</code>.
        </p>
      </div>
    )
  }

  return (
    <div className="scorers-list">
      <h4>{team}</h4>
      <table className="data-table">
        <tbody>
          {scorers.map((s) => (
            <tr key={s.player}>
              <td>{s.player}</td>
              <td>{(s.scorer_probability * 100).toFixed(1)}%</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
