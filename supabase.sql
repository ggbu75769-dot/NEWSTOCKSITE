-- Visual Stock Supabase schema, policies, and RPCs
-- Safe to run multiple times.

create extension if not exists "pgcrypto";

-- Tables
create table if not exists public.stocks (
  ticker text primary key,
  name text not null,
  sector text,
  market text not null default 'US',
  currency text not null default 'USD',
  exchange text,
  created_at timestamptz not null default now()
);

alter table public.stocks add column if not exists market text not null default 'US';
alter table public.stocks add column if not exists currency text not null default 'USD';
alter table public.stocks add column if not exists exchange text;

create table if not exists public.historical_prices (
  ticker text not null references public.stocks(ticker) on delete cascade,
  trade_date date not null,
  open numeric,
  high numeric,
  low numeric,
  close numeric,
  volume bigint,
  rsi_14 numeric,
  created_at timestamptz not null default now(),
  primary key (ticker, trade_date)
);

create index if not exists historical_prices_trade_date_idx
  on public.historical_prices (trade_date);

create index if not exists historical_prices_ticker_date_idx
  on public.historical_prices (ticker, trade_date);

create or replace view public.latest_prices as
with ranked as (
  select
    hp.ticker,
    hp.trade_date,
    hp.open,
    hp.high,
    hp.low,
    hp.close,
    hp.volume,
    hp.rsi_14,
    s.market,
    s.name,
    s.currency,
    s.exchange,
    row_number() over (partition by hp.ticker order by hp.trade_date desc) as rn,
    lag(hp.close) over (partition by hp.ticker order by hp.trade_date desc) as prev_close
  from public.historical_prices hp
  join public.stocks s on s.ticker = hp.ticker
)
select
  ticker,
  trade_date,
  open,
  high,
  low,
  close,
  volume,
  rsi_14,
  market,
  name,
  currency,
  exchange,
  case
    when prev_close is null or prev_close = 0 then null
    else round(((close - prev_close) / prev_close) * 100, 2)
  end as change_pct
from ranked
where rn = 1;

create table if not exists public.daily_rankings (
  id uuid primary key default gen_random_uuid(),
  ranking_date date not null,
  rank integer not null check (rank between 1 and 3),
  ticker text not null references public.stocks(ticker) on delete restrict,
  win_rate numeric not null,
  avg_return numeric not null,
  confluence_score numeric not null,
  created_at timestamptz not null default now(),
  unique (ranking_date, rank)
);

create table if not exists public.profiles (
  id uuid primary key references auth.users(id) on delete cascade,
  email text,
  name text,
  full_name text,
  avatar_url text,
  last_sign_in_at timestamptz,
  created_at timestamptz not null default now()
);

alter table public.profiles add column if not exists email text;
alter table public.profiles add column if not exists name text;
alter table public.profiles add column if not exists last_sign_in_at timestamptz;

-- RLS
alter table public.stocks enable row level security;
alter table public.daily_rankings enable row level security;
alter table public.profiles enable row level security;
alter table public.historical_prices enable row level security;
alter view public.latest_prices set (security_barrier = true);

-- Policies: stocks
drop policy if exists "stocks_select_authenticated" on public.stocks;
create policy "stocks_select_authenticated"
  on public.stocks for select
  using (auth.role() = 'authenticated');

drop policy if exists "stocks_write_service_role" on public.stocks;
create policy "stocks_write_service_role"
  on public.stocks for insert
  with check (auth.role() = 'service_role');

drop policy if exists "stocks_update_service_role" on public.stocks;
create policy "stocks_update_service_role"
  on public.stocks for update
  using (auth.role() = 'service_role')
  with check (auth.role() = 'service_role');

-- Policies: historical_prices
drop policy if exists "historical_prices_select_authenticated" on public.historical_prices;
create policy "historical_prices_select_authenticated"
  on public.historical_prices for select
  using (auth.role() = 'authenticated');

drop policy if exists "historical_prices_write_service_role" on public.historical_prices;
create policy "historical_prices_write_service_role"
  on public.historical_prices for insert
  with check (auth.role() = 'service_role');

drop policy if exists "historical_prices_update_service_role" on public.historical_prices;
create policy "historical_prices_update_service_role"
  on public.historical_prices for update
  using (auth.role() = 'service_role')
  with check (auth.role() = 'service_role');

