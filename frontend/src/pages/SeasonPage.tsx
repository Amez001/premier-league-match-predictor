import type { Awards, SeasonSimulation } from '../api'
import { AwardTable } from '../components/AwardTable'
import { ClubCrest } from '../components/ClubCrest'
import { HBarChart } from '../components/HBarChart'
import { PositionStrip, PositionStripHeader } from '../components/PositionStrip'
import { int, num1, pct, signed } from '../format'

const MIN_SHOWN = 0.001 // only chart clubs with at least a 0.1% chance...
const MAX_SHOWN = 8 // ...and at most 8 of them

export function SeasonPage({ sim, awards }: { sim: SeasonSimulation | null; awards: Awards | null }) {
  if (!sim) {
    return (
      <div className="page">
        <p className="muted">Chargement de la simulation…</p>
      </div>
    )
  }

  const rows = sim.projections
  const total = sim.matches_played + sim.matches_remaining
  const season = `${sim.season_start_year}-${String((sim.season_start_year + 1) % 100).padStart(2, '0')}`
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
        <h1>Projection de fin de saison {season}</h1>
        <p className="standfirst">
          Les {int(sim.matches_remaining)} matchs restants, rejoués {int(sim.n_sims)} fois à partir du modèle de buts.
          Chaque probabilité est la part des saisons simulées où l'événement se produit.
        </p>
      </header>

      <dl className="figures">
        <div className="figure">
          <dt>Favori pour le titre</dt>
          <dd className="figure-value figure-team">
            <ClubCrest team={favourite.team} size={30} />
            {favourite.team}
          </dd>
          <dd className="figure-sub tabular">{pct(favourite.p_title)} des saisons simulées</dd>
        </div>
        <div className="figure">
          <dt>Matchs joués</dt>
          <dd className="figure-value tabular">
            {int(sim.matches_played)}
            <span className="figure-of"> / {int(total)}</span>
          </dd>
          <dd className="figure-sub">
            <span className="progress" aria-hidden="true">
              <span style={{ width: `${(sim.matches_played / total) * 100}%` }} />
            </span>
          </dd>
        </div>
        <div className="figure">
          <dt>Saisons simulées</dt>
          <dd className="figure-value tabular">{int(sim.n_sims)}</dd>
          <dd className="figure-sub tabular">{int(sim.matches_remaining * sim.n_sims)} matchs tirés au sort</dd>
        </div>
      </dl>

      <div className="columns">
        <section className="module">
          <h2>Titre</h2>
          <p className="module-note">Probabilité de finir premier.</p>
          <HBarChart tone="home" data={titleRace.map((r) => ({ key: r.team, team: r.team, label: r.team, value: r.p_title }))} />
        </section>
        <section className="module">
          <h2>Relégation</h2>
          <p className="module-note">Probabilité de finir dans les trois derniers.</p>
          <HBarChart tone="away" data={relegation.map((r) => ({ key: r.team, team: r.team, label: r.team, value: r.p_relegation }))} />
        </section>
      </div>

      <div className="columns">
        <section className="module">
          <h2>Meilleur buteur</h2>
          <p className="module-note">Probabilité de finir meilleur buteur ; en cas d'égalité, le titre est partagé.</p>
          <AwardTable tone="home" unit="buts" rows={awards?.top_scorer ?? []} />
        </section>
        <section className="module">
          <h2>Meilleur passeur</h2>
          <p className="module-note">Probabilité de finir avec le plus de passes décisives.</p>
          <AwardTable tone="away" unit="passes" rows={awards?.top_assister ?? []} />
        </section>
      </div>

      <section className="module">
        <div className="module-head-row">
          <div>
            <h2>Classement projeté</h2>
            <p className="module-note">Trié par points attendus en fin de saison.</p>
          </div>
          <div className="scale-legend">
            <span>Probabilité de finir à la place</span>
            <span className="tabular">0 %</span>
            <span className="scale-legend-ramp" aria-hidden="true" />
            <span className="tabular">≥ 50 %</span>
          </div>
        </div>

        <div className="table-scroll">
          <table className="data-table projection-table">
            <thead>
              <tr>
                <th className="num">#</th>
                <th>Équipe</th>
                <th className="num" title="Matchs joués">
                  J
                </th>
                <th className="num" title="Points actuels">
                  Pts
                </th>
                <th className="num" title="Points attendus en fin de saison">
                  Pts proj.
                </th>
                <th className="num" title="Différence de buts attendue">
                  Diff. proj.
                </th>
                <th className="num">Titre</th>
                <th className="num">Top 4</th>
                <th className="num">Relég.</th>
                <th className="pos-col">
                  <PositionStripHeader n={nTeams} />
                </th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r, i) => (
                <tr key={r.team} className={i === 3 || i === nTeams - 4 ? 'zone-edge' : ''}>
                  <td className="num muted tabular">{i + 1}</td>
                  <td>
                    <span className="team-cell">
                      <ClubCrest team={r.team} size={20} />
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
        <p className="footnote">
          La force de chaque équipe est figée pour toute la simulation : blessures, transferts et changements de forme ne
          sont pas modélisés, et l'incertitude sur la force elle-même n'est pas propagée. Les probabilités du favori sont
          donc un peu trop tranchées, surtout en début de saison. Voir la <a href="#/methode">méthode</a>.
        </p>
      </section>
    </div>
  )
}
