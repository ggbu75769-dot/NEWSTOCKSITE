"""
KOSPI tomorrow-up probability ranking using R2 parquet data.

Output columns:
- ticker, last_date, close
- ret_1d, ret_5d, ret_20d
- volume_ratio_20d
- breakout_ratio_20d
- score, probability_next_up
- reason

Usage:
  python kospi_tomorrow_signal.py --top-n 20
  python kospi_tomorrow_signal.py --as-of 2026-02-12 --top-n 30 --save-csv logs/kospi_top30.csv
"""

from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv

from duckdb_r2_analytics import StockDataAnalytic


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="KOSPI tomorrow-up probability ranking")
    parser.add_argument("--top-n", type=int, default=20, help="number of rows to print")
    parser.add_argument(
        "--lookback-days",
        type=int,
        default=300,
        help="days of history to load for feature generation",
    )
    parser.add_argument(
        "--as-of",
        type=str,
        default="",
        help="as-of date in YYYY-MM-DD. default: latest available date",
    )
    parser.add_argument("--save-csv", type=str, default="", help="optional output csv path")
    return parser.parse_args()


def _as_of_filter(as_of: str) -> str:
    if not as_of:
        return ""
    try:
        datetime.strptime(as_of, "%Y-%m-%d")
    except ValueError as exc:
        raise ValueError("--as-of must be YYYY-MM-DD") from exc
    return f"AND date <= DATE '{as_of}'"


def load_feature_frame(engine: StockDataAnalytic, lookback_days: int, as_of: str) -> pd.DataFrame:
    as_of_clause = _as_of_filter(as_of)

    query = f"""
    WITH raw AS (
      SELECT
        ticker,
        CAST(date AS DATE) AS trade_date,
        close,
        high,
        volume,
        LAG(close, 1) OVER (PARTITION BY ticker ORDER BY date) AS prev_close_1,
        LAG(close, 5) OVER (PARTITION BY ticker ORDER BY date) AS prev_close_5,
        LAG(close, 20) OVER (PARTITION BY ticker ORDER BY date) AS prev_close_20,
        AVG(close) OVER (PARTITION BY ticker ORDER BY date ROWS BETWEEN 19 PRECEDING AND CURRENT ROW) AS sma20,
        AVG(close) OVER (PARTITION BY ticker ORDER BY date ROWS BETWEEN 59 PRECEDING AND CURRENT ROW) AS sma60,
        AVG(close) OVER (PARTITION BY ticker ORDER BY date ROWS BETWEEN 119 PRECEDING AND CURRENT ROW) AS sma120,
        AVG(volume) OVER (PARTITION BY ticker ORDER BY date ROWS BETWEEN 19 PRECEDING AND CURRENT ROW) AS vol_avg20,
        MAX(high) OVER (PARTITION BY ticker ORDER BY date ROWS BETWEEN 19 PRECEDING AND CURRENT ROW) AS high_20,
        ROW_NUMBER() OVER (PARTITION BY ticker ORDER BY date DESC) AS rn
      FROM read_parquet('{engine.data_glob}', hive_partitioning=1)
      WHERE regexp_matches(ticker, '^[0-9]{{6}}$')
        AND date >= current_date - INTERVAL {lookback_days} DAY
        {as_of_clause}
    )
    SELECT
      ticker,
      trade_date,
      close,
      CASE WHEN prev_close_1 IS NULL OR prev_close_1 = 0 THEN NULL ELSE (close / prev_close_1 - 1) * 100 END AS ret_1d,
      CASE WHEN prev_close_5 IS NULL OR prev_close_5 = 0 THEN NULL ELSE (close / prev_close_5 - 1) * 100 END AS ret_5d,
      CASE WHEN prev_close_20 IS NULL OR prev_close_20 = 0 THEN NULL ELSE (close / prev_close_20 - 1) * 100 END AS ret_20d,
      sma20,
      sma60,
      sma120,
      CASE WHEN vol_avg20 IS NULL OR vol_avg20 = 0 THEN NULL ELSE volume / vol_avg20 END AS volume_ratio_20d,
      CASE WHEN high_20 IS NULL OR high_20 = 0 THEN NULL ELSE close / high_20 END AS breakout_ratio_20d
    FROM raw
    WHERE rn = 1
    """

    frame = engine.to_pandas(query)
    if frame.empty:
        return frame

    frame = frame.dropna(subset=["ret_1d", "ret_5d", "ret_20d", "sma20", "sma60", "sma120"]).copy()
    return frame


