-- Apply once in the Supabase SQL Editor for the intended project.
-- SECURITY INVOKER and a constant result: no access to user tables or data.
create or replace function public.keepalive_ping()
returns integer
language sql
stable
security invoker
set search_path = ''
as $function$
  select 1;
$function$;

revoke all on function public.keepalive_ping() from public;
revoke all on function public.keepalive_ping() from authenticated;
grant execute on function public.keepalive_ping() to anon;

-- Supabase REST may require the API role to have USAGE on the exposed schema.
-- Existing schema permissions vary between Supabase projects.
-- Do not revoke unrelated schema permissions just for this function.
