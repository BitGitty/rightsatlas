-- STUDIO-GSC (2026-11-21). Owner: "add Google Search Console data". Daily rows pulled by scripts/gsc_pull.py.
create table if not exists gsc_rows (
  day date not null, query text not null, page text not null,
  clicks int not null default 0, impressions int not null default 0, position real,
  primary key (day, query, page));
alter table gsc_rows enable row level security;   -- read only through studio_data()

create or replace function public.studio_gsc(p_site text, p_key text, p_days int default 28)
returns json language plpgsql security definer set search_path to 'public' as $$
declare ok boolean; d int := least(greatest(coalesce(p_days,28),1),480); r json;
begin
  select exists(select 1 from studio_keys where site = p_site
                and key_hash = encode(sha256(convert_to(p_key,'UTF8')),'hex')) into ok;
  if not ok then perform pg_sleep(1); return null; end if;
  with g as (select * from gsc_rows where day > current_date - d)
  select json_build_object(
    'last_day', (select max(day) from gsc_rows),
    'totals', (select json_build_object('clicks', coalesce(sum(clicks),0), 'impressions', coalesce(sum(impressions),0),
               'queries', count(distinct query), 'avg_position', round((sum(position*impressions)/nullif(sum(impressions),0))::numeric,1)) from g),
    'queries', (select json_agg(x) from (select query, sum(clicks) clicks, sum(impressions) impressions,
               round((sum(position*impressions)/nullif(sum(impressions),0))::numeric,1) position
               from g group by query order by sum(impressions) desc limit 40) x),
    'pages', (select json_agg(x) from (select regexp_replace(page,'^https?://[^/]+','') page, sum(clicks) clicks,
               sum(impressions) impressions, round((sum(position*impressions)/nullif(sum(impressions),0))::numeric,1) position
               from g group by 1 order by sum(impressions) desc limit 25) x),
    'by_day', (select json_agg(x order by x.day) from (select day, sum(clicks) clicks, sum(impressions) impressions
               from g group by day) x)
  ) into r;
  return r;
end $$;
grant execute on function public.studio_gsc(text,text,int) to anon, authenticated;
