import type { Scoreline } from '../api'

interface Props {
  scores: Scoreline[]
}

export function ScorelineTable({ scores }: Props) {
  return (
    <table className="data-table">
      <thead>
        <tr>
          <th>Score</th>
          <th>Probability</th>
        </tr>
      </thead>
      <tbody>
        {scores.map((s) => (
          <tr key={`${s.home_goals}-${s.away_goals}`}>
            <td>
              {s.home_goals}-{s.away_goals}
            </td>
            <td>{(s.probability * 100).toFixed(1)}%</td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}
