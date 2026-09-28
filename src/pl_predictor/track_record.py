"""Track record: this season's predictions against what actually happened.

For every matchweek already played, the whole predictor is rebuilt *as it
stood before that matchweek* and asked to predict it:

- models (Elo, logistic, Poisson) fitted only on matches played before the
  matchweek's first match;
- player shares rebuilt from match-by-match rows of earlier matches only
  (data/match_players.py) - the season-total snapshots would already contain
  the goals being predicted, so they're never used here;
- last season's totals as the share prior, exactly as live.

Nothing from the matchweek itself (or later) can leak in, so the record is a
fair picture of how the site's predictions would have fared. It's computed
with the *current* model code: if the model improves, past matchweeks are
re-scored with it too - it measures today's model, not a log of what the
site displayed back then.

Besides hit rates, each block reports what our own probabilities expected:
if we call the favourite at 55% on average, a calibrated model should be
right about 55% of the time. Beating a coin flip means little; matching
your own stated confidence is the real test.
"""
from __future__ import annotations

import math

import pandas as pd

from pl_predictor.data.load import get_current_season_teams
from pl_predictor.predict import MatchPredictor

SCORERS_LISTED = 3  # per team, as on the Match page


def player_totals_before(match_players: pd.DataFrame, before: str, season_start_year: int) -> pd.DataFrame:
    """Season totals per player as they stood before `before` (ISO date), in
    the same shape as the FBref season snapshot (player_stats.py)."""
    rows = match_players[match_players["date"] < before]
    if rows.empty:
        return pd.DataFrame()
    keys = ["team", "player", "born", "nation"]
    totals = rows.groupby(keys, dropna=False).agg(
        minutes=("minutes", "sum"),
        season_goals=("goals", "sum"),
        season_assists=("assists", "sum"),
        position=("position", lambda s: s.mode().iloc[0]),
    ).reset_index()
    totals["minutes_90s"] = totals.pop("minutes") / 90.0
    totals["season_goals_per90"] = (totals["season_goals"] / totals["minutes_90s"].where(totals["minutes_90s"] > 0)).fillna(0.0)
    totals["season_start_year"] = season_start_year
    return totals


def _player_features_before(match_players, before: str, season: int, last_season):
    from pl_predictor.models.player_goals import prepare_player_features

    latest = player_totals_before(match_players, before, season)
    if latest.empty:
        return None  # first matchweek: nobody has played yet, no basis for scorer predictions
    week_before = (pd.Timestamp(before) - pd.Timedelta(days=7)).date().isoformat()
    previous = player_totals_before(match_players, week_before, season)
    return prepare_player_features(latest, previous if not previous.empty else None, last_season)


def _result(home_goals: int, away_goals: int) -> str:
    return "H" if home_goals > away_goals else "A" if home_goals < away_goals else "D"


def _expected(probabilities: list[float]) -> dict:
    """What our own probabilities predict for the number of hits.

    Each prediction is a yes/no event with its own probability p, so the hit
    count has mean sum(p) and variance sum(p(1-p)) (Poisson-binomial). The
    80% range (mean +/- 1.28 sd) is where a well-calibrated model's hit count
    lands 8 times out of 10 - with 50 matches, a gap of a few points from the
    mean is noise, not a verdict.
    """
    mean = sum(probabilities)
    sd = math.sqrt(sum(p * (1 - p) for p in probabilities))
    return {"expected": mean, "expected_low": max(0.0, mean - 1.28 * sd), "expected_high": mean + 1.28 * sd}


def _summary(records: list[dict]) -> dict:
    """Hit counts vs what our own probabilities expected, for a set of matches."""
    n = len(records)
    fav = [s for r in records if r["scorers_known"] for s in (r["scorers_home"][:1] + r["scorers_away"][:1])]
    listed = [s for r in records if r["scorers_known"] for s in (r["scorers_home"] + r["scorers_away"])]

    def block(hits: int, n_items: int, probabilities: list[float]) -> dict:
        return {"n": n_items, "hits": hits, **_expected(probabilities)}

    return {
        "matches": n,
        "outcome": block(sum(r["outcome_hit"] for r in records), n, [r["p_favourite"] for r in records]),
        "exact": block(sum(r["exact_hit"] for r in records), n, [r["p_predicted_score"] for r in records]),
        "scorer_favourite": block(sum(s["scored"] for s in fav), len(fav), [s["probability"] for s in fav]),
        "scorer_listed": block(sum(s["scored"] for s in listed), len(listed), [s["probability"] for s in listed]),
        "log_loss": (sum(-math.log(max(r["p_actual"], 1e-12)) for r in records) / n) if n else None,
        "log_loss_reference": (sum(-math.log(r["p_reference"]) for r in records) / n) if n else None,
    }


