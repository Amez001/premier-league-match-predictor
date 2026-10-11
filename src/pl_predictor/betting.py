"""Betting backtest: what our predictions would have won or lost at real odds.

Every match since 2013-14 is predicted by the site's own model as it stood
before the match's round, from earlier matches only - the same no-leakage
rule as the season track record (track_record.py) - then priced with the
market's average pre-match odds (data/odds.py).

A fixed list of strategies (STRATEGIES), decided before looking at any
result, is replayed with a flat stake of one unit per bet. Trying dozens of
variants and keeping the best one is how betting backtests fool people: with
enough tries, something wins by luck. `honesty_check` measures that risk by
picking the best strategy on the first half of the seasons and replaying it
on the second half.

Odds and probabilities:
- the implied probability of decimal odds o is 1/o; a match's three implied
  probabilities sum to ~1.05, and those 5% are the bookmaker's margin;
- value bet: our probability p and the odds o give p x o >= 1 + VALUE_EDGE,
  i.e. by our own numbers the bet pays more than it's worth;
- accumulator: pays the product of its odds if every pick wins; its
  probability is the product of the picks' (independent matches).
"""
from __future__ import annotations

import hashlib
import math
from pathlib import Path

import numpy as np
import pandas as pd

from pl_predictor.config import DEFAULT_FIRST_TEST_SEASON_START_YEAR, REPORTS_DIR
from pl_predictor.predict import MatchPredictor

# Same first test season as the walk-forward backtest: the models were tuned on 2008-2012.
FIRST_SEASON = DEFAULT_FIRST_TEST_SEASON_START_YEAR
VALUE_EDGE = 0.05
STRONG_FAVOURITE = 0.60
ACCUMULATOR_SIZES = (2, 3, 4)
VALUE_EDGES_COMPARED = (0.0, 0.05, 0.10, 0.20)

PREDICTIONS_PATH = REPORTS_DIR / "betting_predictions.csv"
# Bump when the way predictions are made here changes (round_starts,
# predict_season); changes to the model code itself are picked up by
# model_fingerprint() automatically.
PREDICTIONS_VERSION = 1
_MODEL_FILES = (
    "predict.py",
    "models/poisson_model.py",
    "models/baseline_logreg.py",
    "features/elo.py",
    "features/engineering.py",
    "data/load.py",
)

OUTCOMES = {"H": ("p_home", "odds_home"), "D": ("p_draw", "odds_draw"), "A": ("p_away", "odds_away")}

STRATEGIES = [
    {
        "key": "fav_model",
        "name": "Notre favori",
        "description": "À chaque match, le résultat que notre modèle juge le plus probable.",
        "kind": "single",
    },
    {
        "key": "fav_market",
        "name": "Le favori des bookmakers",
        "description": "À chaque match, le résultat à la plus petite cote. C'est la référence : parier comme tout le monde.",
        "kind": "single",
    },
    {
        "key": "fav_strong",
        "name": "Nos favoris à plus de 60 %",
        "description": "Seulement les matchs où notre modèle donne plus de 60 % à un résultat.",
        "kind": "single",
    },
    {
        "key": "value",
        "name": "Paris de valeur",
        "description": "Chaque résultat où notre probabilité multipliée par la cote dépasse 1,05 : "
        "selon nous, le bookmaker le sous-estime d'au moins 5 %.",
        "kind": "single",
    },
    {
        "key": "goals_model",
        "name": "Plus ou moins de 2,5 buts",
        "description": "À chaque match, le côté que notre modèle de buts juge le plus probable.",
        "kind": "single",
    },
    {
        "key": "goals_value",
        "name": "Paris de valeur sur les buts",
        "description": "Plus ou moins de 2,5 buts, quand notre probabilité multipliée par la cote dépasse 1,05.",
        "kind": "single",
    },
    *[
        {
            "key": f"acca{k}",
            "name": f"Combiné de {k} favoris",
            "description": f"Un pari par journée : nos {k} plus gros favoris réunis, qui doivent tous gagner.",
            "kind": "accumulator",
        }
        for k in ACCUMULATOR_SIZES
    ],
]


# --------------------------------------------------------------------------
# Predictions, rebuilt before each round
# --------------------------------------------------------------------------
def round_starts(dates: pd.Series) -> pd.Series:
    """Start of each match's round: the Friday on or before a Friday-to-Monday
    (weekend) match, the Tuesday on or before a Tuesday-to-Thursday (midweek)
    one. A round is predicted from the matches played before its start."""
    weekday = dates.dt.weekday  # Monday = 0
    offset = np.where(weekday.between(1, 3), weekday - 1, (weekday - 4) % 7)
    return (dates - pd.to_timedelta(offset, unit="D")).dt.normalize()


