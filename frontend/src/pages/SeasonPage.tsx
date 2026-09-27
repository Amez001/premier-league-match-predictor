import type { SeasonSimulation } from '../api'
import { ClubCrest } from '../components/ClubCrest'
import { HBarChart } from '../components/HBarChart'
import { PositionStrip, PositionStripHeader } from '../components/PositionStrip'
import { int, num1, pct, signed } from '../format'

const MIN_SHOWN = 0.001 // only chart clubs with at least a 0.1% chance...
const MAX_SHOWN = 8 // ...and at most 8 of them

export function SeasonPage({ sim }: { sim: SeasonSimulation | null }) {
  if (!sim) {
    return (
      <div className="page">
        <p className="muted">Chargement de la simulation…</p>
      </div>
    )
  }

  const rows = sim.projections
  const total = sim.matches_played + sim.matches_remaining
  const favourite = rows.reduce((a, b) => (b.p_title > a.p_title ? b : a))
  const titleRace = [...rows]
    .sort((a, b) => b.p_title - a.p_title)
    .filter((r) => r.p_title >= MIN_SHOWN)
    .slice(0, MAX_SHOWN)
  const relegation = [...rows]
    .sort((a, b) => b.p_relegation - a.p_relegation)
    .filter((r) => r.p_relegation >= MIN_SHOWN)
    .slice(0, MAX_SHOWN)
  const nTeams = rows.length

  return (
    <div className="page">
      <header className="page-header">
        <span className="eyebrow">Simulation de saison</span>
        <h1>Qui sera champion ?</h1>
        <p className="lede">
          On rejoue les {int(sim.matches_remaining)} matchs restants {int(sim.n_sims)} fois, en tirant chaque score
          au hasard selon le modèle Poisson, puis on compte l'issue de chaque saison simulée.
        </p>
      </header>

      <div className="stat-row">
        <div className="stat-tile">
          <span className="stat-label">Favori pour le titre</span>
          <span className="stat-value stat-value-team">
            <ClubCrest team={favourite.team} size={34} />
            {favourite.team}
          </span>
          <span className="stat-sub">{pct(favourite.p_title)} des saisons simulées</span>
        </div>
        <div className="stat-tile">
          <span className="stat-label">Matchs joués</span>
          <span className="stat-value">
            {int(sim.matches_played)}
            <span className="stat-value-of"> / {int(total)}</span>
          </span>
          <span className="progress" aria-hidden="true">
            <span style={{ width: `${(sim.matches_played / total) * 100}%` }} />
          </span>
        </div>
        <div className="stat-tile">
          <span className="stat-label">Saisons simulées</span>
          <span className="stat-value">{int(sim.n_sims)}</span>
          <span className="stat-sub">{int(sim.matches_remaining * sim.n_sims)} matchs tirés au sort</span>
        </div>
      </div>

      <div className="grid-2">
        <section className="card">
          <div className="card-head">
            <h2>Course au titre</h2>
            <p className="muted">Probabilité de finir 1er</p>
          </div>
          <HBarChart
            tone="home"
            data={titleRace.map((r) => ({ key: r.team, team: r.team, label: r.team, value: r.p_title }))}
          />
        </section>
        <section className="card">
          <div className="card-head">
            <h2>Lutte pour le maintien</h2>
            <p className="muted">Probabilité de finir dans les 3 derniers</p>
          </div>
          <HBarChart
            tone="away"
            data={relegation.map((r) => ({ key: r.team, team: r.team, label: r.team, value: r.p_relegation }))}
          />
        </section>
      </div>

      <section className="card">
        <div className="card-head card-head-row">
          <div>
            <h2>Classement projeté</h2>
            <p className="muted">Trié par points attendus en fin de saison</p>
          </div>
          <div className="scale-legend">
            <span>Probabilité de finir à cette place</span>
            <span>0 %</span>
            <span className="scale-legend-ramp" aria-hidden="true" />
            <span>≥ 50 %</span>
          </div>
        </div>

        <div className="table-scroll">
          <table className="projection-table">
            <thead>
              <tr>
                <th className="num">#</th>
                <th>Équipe</th>
                <th className="num" title="Matchs joués">J</th>
                <th className="num" title="Points actuels">Pts</th>
                <th className="num" title="Points attendus en fin de saison">Pts proj.</th>
                <th className="num" title="Différence de buts attendue">Diff. proj.</th>
                <th className="num">Titre</th>
                <th className="num">Top 4</th>
                <th className="num">Relégation</th>
                <th className="pos-col">
                  <PositionStripHeader n={nTeams} />
                </th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r, i) => (
                <tr key={r.team} className={i === 3 ? 'sep-after' : i === nTeams - 4 ? 'sep-after' : ''}>
                  <td className="num muted tabular">{i + 1}</td>
                  <td>
                    <span className="team-cell">
                      <ClubCrest team={r.team} size={22} />
                      {r.team}
                    </span>
                  </td>
                  <td className="num tabular muted">{r.played}</td>
                  <td className="num tabular">{r.current_points}</td>
                  <td className="num tabular strong">{num1(r.expected_points)}</td>
                  <td className="num tabular muted">{signed(r.expected_goal_diff)}</td>
                  <td className="num tabular">{pct(r.p_title)}</td>
                  <td className="num tabular">{pct(r.p_top4)}</td>
                  <td className="num tabular">{pct(r.p_relegation)}</td>
                  <td className="pos-col">
                    <PositionStrip team={r.team} probs={r.position_probs} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <aside className="callout">
        <strong>À lire avec prudence.</strong> La force de chaque équipe est figée pour toute la simulation :
        blessures, transferts et changements de forme ne sont pas modélisés, et l'incertitude sur la force
        elle-même n'est pas propagée. Les probabilités du favori sont donc un peu trop tranchées, surtout en
        début de saison. Détails dans <a href="#/methode">la méthode</a>.
      </aside>
    </div>
  )
}
