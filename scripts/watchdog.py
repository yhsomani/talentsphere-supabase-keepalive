#!/usr/bin/env python3
"""Check GitHub Actions history for a recent successful *real* keepalive ping."""
import datetime as dt
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

UTC = dt.timezone.utc


def recent_success(runs, now, max_age_hours):
    threshold = now - dt.timedelta(hours=max_age_hours)
    for run in runs:
        # 'push' runs succeed on unit tests alone; only these events execute ping.
        if run.get("event") not in ("schedule", "workflow_dispatch"):
            continue
        if run.get("conclusion") != "success":
            continue
        timestamp = run.get("updated_at")
        if not timestamp:
            continue
        try:
            finished = dt.datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        except ValueError:
            continue
        if threshold <= finished <= now:
            return True
    return False


def main(environ=None, opener=urllib.request.urlopen, now=None):
    environ = os.environ if environ is None else environ
    token = environ.get("GITHUB_TOKEN", "")
    repo = environ.get("GITHUB_REPOSITORY", "")
    try:
        hours = int(environ.get("WATCHDOG_MAX_AGE_HOURS", "18"))
    except ValueError:
        print("[watchdog] Invalid maximum age.")
        return 2
    if not token or not repo or not all(part and part.replace("-", "").replace("_", "").isalnum() for part in repo.split("/")) or len(repo.split("/")) != 2 or not 6 <= hours <= 168:
        print("[watchdog] Invalid GitHub token/repository or age threshold.")
        return 2
    url = f"https://api.github.com/repos/{repo}/actions/workflows/keepalive.yml/runs?per_page=100"
    request = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "User-Agent": "talentsphere-keepalive-watchdog/1.0",
        },
    )
    try:
        with opener(request, timeout=20) as response:
            if response.status != 200:
                raise ValueError("unexpected status")
            data = json.load(response)
        runs = data.get("workflow_runs")
        if not isinstance(runs, list):
            raise ValueError("missing run history")
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError, ValueError) as error:
        print(f"[watchdog] Failed to retrieve workflow history ({type(error).__name__}).")
        return 1
    current = now or dt.datetime.now(UTC)
    if recent_success(runs, current, hours):
        print(f"[watchdog] OK: a successful database ping completed within {hours} hours.")
        return 0
    print(f"[watchdog] ALERT: no successful database ping in the last {hours} hours.")
    print("[watchdog] Investigate keepalive workflow runs, secrets, and Supabase project status.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