def p_over_2_5(lambda_home: float, lambda_away: float) -> float:
    """P(3 goals or more). The goals model draws each side's goals from
    independent Poisson laws, so the total is Poisson(lambda_home + lambda_away)."""
    total = lambda_home + lambda_away
    return 1.0 - math.exp(-total) * (1.0 + total + total * total / 2.0)


def predict_season(matches: pd.DataFrame, season: int) -> pd.DataFrame:
    """The site's predictions for every played match of `season`, each made
    by a predictor refitted on the matches before the match's round."""
    season_df = matches[matches["season_start_year"] == season].copy()
    if season_df.empty:
        return pd.DataFrame()
    teams = sorted(set(season_df["home_team"]) | set(season_df["away_team"]))
    season_df["round_start"] = round_starts(season_df["date"])

    rows = []
    for start, block in season_df.groupby("round_start", sort=True):
        history = matches[matches["date"] < start]
        if history.empty:
            continue
        predictor = MatchPredictor(history, teams=teams, player_df=None)
        for m in block.itertuples(index=False):
            pred = predictor.predict(m.home_team, m.away_team)
            lam_h, lam_a = pred["expected_goals_home"], pred["expected_goals_away"]
            rows.append(
                {
                    "season_start_year": season,
                    "round_start": start.date().isoformat(),
                    "date": m.date.date().isoformat(),
                    "home_team": m.home_team,
                    "away_team": m.away_team,
                    "p_home": pred["home_win_proba"],
                    "p_draw": pred["draw_proba"],
                    "p_away": pred["away_win_proba"],
                    "lambda_home": lam_h,
                    "lambda_away": lam_a,
                    "p_over": p_over_2_5(lam_h, lam_a),
                }
            )
    return pd.DataFrame(rows)


def model_fingerprint() -> str:
    """Changes whenever the model code changes, so cached predictions made by
    an older model are recomputed. Line endings are normalized: a Windows
    checkout (CRLF) must not look like a different model."""
    package = Path(__file__).resolve().parent
    digest = hashlib.sha1(str(PREDICTIONS_VERSION).encode())
    for rel in _MODEL_FILES:
        digest.update((package / rel).read_bytes().replace(b"\r\n", b"\n"))
    return digest.hexdigest()[:12]


def update_predictions(
    matches: pd.DataFrame,
    path: Path = PREDICTIONS_PATH,
    rebuild: bool = False,
    on_season=None,
) -> pd.DataFrame:
    """Predictions for every season since FIRST_SEASON, cached in `path`.

    Past seasons never change, so they're reused from the cache as long as
    the model is the same; the current season is always recomputed (new
    matches, and the predictions of a round only depend on earlier ones).
    A full rebuild takes several minutes, a weekly update a few seconds.
    """
    fingerprint = model_fingerprint()
    current = int(matches["season_start_year"].max())
    cached = pd.DataFrame()
    if not rebuild and path.exists():
        cached = pd.read_csv(path, encoding="utf-8")
        if cached.empty or "model" not in cached.columns or (cached["model"] != fingerprint).any():
            cached = pd.DataFrame()

    frames = []
    for season in range(FIRST_SEASON, current + 1):
        if season < current and not cached.empty and (cached["season_start_year"] == season).any():
            frames.append(cached[cached["season_start_year"] == season].drop(columns="model"))
            continue
        if on_season:
            on_season(season)
        frames.append(predict_season(matches, season))

    frames = [f for f in frames if not f.empty]
    if not frames:
        return pd.DataFrame()
    predictions = pd.concat(frames, ignore_index=True)
    path.parent.mkdir(parents=True, exist_ok=True)
    predictions.assign(model=fingerprint).round(5).to_csv(path, index=False, encoding="utf-8")
    return predictions


