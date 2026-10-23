#!/usr/bin/env python3
"""
Keep-alive ping for a Supabase project.

READ-ONLY by design: this script only issues HTTP GET requests.
It never inserts, updates, or deletes data, and never creates or alters schema.

Environment variables:
  SUPABASE_URL             Required. e.g. https://qidckctwrkxyiwworchd.supabase.co
  SUPABASE_PUBLISHABLE_KEY Required. Publishable/anon key (sent as the apikey header).
                           Read-only access to public data is all this needs.
  KEEPALIVE_TABLE          Optional. Name of an existing table to run a
                           `select=<col>&limit=1` read against. Leave unset while the
                           project has no public tables; the REST root ping is used instead.
  KEEPALIVE_SELECT_COLUMN  Optional, default "*". Column list for the read.
"""

import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

MAX_ATTEMPTS = 3
RETRY_DELAY_SECONDS = 10
TIMEOUT_SECONDS = 20


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
            # 4xx means misconfiguration (bad key, wrong URL); retrying will not help.
            log(f"{label}: HTTP {error.code} on attempt {attempt}: {error.reason}")
            if 400 <= error.code < 500:
                return False
        except (urllib.error.URLError, TimeoutError) as error:
            log(f"{label}: network error on attempt {attempt}: {error}")

        if attempt < MAX_ATTEMPTS:
            time.sleep(RETRY_DELAY_SECONDS)
    return False


def main() -> int:
    base_url = os.environ.get("SUPABASE_URL", "").rstrip("/")
    key = os.environ.get("SUPABASE_PUBLISHABLE_KEY", "")

    if not base_url or not key:
        log("Missing SUPABASE_URL or SUPABASE_PUBLISHABLE_KEY. Set them as secrets.")
        return 2

    headers = {
        # Publishable keys (sb_publishable_...) are not JWTs, so they go only in
        # the apikey header. Sending them as a Bearer token causes 401 responses.
        "apikey": key,
        "Accept": "application/json",
        "User-Agent": "talentsphere-keepalive/1.0",
    }

    # 1) PostgREST root: a REST API request that is read-only and works with zero tables.
    ok = request_with_retries("rest-root", f"{base_url}/rest/v1/", headers)

    # 2) Optional: a read-only, limit-1 select against a named table, if one exists.
    table = os.environ.get("KEEPALIVE_TABLE", "").strip()
    if table:
        columns = os.environ.get("KEEPALIVE_SELECT_COLUMN", "*").strip() or "*"
        query = urllib.parse.urlencode({"select": columns, "limit": "1"})
        table_url = f"{base_url}/rest/v1/{urllib.parse.quote(table)}?{query}"
        ok = request_with_retries(f"table:{table}", table_url, headers) and ok

    log("Done: all pings succeeded." if ok else "Done: one or more pings FAILED.")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
