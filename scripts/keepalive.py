#!/usr/bin/env python3
"""Read-only, database-backed Supabase activity check.

Requires a dedicated public.keepalive_ping() STABLE SQL function returning 1.
No data, schema or user records are changed by this script.
"""
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

ATTEMPTS = 3
TIMEOUT = 15
RETRY_SECONDS = 5


def log(message):
    print(f"[keepalive] {message}", flush=True)


def configuration(environ):
    url = environ.get("SUPABASE_URL", "").strip().rstrip("/")
    key = environ.get("SUPABASE_PUBLISHABLE_KEY", "").strip()
    function = environ.get("KEEPALIVE_RPC", "keepalive_ping").strip()
    parts = urllib.parse.urlsplit(url)
    if (
        parts.scheme != "https" or not parts.hostname or parts.username
        or parts.password or parts.path or parts.query or parts.fragment
        or not parts.netloc or any(ch.isspace() for ch in url)
    ):
        raise ValueError("SUPABASE_URL must be an HTTPS project origin with no path or credentials")
    if not key or key.startswith(("sb_secret_", "sb_service_role_")):
        raise ValueError("Configure SUPABASE_PUBLISHABLE_KEY with a publishable/anon key, never a secret key")
    if not re.fullmatch(r"[A-Za-z_][A-Za-z_0-9]*", function):
        raise ValueError("KEEPALIVE_RPC must be a PostgreSQL function identifier")
    return url, key, function


def ping(url, key, function, opener=urllib.request.urlopen):
    path = urllib.parse.quote(function, safe="")
    req = urllib.request.Request(
        f"{url}/rest/v1/rpc/{path}",
        headers={"apikey": key, "Accept": "application/json", "User-Agent": "talentsphere-keepalive/2.0"},
        method="GET",
    )
    with opener(req, timeout=TIMEOUT) as response:
        if response.status != 200:
            raise RuntimeError(f"Unexpected HTTP {response.status}")
        body = response.read(4096)
        if json.loads(body) != 1:
            raise RuntimeError("RPC returned an unexpected value; expected JSON integer 1")


def main(environ=None, opener=urllib.request.urlopen, sleep=time.sleep):
    if environ is None:
        environ = os.environ
    try:
        url, key, function = configuration(environ)
    except ValueError as error:
        log(f"Configuration error: {error}")
        return 2
    for attempt in range(1, ATTEMPTS + 1):
        try:
            ping(url, key, function, opener)
            log("Database RPC succeeded (HTTP 200, expected result 1).")
            return 0
        except urllib.error.HTTPError as error:
            log(f"RPC failed: HTTP {error.code}.")
            if 400 <= error.code < 500 and error.code != 429:
                log("Check project URL, API key, and RPC creation/grants.")
                return 1
        except (urllib.error.URLError, TimeoutError, OSError) as error:
            log(f"Network/transport error: {type(error).__name__}")
        except (ValueError, RuntimeError, json.JSONDecodeError) as error:
            log(f"Unexpected RPC response: {type(error).__name__}")
            return 1
        if attempt < ATTEMPTS:
            sleep(RETRY_SECONDS * attempt)
    log("Database activity check failed after retries.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
