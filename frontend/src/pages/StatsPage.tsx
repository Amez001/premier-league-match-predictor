import type { Meta, Stats } from '../api'
import { ClubCrest } from '../components/ClubCrest'
import { FormGuide } from '../components/FormGuide'
import { LeaderList } from '../components/LeaderList'
import { int, longDate, num2, shortDate, signed } from '../format'

const TOTAL_MATCHES = 380
const TOP_ZONE = 4
const RELEGATION_ZONE = 3

const plural = (n: number, one: string, many: string) => `${n} ${n === 1 ? one : many}`

export function StatsPage({ stats, meta }: { stats: Stats | null; meta: Meta | null }) {
  if (!stats) {
    return (
      <div className="page">
        <p className="muted">Chargement des statistiques…</p>
      </div>
    )
  }

  const season = `${stats.season_start_year}-${String((stats.season_start_year + 1) % 100).padStart(2, '0')}`
  const leader = stats.table[0]
  const n = stats.table.length

  return (
    <div className="page">
      <header className="page-header">
        <h1>Premier League {season}</h1>
        <p className="standfirst">
          Les chiffres réels de la saison, sans modèle : classement, forme, derniers résultats, buteurs et passeurs
          {meta && <>, à jour au {longDate(meta.last_match_date)}</>}.
        </p>
      </header>

      <dl className="figures figures-4">
        <div className="figure">
          <dt>En tête</dt>
          <dd className="figure-value figure-team">
            <ClubCrest team={leader.team} size={30} />
            {leader.team}
          </dd>
          <dd className="figure-sub tabular">{plural(leader.points, 'point', 'points')}</dd>
        </div>
        <div className="figure">
          <dt>Matchs joués</dt>
          <dd className="figure-value tabular">
            {int(stats.matches_played)}
            <span className="figure-of"> / {TOTAL_MATCHES}</span>
          </dd>
          <dd className="figure-sub">
            <span className="progress" aria-hidden="true">
              <span style={{ width: `${(stats.matches_played / TOTAL_MATCHES) * 100}%` }} />
            </span>
          </dd>
        </div>
        <div className="figure">
          <dt>Buts marqués</dt>
          <dd className="figure-value tabular">{int(stats.total_goals)}</dd>
          <dd className="figure-sub tabular">{num2(stats.goals_per_match)} par match</dd>
        </div>
        <div className="figure">
          <dt>Meilleur buteur</dt>
          {stats.top_scorers.rows[0] ? (
            <>
              <dd className="figure-value figure-player">{stats.top_scorers.rows[0].player}</dd>
              <dd className="figure-sub tabular">
                {plural(stats.top_scorers.rows[0].goals, 'but', 'buts')} · {stats.top_scorers.rows[0].team}
              </dd>
            </>
          ) : (
            <dd className="figure-sub">—</dd>
          )}
        </div>
      </dl>

      <section className="module">
        <div className="module-head-row">
          <div>
            <h2>Classement</h2>
            <p className="module-note">
              Filets : fin du top {TOP_ZONE} et début de la zone de relégation.
            </p>
          </div>
        </div>
        <div className="table-scroll">
          <table className="data-table standings">
            <thead>
              <tr>
                <th className="num">#</th>
                <th>Équipe</th>
                <th className="num" title="Matchs joués">J</th>
                <th className="num" title="Victoires">G</th>
                <th className="num" title="Nuls">N</th>
                <th className="num" title="Défaites">P</th>
                <th className="num" title="Buts pour">BP</th>
                <th className="num" title="Buts contre">BC</th>
                <th className="num" title="Différence de buts">Diff.</th>
                <th className="num">Pts</th>
                <th className="form-col" title="5 derniers matchs, du plus ancien au plus récent">
                  Forme
                </th>
              </tr>
            </thead>
            <tbody>
              {stats.table.map((r, i) => (
                <tr key={r.team} className={i === TOP_ZONE - 1 || i === n - RELEGATION_ZONE - 1 ? 'zone-edge' : ''}>
                  <td className="num muted tabular">{i + 1}</td>
                  <td>
                    <span className="team-cell">
                      <ClubCrest team={r.team} size={20} />
                      {r.team}
                    </span>
                  </td>
                  <td className="num tabular muted">{r.played}</td>
                  <td className="num tabular">{r.won}</td>
                  <td className="num tabular">{r.drawn}</td>
                  <td className="num tabular">{r.lost}</td>
                  <td className="num tabular muted">{r.goals_for}</td>
                  <td className="num tabular muted">{r.goals_against}</td>
                  <td className="num tabular">{signed(r.goal_diff)}</td>
                  <td className="num tabular strong">{r.points}</td>
                  <td className="form-col">
                    <FormGuide form={r.form} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <div className="columns">
        <section className="module">
          <h2>Meilleurs buteurs</h2>
          <p className="module-note">Un joueur transféré cumule ses buts dans ses deux clubs.</p>
          <LeaderList
            tone="home"
            unit="buts"
            moreTied={stats.top_scorers.more_tied}
            rows={stats.top_scorers.rows.map((p) => ({
              key: `${p.player}-${p.team}`,
              player: p.player,
              team: p.team,
              value: p.goals,
              note: p.assists ? plural(p.assists, 'passe', 'passes') : undefined,
            }))}
          />
        </section>
        <section className="module">
          <h2>Meilleurs passeurs</h2>
          <p className="module-note">Passes décisives en Premier League cette saison.</p>
          <LeaderList
            tone="away"
            unit="passes décisives"
            moreTied={stats.top_assisters.more_tied}
            rows={stats.top_assisters.rows.map((p) => ({
              key: `${p.player}-${p.team}`,
              player: p.player,
              team: p.team,
              value: p.assists,
              note: p.goals ? plural(p.goals, 'but', 'buts') : undefined,
            }))}
          />
        </section>
      </div>

      <section className="module">
        <h2>Derniers résultats</h2>
        <ul className="results">
          {stats.recent_results.map((m) => (
            <li key={`${m.date}-${m.home_team}`} className="result">
              <span className="result-date tabular">{shortDate(m.date)}</span>
              <span className={`result-team result-home${m.home_goals > m.away_goals ? ' is-winner' : ''}`}>
                {m.home_team}
                <ClubCrest team={m.home_team} size={20} />
              </span>
              <span className="result-score tabular">
                {m.home_goals}–{m.away_goals}
              </span>
              <span className={`result-team${m.away_goals > m.home_goals ? ' is-winner' : ''}`}>
                <ClubCrest team={m.away_team} size={20} />
                {m.away_team}
              </span>
            </li>
          ))}
        </ul>
      </section>
    </div>
  )
}
