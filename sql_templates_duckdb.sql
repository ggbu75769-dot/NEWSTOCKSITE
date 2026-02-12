-- Base external table macro for convenience.
-- Replace bucket/prefix once and reuse all templates.
CREATE OR REPLACE MACRO market_data() AS TABLE
SELECT *
FROM read_parquet(
  's3://YOUR_BUCKET/market_data/year=*/ticker=*/part-*.parquet',
  hive_partitioning = 1
);

-- 1) 52-week high/low across all tickers.
WITH y AS (
  SELECT ticker, date, high, low
  FROM market_data()
  WHERE date >= current_date - INTERVAL 365 DAY
)
SELECT
  ticker,
  max(high) AS high_52w,
  min(low) AS low_52w
FROM y
GROUP BY ticker
ORDER BY ticker;

-- 2) Latest close vs. 52-week range.
WITH y AS (
  SELECT ticker, date, high, low, close
  FROM market_data()
  WHERE date >= current_date - INTERVAL 365 DAY
),
ranges AS (
  SELECT ticker, max(high) AS high_52w, min(low) AS low_52w
  FROM y
  GROUP BY ticker
),
latest AS (
  SELECT ticker, close
  FROM y
  QUALIFY row_number() OVER (PARTITION BY ticker ORDER BY date DESC) = 1
)
SELECT
  l.ticker,
  l.close AS last_close,
  r.high_52w,
  r.low_52w,
  (l.close - r.low_52w) / NULLIF(r.high_52w - r.low_52w, 0) AS pct_in_range
FROM latest l
JOIN ranges r USING (ticker)
ORDER BY pct_in_range DESC;

-- 3) Cross-sectional 20-day momentum.
WITH p AS (
  SELECT
    ticker,
    date,
    close,
    close / lag(close, 20) OVER (PARTITION BY ticker ORDER BY date) - 1 AS ret_20d
  FROM market_data()
),
latest AS (
  SELECT ticker, date, ret_20d
  FROM p
  WHERE ret_20d IS NOT NULL
  QUALIFY row_number() OVER (PARTITION BY ticker ORDER BY date DESC) = 1
)
SELECT *
FROM latest
ORDER BY ret_20d DESC;

-- 4) Example single-ticker history slice.
SELECT ticker, date, open, high, low, close, volume, adj_close
FROM market_data()
WHERE ticker = 'AAPL'
  AND date BETWEEN '2024-01-01' AND '2025-12-31'
ORDER BY date;
