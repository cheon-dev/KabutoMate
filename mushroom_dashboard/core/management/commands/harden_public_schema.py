"""Lock down the Supabase ``public`` schema used by this Django project.

Supabase exposes every table in the ``public`` schema through PostgREST to the
``anon`` and ``authenticated`` roles. Django creates its tables there, so
without this hardening anyone holding the (public-by-design) anon key could
read password hashes, session keys, customer PII and OAuth tokens.

The project talks to Postgres directly as the ``postgres`` role, which has
``BYPASSRLS`` in Supabase, so enabling RLS without policies does not affect the
application. Run this after adding tables (i.e. after ``migrate``) to keep the
Supabase Security Advisor clean.
"""

from django.core.management.base import BaseCommand, CommandError
from django.db import connection


HARDENING_STATEMENTS = [
    "revoke all on schema public from anon, authenticated",
    "revoke all on all tables in schema public from anon, authenticated",
    "revoke all on all sequences in schema public from anon, authenticated",
    "revoke all on all functions in schema public from anon, authenticated",
    "alter default privileges in schema public revoke all on tables from anon, authenticated",
    "alter default privileges in schema public revoke all on sequences from anon, authenticated",
    "alter default privileges in schema public revoke all on functions from anon, authenticated",
    """
    do $$
    declare
        r record;
    begin
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
    """,
]


class Command(BaseCommand):
    help = (
        'Revoke Supabase API access to the public schema and enable row level '
        'security on every Django table. Safe to re-run.'
    )

    def handle(self, *args, **options):
        if connection.vendor != 'postgresql':
            raise CommandError(
                'This command only applies to the PostgreSQL/Supabase database '
                f'(current engine: {connection.vendor}).'
            )

        with connection.cursor() as cursor:
            cursor.execute("select 1 from pg_roles where rolname in ('anon', 'authenticated')")
            if cursor.fetchone() is None:
                self.stdout.write(self.style.WARNING(
                    'Supabase roles "anon"/"authenticated" not found; nothing to harden.'
                ))
                return

            cursor.execute(
                "select coalesce(rolbypassrls, false) or rolsuper "
                "from pg_roles where rolname = current_user"
            )
            if not cursor.fetchone()[0]:
                raise CommandError(
                    'The current database role cannot bypass RLS. Enabling RLS would '
                    'lock the application out. Run this as the Supabase "postgres" role.'
                )

            database, role = None, None
            cursor.execute("select current_database(), current_user")
            database, role = cursor.fetchone()

            for statement in HARDENING_STATEMENTS:
                cursor.execute(statement)

            cursor.execute("""
                select count(*)
                from pg_class c
                join pg_namespace n on n.oid = c.relnamespace
                where n.nspname = 'public' and c.relkind = 'r' and not c.relrowsecurity
            """)
            unprotected = cursor.fetchone()[0]

            cursor.execute("""
                select count(*)
                from information_schema.role_table_grants
                where table_schema = 'public' and grantee in ('anon', 'authenticated')
            """)
            api_grants = cursor.fetchone()[0]

        self.stdout.write(self.style.SUCCESS(
            f'Hardened {database} as {role}: '
            f'{unprotected} table(s) without RLS, '
            f'{api_grants} API grant(s) left for anon/authenticated.'
        ))
        if unprotected or api_grants:
            self.stdout.write(self.style.WARNING(
                'Some objects are still exposed. Check that Django owns them '
                '(the revoke statements need table ownership).'
            ))
