# talentsphere-supabase-keepalive

A small, read-only job that pings the TalentSphere production Supabase project
so the free-tier database is not paused for inactivity.

## What it does

- Runs on a GitHub Actions schedule (Monday and Thursday, 06:00 UTC) and on demand.
- Sends HTTP **GET** requests only:
  1. `GET {SUPABASE_URL}/auth/v1/health` - confirms the project is up and the key is accepted (expects 200).
  2. `GET {SUPABASE_URL}/rest/v1/<KEEPALIVE_TABLE>?select=<cols>&limit=1` - only when `KEEPALIVE_TABLE` is set. This is the request that counts as REST/database activity.
- It does **not** insert, update, delete, or alter any data or schema.
- Uses only the Python standard library.

## Setup

1. Add two repository **secrets** (Settings → Secrets and variables → Actions → Secrets → New repository secret):

   | Name | Value |
   | --- | --- |
   | `SUPABASE_URL` | `https://qidckctwrkxyiwworchd.supabase.co` (the API URL, not the dashboard link) |
   | `SUPABASE_PUBLISHABLE_KEY` | The publishable key (`sb_publishable_…`) from Project Settings → API Keys |

   Do not use the `service_role` or secret key.

2. Optional but recommended: once a table exists, add a repository **variable** (Variables tab) so the job makes a real REST request:

   | Name | Value |
   | --- | --- |
   | `KEEPALIVE_TABLE` | the table name, for example `keepalive_ping` |

   Without `KEEPALIVE_TABLE`, the job only checks auth health and logs a warning. That may not count as database activity for Supabase's pause rule.

3. Run the job once to confirm: Actions → "Supabase keep-alive" → Run workflow. A passing run logs `auth-health: OK (HTTP 200…)`.

## Local test

```bash
export SUPABASE_URL="https://qidckctwrkxyiwworchd.supabase.co"
export SUPABASE_PUBLISHABLE_KEY="<publishable key>"
python3 scripts/keepalive.py
```

## Notes

- The PostgREST root (`/rest/v1/`) is **not** used. Supabase accepts only secret keys there and returns `401 Secret API key required` for publishable keys.
- Errors print the HTTP status and the first part of Supabase's response body, which states the cause.
- The workflow is scheduled, so GitHub may delay runs by a few minutes. Two runs a week leave a margin under the 7-day pause limit.
- GitHub disables scheduled workflows after 60 days without repository activity. Re-enable the workflow if that happens, or keep a periodic commit.