# --------------------------------------------------------------------------
# Strategies
# --------------------------------------------------------------------------
def _bets(df: pd.DataFrame, pick: pd.Series, market: str = "1x2") -> pd.DataFrame:
    """One bet per row of `df` whose `pick` is set ("H", "D", "A" for the
    result; "over"/"under" for goals)."""
    rows = df[pick.notna()]
    pick = pick[pick.notna()]
    if market == "1x2":
        col = pick.map({"H": 0, "D": 1, "A": 2}).to_numpy(dtype=int)
        at = np.arange(len(rows))
        p = pd.Series(rows[["p_home", "p_draw", "p_away"]].to_numpy()[at, col], index=rows.index)
        odds = pd.Series(rows[["odds_home", "odds_draw", "odds_away"]].to_numpy()[at, col], index=rows.index)
        won = rows["result"] == pick
        label = [_outcome_label(h, a, o) for h, a, o in zip(rows["home_team"], rows["away_team"], pick)]
    else:
        over = pick == "over"
        p = rows["p_over"].where(over, 1 - rows["p_over"])
        odds = rows["odds_over"].where(over, rows["odds_under"])
        total = rows["home_goals"] + rows["away_goals"]
        won = (total > 2.5) == over
        label = ["Plus de 2,5 buts" if o else "Moins de 2,5 buts" for o in over]
    return pd.DataFrame(
        {
            "season_start_year": rows["season_start_year"],
            "round_start": rows["round_start"],
            "date": rows["date"],
            "match": rows["home_team"] + " - " + rows["away_team"],
            "pick": label,
            "p": p,
            "odds": odds,
            "won": won.astype(bool),
        }
    )


def _outcome_label(home: str, away: str, outcome: str) -> str:
    return home if outcome == "H" else away if outcome == "A" else "Nul"


def _favourite(df: pd.DataFrame) -> pd.Series:
    probs = df[["p_home", "p_draw", "p_away"]].to_numpy()
    return pd.Series(np.array(["H", "D", "A"])[probs.argmax(axis=1)], index=df.index)


def _accumulators(df: pd.DataFrame, size: int) -> pd.DataFrame:
    """Per round: our `size` most confident favourites in one bet."""
    fav = _favourite(df)
    singles = _bets(df, fav)
    singles["confidence"] = singles["p"]
    rows = []
    for start, block in singles.groupby("round_start", sort=True):
        if len(block) < size:
            continue
        picks = block.sort_values(["confidence", "match"], ascending=[False, True]).head(size)
        rows.append(
            {
                "season_start_year": int(picks["season_start_year"].iloc[0]),
                "round_start": start,
                "date": picks["date"].max(),
                "match": " · ".join(picks["match"]),
                "pick": " · ".join(picks["pick"]),
                "p": float(picks["p"].prod()),
                "odds": float(picks["odds"].prod()),
                "won": bool(picks["won"].all()),
            }
        )
    return pd.DataFrame(rows, columns=["season_start_year", "round_start", "date", "match", "pick", "p", "odds", "won"])


def value_picks(df: pd.DataFrame, edge: float) -> pd.DataFrame:
    """Every result where p x odds >= 1 + edge (possibly two in one match)."""
    frames = []
    for outcome, (p_col, odds_col) in OUTCOMES.items():
        is_value = df[p_col] * df[odds_col] >= 1 + edge - 1e-9  # 0.70 x 1.50 is 1.05, not 1.0499999...
        pick = pd.Series(np.where(is_value, outcome, None), index=df.index)
        frames.append(_bets(df, pick))
    return pd.concat(frames).sort_values(["date", "match"], kind="stable")


def strategy_bets(df: pd.DataFrame, key: str) -> pd.DataFrame:
    """The bets a strategy places on `df` (predictions + odds + results)."""
    fav = _favourite(df)
    if key == "fav_model":
        bets = _bets(df, fav)
    elif key == "fav_market":
        odds = df[["odds_home", "odds_draw", "odds_away"]].to_numpy()
        bets = _bets(df, pd.Series(np.array(["H", "D", "A"])[odds.argmin(axis=1)], index=df.index))
    elif key == "fav_strong":
        strong = df[["p_home", "p_draw", "p_away"]].max(axis=1) >= STRONG_FAVOURITE
        bets = _bets(df, fav.where(strong))
    elif key == "value":
        bets = value_picks(df, VALUE_EDGE)
    elif key == "goals_model":
        bets = _bets(df, pd.Series(np.where(df["p_over"] >= 0.5, "over", "under"), index=df.index), market="goals")
    elif key == "goals_value":
        threshold = 1 + VALUE_EDGE - 1e-9
        over = pd.Series(np.where(df["p_over"] * df["odds_over"] >= threshold, "over", None), index=df.index)
        under = pd.Series(np.where((1 - df["p_over"]) * df["odds_under"] >= threshold, "under", None), index=df.index)
        bets = pd.concat([_bets(df, over, market="goals"), _bets(df, under, market="goals")])
    elif key.startswith("acca"):
        bets = _accumulators(df, int(key[4:]))
    else:
        raise ValueError(f"unknown strategy {key!r}")
    return bets.sort_values(["date", "match"], kind="stable").reset_index(drop=True)


