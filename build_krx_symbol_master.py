#!/usr/bin/env python3
"""Build KRX (KOSPI/KOSDAQ) symbol master CSV for UI name mapping.

Usage:
  python build_krx_symbol_master.py
  python build_krx_symbol_master.py --out data/krx_symbol_master.csv
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd
from pykrx import stock as pykrx_stock


def collect_market_rows(market: str, suffix: str) -> list[dict[str, str]]:
    tickers = pykrx_stock.get_market_ticker_list(market=market)
    rows: list[dict[str, str]] = []

    for ticker in tickers:
        try:
            name = pykrx_stock.get_market_ticker_name(ticker)
        except Exception:
            name = ""

        rows.append(
            {
                "market": market,
                "ticker": ticker,
                "symbol": f"{ticker}{suffix}",
                "name_ko": name.strip(),
            }
        )

    return rows


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build KRX symbol master CSV")
    parser.add_argument("--out", default="data/krx_symbol_master.csv", help="Output csv path")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    rows = []
    rows.extend(collect_market_rows("KOSPI", ".KS"))
    rows.extend(collect_market_rows("KOSDAQ", ".KQ"))

    df = pd.DataFrame(rows)
    df = df.drop_duplicates(subset=["symbol"]).sort_values(["market", "ticker"]).reset_index(drop=True)
    df.to_csv(out_path, index=False, encoding="utf-8-sig")

    print(f"saved: {out_path} ({len(df)} rows)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
