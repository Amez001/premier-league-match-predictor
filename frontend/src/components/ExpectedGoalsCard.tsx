import type { Prediction } from '../api'

interface Props {
  prediction: Prediction
}

export function ExpectedGoalsCard({ prediction }: Props) {
  return (
    <div className="stat-row">
      <div className="stat-card">
        <span className="stat-card-label">{prediction.home_team}</span>
        <span className="stat-card-value">{prediction.expected_goals_home.toFixed(2)}</span>
      </div>
      <div className="stat-card">
        <span className="stat-card-label">{prediction.away_team}</span>
        <span className="stat-card-value">{prediction.expected_goals_away.toFixed(2)}</span>
      </div>
    </div>
  )
}