# --------------------------------------------------------------------------
# Results
# --------------------------------------------------------------------------
def _profits(bets: pd.DataFrame) -> np.ndarray:
    """Net result of each 1-unit bet: odds - 1 if it won, -1 otherwise."""
    return np.where(bets["won"], bets["odds"] - 1.0, -1.0)


def _longest_losing_streak(won: pd.Series) -> int:
    longest = current = 0
    for w in won:
        current = 0 if w else current + 1
        longest = max(longest, current)
    return longest


def summarize(bets: pd.DataFrame) -> dict:
    """Hit rate, profit and risk of a list of 1-unit bets in chronological order."""
    n = len(bets)
    if n == 0:
        return {"n_bets": 0, "n_won": 0, "hit_rate": None, "avg_odds": None, "avg_p": None, "profit": 0.0,
                "roi": None, "expected_roi": None, "max_drawdown": 0.0, "longest_losing_streak": 0}
    profits = _profits(bets)
    cumulative = np.concatenate([[0.0], np.cumsum(profits)])
    return {
        "n_bets": n,
        "n_won": int(bets["won"].sum()),
        "hit_rate": float(bets["won"].mean()),
        "avg_odds": float(bets["odds"].mean()),
        "avg_p": float(bets["p"].mean()),
        "profit": float(profits.sum()),
        "roi": float(profits.sum() / n),
        # what our own probabilities promised: E[profit] = p x odds - 1 per bet
        "expected_roi": float((bets["p"] * bets["odds"] - 1).mean()),
        "max_drawdown": float((np.maximum.accumulate(cumulative) - cumulative).max()),
        "longest_losing_streak": _longest_losing_streak(bets["won"]),
    }


def _curve(bets: pd.DataFrame) -> list[list]:
    """Cumulative profit after each round: [[last match date, profit], ...]."""
    if bets.empty:
        return []
    per_round = bets.assign(profit=_profits(bets)).groupby("round_start").agg(date=("date", "max"), profit=("profit", "sum"))
    per_round["cumulative"] = per_round["profit"].cumsum()
    return [[d, round(float(c), 3)] for d, c in zip(per_round["date"], per_round["cumulative"])]


def _by_season(bets: pd.DataFrame) -> list[dict]:
    out = []
    for season, group in bets.groupby("season_start_year", sort=True):
        profits = _profits(group)
        out.append({"season": int(season), "n_bets": len(group), "profit": float(profits.sum()),
                    "roi": float(profits.sum() / len(group))})
    return out


def market_comparison(df: pd.DataFrame) -> dict:
    """Who predicts results better, our model or the bookmakers?

    The market's probabilities are its implied ones with the margin removed
    (each 1/odds divided by their sum). Same matches, same log loss.
    """
    valid = df.dropna(subset=["odds_home", "odds_draw", "odds_away"])
    if valid.empty:
        return {"n_matches": 0, "log_loss_model": None, "log_loss_market": None, "margin": None}
    inverse = 1 / valid[["odds_home", "odds_draw", "odds_away"]].to_numpy()
    booked = inverse.sum(axis=1)
    market = inverse / booked[:, None]
    model = valid[["p_home", "p_draw", "p_away"]].to_numpy()
    idx = valid["result"].map({"H": 0, "D": 1, "A": 2}).to_numpy()
    rows = np.arange(len(valid))
    return {
        "n_matches": len(valid),
        "log_loss_model": float(-np.log(np.clip(model[rows, idx], 1e-12, None)).mean()),
        "log_loss_market": float(-np.log(market[rows, idx]).mean()),
        "margin": float(booked.mean() - 1),
    }


def _period(df: pd.DataFrame, label: str) -> dict:
    strategies = []
    for meta in STRATEGIES:
        bets = strategy_bets(df, meta["key"])
        strategies.append({**meta, **summarize(bets), "curve": _curve(bets), "by_season": _by_season(bets)})
    seasons = sorted(df["season_start_year"].unique())
    return {
        "label": label,
        "first_season": int(seasons[0]) if seasons else None,
        "last_season": int(seasons[-1]) if seasons else None,
        "n_matches": len(df),
        "market": market_comparison(df),
        "strategies": strategies,
    }


