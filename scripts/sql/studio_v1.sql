-- STUDIO-V1 (2026-11-21). Owner: "better analysis data, just like YouTube Studio ... double down on content and
-- understand our audience". Aggregates only, no identity. Dashboard data is returned ONLY with the owner's key.
create extension if not exists pgcrypto;

alter table pageviews add column if not exists secs int;          -- seconds the page was visible (sent on leave)
alter table pageviews add column if not exists device text;       -- phone / tablet / computer (screen width)
alter table pageviews add column if not exists tz text;           -- browser time zone = rough region, not identity
alter table pageviews add column if not exists is_return boolean; -- this browser visited before (a flag, no id)

create table if not exists site_events (
  id bigserial primary key, site text not null, kind text not null, label text, path text,
  ts timestamptz not null default now());
create index if not exists site_events_site_ts on site_events (site, ts);
alter table site_events enable row level security;   -- no direct reads/writes; only through the functions below

create or replace function public.track_view3(p_site text, p_path text default null, p_ref text default null,
  p_kind text default null, p_utm text default null, p_visit text default null, p_device text default null,
  p_tz text default null, p_returning boolean default null)
returns bigint language plpgsql security definer set search_path to 'public' as $$
declare v_id bigint;
begin
  insert into pageviews (site, path, referrer, kind, utm, visit, device, tz, is_return)
  values (left(coalesce(p_site,'?'),40), left(p_path,300), left(nullif(p_ref,''),300), left(p_kind,20),
          left(nullif(p_utm,''),60), left(p_visit,40), left(p_device,12), left(p_tz,60), p_returning)
  returning id into v_id;
  return v_id;
end $$;

-- the same tab updates its own row: engaged flag and visible seconds (capped at 1 hour)
create or replace function public.track_time(p_id bigint, p_visit text, p_secs int, p_engaged boolean default false)
returns void language plpgsql security definer set search_path to 'public' as $$
begin
  update pageviews set secs = greatest(coalesce(secs,0), least(p_secs, 3600)),
                       engaged = engaged or p_engaged or p_secs >= 15
  where id = p_id and visit = p_visit and visit is not null and ts > now() - interval '2 hours';
end $$;

-- site search words and play clicks (what people want)
create or replace function public.track_event(p_site text, p_kind text, p_label text default null, p_path text default null)
returns void language plpgsql security definer set search_path to 'public' as $$
begin
  if p_kind not in ('search','play_film','play_song','outbound') then return; end if;
  insert into site_events (site, kind, label, path)
  values (left(coalesce(p_site,'?'),40), p_kind, left(lower(trim(p_label)),120), left(p_path,300));
end $$;

create table if not exists studio_keys (site text primary key, key_hash text not null);
alter table studio_keys enable row level security;

-- all dashboard numbers in one JSON, only for the right key
create or replace function public.studio_data(p_site text, p_key text, p_days int default 28)
returns json language plpgsql security definer set search_path to 'public' as $$
declare ok boolean; d int := least(greatest(coalesce(p_days,28),1),365); r json;
begin
  select exists(select 1 from studio_keys where site = p_site and key_hash = encode(sha256(convert_to(p_key,'UTF8')),'hex')) into ok;
  if not ok then perform pg_sleep(1); return null; end if;
  with v as (select * from pageviews where site = p_site and ts > now() - make_interval(days => d)),
       h as (select * from v where kind = 'human'),
       e as (select * from site_events where site = p_site and ts > now() - make_interval(days => d))
  select json_build_object(
    'days', d,
    'totals', (select json_build_object('views', count(*), 'human', count(*) filter (where kind='human'),
               'readers', count(*) filter (where kind='human' and engaged),
               'bots', count(*) filter (where kind in ('bot','automation')),
               'unknown_old', count(*) filter (where kind is null),
               'avg_secs', round(avg(secs) filter (where kind='human' and secs is not null)),
               'returning', count(*) filter (where kind='human' and is_return)) from v),
    'by_day', (select json_agg(x order by x.day) from (select (ts at time zone 'UTC')::date as day,
               count(*) filter (where kind='human') human, count(*) filter (where kind='human' and engaged) readers,
               count(*) filter (where kind is null) old_unknown, count(*) filter (where kind in ('bot','automation')) bots
               from v group by 1) x),
    'top_pages', (select json_agg(x) from (select path, count(*) views, count(*) filter (where engaged) readers,
               round(avg(secs)) avg_secs from h group by path order by count(*) desc limit 30) x),
    'sources', (select json_agg(x) from (select coalesce(utm, nullif(regexp_replace(coalesce(referrer,''),
               '^https?://(www\.)?([^/]+).*','\2'),''), '(direct / unknown)') src, count(*) views,
               count(*) filter (where engaged) readers from h group by 1 order by 2 desc limit 15) x),
    'devices', (select json_agg(x) from (select coalesce(device,'?') device, count(*) n from h group by 1 order by 2 desc) x),
    'regions', (select json_agg(x) from (select coalesce(split_part(tz,'/',1)||'/'||split_part(tz,'/',2),'?') tz,
               count(*) n from h group by 1 order by 2 desc limit 15) x),
    'searches', (select json_agg(x) from (select label, count(*) n from e where kind='search' and label <> ''
               group by 1 order by 2 desc limit 25) x),
    'plays', (select json_agg(x) from (select kind, path, count(*) n from e where kind like 'play_%'
               group by 1,2 order by 3 desc limit 20) x)
  ) into r;
  return r;
end $$;

grant execute on function public.track_view3(text,text,text,text,text,text,text,text,boolean) to anon, authenticated;
grant execute on function public.track_time(bigint,text,int,boolean) to anon, authenticated;
grant execute on function public.track_event(text,text,text,text) to anon, authenticated;
grant execute on function public.studio_data(text,text,int) to anon, authenticated;
