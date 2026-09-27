import { clubColor } from '../data/clubColors'
import type { Prediction } from '../api'

interface Props {
  prediction: Prediction
}

export function OutcomeProbabilities({ prediction }: Props) {
  const rows = [
    { label: `${prediction.home_team} win`, value: prediction.home_win_proba, color: clubColor(prediction.home_team) },
    { label: 'Draw', value: prediction.draw_proba, color: '#8a8a8a' },
    { label: `${prediction.away_team} win`, value: prediction.away_win_proba, color: clubColor(prediction.away_team) },
  ]

  return (
    <div className="outcome-probabilities">
      {rows.map((row) => (
        <div className="outcome-row" key={row.label}>
          <div className="outcome-row-header">
            <span>{row.label}</span>
            <span className="outcome-row-value">{(row.value * 100).toFixed(1)}%</span>
          </div>
          <div className="outcome-bar-track">
            <div
              className="outcome-bar-fill"
              style={{ width: `${row.value * 100}%`, background: row.color }}
            />
          </div>
        </div>
      ))}
    </div>
  )
}
