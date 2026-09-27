import type { BacktestRow } from '../api'

interface Props {
  rows: BacktestRow[]
}

export function BacktestTable({ rows }: Props) {
  if (rows.length === 0) {
    return (
      <p className="muted">
        No backtest results yet - run <code>python scripts/run_backtest.py</code>.
      </p>
    )
  }

  const sorted = [...rows].sort((a, b) => parseFloat(a.log_loss) - parseFloat(b.log_loss))

  return (
    <table className="data-table">
      <thead>
        <tr>
          <th>Model</th>
          <th>Accuracy</th>
          <th>Log loss</th>
          <th>Brier score</th>
        </tr>
      </thead>
      <tbody>
        {sorted.map((row) => (
          <tr key={row.model}>
            <td>{row.model}</td>
            <td>{(parseFloat(row.accuracy) * 100).toFixed(1)}%</td>
            <td>{parseFloat(row.log_loss).toFixed(4)}</td>
            <td>{parseFloat(row.brier_score).toFixed(4)}</td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}
