#!/usr/bin/env python
"""CLI: poll a URL until it responds, for run_app.bat.

Used instead of a fixed sleep before opening the browser: uvicorn's actual
startup time (importing pandas/sklearn, fitting the Elo/Poisson models,
running the season simulation) varies enough that a short fixed delay opened
the browser before the server was ready, showing "can't reach this site".

Usage:
    python scripts/wait_for_server.py http://localhost:8000/api/teams 20

Exits 0 as soon as the URL responds, 1 if `timeout_seconds` (default 20)
elapses first. Deliberately dependency-free (urllib, not requests) so it
works even before `pip install -r requirements.txt` has run.
"""
import sys
import time
import urllib.request


def main():
    url = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000/"
    timeout_seconds = float(sys.argv[2]) if len(sys.argv) > 2 else 20.0

    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        try:
            urllib.request.urlopen(url, timeout=1)
            sys.exit(0)
        except Exception:
            time.sleep(0.5)
    sys.exit(1)


if __name__ == "__main__":
    main()
