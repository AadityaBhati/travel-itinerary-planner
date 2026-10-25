alter table public.trips
  add column if not exists title text,
  add column if not exists currency text not null default 'USD',
  add column if not exists preferences jsonb not null default '{"interests":[],"pace":"balanced"}'::jsonb;

update public.trips
set title = coalesce(title, destination || ' getaway')
where title is null;

alter table public.trips
  alter column title set not null,
  alter column owner_id set default auth.uid(),
  alter column itinerary set default '{}'::jsonb;

update public.trips
set itinerary = '{}'::jsonb
where itinerary is null;

alter table public.trips
  alter column itinerary set not null;

create index if not exists trips_owner_updated_idx on public.trips (owner_id, updated_at desc);

create or replace function public.set_trips_updated_at()
returns trigger
language plpgsql
security invoker
set search_path = public
as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

drop trigger if exists trips_set_updated_at on public.trips;
create trigger trips_set_updated_at
before update on public.trips
for each row execute function public.set_trips_updated_at();

drop policy if exists "owners can select trips" on public.trips;
drop policy if exists "owners can insert trips" on public.trips;
drop policy if exists "owners can update trips" on public.trips;
drop policy if exists "owners can delete trips" on public.trips;

create policy "authenticated owners can select trips"
  on public.trips for select to authenticated
  using (auth.uid() = owner_id);

create policy "authenticated owners can insert trips"
  on public.trips for insert to authenticated
  with check (auth.uid() = owner_id);

create policy "authenticated owners can update trips"
  on public.trips for update to authenticated
  using (auth.uid() = owner_id)
  with check (auth.uid() = owner_id);

create policy "authenticated owners can delete trips"
  on public.trips for delete to authenticated
  using (auth.uid() = owner_id);

revoke all on public.trips from anon;
grant select, insert, update, delete on public.trips to authenticated;
