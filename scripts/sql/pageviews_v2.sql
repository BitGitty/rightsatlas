-- PAGEVIEWS-V2 (2026-11-21). Owner: "can we implement something so we can understand 'most views have no source'?"
-- Adds, without breaking the old track_view: kind (human/bot/automation), utm (which of our posts sent them),
-- visit (random id for one browser tab, no cookie, no identity), engaged (stayed 15 s or scrolled = a real reader).
alter table pageviews add column if not exists kind text;
alter table pageviews add column if not exists utm text;
alter table pageviews add column if not exists visit text;
alter table pageviews add column if not exists engaged boolean not null default false;

create or replace function public.track_view2(p_site text, p_path text default null, p_ref text default null,
                                              p_kind text default null, p_utm text default null, p_visit text default null)
returns bigint language plpgsql security definer set search_path to 'public' as $$
declare v_id bigint;
begin
  insert into pageviews (site, path, referrer, kind, utm, visit)
  values (left(coalesce(p_site, '?'), 40), left(p_path, 300), left(nullif(p_ref, ''), 300),
          left(p_kind, 20), left(nullif(p_utm, ''), 60), left(p_visit, 40))
  returning id into v_id;
  return v_id;
end $$;

-- only the same browser tab (matching visit id) can mark its own view as engaged
create or replace function public.track_engaged(p_id bigint, p_visit text)
returns void language plpgsql security definer set search_path to 'public' as $$
begin
  update pageviews set engaged = true where id = p_id and visit = p_visit and visit is not null
    and ts > now() - interval '1 hour';
end $$;

grant execute on function public.track_view2(text, text, text, text, text, text) to anon, authenticated;
grant execute on function public.track_engaged(bigint, text) to anon, authenticated;
