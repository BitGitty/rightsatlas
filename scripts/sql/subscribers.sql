-- SUBSCRIBERS (2026-11-22). Owner: our own audience that does not depend on Google ("tell me when a film becomes
-- free"). Stores only the e-mail address, what they asked for, and when. Readable only by the owner's key.
create table if not exists subscribers (
  id bigserial primary key, site text not null, email text not null, topic text, path text,
  created timestamptz not null default now(), unsubscribed boolean not null default false,
  unique (site, email, topic));
alter table subscribers enable row level security;

create or replace function public.subscribe(p_site text, p_email text, p_topic text default null, p_path text default null)
returns text language plpgsql security definer set search_path to 'public' as $$
declare e text := lower(trim(p_email));
begin
  if e !~ '^[^@\s]{1,64}@[^@\s]{1,190}\.[a-z]{2,24}$' then return 'invalid'; end if;
  -- simple abuse cap: at most 30 new sign-ups per hour site-wide
  if (select count(*) from subscribers where site = p_site and created > now() - interval '1 hour') >= 30 then
    return 'busy'; end if;
  insert into subscribers (site, email, topic, path)
  values (left(coalesce(p_site,'?'),40), left(e,254), left(nullif(p_topic,''),120), left(p_path,300))
  on conflict (site, email, topic) do update set unsubscribed = false;
  return 'ok';
end $$;

create or replace function public.studio_subscribers(p_site text, p_key text)
returns json language plpgsql security definer set search_path to 'public' as $$
declare ok boolean; r json;
begin
  select exists(select 1 from studio_keys where site = p_site
                and key_hash = encode(sha256(convert_to(p_key,'UTF8')),'hex')) into ok;
  if not ok then perform pg_sleep(1); return null; end if;
  select json_build_object(
    'total', (select count(distinct email) from subscribers where site = p_site and not unsubscribed),
    'last7', (select count(*) from subscribers where site = p_site and created > now() - interval '7 days'),
    'topics', (select json_agg(x) from (select coalesce(topic,'(all news)') topic, count(*) n from subscribers
               where site = p_site and not unsubscribed group by 1 order by 2 desc limit 20) x)) into r;
  return r;
end $$;

grant execute on function public.subscribe(text,text,text,text) to anon, authenticated;
grant execute on function public.studio_subscribers(text,text) to anon, authenticated;
