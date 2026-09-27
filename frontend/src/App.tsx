import { lazy, Suspense, useEffect, useState } from 'react'
import './App.css'
import { api, type BacktestRow, type Meta, type SeasonSimulation } from './api'
import { TooltipProvider } from './components/Tooltip'
import { longDate, shortDate } from './format'
import { MatchPage } from './pages/MatchPage'
import { SeasonPage } from './pages/SeasonPage'

// Loaded on demand: it's the only page using KaTeX (~270 kB), which would
// otherwise double the bundle for the Match and Season pages.
const HowItWorksPage = lazy(() => import('./pages/HowItWorksPage').then((m) => ({ default: m.HowItWorksPage })))

type Route = 'match' | 'saison' | 'methode'

const NAV: { route: Route; label: string }[] = [
  { route: 'match', label: 'Match' },
  { route: 'saison', label: 'Saison' },
  { route: 'methode', label: 'Méthode' },
]

function readRoute(): Route {
  const r = window.location.hash.replace(/^#\/?/, '').split('/')[0]
  return r === 'saison' || r === 'methode' ? r : 'match'
}

export default function App() {
  const [route, setRoute] = useState<Route>(readRoute)
  const [teams, setTeams] = useState<string[]>([])
  const [season, setSeason] = useState<SeasonSimulation | null>(null)
  const [meta, setMeta] = useState<Meta | null>(null)
  const [backtest, setBacktest] = useState<BacktestRow[]>([])
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const onHash = () => {
      setRoute(readRoute())
      window.scrollTo({ top: 0 })
    }
    window.addEventListener('hashchange', onHash)
    return () => window.removeEventListener('hashchange', onHash)
  }, [])

  useEffect(() => {
    api.getTeams().then(setTeams).catch((e: Error) => setError(e.message))
    api.getSeason().then(setSeason).catch(() => setSeason(null))
    api.getMeta().then(setMeta).catch(() => setMeta(null))
    api.getBacktestSummary().then(setBacktest).catch(() => setBacktest([]))
  }, [])

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
          </div>
        </header>

        <main className="main">
          {error && (
            <p className="error">
              Impossible de joindre l'API ({error}). Lance <code>uvicorn api.main:app --port 8000</code>.
            </p>
          )}
          {route === 'match' && <MatchPage teams={teams} />}
          {route === 'saison' && <SeasonPage sim={season} />}
          {route === 'methode' && (
            <Suspense fallback={<p className="muted">Chargement…</p>}>
              <HowItWorksPage meta={meta} backtest={backtest} />
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
