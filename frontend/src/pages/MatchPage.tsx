import { useEffect, useState } from 'react'
import { api, type Prediction } from '../api'
import { ClubCrest } from '../components/ClubCrest'
import { HBarChart } from '../components/HBarChart'
import { OutcomeBar } from '../components/OutcomeBar'
import { ScoreHeatmap } from '../components/ScoreHeatmap'
import { TeamPicker } from '../components/TeamPicker'
import { num2, pct, signed } from '../format'

const POSITION_FR: Record<string, string> = { FW: 'ATT', MF: 'MIL', DF: 'DÉF', GK: 'GB' }
const positionLabel = (pos: string) => POSITION_FR[pos.split(',')[0]] ?? pos

export function MatchPage({ teams }: { teams: string[] }) {
  const [home, setHome] = useState('Arsenal')
  const [away, setAway] = useState('Liverpool')
  const [prediction, setPrediction] = useState<Prediction | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Fall back to the first clubs in the list if Arsenal / Liverpool
  // aren't in this season's division.
  useEffect(() => {
    if (teams.length < 2) return
    const h = teams.includes(home) ? home : teams[0]
    const a = teams.includes(away) && away !== h ? away : teams.find((t) => t !== h)!
    setHome(h)
    setAway(a)
  }, [teams]) // eslint-disable-line react-hooks/exhaustive-deps

  // Predict as soon as the fixture changes: no "Predict" button to press.
  useEffect(() => {
    if (!teams.includes(home) || !teams.includes(away) || home === away) return
    let cancelled = false
    setLoading(true)
    setError(null)
    api
      .predict(home, away)
      .then((p) => !cancelled && setPrediction(p))
      .catch((e: Error) => !cancelled && setError(e.message))
      .finally(() => !cancelled && setLoading(false))
    return () => {
      cancelled = true
    }
  }, [home, away, teams])

  const swap = () => {
    setHome(away)
    setAway(home)
  }

  const p = prediction
  const scorerMax = p
    ? Math.max(...p.top_scorers_home.map((s) => s.scorer_probability), ...p.top_scorers_away.map((s) => s.scorer_probability), 1e-9)
    : 1

  return (
    <div className="page">
      <header className="page-header">
        <span className="eyebrow">Prédiction de match</span>
        <h1>Qui gagne ce match ?</h1>
        <p className="lede">
          Choisis deux équipes : le modèle estime l'issue, le score et les buteurs les plus probables.
        </p>
      </header>

      <section className={`card matchup${loading ? ' is-loading' : ''}`} aria-busy={loading}>
        <div className="matchup-teams">
          <div className="matchup-side">
            <ClubCrest team={home} size={96} />
            <TeamPicker label="Domicile" teams={teams} value={home} onChange={setHome} disabledTeam={away} />
          </div>

          <div className="matchup-center">
            <button type="button" className="swap-button" onClick={swap} aria-label="Inverser domicile et extérieur" title="Inverser domicile / extérieur">
              <svg width="18" height="18" viewBox="0 0 24 24" aria-hidden="true">
                <path d="M7 7h13l-4-4M17 17H4l4 4" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
            </button>
            <span className="vs">VS</span>
            {p && (
              <span className="elo-chip" title="Écart de rating Elo (domicile − extérieur)">
                Elo {signed(p.elo_diff)}
              </span>
            )}
          </div>

          <div className="matchup-side">
            <ClubCrest team={away} size={96} />
            <TeamPicker label="Extérieur" teams={teams} value={away} onChange={setAway} disabledTeam={home} align="right" />
          </div>
        </div>

        {error && <p className="error">{error}</p>}

        {p && (
          <OutcomeBar home={p.home_team} away={p.away_team} pHome={p.home_win_proba} pDraw={p.draw_proba} pAway={p.away_win_proba} />
        )}
      </section>

      {p && (
        <div className="grid-2">
          <section className="card">
            <div className="card-head">
              <h2>Buts attendus</h2>
              <p className="muted">Moyenne de buts prévue par le modèle Poisson</p>
            </div>
            <div className="xg">
              <div className="xg-side">
                <span className="xg-team">
                  <i className="swatch swatch-home" aria-hidden="true" />
                  {p.home_team}
                </span>
                <span className="xg-value">{num2(p.expected_goals_home)}</span>
              </div>
              <div className="xg-bars" aria-hidden="true">
                <span className="xg-bar xg-bar-home" style={{ flexGrow: p.expected_goals_home }} />
                <span className="xg-bar xg-bar-away" style={{ flexGrow: p.expected_goals_away }} />
              </div>
              <div className="xg-side xg-side-right">
                <span className="xg-team">
                  {p.away_team}
                  <i className="swatch swatch-away" aria-hidden="true" />
                </span>
                <span className="xg-value">{num2(p.expected_goals_away)}</span>
              </div>
            </div>

            <div className="card-head card-head-spaced">
              <h2>Scores les plus probables</h2>
            </div>
            <ol className="top-scores">
              {p.most_likely_scores.map((s, i) => (
                <li key={`${s.home_goals}-${s.away_goals}`} className={i === 0 ? 'is-first' : ''}>
                  <span className="top-score tabular">
                    {s.home_goals} – {s.away_goals}
                  </span>
                  <span className="top-score-p tabular">{pct(s.probability)}</span>
                </li>
              ))}
            </ol>
          </section>

          <section className="card">
            <div className="card-head">
              <h2>Grille des scores</h2>
              <p className="muted">Probabilité de chaque score exact</p>
            </div>
            <ScoreHeatmap home={p.home_team} away={p.away_team} matrix={p.score_matrix} />
          </section>
        </div>
      )}

      {p && (
        <section className="card">
          <div className="card-head">
            <h2>Buteurs probables</h2>
            <p className="muted">Probabilité de marquer au moins un but dans ce match</p>
          </div>
          {p.top_scorers_home.length === 0 && p.top_scorers_away.length === 0 ? (
            <p className="muted">
              Pas encore de données joueurs : lance <code>python scripts/download_player_data.py</code>.
            </p>
          ) : (
            <div className="grid-2 grid-2-tight">
              {[
                { team: p.home_team, scorers: p.top_scorers_home, tone: 'home' as const },
                { team: p.away_team, scorers: p.top_scorers_away, tone: 'away' as const },
              ].map(({ team, scorers, tone }) => (
                <div key={team}>
                  <h3 className="subhead">
                    <ClubCrest team={team} size={22} />
                    {team}
                  </h3>
                  <HBarChart
                    tone={tone}
                    max={scorerMax}
                    data={scorers.map((s) => ({
                      key: s.player,
                      label: s.player,
                      meta: positionLabel(s.position),
                      value: s.scorer_probability,
                      tooltip: (
                        <>
                          <strong>{s.player}</strong>
                          <span>
                            {pct(s.scorer_probability)} de marquer · {num2(s.lambda_goals)} but attendu
                          </span>
                        </>
                      ),
                    }))}
                  />
                </div>
              ))}
            </div>
          )}
        </section>
      )}
    </div>
  )
}
