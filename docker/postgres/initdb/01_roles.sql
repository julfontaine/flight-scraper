-- The shared migration (supabase/migrations/0001_init.sql) grants/revokes on the Supabase API roles.
-- Plain PostgreSQL does not have them, so create them as no-login roles: the grants then apply cleanly
-- and the migration stays a single file for both backends. Nothing can log in as these roles.
do $$
begin
  if not exists (select 1 from pg_roles where rolname = 'anon') then
    create role anon nologin;
  end if;
  if not exists (select 1 from pg_roles where rolname = 'authenticated') then
    create role authenticated nologin;
  end if;
end
$$;
