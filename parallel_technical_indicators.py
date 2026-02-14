#!/usr/bin/env python3
"""
High-performance technical indicator pipeline for large Korean daily OHLCV datasets.

Key features:
- ProcessPoolExecutor parallelism across tickers
- pandas_ta custom strategy ("BigDataStrategy")
- Batch submission to avoid OOM
- Float downcast (float64 -> float32)
- Single Parquet output with zstd compression

Install:
  pip install pandas numpy pyarrow tqdm pandas_ta yfinance finance-datareader
"""

from __future__ import annotations

import argparse
import gc
import math
import os
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from typing import Iterable, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import pandas_ta as ta
from pandas.api.types import is_float_dtype
from tqdm import tqdm


BASE_COLS = ["Date", "Ticker", "Open", "High", "Low", "Close", "Volume"]

# Keep only main indicator outputs (plus base OHLCV/Ticker).
KEEP_PREFIXES = (
    "SMA_",
    "EMA_",
    "MACD_",
    "MACDh_",
    "MACDs_",
    "ADX_",
    "DMP_",
    "DMN_",
    "PSAR",
    "ITS_",   # Ichimoku conversion line (Tenkan)
    "IKS_",   # Ichimoku base line (Kijun)
    "RSI_",
    "STOCHk_",
    "STOCHd_",
    "CCI_",
    "ROC_",
    "WILLR_",
    "MOM_",
    "BBL_",
    "BBM_",
    "BBU_",
    "BBB_",
    "BBP_",
    "ATR_",
    "KCL_",
    "KCB_",
    "KCU_",
    "KCLe_",
    "KCBe_",
    "KCUe_",
    "STDEV_",
    "OBV",
    "MFI_",
    "CMF_",
    "VWMA_",
)

# Explicitly remove non-requested Ichimoku outputs.
DROP_PREFIXES = ("ISA_", "ISB_", "ICS_")


def build_bigdata_strategy() -> ta.Study:
    # 20 indicator TYPES with requested parameters (VWAP replaced by VWMA for daily bars).
    return ta.Study(
        name="BigDataStrategy",
        description="20-type technical indicator set for big daily equity data",
        ta=[
            # Trend
            {"kind": "sma", "length": 5},
            {"kind": "sma", "length": 20},
            {"kind": "sma", "length": 60},
            {"kind": "sma", "length": 120},
            {"kind": "ema", "length": 12},
            {"kind": "ema", "length": 26},
            {"kind": "macd", "fast": 12, "slow": 26, "signal": 9},
            {"kind": "adx", "length": 14},
            {"kind": "psar"},  # default acceleration params
            {"kind": "ichimoku", "tenkan": 9, "kijun": 26, "senkou": 52},
            # Momentum
            {"kind": "rsi", "length": 14},
            {"kind": "stoch", "k": 14, "d": 3, "smooth_k": 3},
            {"kind": "cci", "length": 14},
            {"kind": "roc", "length": 10},
            {"kind": "willr", "length": 14},
            {"kind": "mom", "length": 10},
            # Volatility
            {"kind": "bbands", "length": 20, "std": 2.0},
            {"kind": "atr", "length": 14},
            {"kind": "kc", "length": 20},
            {"kind": "stdev", "length": 20},
            # Volume
            {"kind": "obv"},
            {"kind": "mfi", "length": 14},
            {"kind": "cmf", "length": 20},
            {"kind": "vwma", "length": 20},
        ],
    )


def chunked(seq: Sequence[str], size: int) -> Iterable[Sequence[str]]:
    for i in range(0, len(seq), size):
        yield seq[i : i + size]


def downcast_float64_to_float32(df: pd.DataFrame) -> pd.DataFrame:
    float_cols = [c for c in df.columns if is_float_dtype(df[c])]
    for col in float_cols:
        df[col] = df[col].astype(np.float32, copy=False)
    return df


def prune_columns(df: pd.DataFrame) -> pd.DataFrame:
    keep = []
    for col in df.columns:
        if col in BASE_COLS[1:]:  # all except Date (Date can be index inside worker)
            keep.append(col)
            continue
        if col.startswith(DROP_PREFIXES):
            continue
        if col.startswith(KEEP_PREFIXES):
            keep.append(col)
    # Ensure unique order
    keep = list(dict.fromkeys(keep))
    return df[keep]


