import { useEffect, useState } from 'react'
import type { Betting, BettingPeriod, BettingRound, BettingSearch, BettingStrategy } from '../api'
import { ClubCrest } from '../components/ClubCrest'
import { HitMark } from '../components/HitMark'
import { ProfitCurve } from '../components/ProfitCurve'
import { SeasonBars } from '../components/SeasonBars'
import { int, money, num2, pct, shortDate } from '../format'

type PeriodKey = 'history' | 'season'
type SortKey = 'profit' | 'hit_rate' | 'roi'

const STAKE_KEY = 'pl-predictor.stake'
const DEFAULT_STAKE = 10
const COMBO_SIZES = ['2', '3', '4']

function readStake(): number {
  try {
    const v = Number(localStorage.getItem(STAKE_KEY))
    return v > 0 ? v : DEFAULT_STAKE
  } catch {
    return DEFAULT_STAKE
  }
}

const NBSP = '\u00a0'
const seasonLabel = (y: number) => `${y}-${String((y + 1) % 100).padStart(2, '0')}`
const num3 = (x: number) => x.toFixed(3).replace('.', ',')
/** "10 $", "2,50 $" */
const stakeLabel = (x: number) => `${Number.isInteger(x) ? int(x) : num2(x)}${NBSP}$`
/** "5 %" for a value-bet edge of 0.05 */
const edgeLabel = (x: number) => `${Math.round(x * 100)}${NBSP}%`

/** "+3,1 %", "−8,9 %", "0,0 %". */
function signedPct(x: number | null): string {
  if (x === null) return '—'
  if (Math.abs(x) < 0.0005) return `0,0${NBSP}%`
  return `${x > 0 ? '+' : '−'}${pct(Math.abs(x))}`
}

function GainCell({ value, max }: { value: number; max: number }) {
  const width = max > 0 ? Math.min(1, Math.abs(value) / max) * 50 : 0
  return (
    <span className="gain-cell">
      <span className="gain-track" aria-hidden="true">
        <span
          className={`gain-bar ${value >= 0 ? 'is-gain' : 'is-loss'}`}
          style={value >= 0 ? { left: '50%', width: `${width}%` } : { right: '50%', width: `${width}%` }}
        />
      </span>
      <span className="gain-value tabular">{money(value)}</span>
    </span>
  )
}

function SortHeader({
  label,
  k,
  sort,
  setSort,
  className,
}: {
  label: string
  k: SortKey
  sort: SortKey
  setSort: (k: SortKey) => void
  className?: string
}) {
  return (
    <th className={className} aria-sort={sort === k ? 'descending' : 'none'}>
      <button type="button" className={`sort-btn${sort === k ? ' is-active' : ''}`} onClick={() => setSort(k)}>
        {label}
        <svg width="8" height="8" viewBox="0 0 8 8" aria-hidden="true">
          <path d="M1 2.5l3 3 3-3" fill="none" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" />
        </svg>
      </button>
    </th>
  )
}

