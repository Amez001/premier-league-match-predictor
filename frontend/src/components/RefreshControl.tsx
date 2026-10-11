import { useEffect, useRef, useState } from 'react'
import { api, type Meta, type RefreshStatus, type RefreshStepStatus } from '../api'
import { longDate } from '../format'

const POLL_MS = 1500

function RefreshIcon({ spinning }: { spinning: boolean }) {
  return (
    <svg className={`refresh-icon${spinning ? ' is-spinning' : ''}`} viewBox="0 0 16 16" width="15" height="15" aria-hidden="true">
      <path d="M13.2 6.2A5.4 5.4 0 0 0 3.1 5" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
      <path d="M2.8 9.8A5.4 5.4 0 0 0 12.9 11" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
      <path d="M13.6 2.6v3.8H9.8M2.4 13.4V9.6h3.8" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  )
}

/** Step state as an icon *and* a text label (for screen readers), never color alone. */
function StepMark({ status }: { status: RefreshStepStatus }) {
  const label = { pending: 'à venir', running: 'en cours', done: 'terminé', failed: 'échec', skipped: 'sauté' }[status]
  return (
    <span className={`step-mark is-${status}`} role="img" aria-label={label}>
      <svg width="10" height="10" viewBox="0 0 12 12" aria-hidden="true">
        {status === 'done' && (
          <path d="M2.5 6.5l2.3 2.3 4.7-5" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
        )}
        {status === 'failed' && <path d="M3 3l6 6M9 3l-6 6" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />}
        {status === 'skipped' && <path d="M3 6h6" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />}
      </svg>
    </span>
  )
}

function elapsed(fromIso: string | null | undefined, toIso?: string | null): string {
  if (!fromIso) return ''
  const seconds = Math.max(0, ((toIso ? Date.parse(toIso) : Date.now()) - Date.parse(fromIso)) / 1000)
  return seconds < 60 ? `${Math.round(seconds)} s` : `${Math.round(seconds / 60)} min`
}

function plural(n: number, one: string, many: string) {
  return `${n} ${n > 1 ? many : one}`
}

function Summary({ status }: { status: RefreshStatus }) {
  const results = status.new_results ?? 0
  const reports = status.new_match_reports ?? 0
  if (results === 0 && reports === 0) return <p>Aucun nouveau match depuis la dernière mise à jour.</p>
  return (
    <p>
      {plural(results, 'nouveau résultat', 'nouveaux résultats')}, {plural(reports, 'nouvelle feuille', 'nouvelles feuilles')}{' '}
      de match.
    </p>
  )
}

/**
 * "Mettre à jour" in the header: starts the data refresh on the server
 * (POST /api/refresh), shows its steps while it runs, and tells the app to
 * reload everything once it's done. The refresh runs on the server, so
 * leaving or reloading the page doesn't stop it: the status is picked up
 * again on mount.
 */
export function RefreshControl({ meta, onFinished }: { meta: Meta | null; onFinished: () => void }) {
  const [status, setStatus] = useState<RefreshStatus | null>(null)
  const [open, setOpen] = useState(false)
  const [starting, setStarting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const wrapRef = useRef<HTMLDivElement>(null)
  const running = status?.state === 'running'

  useEffect(() => {
    api.getRefresh().then(setStatus).catch(() => setStatus(null))
  }, [])

  // Poll while a refresh runs; when it ends, reload the app's data.
  useEffect(() => {
    if (!running) return
    const timer = window.setInterval(() => {
      api
        .getRefresh()
        .then((s) => {
          setStatus(s)
          if (s.state !== 'running') onFinished()
        })
        .catch(() => {})
    }, POLL_MS)
    return () => window.clearInterval(timer)
  }, [running, onFinished])

  useEffect(() => {
    if (!open) return
    const onDown = (e: MouseEvent) => {
      if (wrapRef.current && !wrapRef.current.contains(e.target as Node)) setOpen(false)
    }
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && setOpen(false)
    document.addEventListener('mousedown', onDown)
    document.addEventListener('keydown', onKey)
    return () => {
      document.removeEventListener('mousedown', onDown)
      document.removeEventListener('keydown', onKey)
    }
  }, [open])

  const start = () => {
    setStarting(true)
    setError(null)
    api
      .startRefresh()
      .then(setStatus)
      .catch((e: Error) => setError(e.message))
      .finally(() => setStarting(false))
  }

  const matchStep = status?.steps.find((s) => s.key === 'match_players' && s.status === 'running')
  const showRun = status && status.state !== 'idle'

  return (
    <div className="refresh" ref={wrapRef}>
      <button
        type="button"
        className={`refresh-trigger${running ? ' is-running' : ''}`}
        aria-expanded={open}
        aria-haspopup="dialog"
        onClick={() => setOpen((o) => !o)}
      >
        <RefreshIcon spinning={running} />
        <span className="refresh-trigger-text">
          {running ? (matchStep?.detail ? `Mise à jour · ${matchStep.detail}` : 'Mise à jour…') : 'Mettre à jour'}
        </span>
      </button>

      {open && (
        <div className="refresh-panel" role="dialog" aria-label="Mise à jour des données">
          {running ? (
            <h3>Mise à jour en cours · {elapsed(status.started_at)}</h3>
          ) : status?.state === 'done' ? (
            <h3>Données à jour</h3>
          ) : status?.state === 'error' ? (
            <h3>Mise à jour incomplète</h3>
          ) : (
            <h3>Mettre à jour les données</h3>
          )}

          {!running && meta && (
            <p className="refresh-meta">Dernier résultat pris en compte : {longDate(meta.last_match_date)}.</p>
          )}

          {showRun && (
            <ol className="refresh-steps">
              {status.steps.map((s) => (
                <li key={s.key} className={`is-${s.status}`}>
                  {s.status === 'running' ? <span className="step-spinner" role="img" aria-label="en cours" /> : <StepMark status={s.status} />}
                  <span className="refresh-step-label">{s.label}</span>
                  <span className="refresh-step-detail tabular">
                    {s.status === 'running' && s.detail ? `${s.detail} matchs` : s.status === 'done' && s.seconds ? `${s.seconds} s` : ''}
                  </span>
                  {(s.status === 'failed' || s.status === 'skipped') && s.detail && <span className="refresh-step-error">{s.detail}</span>}
                </li>
              ))}
            </ol>
          )}

          {running ? (
            <p className="refresh-note">
              Environ une minute par nouveau match : FBref limite le rythme des téléchargements. Tu peux continuer à
              naviguer, le site se recharge tout seul à la fin.
            </p>
          ) : (
            <>
              {status && (status.state === 'done' || status.state === 'error') && <Summary status={status} />}
              <p className="refresh-note">
                Télécharge les nouveaux résultats et les statistiques des joueurs, recalcule les prédictions, le bilan et
                l'analyse des paris, puis publie les nouvelles données sur GitHub. Compter environ une minute par nouveau
                match. Les résultats arrivent sur football-data.co.uk un ou deux jours après les matchs : un match tout
                juste joué sera pris en compte à la mise à jour suivante.
              </p>
              {error && <p className="error">{error}</p>}
              <button type="button" className="btn-primary" onClick={start} disabled={starting}>
                {starting ? 'Démarrage…' : status && status.state !== 'idle' ? 'Relancer une mise à jour' : 'Lancer la mise à jour'}
              </button>
            </>
          )}
        </div>
      )}
    </div>
  )
}