def _normalize_single_ticker_df(df_chunk: pd.DataFrame) -> pd.DataFrame:
    df = df_chunk.copy()
    df.columns = [str(c) for c in df.columns]

    required = {"Date", "Ticker", "Open", "High", "Low", "Close", "Volume"}
    missing = required.difference(df.columns)
    if missing:
        raise ValueError(f"Missing required columns: {sorted(missing)}")

    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
    df = df.dropna(subset=["Date"])
    df = df.sort_values("Date").drop_duplicates(subset=["Date"], keep="last")
    df = df.set_index("Date")

    for col in ("Open", "High", "Low", "Close", "Volume"):
        df[col] = pd.to_numeric(df[col], errors="coerce")

    return df


def calculate_indicators(df_chunk: pd.DataFrame) -> Tuple[str, pd.DataFrame, Optional[str]]:
    """
    Worker-safe function for one ticker chunk.
    Returns: (ticker, processed_df, error_message)
    """
    ticker = "UNKNOWN"
    try:
        if df_chunk.empty:
            return ticker, pd.DataFrame(), "empty chunk"

        ticker = str(df_chunk["Ticker"].iloc[0])
        df = _normalize_single_ticker_df(df_chunk)
        if len(df) == 0:
            return ticker, pd.DataFrame(), "no valid rows after normalization"

        # Disable pandas_ta internal multiprocessing to avoid nested parallelism.
        df.ta.cores = 0
        df.ta.study(build_bigdata_strategy(), timed=False, verbose=False, cores=0)

        # Keep only base + main outputs.
        df = prune_columns(df)
        df["Ticker"] = ticker

        # Move Date back to column for stable schema handling in parent.
        df = df.reset_index()
        df = downcast_float64_to_float32(df)
        return ticker, df, None
    except Exception as exc:
        return ticker, pd.DataFrame(), f"{type(exc).__name__}: {exc}"


def load_input_dataframe(input_path: Path) -> pd.DataFrame:
    if not input_path.exists():
        raise FileNotFoundError(f"Input file not found: {input_path}")

    suffix = input_path.suffix.lower()
    if suffix in (".parquet", ".pq"):
        df = pd.read_parquet(input_path)
    elif suffix == ".csv":
        df = pd.read_csv(input_path)
    else:
        raise ValueError(f"Unsupported input extension: {suffix}")

    # Support MultiIndex parquet where Date/Ticker are index levels.
    if isinstance(df.index, pd.MultiIndex):
        level_names = [str(name) if name is not None else "" for name in df.index.names]
        if "Date" in level_names and "Ticker" in level_names:
            df = df.reset_index()
    else:
        index_name = str(df.index.name) if df.index.name is not None else ""
        if index_name == "Date" and "Ticker" in df.columns:
            df = df.reset_index()

    missing = set(BASE_COLS).difference(df.columns)
    if missing:
        raise ValueError(f"Input missing required columns: {sorted(missing)}")
    return df[BASE_COLS].copy()


def align_to_master_columns(df: pd.DataFrame, master_cols: Sequence[str]) -> pd.DataFrame:
    out = df.copy()
    for col in master_cols:
        if col not in out.columns:
            out[col] = np.nan
    # Drop unexpected columns from later workers.
    out = out[list(master_cols)]
    return out


