"""Which combinations of bets would have won the most? And does it mean anything?

betting.py replays nine strategies fixed in advance. This module does the
opposite, on purpose: it tries about a thousand combinations of criteria
- what to bet on, a minimum probability by our model, a range of odds, a
minimum value (our probability x odds - 1), accumulators of 2 to 5 matches
picked by our model, by the market or by value - and keeps the ones that
made the most money over every season since 2013-14.

The best of a thousand tries always looks good, whatever the predictions
are worth. Two checks say how much of it is real:

1. Walk-forward selection: each season, take the best combination of the
   seasons before it - the only ones anyone could have looked at then - and
   bet it that season. The sum is what the search would really have earned.
2. Luck benchmark: rerun the whole search on simulated seasons where every
   result is drawn from the bookmakers' own probabilities (margin removed).
   No combination has any real edge there, yet the best one still shows a
   profit: the real best has to clearly beat that to mean anything.

Everything is in units of one stake per bet, like betting.py.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import sparse

OUTCOMES = (("H", "p_home", "odds_home"), ("D", "p_draw", "odds_draw"), ("A", "p_away", "odds_away"))

# Criteria, simplest first: on a tie the simplest description is kept.
RESULT_SIDES = (None, "H", "D", "A")
RESULT_P_MIN = (0.0, 0.3, 0.4, 0.5, 0.6, 0.7)
RESULT_ODDS = ((1.0, None), (1.0, 1.5), (1.5, 2.0), (2.0, 3.0), (3.0, 5.0), (5.0, None))
GOALS_SIDES = (None, "over", "under")
GOALS_P_MIN = (0.0, 0.5, 0.55, 0.6)
GOALS_ODDS = ((1.0, None), (1.0, 1.8), (1.8, 2.2), (2.2, None))
VALUE_MIN = (None, 0.0, 0.05, 0.10, 0.20)
ACCA_SIZES = (2, 3, 4, 5)
ACCA_RANKINGS = ("model", "market", "value")
ACCA_P_MIN = (0.0, 0.5, 0.6, 0.7)

MIN_BETS = 30  # a combination needs at least this many bets to be ranked
WALK_FORWARD_WARMUP = 3  # seasons of history before the first walk-forward choice
N_LUCK_SIMS = 200
TOP_N = 10

_SIDE_LABEL = {
    None: "Tout résultat",
    "H": "Victoire à domicile",
    "D": "Match nul",
    "A": "Victoire à l'extérieur",
}
_GOALS_LABEL = {None: "Plus ou moins de 2,5 buts", "over": "Plus de 2,5 buts", "under": "Moins de 2,5 buts"}
_RANKING_LABEL = {"model": "favoris de notre modèle", "market": "favoris des bookmakers", "value": "meilleure valeur"}


def _pct(x: float) -> str:
    return f"{x * 100:.0f} %".replace(".", ",")


def _odds(x: float) -> str:
    return f"{x:.2f}".rstrip("0").rstrip(".").replace(".", ",")


def _odds_label(band: tuple[float, float | None]) -> str | None:
    lo, hi = band
    if lo <= 1.0 and hi is None:
        return None
    if lo <= 1.0:
        return f"cote < {_odds(hi)}"
    if hi is None:
        return f"cote ≥ {_odds(lo)}"
    return f"cote {_odds(lo)} à {_odds(hi)}"


def _describe(head: str, *conditions: str | None) -> str:
    return " · ".join([head, *[c for c in conditions if c]])


# --------------------------------------------------------------------------
# Candidate bets and the outcomes that settle them
# --------------------------------------------------------------------------
def candidates(df: pd.DataFrame) -> pd.DataFrame:
    """Every single bet on offer: three results and two goal lines per match,
    with our probability, the odds, the market's fair probability (margin
    removed, for the luck benchmark) and whether it won."""
    df = df.reset_index(drop=True)
    total_goals = df["home_goals"] + df["away_goals"]
    inverse = 1 / df[["odds_home", "odds_draw", "odds_away"]].to_numpy()
    fair = inverse / inverse.sum(axis=1, keepdims=True)
    inv_over, inv_under = 1 / df["odds_over"].to_numpy(), 1 / df["odds_under"].to_numpy()
    fair_over = inv_over / (inv_over + inv_under)

    frames = []
    for i, (side, p_col, odds_col) in enumerate(OUTCOMES):
        frames.append(pd.DataFrame({"match": df.index, "market": "result", "side": side, "p": df[p_col],
                                    "odds": df[odds_col], "fair": fair[:, i], "won": df["result"] == side}))
    frames.append(pd.DataFrame({"match": df.index, "market": "goals", "side": "over", "p": df["p_over"],
                                "odds": df["odds_over"], "fair": fair_over, "won": total_goals > 2.5}))
    frames.append(pd.DataFrame({"match": df.index, "market": "goals", "side": "under", "p": 1 - df["p_over"],
                                "odds": df["odds_under"], "fair": 1 - fair_over, "won": total_goals < 2.5}))
    cand = pd.concat(frames, ignore_index=True)
    cand["edge"] = cand["p"] * cand["odds"] - 1
    cand["season"] = df["season_start_year"].to_numpy()[cand["match"]]
    cand["round"] = df["round_start"].to_numpy()[cand["match"]]
    return cand


def simulate_outcomes(df: pd.DataFrame, cand: pd.DataFrame, n_sims: int, rng: np.random.Generator) -> np.ndarray:
    """(candidates x n_sims) won/lost, every result drawn from the market's
    fair probabilities: a world where the odds are exactly right."""
    n = len(df)
    won = np.zeros((len(cand), n_sims), dtype=bool)
    result = cand[cand["market"] == "result"]
    fair = np.stack([result[result["side"] == s]["fair"].to_numpy() for s, _, _ in OUTCOMES], axis=1)
    draws = rng.random((n, n_sims))
    cumulative = np.cumsum(fair, axis=1)
    outcome = (draws[:, :, None] > cumulative[:, None, :2]).sum(axis=2)  # 0 home, 1 draw, 2 away
    for i, (side, _, _) in enumerate(OUTCOMES):
        rows = result.index[result["side"] == side]
        won[rows] = outcome == i
    goals = cand[cand["market"] == "goals"]
    over_rows, under_rows = goals.index[goals["side"] == "over"], goals.index[goals["side"] == "under"]
    over = rng.random((n, n_sims)) < cand.loc[over_rows, "fair"].to_numpy()[:, None]
    won[over_rows] = over
    won[under_rows] = ~over
    return won


# --------------------------------------------------------------------------
# The combinations
# --------------------------------------------------------------------------
def single_strategies(cand: pd.DataFrame) -> tuple[list[str], sparse.csr_matrix]:
    """Single-bet combinations: (descriptions, strategies x candidates mask)."""
    names, rows = [], []
    for market, sides, p_mins, bands, labels in (
        ("result", RESULT_SIDES, RESULT_P_MIN, RESULT_ODDS, _SIDE_LABEL),
        ("goals", GOALS_SIDES, GOALS_P_MIN, GOALS_ODDS, _GOALS_LABEL),
    ):
        in_market = (cand["market"] == market).to_numpy()
        for side in sides:
            on_side = in_market & ((cand["side"] == side).to_numpy() if side else True)
            for p_min in p_mins:
                confident = on_side & (cand["p"].to_numpy() >= p_min)
                for band in bands:
                    lo, hi = band
                    odds = cand["odds"].to_numpy()
                    priced = confident & (odds >= lo) & ((odds < hi) if hi else True)
                    for value in VALUE_MIN:
                        mask = priced & ((cand["edge"].to_numpy() >= value - 1e-9) if value is not None else True)
                        names.append(
                            _describe(
                                labels[side],
                                f"notre proba ≥ {_pct(p_min)}" if p_min > 0 else None,
                                _odds_label(band),
                                f"valeur ≥ {_pct(value)}" if value is not None else None,
                            )
                        )
                        rows.append(np.flatnonzero(mask))
    indptr = np.cumsum([0, *[len(r) for r in rows]])
    data = np.ones(indptr[-1], dtype=np.float32)
    matrix = sparse.csr_matrix((data, np.concatenate(rows), indptr), shape=(len(rows), len(cand)))
    return names, matrix


def accumulator_bets(cand: pd.DataFrame) -> tuple[list[str], pd.DataFrame, sparse.csr_matrix]:
    """Accumulator combinations: (descriptions, one row per accumulator placed
    with its strategy, season, round and odds, accumulators x candidates
    incidence of their picks)."""
    names, bets, picks = [], [], []
    for market in ("result", "goals"):
        pool = cand[cand["market"] == market]
        for ranking in ACCA_RANKINGS:
            # one pick per match: the outcome this ranking likes best
            score = {"model": pool["p"], "market": -pool["odds"], "value": pool["edge"]}[ranking]
            best = pool.assign(score=score).sort_values(["match", "score"], ascending=[True, False])
            best = best[~best["match"].duplicated()]
            for p_min in ACCA_P_MIN:
                eligible = best[best["p"] >= p_min].sort_values(["round", "score"], ascending=[True, False])
                for size in ACCA_SIZES:
                    strategy = len(names)
                    names.append(
                        _describe(
                            f"Combiné {'buts ' if market == 'goals' else ''}de {size}",
                            _RANKING_LABEL[ranking],
                            f"chacun ≥ {_pct(p_min)}" if p_min > 0 else None,
                        )
                    )
                    for rnd, group in eligible.groupby("round", sort=True):
                        if len(group) < size:
                            continue
                        top = group.head(size)
                        bets.append((strategy, int(top["season"].iloc[0]), rnd, float(top["odds"].prod())))
                        picks.append(top.index.to_numpy())
    table = pd.DataFrame(bets, columns=["strategy", "season", "round", "odds"])
    indptr = np.cumsum([0, *[len(p) for p in picks]])
    data = np.ones(indptr[-1], dtype=np.float32)
    incidence = sparse.csr_matrix((data, np.concatenate(picks) if picks else [], indptr), shape=(len(picks), len(cand)))
    return names, table, incidence


class Search:
    """All combinations, with their bets precomputed: settling them against
    any set of outcomes is then a couple of sparse matrix products."""

    def __init__(self, df: pd.DataFrame):
        self.df = df.reset_index(drop=True)
        self.cand = candidates(self.df)
        single_names, self.singles = single_strategies(self.cand)
        acca_names, self.accas, self.acca_picks = accumulator_bets(self.cand)
        self.names = single_names + acca_names
        self.n_singles = len(single_names)
        self.seasons = sorted(self.df["season_start_year"].unique())
        season_of = {s: i for i, s in enumerate(self.seasons)}
        cand_season = self.cand["season"].map(season_of).to_numpy()
        self._cand_by_season = sparse.csr_matrix(
            (np.ones(len(self.cand), dtype=np.float32), (np.arange(len(self.cand)), cand_season)),
            shape=(len(self.cand), len(self.seasons)),
        )
        self._acca_season = self.accas["season"].map(season_of).to_numpy()
        self._acca_strategy = self.accas["strategy"].to_numpy() + self.n_singles
        n_acca_strategies = len(self.names) - self.n_singles
        self._acca_membership = sparse.csr_matrix(
            (np.ones(len(self.accas), dtype=np.float32), (self.accas["strategy"].to_numpy(), np.arange(len(self.accas)))),
            shape=(n_acca_strategies, len(self.accas)),
        )
        self.n_bets = self._per_season(np.ones(len(self.cand)), np.ones(len(self.accas)))

    def _per_season(self, single_values: np.ndarray, acca_values: np.ndarray) -> np.ndarray:
        """Sum a per-bet quantity by strategy and season: (strategies x seasons)."""
        singles = (self.singles @ self._cand_by_season.multiply(single_values[:, None]).tocsc()).toarray()
        accas = np.zeros((len(self.names) - self.n_singles, len(self.seasons)))
        np.add.at(accas, (self._acca_strategy - self.n_singles, self._acca_season), acca_values)
        return np.vstack([singles, accas])

    def settle(self, won: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        """Profit of every single bet and every accumulator for one set of outcomes."""
        single_profit = np.where(won, self.cand["odds"].to_numpy() - 1, -1.0)
        losses = self.acca_picks @ (~won).astype(np.float32)
        acca_profit = np.where(losses == 0, self.accas["odds"].to_numpy() - 1, -1.0)
        return single_profit, acca_profit

    def profit_by_season(self, won: np.ndarray) -> np.ndarray:
        return self._per_season(*self.settle(won))

    def total_profit_many(self, won: np.ndarray) -> np.ndarray:
        """(strategies x simulations) total profit, outcomes given as (candidates x simulations)."""
        odds = self.cand["odds"].to_numpy()[:, None]
        single_profit = np.where(won, odds - 1, -1.0).astype(np.float32)
        singles = self.singles @ single_profit
        losses = self.acca_picks @ (~won).astype(np.float32)
        acca_profit = np.where(losses == 0, self.accas["odds"].to_numpy()[:, None] - 1, -1.0).astype(np.float32)
        accas = self._acca_membership @ acca_profit
        return np.vstack([np.asarray(singles), np.asarray(accas)])


# --------------------------------------------------------------------------
# The report
# --------------------------------------------------------------------------
def _best(profit: np.ndarray, n_bets: np.ndarray) -> int | None:
    eligible = np.flatnonzero(n_bets >= MIN_BETS)
    if len(eligible) == 0:
        return None
    return int(eligible[np.argmax(profit[eligible])])


def walk_forward(search: Search, by_season: np.ndarray) -> dict | None:
    """Each season, bet the combination that made the most over the seasons
    before it (with at least MIN_BETS bets): what the search would really
    have earned someone following it."""
    seasons = search.seasons
    if len(seasons) <= WALK_FORWARD_WARMUP:
        return None
    picks = []
    for i in range(WALK_FORWARD_WARMUP, len(seasons)):
        chosen = _best(by_season[:, :i].sum(axis=1), search.n_bets[:, :i].sum(axis=1))
        if chosen is None:
            continue
        picks.append({"season": int(seasons[i]), "name": search.names[chosen],
                      "n_bets": int(search.n_bets[chosen, i]), "profit": float(by_season[chosen, i])})
    n = sum(p["n_bets"] for p in picks)
    profit = sum(p["profit"] for p in picks)
    return {"seasons": picks, "n_bets": n, "profit": profit, "roi": profit / n if n else None}


def luck_benchmark(search: Search, real_best_profit: float, n_sims: int = N_LUCK_SIMS, seed: int = 7) -> dict:
    """The search rerun on seasons simulated from the market's fair odds."""
    rng = np.random.default_rng(seed)
    won = simulate_outcomes(search.df, search.cand, n_sims, rng)
    totals = search.total_profit_many(won)
    eligible = search.n_bets.sum(axis=1) >= MIN_BETS
    best = totals[eligible].max(axis=0)
    return {
        "n_sims": n_sims,
        "best_profit_median": float(np.median(best)),
        "best_profit_p90": float(np.percentile(best, 90)),
        # share of simulated searches whose best did at least as well as the real one
        "share_as_good": float((best >= real_best_profit).mean()),
    }


