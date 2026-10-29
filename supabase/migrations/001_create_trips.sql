create table if not exists public.trips (
  id uuid primary key default gen_random_uuid(),
  owner_id uuid not null references auth.users(id) on delete cascade,
  destination text not null,
  start_date date not null,
  end_date date not null,
  travelers integer not null default 1 check (travelers > 0),
  budget numeric(12,2) not null check (budget > 0),
  interests jsonb not null default '[]'::jsonb,
  itinerary jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  check (end_date >= start_date)
);
alter table public.trips enable row level security;
create policy "owners can select trips" on public.trips for select using (auth.uid() = owner_id);
create policy "owners can insert trips" on public.trips for insert with check (auth.uid() = owner_id);
create policy "owners can update trips" on public.trips for update using (auth.uid() = owner_id) with check (auth.uid() = owner_id);
create policy "owners can delete trips" on public.trips for delete using (auth.uid() = owner_id);