def honesty_check(df: pd.DataFrame, current_season: int) -> dict | None:
    """Pick the strategy that made the most on the first half of the complete
    seasons, then see what it made on the second half - what someone choosing
    from the past would actually have got."""
    complete = sorted(s for s in df["season_start_year"].unique() if s < current_season)
    if len(complete) < 4:
        return None
    half = (len(complete) + 1) // 2
    first, second = complete[:half], complete[half:]
    rows = []
    for meta in STRATEGIES:
        a = summarize(strategy_bets(df[df["season_start_year"].isin(first)], meta["key"]))
        b = summarize(strategy_bets(df[df["season_start_year"].isin(second)], meta["key"]))
        rows.append({"key": meta["key"], "name": meta["name"], "profit_first": a["profit"], "roi_first": a["roi"],
                     "profit_second": b["profit"], "roi_second": b["roi"]})
    best = max(rows, key=lambda r: r["profit_first"])
    return {
        "first": [int(first[0]), int(first[-1])],
        "second": [int(second[0]), int(second[-1])],
        "best_first": best["key"],
        "strategies": rows,
    }


def value_edge_comparison(df: pd.DataFrame) -> list[dict]:
    """Value betting at several edges: does being pickier help?"""
    return [{"edge": edge, **summarize(value_picks(df, edge))} for edge in VALUE_EDGES_COMPARED]


def season_rounds(df: pd.DataFrame, schedule: pd.DataFrame | None = None) -> list[dict]:
    """This season, round by round: every match's favourite (by our model),
    most confident first, and the accumulators they make."""
    weeks = {}
    if schedule is not None and not schedule.empty:
        weeks = {(h, a): int(w) for h, a, w in zip(schedule["home_team"], schedule["away_team"], schedule["week"])}
    rounds = []
    for start, block in df.groupby("round_start", sort=True):
        picks = _bets(block, _favourite(block)).sort_values(["p", "match"], ascending=[False, True])
        if picks.empty:
            continue
        rows = block.set_index(block["home_team"] + " - " + block["away_team"])
        match_weeks = [weeks.get(tuple(m.split(" - ", 1))) for m in picks["match"]]
        known = [w for w in match_weeks if w is not None]
        combos = {}
        for k in ACCUMULATOR_SIZES:
            if len(picks) >= k:
                top = picks.head(k)
                combos[str(k)] = {"odds": float(top["odds"].prod()), "p": float(top["p"].prod()), "won": bool(top["won"].all())}
        rounds.append(
            {
                "round_start": start,
                "first_date": block["date"].min(),
                "last_date": block["date"].max(),
                "matchweek": max(set(known), key=known.count) if known else None,
                "picks": [
                    {
                        "home_team": r.match.split(" - ", 1)[0],
                        "away_team": r.match.split(" - ", 1)[1],
                        "pick": r.pick,
                        "p": float(r.p),
                        "odds": float(r.odds),
                        "won": bool(r.won),
                        "score": [int(rows.at[r.match, "home_goals"]), int(rows.at[r.match, "away_goals"])],
                    }
                    for r in picks.itertuples(index=False)
                ],
                "combos": combos,
            }
        )
    return rounds


def build_report(
    matches: pd.DataFrame,
    predictions: pd.DataFrame,
    odds: pd.DataFrame,
    schedule: pd.DataFrame | None = None,
) -> dict:
    """Everything the "Paris" page shows, in units of 1 per bet (the page
    multiplies by the stake)."""
    results = matches[["season_start_year", "season_code", "home_team", "away_team", "home_goals", "away_goals", "result"]]
    df = (
        predictions.merge(results, on=["season_start_year", "home_team", "away_team"], how="inner")
        .merge(odds, on=["season_code", "home_team", "away_team"], how="left")
        .dropna(subset=["odds_home", "odds_draw", "odds_away", "odds_over", "odds_under"])
        .sort_values(["date", "home_team"], kind="stable")
        .reset_index(drop=True)
    )
    current = int(matches["season_start_year"].max())
    this_season = df[df["season_start_year"] == current]
    return {
        "model_fingerprint": model_fingerprint(),
        "season_start_year": current,
        "value_edge": VALUE_EDGE,
        "periods": {
            "history": _period(df, "history"),
            "season": _period(this_season, "season"),
        },
        "honesty": honesty_check(df, current),
        "value_edges": value_edge_comparison(df),
        "rounds": season_rounds(this_season, schedule),
    }