def build_track_record(
    matches: pd.DataFrame,
    schedule: pd.DataFrame,
    match_players: pd.DataFrame | None,
    last_season: pd.DataFrame | None,
) -> dict:
    """Predict every played matchweek of the current season from data strictly
    before it, and compare with the actual results and scorers."""
    season = int(matches["season_start_year"].max())
    teams = get_current_season_teams(matches)
    played = matches[matches["season_start_year"] == season]

    # football-data.co.uk has the results the models train on; FBref's
    # schedule adds official matchweeks and the game ids of the scorer data.
    fixtures = played.merge(
        schedule[["home_team", "away_team", "week", "game_id"]], on=["home_team", "away_team"], how="left"
    )
    fixtures = fixtures[fixtures["week"].notna()]
    stored_games = set(match_players["game_id"]) if match_players is not None and len(match_players) else set()

    # Reference: always predict the historical home/draw/away frequencies,
    # measured on seasons before this one (no information about the teams).
    before_season = matches[matches["season_start_year"] < season]
    base_rates = before_season["result"].value_counts(normalize=True).to_dict()

    records: list[dict] = []
    for week in sorted(fixtures["week"].astype(int).unique()):
        week_fixtures = schedule[schedule["week"] == week]
        cutoff = str(week_fixtures["date"].min())  # predictions made before the matchweek's first match
        history = matches[matches["date"] < pd.Timestamp(cutoff)]
        if history.empty:
            continue  # nothing to learn from yet (only possible with a data set that starts this season)
        player_df = (
            _player_features_before(match_players, cutoff, season, last_season) if stored_games else None
        )
        predictor = MatchPredictor(history, teams=teams, player_df=player_df)

        for m in fixtures[fixtures["week"] == week].sort_values(["date", "home_team"]).itertuples(index=False):
            pred = predictor.predict(m.home_team, m.away_team)
            probs = {"H": pred["home_win_proba"], "D": pred["draw_proba"], "A": pred["away_win_proba"]}
            favourite = max(probs, key=probs.get)
            actual = _result(m.home_goals, m.away_goals)
            top_score = pred["most_likely_scores"][0]

            scorers_known = player_df is not None and m.game_id in stored_games
            actual_scorers = (
                match_players[(match_players["game_id"] == m.game_id) & (match_players["goals"] > 0)]
                if scorers_known
                else pd.DataFrame(columns=["team", "player", "goals"])
            )
            scored = set(zip(actual_scorers["team"], actual_scorers["player"]))

            def listed(team: str, scorers: list[dict]) -> list[dict]:
                return [
                    {"player": s["player"], "probability": s["scorer_probability"], "scored": (team, s["player"]) in scored}
                    for s in scorers[:SCORERS_LISTED]
                ]

            records.append(
                {
                    "week": int(week),
                    "date": m.date.date().isoformat(),
                    "home_team": m.home_team,
                    "away_team": m.away_team,
                    "home_goals": int(m.home_goals),
                    "away_goals": int(m.away_goals),
                    "p_home": probs["H"],
                    "p_draw": probs["D"],
                    "p_away": probs["A"],
                    "favourite": favourite,
                    "p_favourite": probs[favourite],
                    "actual": actual,
                    "p_actual": probs[actual],
                    "p_reference": base_rates.get(actual, 1 / 3),
                    "outcome_hit": favourite == actual,
                    "predicted_score": [top_score["home_goals"], top_score["away_goals"]],
                    "p_predicted_score": top_score["probability"],
                    "exact_hit": (top_score["home_goals"], top_score["away_goals"]) == (m.home_goals, m.away_goals),
                    "expected_goals": [pred["expected_goals_home"], pred["expected_goals_away"]],
                    "scorers_known": scorers_known,
                    "scorers_home": listed(m.home_team, pred["top_scorers_home"]) if scorers_known else [],
                    "scorers_away": listed(m.away_team, pred["top_scorers_away"]) if scorers_known else [],
                    "actual_scorers": [
                        {"team": s.team, "player": s.player, "goals": int(s.goals)}
                        for s in actual_scorers.itertuples(index=False)
                    ],
                }
            )

    weeks = [{"week": w, **_summary([r for r in records if r["week"] == w])} for w in sorted({r["week"] for r in records})]
    return {"season_start_year": season, "overall": _summary(records), "weeks": weeks, "matches": records}
