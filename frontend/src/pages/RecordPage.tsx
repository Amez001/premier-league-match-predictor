import type { HitBlock, RecordMatch, RecordSummary, TrackRecord } from '../api'
import { ClubCrest } from '../components/ClubCrest'
import { CumulativeChart, type CumulativePoint } from '../components/CumulativeChart'
import { HitMark } from '../components/HitMark'
import { num1, num2, pct, shortDate } from '../format'

type BlockKey = 'outcome' | 'exact' | 'scorer_favourite'

/** Running totals after each matchweek. Weekly hit counts are independent,
 *  so their variances add: the cumulative 80% range comes from the summed
 *  variance, not from adding up the weekly ranges. */
function cumulative(weeks: TrackRecord['weeks'], key: BlockKey): CumulativePoint[] {
  let hits = 0
  let n = 0
  let expected = 0
  let variance = 0
  // A matchweek with nothing to score for this block (e.g. scorers before any
  // player data) adds no point - carrying the last value forward would draw
  // a flat line that looks like stability the data doesn't show.
  return weeks
    .filter((w) => w[key].n > 0)
    .map((w) => {
      const b = w[key]
      const sd = (b.expected_high - b.expected) / 1.28
      hits += b.hits
      n += b.n
      expected += b.expected
      variance += sd * sd
      const half = 1.28 * Math.sqrt(variance)
      return { week: w.week, hits, n, expected, expected_low: Math.max(0, expected - half), expected_high: expected + half }
    })
}

function Verdict({ b }: { b: HitBlock }) {
  if (b.n === 0) return null
  const [cls, label] =
    b.hits < b.expected_low
      ? ['is-below', 'En dessous de l’attendu']
      : b.hits > b.expected_high
        ? ['is-above', 'Au-dessus de l’attendu']
        : ['is-within', 'Dans la fourchette attendue']
  return <span className={`verdict ${cls}`}>{label}</span>
}

function Figure({ label, b, unit }: { label: string; b: HitBlock; unit: string }) {
  return (
    <div className="figure">
      <dt>{label}</dt>
      {b.n > 0 ? (
        <>
          <dd className="figure-value tabular">
            {b.hits}
            <span className="figure-of"> / {b.n}</span>
          </dd>
          <dd className="figure-sub tabular">
            {pct(b.hits / b.n)} · attendu {Math.round(b.expected_low)} à {Math.round(b.expected_high)} {unit}
          </dd>
          <dd>
            <Verdict b={b} />
          </dd>
        </>
      ) : (
        <dd className="figure-sub">Pas encore de données.</dd>
      )}
    </div>
  )
}

const outcomeLabel = (m: RecordMatch, r: 'H' | 'D' | 'A') => (r === 'H' ? m.home_team : r === 'A' ? m.away_team : 'Nul')
const pOf = (m: RecordMatch, r: 'H' | 'D' | 'A') => (r === 'H' ? m.p_home : r === 'A' ? m.p_away : m.p_draw)

function ScorerPickCell({ picks }: { picks: RecordMatch['scorers_home'] }) {
  const fav = picks[0]
  if (!fav) return <span className="muted">—</span>
  return (
    <span className="pick" title={`${fav.player} : ${pct(fav.probability)} de marquer`}>
      <HitMark hit={fav.scored} />
      <span className="pick-name">{fav.player}</span>
      <span className="pick-p tabular">{pct(fav.probability)}</span>
    </span>
  )
}

function MatchRow({ m, firstWeek }: { m: RecordMatch; firstWeek: number }) {
  const scorers = m.actual_scorers
    .map((s) => (s.goals > 1 ? `${s.player} (${s.goals})` : s.player))
    .join(', ')
  return (
    <li className="rec-match">
      <div className="rec-fixture">
        <span className="rec-date tabular">{shortDate(m.date)}</span>
        <span className="rec-team rec-home">
          {m.home_team}
          <ClubCrest team={m.home_team} size={20} />
        </span>
        <span className="rec-score tabular">
          {m.home_goals}–{m.away_goals}
        </span>
        <span className="rec-team">
          <ClubCrest team={m.away_team} size={20} />
          {m.away_team}
        </span>
      </div>
      <div className="rec-preds">
        <span className="rec-pred">
          <span className="rec-label">Pronostic</span>
          <HitMark hit={m.outcome_hit} />
          <span>{outcomeLabel(m, m.favourite)}</span>
          <span className="pick-p tabular">{pct(m.p_favourite)}</span>
          {!m.outcome_hit && (
            <span className="rec-actual-p tabular">
              ({outcomeLabel(m, m.actual)} : {pct(pOf(m, m.actual))})
            </span>
          )}
        </span>
        <span className="rec-pred">
          <span className="rec-label">Score</span>
          <HitMark hit={m.exact_hit} />
          <span className="tabular">
            {m.predicted_score[0]}–{m.predicted_score[1]}
          </span>
          <span className="pick-p tabular">{pct(m.p_predicted_score)}</span>
        </span>
        {m.scorers_known ? (
          <span className="rec-pred rec-scorers">
            <span className="rec-label">Buteurs</span>
            <ScorerPickCell picks={m.scorers_home} />
            <ScorerPickCell picks={m.scorers_away} />
          </span>
        ) : (
          <span className="rec-pred rec-scorers muted">
            <span className="rec-label">Buteurs</span>
            {m.week === firstWeek ? 'Pas de pronostic (1re journée)' : 'Données buteurs à venir'}
          </span>
        )}
      </div>
      {scorers && <div className="rec-actual-scorers">Buts : {scorers}</div>}
    </li>
  )
}