function StrategyTable({
  period,
  stake,
  selected,
  onSelect,
}: {
  period: BettingPeriod
  stake: number
  selected: string
  onSelect: (key: string) => void
}) {
  const [sort, setSort] = useState<SortKey>('profit')
  const rows = [...period.strategies].sort((a, b) => (b[sort] ?? -Infinity) - (a[sort] ?? -Infinity))
  const maxAbs = Math.max(...period.strategies.map((s) => Math.abs(s.profit * stake)), 1e-9)
  return (
    <div className="table-scroll">
      <table className="data-table bet-table">
        <thead>
          <tr>
            <th>Stratégie</th>
            <th className="num">Paris</th>
            <SortHeader label="Gagnés" k="hit_rate" sort={sort} setSort={setSort} className="num" />
            <th className="num">Cote moy.</th>
            <th className="num">Misé</th>
            <SortHeader label="Gain" k="profit" sort={sort} setSort={setSort} />
            <SortHeader label="Rendement" k="roi" sort={sort} setSort={setSort} className="num" />
          </tr>
        </thead>
        <tbody>
          {rows.map((s) => (
            <tr
              key={s.key}
              className={`bet-row${s.key === selected ? ' is-selected' : ''}`}
              tabIndex={0}
              aria-selected={s.key === selected}
              onClick={() => onSelect(s.key)}
              onKeyDown={(e) => (e.key === 'Enter' || e.key === ' ') && (e.preventDefault(), onSelect(s.key))}
            >
              <td className="bet-name-cell">
                <span className="bet-name">{s.name}</span>
                <span className="bet-desc">{s.description}</span>
              </td>
              <td className="num tabular">{int(s.n_bets)}</td>
              <td className="num tabular">{s.hit_rate !== null ? pct(s.hit_rate) : '—'}</td>
              <td className="num tabular">{s.avg_odds !== null ? num2(s.avg_odds) : '—'}</td>
              <td className="num tabular">{money(s.n_bets * stake).replace('+', '')}</td>
              <td>
                <GainCell value={s.profit * stake} max={maxAbs} />
              </td>
              <td className="num tabular">{signedPct(s.roi)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function StrategyDetail({ s, stake, period }: { s: BettingStrategy; stake: number; period: PeriodKey }) {
  if (s.n_bets === 0) {
    return <p className="muted">Aucun pari pour cette stratégie sur la période.</p>
  }
  return (
    <>
      <ProfitCurve curve={s.curve} stake={stake} label={`Gain cumulé, ${s.name}`} byYear={period === 'history'} />
      <dl className="bet-facts">
        <div>
          <dt>Paris gagnés</dt>
          <dd className="tabular">
            {int(s.n_won)} sur {int(s.n_bets)}
          </dd>
        </div>
        <div>
          <dt>Pire série</dt>
          <dd className="tabular">{int(s.longest_losing_streak)} paris perdus d'affilée</dd>
        </div>
        <div>
          <dt>Plus forte baisse</dt>
          <dd className="tabular">{money(-s.max_drawdown * stake)} depuis un sommet</dd>
        </div>
        <div>
          <dt>Promis par notre modèle</dt>
          <dd className="tabular">
            {signedPct(s.expected_roi)} <span className="muted">· obtenu {signedPct(s.roi)}</span>
          </dd>
        </div>
      </dl>
      {period === 'history' && s.by_season.length > 1 && (
        <>
          <h3 className="module-subhead bet-subhead">Saison par saison</h3>
          <SeasonBars data={s.by_season} stake={stake} />
        </>
      )}
    </>
  )
}

function Honesty({ betting }: { betting: Betting }) {
  const h = betting.honesty
  if (!h) return null
  const best = h.strategies.find((r) => r.key === h.best_first)
  if (!best) return null
  const first = `${seasonLabel(h.first[0])} à ${seasonLabel(h.first[1])}`
  const second = `${seasonLabel(h.second[0])} à ${seasonLabel(h.second[1])}`
  const edges = betting.value_edges.filter((e) => e.n_bets > 0)
  const loosest = edges[0]
  const strictest = edges[edges.length - 1]
  return (
    <section className="module">
      <h2>Le piège du rétroviseur</h2>
      <p className="module-note">Choisir la meilleure stratégie après coup, puis la jouer pour de vrai.</p>
      <div className="prose">
        <p>
          De {first}, la stratégie la plus rentable était « {best.name} », avec un rendement de{' '}
          <strong>{signedPct(best.roi_first)}</strong>. Quelqu'un qui l'aurait choisie pour les saisons suivantes
          aurait obtenu <strong>{signedPct(best.roi_second)}</strong> de {second}. Avec neuf stratégies, il y en a
          presque toujours une qui gagne pendant quelques saisons par chance : c'est le résultat sur les saisons
          suivantes qui compte.
        </p>
        {loosest && strictest && loosest !== strictest && loosest.roi !== null && strictest.roi !== null && (
          <p>
            {strictest.roi <= loosest.roi ? "Être plus exigeant n'aide pas non plus." : 'Être plus exigeant aide un peu.'}{' '}
            Les paris de valeur au seuil de {edgeLabel(loosest.edge)} rendent {signedPct(loosest.roi)} sur{' '}
            {int(loosest.n_bets)} paris ; au seuil de {edgeLabel(strictest.edge)}, {signedPct(strictest.roi)} sur{' '}
            {int(strictest.n_bets)}.
            {strictest.roi <= loosest.roi &&
              " Quand notre modèle s'écarte beaucoup du marché, c'est le plus souvent lui qui se trompe."}
          </p>
        )}
      </div>
      <div className="table-scroll">
        <table className="data-table honesty-table">
          <thead>
            <tr>
              <th>Stratégie</th>
              <th className="num">{first}</th>
              <th className="num">{second}</th>
            </tr>
          </thead>
          <tbody>
            {[...h.strategies]
              .sort((a, b) => b.profit_first - a.profit_first)
              .map((r) => (
                <tr key={r.key} className={r.key === h.best_first ? 'is-best' : ''}>
                  <td>{r.name}</td>
                  <td className="num tabular">{signedPct(r.roi_first)}</td>
                  <td className="num tabular">{signedPct(r.roi_second)}</td>
                </tr>
              ))}
          </tbody>
        </table>
      </div>
      <p className="footnote">Rendement : gain ou perte divisé par la somme misée.</p>
    </section>
  )
}

function SearchVerdict({ search }: { search: BettingSearch }) {
  const wf = search.walk_forward
  const luck = search.luck
  if (!wf || !luck) return null
  const foundInTime = wf.profit > 0
  const beatsLuck = luck.share_as_good < 0.05
  let text: string
  if (!foundInTime && !beatsLuck) {
    text =
      'Les combinaisons gagnantes sont celles que le hasard a favorisées. La recherche ne les trouvait pas à temps, et le hasard seul en produit d’aussi belles : rien n’indique un vrai filon.'
  } else if (!foundInTime) {
    text =
      'La meilleure combinaison fait mieux que le hasard, mais personne ne l’aurait choisie à temps : celles qui brillaient sur les saisons précédentes ont perdu ensuite.'
  } else if (!beatsLuck) {
    text =
      'Choisir la meilleure combinaison du passé a payé, mais le hasard seul produit d’aussi beaux résultats : c’est peut-être de la chance.'
  } else {
    text =
      'La meilleure combinaison bat le hasard et aurait été trouvée à temps : un signal à surveiller, pas encore une preuve.'
  }
  return <p className="search-verdict">{text}</p>
}

function CombinationSearch({ search, stake }: { search: BettingSearch; stake: number }) {
  const top = search.top
  if (top.length === 0) return null
  const maxAbs = Math.max(...top.map((t) => Math.abs(t.profit * stake)), 1e-9)
  const wf = search.walk_forward
  const luck = search.luck
  const first = search.seasons[0]
  return (
    <section className="module">
      <h2>Les combinaisons qui auraient rapporté le plus</h2>
      <p className="module-note">
        {int(search.n_combinations)} combinaisons de critères testées depuis {seasonLabel(first)} : type de pari, seuil de
        notre probabilité, fourchette de cotes, valeur minimale, combinés de 2 à 5 matchs. Parmi les{' '}
        {int(search.n_ranked)} qui comptent au moins {search.min_bets} paris, {int(search.n_profitable)} finissent
        gagnantes. Voici les dix meilleures, avec {stakeLabel(stake)} par pari.
      </p>
      <div className="table-scroll">
        <table className="data-table search-table">
          <thead>
            <tr>
              <th className="num">#</th>
              <th>Combinaison</th>
              <th className="num">Paris</th>
              <th className="num">Gagnés</th>
              <th className="num">Cote moy.</th>
              <th>Gain</th>
              <th className="num">Rendement</th>
              <th className="num">Saisons gagnantes</th>
            </tr>
          </thead>
          <tbody>
            {top.map((t, i) => (
              <tr key={t.name}>
                <td className="num tabular muted">{i + 1}</td>
                <td className="search-name">{t.name}</td>
                <td className="num tabular">{int(t.n_bets)}</td>
                <td className="num tabular">{pct(t.hit_rate)}</td>
                <td className="num tabular">{num2(t.avg_odds)}</td>
                <td>
                  <GainCell value={t.profit * stake} max={maxAbs} />
                </td>
                <td className="num tabular">{signedPct(t.roi)}</td>
                <td className="num tabular">
                  {t.seasons_won} sur {t.seasons_played}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {wf && luck && (
        <>
          <dl className="figures search-checks">
            <div className="figure">
              <dt>Choisie à l'époque</dt>
              <dd className="figure-value tabular">{money(wf.profit * stake)}</dd>
              <dd className="figure-sub">
                En jouant chaque saison la meilleure combinaison des saisons précédentes, les seules connues alors :{' '}
                {int(wf.n_bets)} paris, rendement {signedPct(wf.roi)}.
              </dd>
            </div>
            <div className="figure">
              <dt>Ce que donne le hasard</dt>
              <dd className="figure-value tabular">{money(luck.best_profit_median * stake)}</dd>
              <dd className="figure-sub">
                Gain de la meilleure combinaison quand chaque résultat est tiré selon les cotes elles-mêmes, où aucune n'a
                d'avantage réel (médiane de {luck.n_sims} saisons simulées). Elle fait au moins aussi bien que notre
                meilleure dans {pct(luck.share_as_good)} des cas.
              </dd>
            </div>
          </dl>
          <SearchVerdict search={search} />
          <details className="search-details">
            <summary>Les choix saison par saison</summary>
            <div className="table-scroll">
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Saison</th>
                    <th>Meilleure combinaison des saisons précédentes</th>
                    <th className="num">Paris</th>
                    <th className="num">Résultat</th>
                  </tr>
                </thead>
                <tbody>
                  {wf.seasons.map((s) => (
                    <tr key={s.season}>
                      <td className="tabular">{seasonLabel(s.season)}</td>
                      <td className="search-name">{s.name}</td>
                      <td className="num tabular">{int(s.n_bets)}</td>
                      <td className="num tabular">{money(s.profit * stake)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </details>
        </>
      )}
    </section>
  )
}

function roundTitle(r: BettingRound) {
  return r.matchweek ? `Journée ${r.matchweek}` : `Semaine du ${shortDate(r.round_start)}`
}

function RoundCard({ r, stake }: { r: BettingRound; stake: number }) {
  const span = r.first_date === r.last_date ? shortDate(r.first_date) : `${shortDate(r.first_date)} – ${shortDate(r.last_date)}`
  return (
    <article className="bet-round">
      <header className="bet-round-head">
        <h3>{roundTitle(r)}</h3>
        <span className="muted tabular">{span}</span>
      </header>
      <ol className="bet-picks">
        {r.picks.slice(0, 4).map((p, i) => (
          <li key={`${p.home_team}-${p.away_team}`}>
            <span className="bet-rank tabular">{i + 1}</span>
            <HitMark hit={p.won} />
            <span className="bet-pick">
              {p.pick !== 'Nul' && <ClubCrest team={p.pick} size={18} />}
              <span className="bet-pick-name">{p.pick === 'Nul' ? 'Match nul' : p.pick}</span>
            </span>
            <span className="bet-fixture">
              {p.home_team} {p.score[0]}–{p.score[1]} {p.away_team}
            </span>
            <span className="bet-p tabular">{pct(p.p)}</span>
            <span className="bet-odds tabular">cote {num2(p.odds)}</span>
          </li>
        ))}
      </ol>
      <ul className="bet-combos">
        {COMBO_SIZES.filter((k) => r.combos[k]).map((k) => {
          const c = r.combos[k]
          return (
            <li key={k}>
              <span className="bet-combo-name">Combiné de {k}</span>
              <span className="tabular">cote {num2(c.odds)}</span>
              <span className="muted tabular">{pct(c.p)} selon nous</span>
              <span className="bet-combo-result">
                <HitMark hit={c.won} />
                {c.won ? 'Gagné' : 'Perdu'}
              </span>
              <span className="bet-combo-money tabular">{money(c.won ? (c.odds - 1) * stake : -stake)}</span>
            </li>
          )
        })}
      </ul>
    </article>
  )
}

export function BettingPage({ betting }: { betting: Partial<Betting> | null }) {
  const [stake, setStake] = useState<number>(readStake)
  const [stakeText, setStakeText] = useState(String(readStake()))
  const [period, setPeriod] = useState<PeriodKey>('history')
  const [selected, setSelected] = useState<string | null>(null)

  useEffect(() => {
    try {
      localStorage.setItem(STAKE_KEY, String(stake))
    } catch {
      // private mode or blocked storage: the stake just isn't remembered
    }
  }, [stake])

  if (!betting) {
    return (
      <div className="page">
        <p className="muted">Chargement de l'analyse des paris…</p>
      </div>
    )
  }
  if (!betting.periods) {
    return (
      <div className="page">
        <header className="page-header">
          <h1>Et si on avait parié ?</h1>
        </header>
        <p className="muted">
          Pas encore d'analyse : lance <code>python scripts/build_betting.py</code> (quelques minutes la première fois).
        </p>
      </div>
    )
  }

  const b = betting as Betting
  const current = b.periods[period]
  const byProfit = [...current.strategies].sort((x, y) => y.profit - x.profit)
  const best = byProfit[0]
  const fav = current.strategies.find((s) => s.key === 'fav_model')!
  const shown = current.strategies.find((s) => s.key === (selected ?? best.key)) ?? best
  const market = current.market
  const marketWins = market.log_loss_market !== null && market.log_loss_model !== null && market.log_loss_market < market.log_loss_model
  const periodName =
    period === 'history' ? `de ${seasonLabel(current.first_season ?? 2013)} à aujourd'hui` : `en ${seasonLabel(b.season_start_year)}`

  const onStake = (text: string) => {
    setStakeText(text)
    const v = Number(text.replace(',', '.'))
    if (v > 0 && v < 1e7) setStake(v)
  }

  return (
    <div className="page">
      <header className="page-header">
        <h1>Et si on avait parié ?</h1>
        <p className="standfirst">
          Nos prédictions de l'époque, faites avant chaque journée avec les seules données disponibles, face aux
          vraies cotes des bookmakers. Neuf stratégies, fixées à l'avance, rejouées pari par pari.
        </p>
      </header>

      <div className="bet-controls">
        <label className="stake-field">
          <span>Mise par pari</span>
          <span className="stake-input">
            <input
              type="text"
              inputMode="decimal"
              value={stakeText}
              onChange={(e) => onStake(e.target.value)}
              onBlur={() => setStakeText(String(stake))}
              aria-describedby="stake-unit"
            />
            <span id="stake-unit">$</span>
          </span>
        </label>
        <div className="segmented" role="radiogroup" aria-label="Période">
          {(['history', 'season'] as PeriodKey[]).map((k) => (
            <button
              key={k}
              type="button"
              role="radio"
              aria-checked={period === k}
              className={period === k ? 'is-active' : ''}
              onClick={() => setPeriod(k)}
            >
              {k === 'history' ? `Depuis ${seasonLabel(b.periods.history.first_season ?? 2013)}` : 'Cette saison'}
            </button>
          ))}
        </div>
      </div>

      <dl className="figures figures-4">
        <div className="figure">
          <dt>{best.profit >= 0 ? 'Meilleure stratégie' : 'La moins mauvaise'}</dt>
          <dd className="figure-value tabular">{money(best.profit * stake)}</dd>
          <dd className="figure-sub">
            {best.name} · rendement {signedPct(best.roi)}
          </dd>
        </div>
        <div className="figure">
          <dt>Notre favori à chaque match</dt>
          <dd className="figure-value tabular">{money(fav.profit * stake)}</dd>
          <dd className="figure-sub tabular">
            {int(fav.n_bets)} paris · {fav.hit_rate !== null ? pct(fav.hit_rate) : '—'} gagnés
          </dd>
        </div>
        <div className="figure">
          <dt>Qui prédit le mieux ?</dt>
          <dd className="figure-value figure-text">{marketWins ? 'Les bookmakers' : 'Notre modèle'}</dd>
          {market.log_loss_market !== null && market.log_loss_model !== null && (
            <dd className="figure-sub tabular">
              log loss {num3(market.log_loss_market)} pour eux, {num3(market.log_loss_model)} pour nous (plus bas = mieux)
            </dd>
          )}
        </div>
        <div className="figure">
          <dt>Marge des bookmakers</dt>
          <dd className="figure-value tabular">{market.margin !== null ? pct(market.margin) : '—'}</dd>
          <dd className="figure-sub">prélevée en moyenne sur chaque match</dd>
        </div>
      </dl>

      <section className="module">
        <div className="module-head-row">
          <div>
            <h2>Les stratégies</h2>
            <p className="module-note">
              Gain ou perte {periodName}, avec {stakeLabel(stake)} par pari. Choisis une stratégie pour voir
              son évolution.
            </p>
          </div>
          <div className="legend">
            <span className="legend-item">
              <i className="swatch swatch-gain" aria-hidden="true" />
              Gain
            </span>
            <span className="legend-item">
              <i className="swatch swatch-loss" aria-hidden="true" />
              Perte
            </span>
          </div>
        </div>
        <StrategyTable period={current} stake={stake} selected={shown.key} onSelect={setSelected} />
        {period === 'season' && (
          <p className="footnote">
            Sur {int(current.n_matches)} matchs, le hasard domine : une saison ne suffit pas à distinguer une bonne
            stratégie d'une stratégie chanceuse. La période depuis {seasonLabel(b.periods.history.first_season ?? 2013)}{' '}
            compte {int(b.periods.history.n_matches)} matchs.
          </p>
        )}
      </section>

      <section className="module">
        <h2>{shown.name}</h2>
        <p className="module-note">{shown.description}</p>
        <StrategyDetail s={shown} stake={stake} period={period} />
      </section>

      {period === 'history' && b.search && <CombinationSearch search={b.search} stake={stake} />}

      {period === 'history' && <Honesty betting={b} />}

      {b.rounds.length > 0 && (
        <section className="module">
          <h2>Les combinés de la saison</h2>
          <p className="module-note">
            Chaque journée, nos quatre favoris les plus sûrs. Le combiné de 2 réunit les deux premiers, celui de 3 les
            trois premiers : il ne paie que si tous gagnent.
          </p>
          <div className="bet-rounds">
            {[...b.rounds].reverse().map((r) => (
              <RoundCard key={r.round_start} r={r} stake={stake} />
            ))}
          </div>
        </section>
      )}

      <p className="footnote">
        Cotes : moyenne des bookmakers relevée par football-data.co.uk avant chaque match ; chez un seul bookmaker, la
        cote est souvent un peu plus basse. Un pari gagnant rapporte la mise multipliée par la cote, mise comprise. Cette
        analyse regarde le passé et ne garantit rien pour la suite : la marge prélevée sur chaque pari fait perdre la
        plupart des parieurs sur la durée.
      </p>
    </div>
  )
}
