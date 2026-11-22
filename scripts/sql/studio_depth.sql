-- STUDIO-DEPTH (2026-11-22). Owner: "can we analyse how people react / read our blog posts?" -> how far down they read.
alter table pageviews add column if not exists depth int;   -- max % of the page scrolled (0-100)

drop function if exists public.track_time(bigint, text, int, boolean);
create or replace function public.track_time(p_id bigint, p_visit text, p_secs int, p_engaged boolean default false,
                                             p_depth int default null)
returns void language plpgsql security definer set search_path to 'public' as $$
begin
  update pageviews set secs = greatest(coalesce(secs,0), least(p_secs, 3600)),
                       engaged = engaged or p_engaged or p_secs >= 15,
                       depth = greatest(coalesce(depth,0), least(coalesce(p_depth,0),100))
  where id = p_id and visit = p_visit and visit is not null and ts > now() - interval '2 hours';
end $$;
grant execute on function public.track_time(bigint,text,int,boolean,int) to anon, authenticated;

-- blog posts: views, readers, time, how far down, % who reached the end (75%+)
create or replace function public.studio_posts(p_site text, p_key text, p_days int default 28)
returns json language plpgsql security definer set search_path to 'public' as $$
declare ok boolean; d int := least(greatest(coalesce(p_days,28),1),365); r json;
begin
  select exists(select 1 from studio_keys where site = p_site
                and key_hash = encode(sha256(convert_to(p_key,'UTF8')),'hex')) into ok;
  if not ok then perform pg_sleep(1); return null; end if;
  select json_agg(x) into r from (
    select path, count(*) views, count(*) filter (where engaged) readers, round(avg(secs)) avg_secs,
           round(avg(depth)) avg_depth, round(100.0 * count(*) filter (where depth >= 75) / nullif(count(*),0)) pct_end
    from pageviews where site = p_site and kind = 'human' and path like '/blog/%' and path <> '/blog/'
      and ts > now() - make_interval(days => d)
    group by path order by count(*) desc limit 40) x;
  return coalesce(r, '[]'::json);
end $$;
grant execute on function public.studio_posts(text,text,int) to anon, authenticated;
