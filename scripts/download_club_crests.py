#!/usr/bin/env python
"""CLI: best-effort fetch of real club crest images from Wikipedia.

Usage:
    python scripts/download_club_crests.py

Writes frontend/public/crests/<slug>.png for each of the 20 current clubs it
manages to resolve; skips clubs that already have one (--force to re-fetch).
The resulting files are committed, so this only needs re-running when a
newly promoted club arrives. Anything it can't confidently resolve is simply
skipped; the frontend's <ClubCrest> component falls back to a colored
monogram for those, so a missing crest never breaks the UI.

Wikipedia's `pageimages` API deliberately excludes non-free logos, so this
walks the article's image list instead and picks the most plausible crest
file by filename heuristics (prefers "<club> fc.svg"/"crest.svg"/"logo.svg",
avoids filenames tagged with an old crest's year).
"""
from __future__ import annotations

import re
import sys
import time
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from pl_predictor.data.load import get_current_season_teams, load_clean_matches  # noqa: E402

WIKI_API = "https://en.wikipedia.org/w/api.php"
HEADERS = {"User-Agent": "premier-league-match-predictor (personal, non-commercial project)"}
OUT_DIR = Path(__file__).resolve().parents[1] / "frontend" / "public" / "crests"
THUMB_WIDTH = 200

# football-data.co.uk name -> Wikipedia article title. Needed because the two
# sources spell several clubs differently (e.g. "Man City" vs "Manchester
# City F.C."), same issue as FBREF_TEAM_NAME_FIXES in player_stats.py.
WIKIPEDIA_TITLES = {
    "Arsenal": "Arsenal F.C.",
    "Aston Villa": "Aston Villa F.C.",
    "Bournemouth": "AFC Bournemouth",
    "Brentford": "Brentford F.C.",
    "Brighton": "Brighton & Hove Albion F.C.",
    "Burnley": "Burnley F.C.",
    "Chelsea": "Chelsea F.C.",
    "Crystal Palace": "Crystal Palace F.C.",
    "Everton": "Everton F.C.",
    "Fulham": "Fulham F.C.",
    "Leeds": "Leeds United F.C.",
    "Liverpool": "Liverpool F.C.",
    "Man City": "Manchester City F.C.",
    "Man United": "Manchester United F.C.",
    "Newcastle": "Newcastle United F.C.",
    "Nottm Forest": "Nottingham Forest F.C.",
    "Sunderland": "Sunderland A.F.C.",
    "Tottenham": "Tottenham Hotspur F.C.",
    "West Ham": "West Ham United F.C.",
    "Wolves": "Wolverhampton Wanderers F.C.",
    "Coventry": "Coventry City F.C.",
    "Hull": "Hull City A.F.C.",
    "Ipswich": "Ipswich Town F.C.",
    "Leicester": "Leicester City F.C.",
    "Southampton": "Southampton F.C.",
    "Sheffield United": "Sheffield United F.C.",
    "Luton": "Luton Town F.C.",
    "Norwich": "Norwich City F.C.",
    "Watford": "Watford F.C.",
    "Middlesbrough": "Middlesbrough F.C.",
    "West Brom": "West Bromwich Albion F.C.",
}

_YEAR_RE = re.compile(r"(18|19|20)\d{2}")
_GOOD_HINTS = ("fc.svg", "fc.png", "crest.svg", "crest.png", "logo.svg", "logo.png", "badge.svg", "badge.png")
# Generic Wikimedia chrome, or other same-name-but-wrong-thing files (a
# council's coat of arms, a league-performance chart, ...) that happen to
# match the "*.svg"/"logo" hints or contain the club's name but are never the
# actual crest - must be excluded regardless of team name.
_GENERIC_BLOCKLIST = (
    "commons-logo",
    "wiktionary",
    "wikiquote",
    "edit-clear",
    "ambox",
    "wikimedia-logo",
    "league performance",
    "arms of",
    "coat of arms",
    "city council",
    "kit body",
    "kit left arm",
    "kit right arm",
    "kit shorts",
    "kit socks",
    "kit half",
    "shirt pattern",
)
# Filenames containing these are a real crest but an outdated one - only used
# if nothing better is found (see the no_old/no_year fallback order below).
_STALE_HINTS = ("old logo", "old crest", "former")

# The distinctive word(s) from each team's name that a genuine crest filename
# should contain (avoids e.g. matching Wikipedia's generic "Commons-logo.svg"
# just because it also ends in "logo.svg").
_NAME_KEYWORDS = {
    "Arsenal": ["arsenal"],
    "Aston Villa": ["aston villa", "avfc"],
    "Bournemouth": ["bournemouth"],
    "Brentford": ["brentford"],
    "Brighton": ["brighton"],
    "Burnley": ["burnley"],
    "Chelsea": ["chelsea"],
    "Crystal Palace": ["crystal palace"],
    "Everton": ["everton"],
    "Fulham": ["fulham"],
    "Leeds": ["leeds"],
    "Liverpool": ["liverpool"],
    "Man City": ["manchester city", "man city"],
    "Man United": ["manchester united", "man utd", "man united"],
    "Newcastle": ["newcastle"],
    "Nottm Forest": ["nottingham forest", "notts forest"],
    "Sunderland": ["sunderland"],
    "Tottenham": ["tottenham"],
    "West Ham": ["west ham"],
    "Wolves": ["wolverhampton", "wolves"],
    "Coventry": ["coventry"],
    "Hull": ["hull city"],
    "Ipswich": ["ipswich"],
    "Leicester": ["leicester"],
    "Southampton": ["southampton"],
    "Sheffield United": ["sheffield united"],
    "Luton": ["luton"],
    "Norwich": ["norwich"],
    "Watford": ["watford"],
    "Middlesbrough": ["middlesbrough"],
    "West Brom": ["west bromwich", "west brom"],
}


