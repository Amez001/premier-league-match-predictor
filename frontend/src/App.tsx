import { useEffect, useState } from 'react'
import './App.css'
import { api, type BacktestRow, type Prediction } from './api'
import { BacktestTable } from './components/BacktestTable'
import { ExpectedGoalsCard } from './components/ExpectedGoalsCard'
import { OutcomeProbabilities } from './components/OutcomeProbabilities'
import { ScorelineTable } from './components/ScorelineTable'
import { ScorersList } from './components/ScorersList'
import { TeamSelect } from './components/TeamSelect'

export default function App() {
  const [teams, setTeams] = useState<string[]>([])
  const [home, setHome] = useState('Arsenal')
  const [away, setAway] = useState('Liverpool')
  const [prediction, setPrediction] = useState<Prediction | null>(null)
  const [backtest, setBacktest] = useState<BacktestRow[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [showBacktest, setShowBacktest] = useState(false)

  useEffect(() => {
    api
      .getTeams()
      .then((fetched) => {
        setTeams(fetched)
        if (fetched.length >= 2) {
          const h = fetched.includes('Arsenal') ? 'Arsenal' : fetched[0]
          const a = fetched.includes('Liverpool') ? 'Liverpool' : fetched[1]
          setHome(h)
          setAway(a)
        }
      })
      .catch((err: Error) => setError(err.message))
  }, [])

  useEffect(() => {
    api.getBacktestSummary().then(setBacktest).catch(() => setBacktest([]))
  }, [])

  const runPrediction = () => {
    setLoading(true)
    setError(null)
    api
      .predict(home, away)
      .then(setPrediction)
      .catch((err: Error) => setError(err.message))
      .finally(() => setLoading(false))
  }

  return (
    <div className="app">
      <header className="app-header">
        <h1>⚽ Premier League Match Predictor</h1>
        <p className="muted">
          Elo + logistic regression for match outcome, Poisson goals model for the scoreline and probable scorers.
        </p>
      </header>

      <section className="card team-picker">
        <TeamSelect label="Home team" teams={teams} value={home} onChange={setHome} disabledTeam={away} />
        <TeamSelect label="Away team" teams={teams} value={away} onChange={setAway} disabledTeam={home} />
        <button className="predict-button" onClick={runPrediction} disabled={loading || teams.length === 0}>
          {loading ? 'Predicting...' : 'Predict'}
        </button>
      </section>

      {error && <p className="error">{error}</p>}

      {prediction && (
        <section className="card result">
          <h2>
            {prediction.home_team} vs {prediction.away_team}
          </h2>

          <OutcomeProbabilities prediction={prediction} />
          <p className="predicted-result">
            Predicted result: <strong>{prediction.predicted_result}</strong>
          </p>

          <h3>Expected goals</h3>
          <ExpectedGoalsCard prediction={prediction} />

          <h3>Most likely scorelines</h3>
          <ScorelineTable scores={prediction.most_likely_scores} />

          <h3>Most likely scorers</h3>
          <div className="scorers-columns">
            <ScorersList team={prediction.home_team} scorers={prediction.top_scorers_home} />
            <ScorersList team={prediction.away_team} scorers={prediction.top_scorers_away} />
          </div>

          <p className="muted small">
            Elo rating gap ({prediction.home_team} - {prediction.away_team}): {prediction.elo_diff >= 0 ? '+' : ''}
            {prediction.elo_diff.toFixed(0)}
          </p>
        </section>
      )}

      <section className="card">
        <button className="link-button" onClick={() => setShowBacktest((v) => !v)}>
          {showBacktest ? '▾' : '▸'} Model backtest performance
        </button>
        {showBacktest && <BacktestTable rows={backtest} />}
      </section>
    </div>
  )
}