function WeekHeader({ w }: { w: RecordSummary & { week: number } }) {
  return (
    <div className="module-head-row">
      <h2>Journée {w.week}</h2>
      <p className="module-note tabular">
        {w.outcome.hits}/{w.outcome.n} bons résultats (attendu {num1(w.outcome.expected)}) · {w.exact.hits} score
        {w.exact.hits > 1 ? 's' : ''} exact{w.exact.hits > 1 ? 's' : ''}
        {w.scorer_favourite.n > 0 && (
          <>
            {' '}
            · buteur favori {w.scorer_favourite.hits}/{w.scorer_favourite.n}
          </>
        )}
      </p>
    </div>
  )
}

export function RecordPage({ record }: { record: TrackRecord | null }) {
  if (!record) {
    return (
      <div className="page">
        <p className="muted">Chargement du bilan…</p>
      </div>
    )
  }
  if (!record.matches || record.matches.length === 0) {
    return (
      <div className="page">
        <header className="page-header">
          <h1>Bilan des prédictions</h1>
        </header>
        <p className="muted">
          Pas encore de bilan : lance <code>python scripts/download_match_players.py</code> puis{' '}
          <code>python scripts/build_track_record.py</code>.
        </p>
      </div>
    )
  }

  const o = record.overall
  const weeksDesc = [...record.weeks].sort((a, b) => b.week - a.week)
  const firstWeek = Math.min(...record.weeks.map((w) => w.week))

  return (
    <div className="page">
      <header className="page-header">
        <h1>Bilan des prédictions</h1>
        <p className="standfirst">
          Avant chaque journée, le modèle est reconstruit avec les seules données disponibles à ce moment-là, puis
          confronté aux vrais résultats. {o.matches} matchs sur {record.weeks.length} journées.
        </p>
      </header>

      <dl className="figures figures-4">
        <Figure label="Bon résultat (V/N/D)" b={o.outcome} unit="" />
        <Figure label="Score exact" b={o.exact} unit="" />
        <Figure label="Buteur favori a marqué" b={o.scorer_favourite} unit="" />
        <div className="figure">
          <dt>Log loss</dt>
          <dd className="figure-value tabular">{o.log_loss !== null ? num2(o.log_loss) : '—'}</dd>
          <dd className="figure-sub tabular">
            {o.log_loss_reference !== null && <>référence {num2(o.log_loss_reference)} (plus bas = mieux)</>}
          </dd>
          {o.log_loss !== null && o.log_loss_reference !== null && (
            <dd>
              <span className={`verdict ${o.log_loss < o.log_loss_reference ? 'is-above' : 'is-below'}`}>
                {o.log_loss < o.log_loss_reference ? 'Meilleur que la référence' : 'Moins bon que la référence'}
              </span>
            </dd>
          )}
        </div>
      </dl>

      <section className="module">
        <div className="module-head-row">
          <div>
            <h2>Au fil des journées</h2>
            <p className="module-note">
              Taux de réussite cumulé, comparé à ce que nos propres probabilités annonçaient.
            </p>
          </div>
          <div className="legend">
            <span className="legend-item">
              <i className="legend-line" aria-hidden="true" />
              Réel
            </span>
            <span className="legend-item">
              <i className="legend-band" aria-hidden="true" />
              Attendu (8 fois sur 10 dans la bande)
            </span>
          </div>
        </div>
        <div className="cum-grid-3">
          <CumulativeChart title="Bon résultat" points={cumulative(record.weeks, 'outcome')} yMax={1} />
          <CumulativeChart title="Score exact" points={cumulative(record.weeks, 'exact')} yMax={0.4} />
          <CumulativeChart title="Buteur favori" points={cumulative(record.weeks, 'scorer_favourite')} yMax={0.8} />
        </div>
        <p className="footnote">
          Avec quelques dizaines de matchs, un écart de quelques points avec l’attendu relève du hasard. Ce qui compte,
          c’est que la ligne reste dans la bande. Les buteurs ne sont pronostiqués qu’à partir de la 2<sup>e</sup>{' '}
          journée : avant, personne n’a encore joué. Le bilan est recalculé avec le modèle actuel.
        </p>
      </section>

      {weeksDesc.map((w) => (
        <section key={w.week} className="module">
          <WeekHeader w={w} />
          <ul className="rec-list">
            {record.matches
              .filter((m) => m.week === w.week)
              .map((m) => (
                <MatchRow key={`${m.home_team}-${m.away_team}`} m={m} firstWeek={firstWeek} />
              ))}
          </ul>
        </section>
      ))}
    </div>
  )
}
