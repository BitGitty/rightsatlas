-- RightsAtlas on-site suggestions (2026-10-10). Visitors submit through the RPC only;
-- the table is closed to anon/authenticated (RLS on, no policies). Spam: honeypot field,
-- 5/hour per hashed IP, 100/hour overall, length caps.
create table if not exists public.site_suggestions (
  id bigserial primary key,
  ts timestamptz not null default now(),
  site text not null,
  kind text not null check (kind in ('film','correction','idea','other')),
  film text, year text, page text,
  message text,
  email text,
  ip_hash text,
  handled boolean not null default false
);
alter table public.site_suggestions enable row level security;
revoke all on public.site_suggestions from anon, authenticated;

create or replace function public.submit_suggestion(
  p_site text, p_kind text, p_film text default null, p_year text default null,
  p_page text default null, p_message text default null, p_email text default null, p_hp text default null)
returns text language plpgsql security definer set search_path to 'public' as $fn$
declare v_ip text; v_hash text; v_n int;
begin
  if coalesce(p_hp, '') <> '' then return 'ok'; end if;              -- honeypot: bots fill it
  if p_kind is null or p_kind not in ('film','correction','idea','other') then return 'bad kind'; end if;
  if p_kind = 'film' and coalesce(btrim(p_film), '') = '' then return 'film title needed'; end if;
  if p_kind <> 'film' and coalesce(btrim(p_message), '') = '' then return 'message needed'; end if;
  v_ip := split_part(coalesce(nullif(current_setting('request.headers', true), '')::json->>'x-forwarded-for', ''), ',', 1);
  v_hash := md5('ra-suggest-2026:' || v_ip);
  select count(*) into v_n from site_suggestions where ip_hash = v_hash and ts > now() - interval '1 hour';
  if v_n >= 5 then return 'too many'; end if;
  select count(*) into v_n from site_suggestions where ts > now() - interval '1 hour';
  if v_n >= 100 then return 'busy'; end if;
  insert into site_suggestions (site, kind, film, year, page, message, email, ip_hash)
  values (left(coalesce(p_site, '?'), 40), p_kind, left(btrim(p_film), 200), left(btrim(p_year), 10),
          left(btrim(p_page), 300), left(btrim(p_message), 4000), left(btrim(p_email), 200), v_hash);
  return 'ok';
end;
$fn$;
revoke all on function public.submit_suggestion(text,text,text,text,text,text,text,text) from public;
grant execute on function public.submit_suggestion(text,text,text,text,text,text,text,text) to anon;
