-- ============================================================================
-- Supabase lock-down for the Django "public" schema
-- ============================================================================
-- Fixes the Supabase Security Advisor findings emailed on 17 Oct 2026:
--   * rls_disabled_in_public      -> "Table publicly accessible"
--   * sensitive_columns_exposed   -> "Sensitive data publicly accessible"
--
-- Why this is safe for the Django app:
--   * The app connects with DATABASE_URL as the `postgres` role.
--   * In Supabase that role has BYPASSRLS = true (verified on this project),
--     so enabling RLS without policies does not affect Django queries or
--     `manage.py migrate`.
--   * The project has no Supabase JS client and does not call PostgREST, so
--     the `anon` / `authenticated` roles do not need any access at all.
--
-- Run in: Supabase Dashboard -> SQL Editor (executes as `postgres`).
-- Then re-open Advisor -> Security Advisor and refresh.
-- ============================================================================

begin;

-- ---------------------------------------------------------------------------
-- 1. Remove the REST API's reach into the public schema.
--    (anon key is public by design, so it must not be able to see these
--     tables: auth_user hashes, django_session keys, user PII, OAuth tokens)
-- ---------------------------------------------------------------------------
revoke all on schema public from anon, authenticated;
revoke all on all tables    in schema public from anon, authenticated;
revoke all on all sequences in schema public from anon, authenticated;
revoke all on all functions in schema public from anon, authenticated;

-- ---------------------------------------------------------------------------
-- 2. Make sure tables created later by `manage.py migrate` are not
--    auto-granted to the API roles either.
-- ---------------------------------------------------------------------------
alter default privileges in schema public revoke all on tables    from anon, authenticated;
alter default privileges in schema public revoke all on sequences from anon, authenticated;
alter default privileges in schema public revoke all on functions from anon, authenticated;

-- ---------------------------------------------------------------------------
-- 3. Enable RLS on every existing table in `public`.
--    No policies on purpose: only the owner `postgres` (Django) may read.
--    The guard aborts the script instead of locking Django out if the
--    current role cannot bypass RLS.
-- ---------------------------------------------------------------------------
do $$
declare
    r record;
begin
    if not (select coalesce(rolbypassrls, false) or rolsuper
            from pg_roles
            where rolname = current_user) then
        raise exception
            'Role % cannot bypass RLS. Run this in the Supabase SQL Editor as postgres.',
            current_user;
    end if;

    for r in
        select c.relname
        from pg_class c
        join pg_namespace n on n.oid = c.relnamespace
        where n.nspname = 'public'
          and c.relkind = 'r'
          and not c.relrowsecurity
    loop
        execute format('alter table public.%I enable row level security', r.relname);
    end loop;
end
$$;

commit;

-- ============================================================================
-- VERIFY (run these one block at a time after the commit above)
-- ============================================================================
-- a) Expect 0 rows: every public table now has RLS enabled.
-- select c.relname
-- from pg_class c
-- join pg_namespace n on n.oid = c.relnamespace
-- where n.nspname = 'public' and c.relkind = 'r' and not c.relrowsecurity;
--
-- b) Expect "permission denied for schema public" (that is the goal).
-- set role anon;
-- select count(*) from public.auth_user;
-- reset role;
--
-- c) Expect a normal number: Django's postgres role still has full access.
-- select count(*) from public.auth_user;

-- ============================================================================
-- ROLLBACK (only if you ever decide to use the Supabase REST API/JS client)
-- ============================================================================
-- grant usage on schema public to anon, authenticated;
-- grant all on all tables in schema public to anon, authenticated;
-- grant all on all sequences in schema public to anon, authenticated;
-- alter table public.<table_name> disable row level security;   -- per table
-- (Re-enabling the REST API for auth_user/django_session is NOT recommended.)
