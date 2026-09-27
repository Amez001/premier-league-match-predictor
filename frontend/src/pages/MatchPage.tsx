import { useEffect, useState } from 'react'
import { api, type Prediction } from '../api'
import { ClubCrest } from '../components/ClubCrest'
import { HBarChart } from '../components/HBarChart'
import { OutcomeBar } from '../components/OutcomeBar'
import { ScoreHeatmap } from '../components/ScoreHeatmap'
import { TeamPicker } from '../components/TeamPicker'
import { int, num2, pct } from '../format'

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

  // Predict as soon as the fixture changes: there's no button to press.
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
      <h1 className="sr-only">
        Prédiction : {home} contre {away}
      </h1>

      <section className={`fixture${loading ? ' is-loading' : ''}`} aria-busy={loading}>
        <div className="fixture-row">
          <div className="fixture-team">
            <ClubCrest team={home} size={76} />
            <div className="fixture-team-text">
              <TeamPicker label="Équipe à domicile" teams={teams} value={home} onChange={setHome} disabledTeam={away} />
              <span className="fixture-meta tabular">Domicile{p && <> · Elo {int(Math.round(p.elo_home))}</>}</span>
            </div>
          </div>

          <button type="button" className="swap" onClick={swap} aria-label="Inverser domicile et extérieur">
            <svg width="20" height="20" viewBox="0 0 24 24" aria-hidden="true">
              <path d="M4 8h15m0 0l-4-4m4 4l-4 4M20 16H5m0 0l4-4m-4 4l4 4" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          </button>

          <div className="fixture-team fixture-team-away">
            <div className="fixture-team-text">
              <TeamPicker label="Équipe à l'extérieur" teams={teams} value={away} onChange={setAway} disabledTeam={home} align="right" />
              <span className="fixture-meta tabular">Extérieur{p && <> · Elo {int(Math.round(p.elo_away))}</>}</span>
            </div>
            <ClubCrest team={away} size={76} />
          </div>
        </div>

        {error && <p className="error">{error}</p>}

        {p && <OutcomeBar home={p.home_team} away={p.away_team} pHome={p.home_win_proba} pDraw={p.draw_proba} pAway={p.away_win_proba} />}
      </section>

      {p && (
        <div className="columns">
          <section className="module">
            <h2>Buts attendus</h2>
            <div className="xg">
              <div className="xg-side">
                <span className="xg-value tabular">{num2(p.expected_goals_home)}</span>
                <span className="xg-team">
                  <i className="swatch swatch-home" aria-hidden="true" />
                  {p.home_team}
                </span>
              </div>
              <div className="xg-bars" aria-hidden="true">
                <span className="xg-bar xg-bar-home" style={{ flexGrow: p.expected_goals_home }} />
                <span className="xg-bar xg-bar-away" style={{ flexGrow: p.expected_goals_away }} />
              </div>
              <div className="xg-side xg-side-away">
                <span className="xg-value tabular">{num2(p.expected_goals_away)}</span>
                <span className="xg-team">
                  {p.away_team}
                  <i className="swatch swatch-away" aria-hidden="true" />
                </span>
              </div>
            </div>

            <h2 className="module-subhead">Scores les plus probables</h2>
            <ol className="top-scores">
              {p.most_likely_scores.map((s) => (
                <li key={`${s.home_goals}-${s.away_goals}`}>
                  <span className="top-score tabular">
                    {s.home_goals}–{s.away_goals}
                  </span>
                  <span className="top-score-bar" aria-hidden="true">
                    <span style={{ width: `${(s.probability / p.most_likely_scores[0].probability) * 100}%` }} />
                  </span>
                  <span className="top-score-p tabular">{pct(s.probability)}</span>
                </li>
              ))}
            </ol>
          </section>

          <section className="module">
            <h2>Grille des scores</h2>
            <ScoreHeatmap home={p.home_team} away={p.away_team} matrix={p.score_matrix} />
          </section>
        </div>
      )}

      {p && (
        <section className="module">
          <h2>Buteurs probables</h2>
          <p className="module-note">Probabilité de marquer au moins un but dans ce match.</p>
          {p.top_scorers_home.length === 0 && p.top_scorers_away.length === 0 ? (
            <p className="muted">
              Pas encore de données joueurs : lance <code>python scripts/download_player_data.py</code>.
            </p>
          ) : (
            <div className="columns">
              {[
                { team: p.home_team, scorers: p.top_scorers_home, tone: 'home' as const },
                { team: p.away_team, scorers: p.top_scorers_away, tone: 'away' as const },
              ].map(({ team, scorers, tone }) => (
                <div key={team}>
                  <h3 className="team-heading">
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
