# talentsphere-supabase-keepalive

A small, read-only job that pings the TalentSphere production Supabase project
so the free-tier database is not paused for inactivity.

## What it does

- Runs on a GitHub Actions schedule (Monday and Thursday, 06:00 UTC) and on demand.
- Sends HTTP **GET** requests only:
  - `GET {SUPABASE_URL}/rest/v1/` (PostgREST root, works with zero tables), and
  - optionally `GET /rest/v1/<table>?select=...&limit=1` if `KEEPALIVE_TABLE` is set.
- It does **not** insert, update, delete, or alter any data or schema.
- Uses only the Python standard library.

## One-time setup

1. Create a **private** GitHub repository (for example `yhsomani/talentsphere-supabase-keepalive`) and push this folder to it:

   ```bash
   cd talentsphere-supabase-keepalive
   git init -b main
   git add .
   git commit -m "Add Supabase keep-alive workflow"
   gh repo create talentsphere-supabase-keepalive --private --source . --push
   ```

2. Add the project URL and publishable key as repository **secrets**
   (Settings → Secrets and variables → Actions → New repository secret), or with the CLI:

   ```bash
   gh secret set SUPABASE_URL --body "https://qidckctwrkxyiwworchd.supabase.co"
   gh secret set SUPABASE_PUBLISHABLE_KEY    # paste the key when prompted
   ```

   Use the **publishable/anon** key from the Supabase dashboard (Project Settings → API Keys).
   Do not use the `service_role` key.

3. Optional: once a table exists, set a repository **variable** so the job also runs a read-only select:

   ```bash
   gh variable set KEEPALIVE_TABLE --body "your_table_name"
   ```

4. Trigger a first run to confirm: Actions → "Supabase keep-alive" → Run workflow.

## Local test

```bash
export SUPABASE_URL="https://qidckctwrkxyiwworchd.supabase.co"
export SUPABASE_PUBLISHABLE_KEY="<publishable key>"
python3 scripts/keepalive.py
```

## Notes

- Supabase's free-tier inactivity rule counts REST API requests and database connections. A GET to the REST root is a REST request, so it counts as activity.
- The workflow is scheduled, so GitHub may delay runs by a few minutes. Two runs a week leave a comfortable margin under the 7-day limit.
- Scheduled workflows on GitHub are disabled automatically after 60 days without repository activity. Re-enable the workflow if that happens, or keep a periodic commit.
- If the job fails with HTTP 401 or 403, check that the key is the publishable key and that the URL matches the project.
