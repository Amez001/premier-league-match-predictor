export interface Scoreline {
  home_goals: number
  away_goals: number
  probability: number
}

export interface Scorer {
  player: string
  position: string
  lambda_goals: number
  scorer_probability: number
}

export interface Prediction {
  home_team: string
  away_team: string
  home_win_proba: number
  draw_proba: number
  away_win_proba: number
  predicted_result: string
  expected_goals_home: number
  expected_goals_away: number
  most_likely_scores: Scoreline[]
  elo_diff: number
  top_scorers_home: Scorer[]
  top_scorers_away: Scorer[]
}

export interface BacktestRow {
  model: string
  accuracy: string
  log_loss: string
  brier_score: string
  n_matches: string
  n_seasons: string
}

async function getJson<T>(url: string): Promise<T> {
  const res = await fetch(url)
  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    throw new Error(body.detail ?? `Request to ${url} failed (${res.status})`)
  }
  return res.json() as Promise<T>
}

export const api = {
  getTeams: () => getJson<string[]>('/api/teams'),
  predict: (home: string, away: string) =>
    getJson<Prediction>(`/api/predict?home=${encodeURIComponent(home)}&away=${encodeURIComponent(away)}`),
  getBacktestSummary: () => getJson<BacktestRow[]>('/api/backtest-summary'),
}