def score_row(row: pd.Series) -> tuple[float, float, str]:
    score = 0.0
    reasons: list[str] = []

    close = float(row["close"])
    sma20 = float(row["sma20"])
    sma60 = float(row["sma60"])
    sma120 = float(row["sma120"])
    ret_1d = float(row["ret_1d"])
    ret_5d = float(row["ret_5d"])
    ret_20d = float(row["ret_20d"])
    volume_ratio = float(row["volume_ratio_20d"]) if pd.notna(row["volume_ratio_20d"]) else 0.0
    breakout_ratio = float(row["breakout_ratio_20d"]) if pd.notna(row["breakout_ratio_20d"]) else 0.0

    if close > sma20:
        score += 15
        reasons.append("close>sma20")
    if close > sma60:
        score += 12
        reasons.append("close>sma60")
    if sma20 > sma60:
        score += 10
        reasons.append("sma20>sma60")
    if sma60 > sma120:
        score += 8
        reasons.append("sma60>sma120")

    if ret_20d > 0:
        score += min(15, ret_20d * 0.8)
        reasons.append("20d_momentum")
    if ret_5d > 0:
        score += min(10, ret_5d * 1.2)
        reasons.append("5d_momentum")

    if 1.2 <= volume_ratio <= 3.5:
        score += 10
        reasons.append("volume_spike")
    elif volume_ratio > 3.5:
        score += 5
        reasons.append("high_volume")

    if breakout_ratio >= 0.995:
        score += 10
        reasons.append("near_20d_high")

    # Penalize excessive single-day surge (mean reversion risk).
    if ret_1d >= 8:
        score -= 8
        reasons.append("overheated_1d")

    # Convert score to pseudo-probability range.
    probability = max(5.0, min(95.0, 28.0 + score * 0.72))

    return round(score, 2), round(probability, 2), ",".join(reasons)


def build_ranking(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return frame

    scored = frame.copy()
    out = scored.apply(score_row, axis=1, result_type="expand")
    out.columns = ["score", "probability_next_up", "reason"]
    scored = pd.concat([scored, out], axis=1)

    scored = scored.sort_values(["probability_next_up", "score", "ret_20d"], ascending=False)
    scored.insert(0, "rank", range(1, len(scored) + 1))
    return scored


def main() -> None:
    load_dotenv(Path(__file__).resolve().parent / ".env.r2.local", override=False)
    load_dotenv(Path(__file__).resolve().parent / ".env.local", override=False)
    load_dotenv(Path(__file__).resolve().parent / ".env", override=False)

    args = parse_args()

    engine = StockDataAnalytic()
    try:
        frame = load_feature_frame(engine, lookback_days=args.lookback_days, as_of=args.as_of)
        ranking = build_ranking(frame)
    finally:
        engine.close()

    if ranking.empty:
        print("No KOSPI rows found in dataset for the requested range.")
        return

    top = ranking.head(args.top_n).copy()

    # Pretty print selected columns.
    cols = [
        "rank",
        "ticker",
        "trade_date",
        "close",
        "ret_1d",
        "ret_5d",
        "ret_20d",
        "volume_ratio_20d",
        "breakout_ratio_20d",
        "score",
        "probability_next_up",
        "reason",
    ]
    print(top[cols].to_string(index=False))

    if args.save_csv:
        out_path = Path(args.save_csv)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        top.to_csv(out_path, index=False, encoding="utf-8-sig")
        print(f"\nSaved: {out_path}")


if __name__ == "__main__":
    main()
