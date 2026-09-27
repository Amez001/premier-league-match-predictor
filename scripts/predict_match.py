#!/usr/bin/env python
"""CLI: predict a single match from the command line.

Usage:
    python scripts/predict_match.py "Arsenal" "Liverpool"
"""
import argparse

from pl_predictor.data.load import load_clean_matches
from pl_predictor.predict import MatchPredictor, format_prediction


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("home_team")
    parser.add_argument("away_team")
    args = parser.parse_args()

    matches = load_clean_matches()
    predictor = MatchPredictor(matches)

    try:
        pred = predictor.predict(args.home_team, args.away_team)
    except ValueError as exc:
        print(exc)
        print("\nKnown team names include:", ", ".join(predictor.known_teams[:15]), "...")
        return

    print(format_prediction(pred))


if __name__ == "__main__":
    main()
