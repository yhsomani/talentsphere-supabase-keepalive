#!/usr/bin/env python3
"""Check for a recent successful database ping, not merely successful CI tests."""
import datetime as dt
import json
import os
import re
import sys
import urllib.error
import urllib.request

UTC = dt.timezone.utc


def recent_success(runs, now, max_age_hours):
    """Candidate completed runs; only scheduled/manual events on main qualify."""
    threshold = now - dt.timedelta(hours=max_age_hours)
    for run in runs:
        if run.get("event") not in ("schedule", "workflow_dispatch"):
            continue
        if run.get("head_branch") != "main" or run.get("conclusion") != "success":
            continue
        timestamp = run.get("updated_at")
        if not timestamp:
            continue
        try:
            finished = dt.datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        except (ValueError, TypeError, AttributeError):
            continue
        if threshold <= finished <= now:
            yield run


def fetch_json(url, token, opener):
    request = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "User-Agent": "talentsphere-keepalive-watchdog/2.0",
        },
    )
    with opener(request, timeout=20) as response:
        if response.status != 200:
            raise ValueError("unexpected GitHub API status")
        return json.load(response)


def main(environ=None, opener=urllib.request.urlopen, now=None):
    environ = os.environ if environ is None else environ
    token = environ.get("GITHUB_TOKEN", "")
    repo = environ.get("GITHUB_REPOSITORY", "")
    try:
        hours = int(environ.get("WATCHDOG_MAX_AGE_HOURS", "18"))
    except ValueError:
        print("[watchdog] Invalid maximum age.")
        return 2
    if not token or not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repo) or not 6 <= hours <= 168:
        print("[watchdog] Invalid GitHub token/repository or age threshold.")
        return 2
    base = f"https://api.github.com/repos/{repo}"
    try:
        data = fetch_json(f"{base}/actions/workflows/keepalive.yml/runs?branch=main&per_page=100", token, opener)
        runs = data.get("workflow_runs")
        if not isinstance(runs, list):
            raise ValueError("missing run history")
        current = now or dt.datetime.now(UTC)
        for run in recent_success(runs, current, hours):
            run_id = run.get("id")
            if not isinstance(run_id, int) or run_id <= 0:
                continue
            # A successful workflow is not enough: verify the actual database ping job.
            jobs = fetch_json(f"{base}/actions/runs/{run_id}/jobs?per_page=100", token, opener)
            if any(job.get("name") == "ping" and job.get("conclusion") == "success"
                   for job in jobs.get("jobs", [])):
                print(f"[watchdog] OK: verified successful database ping within {hours} hours.")
                return 0
    except (urllib.error.URLError, TimeoutError, OSError, ValueError, TypeError, KeyError) as error:
        print(f"[watchdog] Unable to verify ping history ({type(error).__name__}).")
        return 1
    print(f"[watchdog] ALERT: no verified successful database ping in the last {hours} hours.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
