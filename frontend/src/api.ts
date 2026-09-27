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
  score_matrix: number[][]
  elo_diff: number
  elo_home: number
  elo_away: number
  top_scorers_home: Scorer[]
  top_scorers_away: Scorer[]
}

export interface TableRow {
  team: string
  played: number
  won: number
  drawn: number
  lost: number
  goals_for: number
  goals_against: number
  goal_diff: number
  points: number
}

export interface Projection {
  team: string
  current_points: number
  played: number
  expected_points: number
  expected_goal_diff: number
  p_title: number
  p_top4: number
  p_relegation: number
  expected_position: number
  position_probs: number[]
}

export interface SeasonSimulation {
  season_start_year: number
  n_sims: number
  matches_played: number
  matches_remaining: number
  current_table: TableRow[]
  projections: Projection[]
}

export interface Meta {
  season: string
  last_match_date: string
  n_matches_history: number
  first_season: string
  players_snapshot_date: string | null
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
    throw new Error(body.detail ?? `La requête ${url} a échoué (${res.status})`)
  }
  return res.json() as Promise<T>
}

export const api = {
  getTeams: () => getJson<string[]>('/api/teams'),
  predict: (home: string, away: string) =>
    getJson<Prediction>(`/api/predict?home=${encodeURIComponent(home)}&away=${encodeURIComponent(away)}`),
  getSeason: () => getJson<SeasonSimulation>('/api/season'),
  getMeta: () => getJson<Meta>('/api/meta'),
  getBacktestSummary: () => getJson<BacktestRow[]>('/api/backtest-summary'),
}