def run_parallel_pipeline(
    raw_df: pd.DataFrame,
    output_path: Path,
    batch_tickers: int = 120,
    max_workers: Optional[int] = None,
) -> None:
    df = raw_df[BASE_COLS].copy()
    df["Ticker"] = df["Ticker"].astype(str)
    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
    df = df.dropna(subset=["Date"]).sort_values(["Ticker", "Date"]).reset_index(drop=True)

    ticker_to_index = df.groupby("Ticker", sort=False).indices
    tickers = list(ticker_to_index.keys())
    if not tickers:
        raise RuntimeError("No tickers found in input dataframe.")

    if max_workers is None:
        max_workers = max(1, (os.cpu_count() or 2) - 1)

    print(f"Input rows: {len(df):,}, tickers: {len(tickers):,}")
    print(f"Using workers: {max_workers}, ticker batch size: {batch_tickers}")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    writer: Optional[pq.ParquetWriter] = None
    master_cols: Optional[List[str]] = None
    master_dtypes: Optional[dict] = None

    errors: List[Tuple[str, str]] = []
    total_ok = 0

    with ProcessPoolExecutor(max_workers=max_workers) as executor:
        pbar = tqdm(total=len(tickers), desc="Tickers processed", unit="ticker")

        for batch in chunked(tickers, batch_tickers):
            futures = []
            for tk in batch:
                idx = ticker_to_index[tk]
                # Send only one ticker slice to worker to preserve time-series integrity.
                ticker_df = df.iloc[idx][BASE_COLS].copy()
                futures.append(executor.submit(calculate_indicators, ticker_df))

            for fut in as_completed(futures):
                ticker, result_df, err = fut.result()
                pbar.update(1)

                if err is not None:
                    errors.append((ticker, err))
                    continue
                if result_df.empty:
                    errors.append((ticker, "empty output"))
                    continue

                result_df = result_df.sort_values(["Date", "Ticker"]).reset_index(drop=True)
                result_df = downcast_float64_to_float32(result_df)

                if master_cols is None:
                    master_cols = list(result_df.columns)
                    master_dtypes = {c: result_df[c].dtype for c in master_cols}
                result_df = align_to_master_columns(result_df, master_cols)
                for c, dt in (master_dtypes or {}).items():
                    try:
                        result_df[c] = result_df[c].astype(dt, copy=False)
                    except Exception:
                        # Fallback to float32 for float-like columns when exact cast fails.
                        if is_float_dtype(result_df[c]):
                            result_df[c] = result_df[c].astype(np.float32, copy=False)

                table = pa.Table.from_pandas(result_df, preserve_index=False)
                if writer is None:
                    writer = pq.ParquetWriter(
                        output_path.as_posix(),
                        table.schema,
                        compression="zstd",
                    )
                writer.write_table(table)
                total_ok += 1

                del result_df, table

            gc.collect()

        pbar.close()

    if writer is not None:
        writer.close()
    else:
        raise RuntimeError("No successful ticker output. Nothing written.")

    size_mb = output_path.stat().st_size / (1024 * 1024)
    print("\nPipeline complete.")
    print(f"Successful tickers: {total_ok:,}/{len(tickers):,}")
    print(f"Failed tickers: {len(errors):,}")
    print(f"Output: {output_path}")
    print(f"Output size: {size_mb:,.2f} MB")

    if errors:
        err_preview = "\n".join([f"  - {tk}: {msg}" for tk, msg in errors[:20]])
        print("Error preview (first 20):")
        print(err_preview)


def download_sample_data_for_testing(
    tickers: Sequence[str],
    years: int = 10,
) -> pd.DataFrame:
    import yfinance as yf

    end = pd.Timestamp.today().normalize() + pd.Timedelta(days=1)
    start = (pd.Timestamp.today().normalize() - pd.DateOffset(years=years)).date()

    raw = yf.download(
        tickers=list(tickers),
        start=str(start),
        end=str(end.date()),
        interval="1d",
        auto_adjust=True,
        group_by="ticker",
        progress=False,
        threads=True,
        actions=False,
    )
    if raw.empty:
        raise RuntimeError("Sample download returned empty data.")

    if isinstance(raw.columns, pd.MultiIndex):
        level0 = {str(v) for v in raw.columns.get_level_values(0)}
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
            raise RuntimeError("Unexpected yfinance shape for multi-ticker sample download.")
        long_df = raw.reset_index()
        long_df["Ticker"] = tickers[0]

    for col in ("Open", "High", "Low", "Close", "Volume"):
        if col not in long_df.columns:
            long_df[col] = np.nan

    long_df = long_df[BASE_COLS].dropna(subset=["Close"]).reset_index(drop=True)
    return long_df


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Parallel technical indicator calculation using pandas_ta + ProcessPoolExecutor."
    )
    parser.add_argument(
        "--input",
        type=str,
        default="",
        help="Input data path (.parquet or .csv). Must contain Date,Ticker,Open,High,Low,Close,Volume.",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="stock_data/korean_market_10y_with_indicators.parquet",
        help="Output parquet path.",
    )
    parser.add_argument("--batch-tickers", type=int, default=120, help="Tickers submitted per batch.")
    parser.add_argument("--max-workers", type=int, default=0, help="0 means auto (cpu_count-1).")
    parser.add_argument(
        "--sample-tickers",
        type=str,
        default="005930.KS,000660.KS,035420.KS,051910.KS",
        help="Used only when --input is omitted. Comma-separated yfinance tickers.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    output_path = Path(args.output)

    if args.input:
        raw_df = load_input_dataframe(Path(args.input))
    else:
        sample_tickers = [t.strip() for t in args.sample_tickers.split(",") if t.strip()]
        print("No --input provided. Downloading sample data via yfinance...")
        raw_df = download_sample_data_for_testing(sample_tickers, years=10)

    max_workers = None if args.max_workers <= 0 else args.max_workers
    run_parallel_pipeline(
        raw_df=raw_df,
        output_path=output_path,
        batch_tickers=args.batch_tickers,
        max_workers=max_workers,
    )


if __name__ == "__main__":
    main()
