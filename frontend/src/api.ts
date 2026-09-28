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

export interface AwardRow {
  player: string
  team: string
  position: string
  current: number
  expected_final: number
  p10: number
  p90: number
  p_top: number
}

export interface Awards {
  n_sims: number
  top_scorer: AwardRow[]
  top_assister: AwardRow[]
}

export interface PlayerLeader {
  player: string
  team: string
  position: string
  goals: number
  assists: number
  minutes_90s: number
}

export interface RecentResult {
  date: string
  home_team: string
  away_team: string
  home_goals: number
  away_goals: number
}

export interface Stats {
  season_start_year: number
  matches_played: number
  total_goals: number
  goals_per_match: number
  table: (TableRow & { form: ('W' | 'D' | 'L')[] })[]
  recent_results: RecentResult[]
  top_scorers: Leaderboard
  top_assisters: Leaderboard
}

export interface Leaderboard {
  rows: PlayerLeader[]
  /** players level with the last one shown, left out by the list length */
  more_tied: number
}

export interface HitBlock {
  n: number
  hits: number
  /** what our own probabilities predicted: mean and 80% range of the hit count */
  expected: number
  expected_low: number
  expected_high: number
}

export interface RecordSummary {
  matches: number
  outcome: HitBlock
  exact: HitBlock
  scorer_favourite: HitBlock
  scorer_listed: HitBlock
  log_loss: number | null
  log_loss_reference: number | null
}

export interface ScorerPick {
  player: string
  probability: number
  scored: boolean
}

export interface RecordMatch {
  week: number
  date: string
  home_team: string
  away_team: string
  home_goals: number
  away_goals: number
  p_home: number
  p_draw: number
  p_away: number
  favourite: 'H' | 'D' | 'A'
  p_favourite: number
  actual: 'H' | 'D' | 'A'
  outcome_hit: boolean
  predicted_score: [number, number]
  p_predicted_score: number
  exact_hit: boolean
  scorers_known: boolean
  scorers_home: ScorerPick[]
  scorers_away: ScorerPick[]
  actual_scorers: { team: string; player: string; goals: number }[]
}

export interface TrackRecord {
  season_start_year: number
  overall: RecordSummary
  weeks: (RecordSummary & { week: number })[]
  matches: RecordMatch[]
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
  getAwards: () => getJson<Awards>('/api/awards'),
  getStats: () => getJson<Stats>('/api/stats'),
  /** `{}` until scripts/build_track_record.py has run - RecordPage handles that. */
  getTrackRecord: () => getJson<Partial<TrackRecord>>('/api/track-record'),
  getMeta: () => getJson<Meta>('/api/meta'),
  getBacktestSummary: () => getJson<BacktestRow[]>('/api/backtest-summary'),
}
