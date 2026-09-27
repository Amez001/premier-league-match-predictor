import { lazy, Suspense, useEffect, useState } from 'react'
import './App.css'
import { api, type BacktestRow, type Meta, type SeasonSimulation } from './api'
import { TooltipProvider } from './components/Tooltip'
import { longDate } from './format'
import { MatchPage } from './pages/MatchPage'
import { SeasonPage } from './pages/SeasonPage'

// Loaded on demand: it's the only page using KaTeX (~270 kB), which would
// otherwise double the bundle for the Match and Season pages.
const HowItWorksPage = lazy(() => import('./pages/HowItWorksPage').then((m) => ({ default: m.HowItWorksPage })))

type Route = 'match' | 'saison' | 'methode'

const NAV: { route: Route; label: string }[] = [
  { route: 'match', label: 'Match' },
  { route: 'saison', label: 'Saison' },
  { route: 'methode', label: 'Comment ça marche' },
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
          <a href="#/match" className="brand" aria-label="Accueil">
            <span className="brand-mark" aria-hidden="true">
              <svg viewBox="0 0 32 32" width="20" height="20">
                <circle cx="16" cy="16" r="13" fill="none" stroke="currentColor" strokeWidth="2.4" />
                <path d="M16 9l6 4.4-2.3 7h-7.4L10 13.4z" fill="currentColor" />
              </svg>
            </span>
            <span className="brand-name">
              PL<span className="brand-name-light"> Predictor</span>
            </span>
          </a>
          <nav className="tabs" aria-label="Navigation principale">
            {NAV.map((n) => (
              <a key={n.route} href={`#/${n.route}`} className={`tab${route === n.route ? ' is-active' : ''}`} aria-current={route === n.route ? 'page' : undefined}>
                {n.label}
              </a>
            ))}
          </nav>
          {meta && <span className="season-pill">Saison {meta.season}</span>}
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
          <span>
            Données{' '}
            <a href="https://www.football-data.co.uk/">football-data.co.uk</a> & <a href="https://fbref.com/">FBref</a>
            {meta && <> · dernier match pris en compte le {longDate(meta.last_match_date)}</>}
          </span>
          <span className="muted">Probabilités, pas des certitudes. Projet perso, non affilié à la Premier League.</span>
        </footer>
      </div>
    </TooltipProvider>
  )
}
