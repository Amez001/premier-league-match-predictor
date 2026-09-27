"""Streamlit prediction dashboard.

Run with:
    streamlit run dashboard/app.py
"""
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

# allow running with `streamlit run dashboard/app.py` without installing the package
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from pl_predictor.data.load import load_clean_matches  # noqa: E402
from pl_predictor.predict import MatchPredictor  # noqa: E402

st.set_page_config(page_title="Premier League Match Predictor", page_icon="⚽", layout="centered")


@st.cache_resource(show_spinner="Loading historical data and fitting models...")
def get_predictor() -> MatchPredictor:
    matches = load_clean_matches()
    return MatchPredictor(matches)


st.title("⚽ Premier League Match Predictor")
st.caption(
    "Elo ratings + logistic regression for match outcome, Poisson goals model for the scoreline. "
    "Trained on historical results from football-data.co.uk."
)

try:
    predictor = get_predictor()
except FileNotFoundError as exc:
    st.error(f"{exc}")
    st.stop()

teams = predictor.known_teams
col1, col2 = st.columns(2)
with col1:
    home = st.selectbox("Home team", teams, index=teams.index("Arsenal") if "Arsenal" in teams else 0)
with col2:
    away_options = [t for t in teams if t != home]
    away = st.selectbox("Away team", away_options, index=away_options.index("Liverpool") if "Liverpool" in away_options else 0)

if st.button("Predict", type="primary", use_container_width=True):
    pred = predictor.predict(home, away)

    st.divider()
    st.subheader(f"{pred['home_team']} vs {pred['away_team']}")

    c1, c2, c3 = st.columns(3)
    c1.metric(f"{home} win", f"{pred['home_win_proba']*100:.1f}%")
    c2.metric("Draw", f"{pred['draw_proba']*100:.1f}%")
    c3.metric(f"{away} win", f"{pred['away_win_proba']*100:.1f}%")

    st.bar_chart(
        pd.DataFrame(
            {"probability": [pred["home_win_proba"], pred["draw_proba"], pred["away_win_proba"]]},
            index=[f"{home} win", "Draw", f"{away} win"],
        )
    )

    st.success(f"Predicted result: **{pred['predicted_result']}**")

    st.subheader("Expected goals")
    eg1, eg2 = st.columns(2)
    eg1.metric(home, f"{pred['expected_goals_home']:.2f}")
    eg2.metric(away, f"{pred['expected_goals_away']:.2f}")

    st.subheader("Most likely scorelines")
    scores_df = pd.DataFrame(pred["most_likely_scores"])
    scores_df["score"] = scores_df["home_goals"].astype(str) + "-" + scores_df["away_goals"].astype(str)
    scores_df["probability (%)"] = (scores_df["probability"] * 100).map(lambda x: f"{x:.1f}")
    st.table(scores_df[["score", "probability (%)"]].set_index("score"))

    st.caption(f"Elo rating gap ({home} - {away}): {pred['elo_diff']:+.0f}")

st.divider()
with st.expander("Model backtest performance"):
    summary_path = Path(__file__).resolve().parents[1] / "reports" / "backtest_summary.csv"
    if summary_path.exists():
        st.dataframe(pd.read_csv(summary_path), use_container_width=True)
    else:
        st.info("Run `python scripts/run_backtest.py` first to generate backtest results.")