grant select on public.latest_prices to authenticated;

-- Policies: daily_rankings
drop policy if exists "daily_rankings_select_authenticated" on public.daily_rankings;
create policy "daily_rankings_select_authenticated"
  on public.daily_rankings for select
  using (auth.role() = 'authenticated');

drop policy if exists "daily_rankings_write_service_role" on public.daily_rankings;
create policy "daily_rankings_write_service_role"
  on public.daily_rankings for insert
  with check (auth.role() = 'service_role');

drop policy if exists "daily_rankings_update_service_role" on public.daily_rankings;
create policy "daily_rankings_update_service_role"
  on public.daily_rankings for update
  using (auth.role() = 'service_role')
  with check (auth.role() = 'service_role');

-- Policies: profiles
drop policy if exists "profiles_select_own" on public.profiles;
create policy "profiles_select_own"
  on public.profiles for select
  using (auth.uid() = id);

drop policy if exists "profiles_update_own" on public.profiles;
create policy "profiles_update_own"
  on public.profiles for update
  using (auth.uid() = id)
  with check (auth.uid() = id);

drop policy if exists "profiles_insert_own" on public.profiles;
create policy "profiles_insert_own"
  on public.profiles for insert
  with check (auth.uid() = id);

-- Profile bootstrap from auth.users (Google OAuth)
create or replace function public.handle_new_user()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
begin
  insert into public.profiles (id, email, name, full_name, avatar_url)
  values (
    new.id,
    new.email,
    new.raw_user_meta_data->>'name',
    new.raw_user_meta_data->>'full_name',
    new.raw_user_meta_data->>'avatar_url'
  )
  on conflict (id) do update set
    email = excluded.email,
    name = excluded.name,
    full_name = excluded.full_name,
    avatar_url = excluded.avatar_url,
    last_sign_in_at = now();
  return new;
end;
$$;

drop trigger if exists on_auth_user_created on auth.users;
create trigger on_auth_user_created
after insert on auth.users
for each row execute procedure public.handle_new_user();

-- Public masked view for daily rankings
create or replace function public.get_daily_rankings_public(p_date date default null)
returns table (
  ranking_date date,
  rank integer,
  win_rate numeric,
  avg_return numeric,
  confluence_score numeric,
  ticker text,
  name text
)
language sql
security definer
set search_path = public
as $$
  select
    dr.ranking_date,
    dr.rank,
    dr.win_rate,
    dr.avg_return,
    dr.confluence_score,
    case when auth.role() = 'authenticated' then s.ticker else 'MYST' end as ticker,
    case when auth.role() = 'authenticated' then s.name else 'This Mystery Stock' end as name
  from public.daily_rankings dr
  join public.stocks s on s.ticker = dr.ticker
  where p_date is null or dr.ranking_date = p_date
$$;

grant execute on function public.get_daily_rankings_public(date) to anon, authenticated;

create or replace view public.daily_rankings_public as
select * from public.get_daily_rankings_public(null);

grant select on public.daily_rankings_public to anon, authenticated;

-- Search RPC for interactive search
create or replace function public.search_stock_public(p_symbol text)
returns table (
  ticker text,
  name text,
  sector text,
  ranking_date date,
  rank integer,
  win_rate numeric,
  avg_return numeric,
  confluence_score numeric
)
language sql
security definer
set search_path = public
as $$
  with latest_rank as (
    select
      dr.ticker,
      dr.ranking_date,
      dr.rank,
      dr.win_rate,
      dr.avg_return,
      dr.confluence_score
    from public.daily_rankings dr
    where dr.ranking_date = (select max(ranking_date) from public.daily_rankings)
  )
  select
    case when auth.role() = 'authenticated' then s.ticker else 'MYST' end as ticker,
    case when auth.role() = 'authenticated' then s.name else 'This Mystery Stock' end as name,
    s.sector,
    lr.ranking_date,
    lr.rank,
    lr.win_rate,
    lr.avg_return,
    lr.confluence_score
  from public.stocks s
  left join latest_rank lr on lr.ticker = s.ticker
  where upper(s.ticker) = upper(p_symbol)
  limit 1
$$;

grant execute on function public.search_stock_public(text) to anon, authenticated;
