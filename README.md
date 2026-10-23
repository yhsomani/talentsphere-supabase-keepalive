# TalentSphere Supabase keepalive

A least-privilege, read-only **database query** run by GitHub Actions twice weekly.
The previous /rest/v1/ root probe returned 401 with a publishable key because
Supabase requires a secret key at that endpoint. An Auth health probe returned
200, but does **not** establish that a database query happened.

## One-time setup (required before the workflow can succeed)

1. In the **correct Supabase project**, open SQL Editor and run
   [sql/keepalive_ping.sql](sql/keepalive_ping.sql). Review the SQL first. The
   function executes `SELECT 1`, returns JSON number `1`, and reads no user data.
   It uses `SECURITY INVOKER`, not `SECURITY DEFINER`.
2. In repository **Settings > Secrets and variables > Actions**, set:
   - `SUPABASE_URL`: HTTPS project origin, such as `https://YOUR_PROJECT.supabase.co`
   - `SUPABASE_PUBLISHABLE_KEY`: that project's publishable key
     (`sb_publishable_...`), or legacy anon JWT.
   **Do not store service_role or secret keys for this job.**
3. In **Actions > Supabase keep-alive > Run workflow**, launch one manual
   run on the default branch. The ping must report
   `Database RPC succeeded (HTTP 200, expected result 1).`
   View run history to verify actual scheduled executions.

The probe sends GET `/rest/v1/rpc/keepalive_ping` with only an `apikey`
header. The RPC must be in an exposed API schema (normally `public`), and
`anon` must be permitted to execute it. If the function is not available,
PostgREST may need its schema cache refreshed. The SQL is deliberately
idempotent, but grants must be reviewed according to project policy.

## Reliability and limitations

- GitHub's cron schedule is Monday and Thursday 06:00 **UTC**. GitHub Actions
  scheduled runs may be delayed, dropped, or disabled after repository inactivity.
- This runs an actual database query, but **no keepalive technique is guaranteed**
  to prevent Supabase free-tier pausing. Supabase's policy and what it counts as
  qualifying activity may change. Use a paid plan for uptime guarantees.
- A paused project may require manual restoration in Supabase before a ping
  can succeed. The script does not attempt to revive it with privileged API keys.
- A 401/403 usually means the wrong project/key or missing RPC permissions.
  A 404 usually means the RPC was not created/exposed in the target project.
- The job fails if the body is not the expected JSON scalar `1`.
  It never sends credentials in URLs or logs response bodies.
- Unauthenticated callers with the publishable key may invoke this RPC;
  the function must remain constant, read-only, and free of private data.
- The GitHub diagnostic workflow that printed API response bodies has been
  removed. If any sensitive data appeared in earlier logs, restrict access and
  rotate affected credentials.

## Local tests

```bash
python3 -m unittest discover -s tests -v
SUPABASE_URL=https://YOUR_PROJECT.supabase.co \
SUPABASE_PUBLISHABLE_KEY=sb_publishable_YOUR_KEY \
python3 scripts/keepalive.py
```

No dependencies beyond the Python standard library.
