import { lazy, Suspense, useCallback, useEffect, useState } from 'react'
import './App.css'
import {
  api,
  type Awards,
  type BacktestRow,
  type Betting,
  type Meta,
  type SeasonSimulation,
  type Stats,
  type TrackRecord,
} from './api'
import { RefreshControl } from './components/RefreshControl'
import { TooltipProvider } from './components/Tooltip'
import { longDate, shortDate } from './format'
import { BettingPage } from './pages/BettingPage'
import { MatchPage } from './pages/MatchPage'
import { RecordPage } from './pages/RecordPage'
import { SeasonPage } from './pages/SeasonPage'
import { StatsPage } from './pages/StatsPage'

// Loaded on demand: it's the only page using KaTeX (~270 kB), which would
// otherwise double the bundle for the Match and Season pages.
const HowItWorksPage = lazy(() => import('./pages/HowItWorksPage').then((m) => ({ default: m.HowItWorksPage })))

type Route = 'match' | 'stats' | 'saison' | 'bilan' | 'paris' | 'methode'

const NAV: { route: Route; label: string }[] = [
  { route: 'match', label: 'Match' },
  { route: 'stats', label: 'Stats' },
  { route: 'saison', label: 'Projections' },
  { route: 'bilan', label: 'Bilan' },
  { route: 'paris', label: 'Paris' },
  { route: 'methode', label: 'Méthode' },
]

function readRoute(): Route {
  const r = window.location.hash.replace(/^#\/?/, '').split('/')[0]
  return r === 'stats' || r === 'saison' || r === 'bilan' || r === 'paris' || r === 'methode' ? r : 'match'
}

export default function App() {
  const [route, setRoute] = useState<Route>(readRoute)
  const [teams, setTeams] = useState<string[]>([])
  const [season, setSeason] = useState<SeasonSimulation | null>(null)
  const [awards, setAwards] = useState<Awards | null>(null)
  const [stats, setStats] = useState<Stats | null>(null)
  const [record, setRecord] = useState<TrackRecord | null>(null)
  const [meta, setMeta] = useState<Meta | null>(null)
  const [backtest, setBacktest] = useState<BacktestRow[]>([])
  const [betting, setBetting] = useState<Partial<Betting> | null>(null)
  // bumped after a data refresh, so pages that fetch on their own (Match) fetch again
  const [dataVersion, setDataVersion] = useState(0)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const onHash = () => {
      setRoute(readRoute())
      window.scrollTo({ top: 0 })
    }
    window.addEventListener('hashchange', onHash)
    return () => window.removeEventListener('hashchange', onHash)
  }, [])

  const loadAll = useCallback(() => {
    api
      .getTeams()
      .then((t) => {
        setTeams(t)
        setError(null)
      })
      .catch((e: Error) => setError(e.message))
    api.getSeason().then(setSeason).catch(() => setSeason(null))
    api.getAwards().then(setAwards).catch(() => setAwards(null))
    api.getStats().then(setStats).catch(() => setStats(null))
    api
      .getTrackRecord()
      .then((r) => setRecord({ matches: [], weeks: [], ...r } as TrackRecord))
      .catch(() => setRecord(null))
    api.getMeta().then(setMeta).catch(() => setMeta(null))
    api.getBacktestSummary().then(setBacktest).catch(() => setBacktest([]))
    api.getBetting().then(setBetting).catch(() => setBetting({}))
  }, [])

  useEffect(loadAll, [loadAll])

  const onRefreshed = useCallback(() => {
    loadAll()
    setDataVersion((v) => v + 1)
  }, [loadAll])

  return (
    <TooltipProvider>
      <div className="shell">
        <header className="topbar">
          <div className="topbar-inner">
            <a href="#/match" className="brand" aria-label="PL Predictor, accueil">
              <svg viewBox="0 0 32 32" width="22" height="22" aria-hidden="true">
                <rect width="32" height="32" rx="7" fill="currentColor" />
                <path d="M16 4v24" stroke="var(--page)" strokeWidth="2.4" />
                <circle cx="16" cy="16" r="6.2" fill="none" stroke="var(--page)" strokeWidth="2.4" />
                <circle cx="16" cy="16" r="1.6" fill="var(--page)" />
              </svg>
              <span className="brand-name">PL Predictor</span>
            </a>
            <nav className="nav" aria-label="Navigation principale">
              {NAV.map((n) => (
                <a
                  key={n.route}
                  href={`#/${n.route}`}
                  className={`nav-link${route === n.route ? ' is-active' : ''}`}
                  aria-current={route === n.route ? 'page' : undefined}
                >
                  {n.label}
                </a>
              ))}
            </nav>
            {meta && (
              <span className="data-stamp tabular">
                {meta.season} <span className="data-stamp-sep">·</span> données au {shortDate(meta.last_match_date)}
              </span>
            )}
            <RefreshControl meta={meta} onFinished={onRefreshed} />
          </div>
        </header>

        <main className="main">
          {error && (
            <p className="error">
              Impossible de joindre l'API ({error}). Lance <code>uvicorn api.main:app --port 8000</code>.
            </p>
          )}
          {route === 'match' && <MatchPage teams={teams} dataVersion={dataVersion} />}
          {route === 'stats' && <StatsPage stats={stats} meta={meta} />}
          {route === 'saison' && <SeasonPage sim={season} awards={awards} />}
          {route === 'bilan' && <RecordPage record={record} />}
          {route === 'paris' && <BettingPage betting={betting} />}
          {route === 'methode' && (
            <Suspense fallback={<p className="muted">Chargement…</p>}>
              <HowItWorksPage meta={meta} backtest={backtest} betting={betting} />
            </Suspense>
          )}
        </main>

        <footer className="footer">
          <div className="footer-inner">
            <span>
              Données : <a href="https://www.football-data.co.uk/">football-data.co.uk</a> et{' '}
              <a href="https://fbref.com/">FBref</a>
              {meta && <>. Dernier match pris en compte le {longDate(meta.last_match_date)}.</>}
            </span>
            <span>Projet personnel, sans lien avec la Premier League.</span>
          </div>
        </footer>
      </div>
    </TooltipProvider>
  )
}