def search_report(df: pd.DataFrame) -> dict | None:
    """Best combinations over all seasons in `df` (predictions + odds +
    results, as merged by betting.build_report), plus the two checks."""
    if df.empty or df["season_start_year"].nunique() < 2:
        return None
    search = Search(df)
    actual = search.cand["won"].to_numpy()
    by_season = search.profit_by_season(actual)
    total, n_bets = by_season.sum(axis=1), search.n_bets.sum(axis=1)

    # hit counts and average odds, for the table
    single_won, acca_won = actual.astype(float), np.zeros(len(search.accas))
    losses = search.acca_picks @ (~actual).astype(np.float32)
    acca_won[losses == 0] = 1.0
    wins = search._per_season(single_won, acca_won).sum(axis=1)
    odds_sum = search._per_season(search.cand["odds"].to_numpy(), search.accas["odds"].to_numpy()).sum(axis=1)

    order = np.argsort(-total, kind="stable")
    top, seen = [], set()
    for i in order:
        if n_bets[i] < MIN_BETS:
            continue
        signature = (int(n_bets[i]), round(float(total[i]), 6))  # same bets under another description
        if signature in seen:
            continue
        seen.add(signature)
        top.append(
            {
                "name": search.names[i],
                "n_bets": int(n_bets[i]),
                "hit_rate": float(wins[i] / n_bets[i]),
                "avg_odds": float(odds_sum[i] / n_bets[i]),
                "profit": float(total[i]),
                "roi": float(total[i] / n_bets[i]),
                "seasons_won": int((by_season[i] > 0).sum()),
                "seasons_played": int((search.n_bets[i] > 0).sum()),
                "by_season": [float(v) for v in by_season[i]],
            }
        )
        if len(top) == TOP_N:
            break

    return {
        "n_combinations": len(search.names),
        "min_bets": MIN_BETS,
        "seasons": [int(s) for s in search.seasons],
        "n_profitable": int(((total > 0) & (n_bets >= MIN_BETS)).sum()),
        "n_ranked": int((n_bets >= MIN_BETS).sum()),
        "top": top,
        "walk_forward": walk_forward(search, by_season),
        "luck": luck_benchmark(search, top[0]["profit"]) if top else None,
    }
