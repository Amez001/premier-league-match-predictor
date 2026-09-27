"""Real, current-season statistics for the dashboard (no modelling involved).

Everything here is read straight off the data: the league table from played
matches, each club's last five results, the latest results, and the top
scorers / assist providers from the FBref player snapshot.
"""
from __future__ import annotations

import pandas as pd

from pl_predictor.data.load import get_current_season_teams
from pl_predictor.models.player_goals import player_identity
from pl_predictor.simulation import league_table

FORM_LENGTH = 5
LEADERS_SHOWN = 10
RECENT_RESULTS_SHOWN = 10


def team_form(season_matches: pd.DataFrame, teams: list[str], n: int = FORM_LENGTH) -> dict[str, list[str]]:
    """Each club's last n results, oldest first: 'W', 'D' or 'L'."""
    ordered = season_matches.sort_values(["date", "match_id"])
    form: dict[str, list[str]] = {t: [] for t in teams}
    for r in ordered.itertuples(index=False):
        if r.home_goals == r.away_goals:
            form[r.home_team].append("D")
            form[r.away_team].append("D")
        else:
            home_won = r.home_goals > r.away_goals
            form[r.home_team].append("W" if home_won else "L")
            form[r.away_team].append("L" if home_won else "W")
    return {t: results[-n:] for t, results in form.items()}


def player_leaders(player_df: pd.DataFrame) -> tuple[dict, dict]:
    """Top scorers and top assist providers, as {"rows": [...], "more_tied": n}.

    A player who changed clubs mid-season counts his goals at both (as the
    Golden Boot does) and is shown at his current club. `more_tied` counts
    players level with the last one shown but cut off by the list length, so
    the page can say so instead of silently picking some of them.
    """
    df = player_df.assign(_id=player_identity(player_df))
    totals = df.groupby("_id")[["season_goals", "season_assists", "minutes_90s"]].sum()
    current = df[df["is_current_club"]] if "is_current_club" in df.columns else df.drop_duplicates("_id")
    info = current.set_index("_id")[["player", "team", "position"]]
    per_player = info.join(totals).reset_index(drop=True)
    per_player = per_player.rename(columns={"season_goals": "goals", "season_assists": "assists"})
    per_player["goals"] = per_player["goals"].astype(int)
    per_player["assists"] = per_player["assists"].astype(int)

    def top(by: str, then: str) -> dict:
        ranked = per_player[per_player[by] > 0].sort_values([by, then, "minutes_90s"], ascending=[False, False, True])
        shown = ranked.head(LEADERS_SHOWN)
        more_tied = 0
        if len(shown) == LEADERS_SHOWN:
            more_tied = int((ranked[by] == shown[by].iloc[-1]).sum()) - int((shown[by] == shown[by].iloc[-1]).sum())
        return {"rows": shown.to_dict(orient="records"), "more_tied": more_tied}

    return top("goals", "assists"), top("assists", "goals")


def current_stats(matches: pd.DataFrame, player_df: pd.DataFrame | None) -> dict:
    season = int(matches["season_start_year"].max())
    played = matches[matches["season_start_year"] == season]
    teams = get_current_season_teams(matches)

    table = league_table(played, teams)
    form = team_form(played, teams)
    table["form"] = table["team"].map(form)

    recent = played.sort_values(["date", "match_id"], ascending=False).head(RECENT_RESULTS_SHOWN)
    recent_results = [
        {
            "date": r.date.date().isoformat(),
            "home_team": r.home_team,
            "away_team": r.away_team,
            "home_goals": int(r.home_goals),
            "away_goals": int(r.away_goals),
        }
        for r in recent.itertuples(index=False)
    ]

    empty = {"rows": [], "more_tied": 0}
    scorers, assisters = player_leaders(player_df) if player_df is not None else (empty, empty)
    total_goals = int((played["home_goals"] + played["away_goals"]).sum())

    return {
        "season_start_year": season,
        "matches_played": len(played),
        "total_goals": total_goals,
        "goals_per_match": total_goals / len(played) if len(played) else 0.0,
        "table": table.to_dict(orient="records"),
        "recent_results": recent_results,
        "top_scorers": scorers,
        "top_assisters": assisters,
    }