def slugify(team: str) -> str:
    slug = team.lower()
    slug = re.sub(r"[^a-z0-9]+", "-", slug).strip("-")
    return slug


def _pick_crest_filename(team: str, images: list[str]) -> str | None:
    keywords = _NAME_KEYWORDS.get(team, [team.lower()])
    candidates = [
        img
        for img in images
        if img.lower().endswith((".svg", ".png"))
        and not any(bad in img.lower() for bad in _GENERIC_BLOCKLIST)
        and any(kw in img.lower() for kw in keywords)
    ]
    # Prefer filenames that look like the current crest: no year and no
    # "old"/"former" marker in the name, falling back progressively.
    fresh = [
        c for c in candidates if not _YEAR_RE.search(c) and not any(h in c.lower() for h in _STALE_HINTS)
    ]
    no_year = [c for c in candidates if not _YEAR_RE.search(c)]
    for pool in (fresh, no_year, candidates):
        for hint in _GOOD_HINTS:
            for c in pool:
                if c.lower().replace(" ", "").endswith(hint.replace(" ", "")):
                    return c
        if pool:
            return pool[0]  # no exact hint match, but still name-relevant - better than nothing
    return None


def _get_with_retry(session: requests.Session, url: str, **kwargs) -> requests.Response:
    """GET with a couple of retries on 429 (Wikipedia rate limiting) using
    exponential backoff - a handful of quick lookups per club otherwise trips
    it easily.
    """
    for attempt in range(4):
        resp = session.get(url, **kwargs)
        if resp.status_code != 429:
            resp.raise_for_status()
            return resp
        time.sleep(2**attempt)  # 1s, 2s, 4s, 8s
    resp.raise_for_status()
    return resp


def _fetch_image_thumb_url(session: requests.Session, filename: str) -> str | None:
    resp = _get_with_retry(
        session,
        WIKI_API,
        params={
            "action": "query",
            "titles": filename,
            "prop": "imageinfo",
            "iiprop": "url",
            "iiurlwidth": THUMB_WIDTH,
            "format": "json",
        },
        headers=HEADERS,
        timeout=15,
    )
    pages = resp.json().get("query", {}).get("pages", {})
    for page in pages.values():
        info = page.get("imageinfo")
        if info:
            # thumburl rasterizes SVGs to PNG automatically at the requested width.
            return info[0].get("thumburl") or info[0].get("url")
    return None


def fetch_crest(session: requests.Session, team: str, article_title: str) -> bool:
    resp = _get_with_retry(
        session,
        WIKI_API,
        params={"action": "query", "titles": article_title, "prop": "images", "imlimit": 100, "format": "json"},
        headers=HEADERS,
        timeout=15,
    )
    pages = resp.json().get("query", {}).get("pages", {})
    images = [img["title"] for page in pages.values() for img in page.get("images", [])]

    filename = _pick_crest_filename(team, images)
    if filename is None:
        print(f"  {team}: no crest candidate found, skipping (will use a monogram)")
        return False

    thumb_url = _fetch_image_thumb_url(session, filename)
    if thumb_url is None:
        print(f"  {team}: could not resolve a URL for {filename}, skipping")
        return False

    img_resp = _get_with_retry(session, thumb_url, headers=HEADERS, timeout=15)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    dest = OUT_DIR / f"{slugify(team)}.png"
    dest.write_bytes(img_resp.content)
    print(f"  {team}: saved {dest.name} (from {filename})")
    return True


def main():
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--force", action="store_true", help="re-fetch crests that already exist on disk")
    args = parser.parse_args()

    matches = load_clean_matches()
    teams = get_current_season_teams(matches)

    session = requests.Session()
    resolved = 0
    for team in teams:
        if not args.force and (OUT_DIR / f"{slugify(team)}.png").exists():
            print(f"  {team}: already have a crest, skipping (use --force to re-fetch)")
            resolved += 1
            continue

        title = WIKIPEDIA_TITLES.get(team)
        if title is None:
            print(f"  {team}: no Wikipedia title configured, skipping")
            continue
        try:
            if fetch_crest(session, team, title):
                resolved += 1
        except requests.RequestException as exc:
            print(f"  {team}: request failed ({exc}), skipping")
        time.sleep(3)  # be polite to Wikipedia's API

    print(f"\nResolved {resolved}/{len(teams)} crests into {OUT_DIR}")
    print("Teams without a crest fall back to a colored monogram in the UI.")


if __name__ == "__main__":
    main()
