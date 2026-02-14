#!/usr/bin/env python3
"""
Rebuild Korean stock library into one optimized Parquet dataset.

Requirements:
  pip install FinanceDataReader yfinance pandas pyarrow tqdm numpy
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Iterable, List

import numpy as np
import pandas as pd
import yfinance as yf
from tqdm import tqdm

import FinanceDataReader as fdr


def cleanup_csv_files(target_dir: Path) -> int:
    target_dir.mkdir(parents=True, exist_ok=True)
    deleted = 0
    for csv_path in target_dir.rglob("*.csv"):
        csv_path.unlink(missing_ok=True)
        deleted += 1
    return deleted


def _find_column(df: pd.DataFrame, candidates: List[str]) -> str:
    for name in candidates:
        if name in df.columns:
            return name
    raise KeyError(f"Missing expected columns. candidates={candidates}, available={list(df.columns)}")


def fetch_krx_tickers() -> pd.DataFrame:
    market_config = [
        ("KOSPI", ".KS"),
        ("KOSDAQ", ".KQ"),
    ]

    frames: List[pd.DataFrame] = []
    for market_name, suffix in market_config:
        listing = fdr.StockListing(market_name)

        symbol_col = _find_column(listing, ["Symbol", "Code", "symbol", "code"])
        name_col = _find_column(listing, ["Name", "name", "Company", "company"])

        symbols = (
            listing[symbol_col]
            .astype(str)
            .str.strip()
            .str.replace(r"\.0$", "", regex=True)
            .str.zfill(6)
        )
        names = listing[name_col].astype(str).str.strip()

        frame = pd.DataFrame(
            {
                "Market": market_name,
                "Symbol": symbols,
                "Name": names,
                "Ticker": symbols + suffix,
            }
        )
        frames.append(frame)

    all_tickers = pd.concat(frames, ignore_index=True).drop_duplicates(subset=["Ticker"])
    all_tickers = all_tickers[all_tickers["Ticker"].str.match(r"^\d{6}\.(KS|KQ)$")]
    all_tickers = all_tickers.reset_index(drop=True)
    return all_tickers


def chunked(items: List[str], size: int) -> Iterable[List[str]]:
    for i in range(0, len(items), size):
        yield items[i : i + size]


def normalize_download_output(raw: pd.DataFrame, tickers: List[str]) -> pd.DataFrame:
    if raw.empty:
        return pd.DataFrame(columns=["Date", "Ticker", "Open", "High", "Low", "Close", "Volume"])

    if isinstance(raw.columns, pd.MultiIndex):
        level0 = {str(v) for v in raw.columns.get_level_values(0)}
        # yfinance layout can vary between [Ticker, Field] and [Field, Ticker].
        if {"Open", "High", "Low", "Close", "Volume"}.issubset(level0):
            long_df = (
                raw.stack(level=1, future_stack=True)
                .rename_axis(index=["Date", "Ticker"])
                .reset_index()
            )
        else:
            long_df = (
                raw.stack(level=0, future_stack=True)
                .rename_axis(index=["Date", "Ticker"])
                .reset_index()
            )
    else:
        if len(tickers) != 1:
            return pd.DataFrame(columns=["Date", "Ticker", "Open", "High", "Low", "Close", "Volume"])
        long_df = raw.reset_index()
        long_df["Ticker"] = tickers[0]

    long_df.columns = [str(c) for c in long_df.columns]
    required = ["Date", "Ticker", "Open", "High", "Low", "Close", "Volume"]
    for col in required:
        if col not in long_df.columns:
            long_df[col] = np.nan

    long_df = long_df[required]
    long_df = long_df.dropna(subset=["Close"])
    return long_df


def download_10y_daily_data(
    tickers: List[str], chunk_size: int, start_date: str, end_date: str
) -> pd.DataFrame:
    batches = list(chunked(tickers, chunk_size))
    frames: List[pd.DataFrame] = []

    for batch in tqdm(batches, desc="Downloading (1d batches)", unit="batch"):
        try:
            raw = yf.download(
                tickers=batch,
                start=start_date,
                end=end_date,
                interval="1d",
                auto_adjust=True,
                group_by="ticker",
                progress=False,
                threads=True,
                actions=False,
            )
            normalized = normalize_download_output(raw, batch)
            if not normalized.empty:
                frames.append(normalized)
        except Exception as exc:
            print(f"[WARN] batch failed ({len(batch)} tickers): {exc}")

    if not frames:
        raise RuntimeError("No data downloaded. Check network/access/ticker list.")

    return pd.concat(frames, ignore_index=True)


def add_features(df: pd.DataFrame) -> pd.DataFrame:
    df = df.sort_values(["Ticker", "Date"]).reset_index(drop=True)
    g = df.groupby("Ticker", sort=False)

    df["TradingValue"] = df["Close"] * df["Volume"]
    df["Return1D"] = g["Close"].pct_change()

    for window in (5, 20, 60, 120):
        df[f"MA{window}"] = (
            g["Close"].rolling(window=window, min_periods=window).mean().reset_index(level=0, drop=True)
        )

    df["Volatility20"] = (
        g["Return1D"].rolling(window=20, min_periods=20).std().reset_index(level=0, drop=True)
    )

    float64_cols = df.select_dtypes(include=["float64"]).columns
    df[float64_cols] = df[float64_cols].astype(np.float32)
    return df


def build_pipeline(target_dir: Path, output_name: str, chunk_size: int, years: int) -> None:
    print(f"[1/5] Cleanup CSV files in: {target_dir}")
    deleted_files = cleanup_csv_files(target_dir)
    print(f"  Deleted CSV files: {deleted_files}")

    print("[2/5] Fetching KOSPI + KOSDAQ ticker universe...")
    ticker_meta = fetch_krx_tickers()
    tickers = ticker_meta["Ticker"].tolist()
    print(f"  Total tickers: {len(tickers):,}")

    end_ts = pd.Timestamp.today().normalize() + pd.Timedelta(days=1)
    start_ts = (pd.Timestamp.today().normalize() - pd.DateOffset(years=years)).date()

    print("[3/5] Downloading 10-year daily data in batches...")
    market_df = download_10y_daily_data(
        tickers=tickers,
        chunk_size=chunk_size,
        start_date=str(start_ts),
        end_date=str(end_ts.date()),
    )

    market_df["Date"] = pd.to_datetime(market_df["Date"]).dt.tz_localize(None)
    market_df = market_df.drop_duplicates(subset=["Date", "Ticker"], keep="last")

    market_df = market_df.merge(ticker_meta, on="Ticker", how="left")
    market_df["Market"] = market_df["Market"].astype("category")
    market_df["Symbol"] = market_df["Symbol"].astype("category")
    market_df["Name"] = market_df["Name"].astype("category")

    print("[4/5] Feature engineering (vectorized)...")
    market_df = add_features(market_df)

    output_path = target_dir / output_name
    print("[5/5] Saving Parquet (pyarrow + zstd)...")
    final_df = market_df.set_index(["Date", "Ticker"]).sort_index()
    final_df.to_parquet(output_path, engine="pyarrow", compression="zstd", index=True)

    size_mb = output_path.stat().st_size / (1024 * 1024)
    print("Done.")
    print(f"  Output file: {output_path}")
    print(f"  Rows: {len(final_df):,}")
    print(f"  File size: {size_mb:,.2f} MB")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Rebuild KOSPI/KOSDAQ 10-year daily dataset into single zstd Parquet."
    )
    parser.add_argument("--target-dir", type=Path, default=Path("./stock_data"))
    parser.add_argument("--output-name", type=str, default="korean_market_10y.parquet")
    parser.add_argument("--chunk-size", type=int, default=100)
    parser.add_argument("--years", type=int, default=10)
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    build_pipeline(
        target_dir=args.target_dir,
        output_name=args.output_name,
        chunk_size=args.chunk_size,
        years=args.years,
    )
