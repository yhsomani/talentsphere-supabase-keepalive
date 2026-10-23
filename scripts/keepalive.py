#!/usr/bin/env python3
"""
Keep-alive ping for a Supabase project.

READ-ONLY by design: this script only issues HTTP GET requests.
It never inserts, updates, or deletes data, and never creates or alters schema.

Checks, in order:
  1. GET {SUPABASE_URL}/auth/v1/health  - confirms the project is up and the
     publishable key is accepted (expects HTTP 200).
  2. GET {SUPABASE_URL}/rest/v1/<KEEPALIVE_TABLE>?select=<cols>&limit=1
     - only when KEEPALIVE_TABLE is set. This is the request that counts as
       REST/database activity for Supabase's free-tier inactivity rule.

Why not /rest/v1/ (the PostgREST root)? Supabase only accepts secret keys there;
with a publishable key it returns 401 "Secret API key required". Table requests
accept publishable keys, so they are the correct ping once a table exists.

Environment variables:
  SUPABASE_URL             Required. e.g. https://qidckctwrkxyiwworchd.supabase.co
                           (the API URL, not the dashboard URL).
  SUPABASE_PUBLISHABLE_KEY Required. Publishable (sb_publishable_...) or legacy anon
                           key. Sent only in the apikey header.
  KEEPALIVE_TABLE          Optional. An existing table to read with limit=1.
  KEEPALIVE_SELECT_COLUMN  Optional, default "*". Column list for the table read.
"""

import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

MAX_ATTEMPTS = 3
RETRY_DELAY_SECONDS = 10
TIMEOUT_SECONDS = 20
ERROR_BODY_CHARS = 300


def log(message: str) -> None:
    print(f"[keepalive] {message}", flush=True)


def get(url: str, headers: dict) -> tuple[int, str]:
    request = urllib.request.Request(url, headers=headers, method="GET")
    with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
        body = response.read().decode("utf-8", errors="replace")
        return response.status, body


def request_with_retries(label: str, url: str, headers: dict) -> bool:
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            status, body = get(url, headers)
            if 200 <= status < 300:
                log(f"{label}: OK (HTTP {status}, {len(body)} bytes)")
                return True
            log(f"{label}: unexpected HTTP {status} on attempt {attempt}")
        except urllib.error.HTTPError as error:
            details = error.read().decode("utf-8", errors="replace")[:ERROR_BODY_CHARS]
            log(f"{label}: HTTP {error.code} on attempt {attempt}: {error.reason} {details}")
            # 4xx means misconfiguration (bad key, wrong URL, missing table);
            # retrying will not help.
            if 400 <= error.code < 500:
                return False
        except (urllib.error.URLError, TimeoutError) as error:
            log(f"{label}: network error on attempt {attempt}: {error}")

        if attempt < MAX_ATTEMPTS:
            time.sleep(RETRY_DELAY_SECONDS)
    return False


def main() -> int:
    base_url = os.environ.get("SUPABASE_URL", "").strip().rstrip("/")
    key = os.environ.get("SUPABASE_PUBLISHABLE_KEY", "").strip()

    if not base_url or not key:
        log("Missing SUPABASE_URL or SUPABASE_PUBLISHABLE_KEY. Set them as secrets.")
        return 2

    headers = {
        "apikey": key,
        "Accept": "application/json",
        "User-Agent": "talentsphere-keepalive/1.0",
    }

    # 1) Auth health: confirms the project is reachable and the key is accepted.
    ok = request_with_retries("auth-health", f"{base_url}/auth/v1/health", headers)

    # 2) Table read: the request that counts as database activity.
    table = os.environ.get("KEEPALIVE_TABLE", "").strip()
    if table:
        columns = os.environ.get("KEEPALIVE_SELECT_COLUMN", "*").strip() or "*"
        query = urllib.parse.urlencode({"select": columns, "limit": "1"})
        table_url = f"{base_url}/rest/v1/{urllib.parse.quote(table)}?{query}"
        ok = request_with_retries(f"table:{table}", table_url, headers) and ok
    else:
        log(
            "WARNING: KEEPALIVE_TABLE is not set, so no REST/database request was made. "
            "Create a table and set KEEPALIVE_TABLE to keep the database active."
        )

    log("Done: all pings succeeded." if ok else "Done: one or more pings FAILED.")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
