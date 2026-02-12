-- PostgreSQL schema for historical stock data pipeline
-- Requirements:
-- 1) Primary Key: (symbol, trade_date)
-- 2) Index on trade_date
-- 3) DECIMAL(18,4) for price-related fields

create table if not exists public.stock_daily_prices (
  symbol varchar(16) not null,
  trade_date date not null,
  open decimal(18,4) not null,
  high decimal(18,4) not null,
  low decimal(18,4) not null,
  close decimal(18,4) not null,
  adj_close decimal(18,4) not null,
  volume bigint not null,
  daily_return decimal(18,4),
  rsi_14 decimal(18,4),
  sma_20 decimal(18,4),
  sma_60 decimal(18,4),
  sma_120 decimal(18,4),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint stock_daily_prices_pkey primary key (symbol, trade_date)
);

create index if not exists stock_daily_prices_trade_date_idx
  on public.stock_daily_prices (trade_date);

