#!/usr/bin/env python3
"""Fetch historical stock data and back it up to GitHub with Git LFS.

Examples:
  python stock_data_lfs_backup.py --symbols AAPL TSLA 005930.KS --push
  python stock_data_lfs_backup.py --krx-markets KOSPI KOSDAQ --start-date 2026-01-01 --push \
    --commit-message "Backup 2026 KOSPI/KOSDAQ data"
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import time
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Iterable

try:
    import yfinance as yf
except Exception:  # pragma: no cover - optional dependency at runtime
    yf = None

try:
    from pykrx import stock as pykrx_stock
except Exception:  # pragma: no cover - optional dependency at runtime
    pykrx_stock = None


def run_command(command: list[str], check: bool = True) -> subprocess.CompletedProcess:
    """Run a shell command and surface failures with stderr."""
    print("$", " ".join(command))
    result = subprocess.run(command, text=True, capture_output=True, check=False)
    if check and result.returncode != 0:
        raise RuntimeError(
            f"Command failed ({result.returncode}): {' '.join(command)}\n"
            f"stdout:\n{result.stdout}\n"
            f"stderr:\n{result.stderr}"
        )
    return result


def krx_symbols(markets: Iterable[str]) -> list[str]:
    """Return yfinance-compatible KRX symbols from pykrx market lists."""
    if pykrx_stock is None:
        raise RuntimeError("pykrx is required for --krx-markets. Install with: pip install pykrx")

    market_to_suffix = {"KOSPI": ".KS", "KOSDAQ": ".KQ"}
    symbols: list[str] = []
    seen: set[str] = set()

    for market in markets:
        normalized = market.strip().upper()
        if normalized not in market_to_suffix:
            raise ValueError(f"Unsupported KRX market: {market}. Use KOSPI and/or KOSDAQ")

        ticker_list = pykrx_stock.get_market_ticker_list(market=normalized)
        suffix = market_to_suffix[normalized]

        for ticker in ticker_list:
            symbol = f"{ticker}{suffix}"
            if symbol not in seen:
                seen.add(symbol)
                symbols.append(symbol)

    return symbols


def fetch_symbol_history(
    symbol: str,
    output_dir: Path,
    start_date: str,
    end_date: str,
    retries: int = 3,
    retry_delay_seconds: float = 2.0,
) -> Path:
    """Fetch daily candle history for one symbol and save to CSV."""
    if yf is None:
        raise RuntimeError("yfinance is required. Install with: pip install yfinance")

    last_error: Exception | None = None

    for attempt in range(1, retries + 1):
        try:
            ticker = yf.Ticker(symbol)
            df = ticker.history(start=start_date, end=end_date, interval="1d", auto_adjust=False)
            if df.empty:
                raise RuntimeError(f"No rows returned for symbol '{symbol}'")

            output_dir.mkdir(parents=True, exist_ok=True)
            output_path = output_dir / f"{symbol}.csv"
            df.to_csv(output_path)
            print(f"Saved {symbol}: {len(df)} rows -> {output_path}")
            return output_path
        except Exception as exc:
            last_error = exc
            if attempt < retries:
                sleep_seconds = retry_delay_seconds * attempt
                print(
                    f"[{symbol}] fetch attempt {attempt}/{retries} failed: {exc}. "
                    f"Retrying in {sleep_seconds:.1f}s..."
                )
                time.sleep(sleep_seconds)
            else:
                print(f"[{symbol}] failed after {retries} attempts: {exc}")

    raise RuntimeError(f"Failed to fetch '{symbol}'") from last_error


def fetch_historical_data(
    symbols: Iterable[str],
    output_dir: Path = Path("data"),
    start_date: str = "2026-01-01",
    end_date: str | None = None,
    retries: int = 3,
    retry_delay_seconds: float = 2.0,
    continue_on_error: bool = True,
) -> tuple[list[Path], list[str]]:
    """Fetch all symbols and return (created_files, failed_symbols)."""
    end_value = end_date or date.today().isoformat()
    created_files: list[Path] = []
    failed_symbols: list[str] = []

    for raw_symbol in symbols:
        symbol = raw_symbol.strip().upper()
        if not symbol:
            continue

        try:
            csv_path = fetch_symbol_history(
                symbol=symbol,
                output_dir=output_dir,
                start_date=start_date,
                end_date=end_value,
                retries=retries,
                retry_delay_seconds=retry_delay_seconds,
            )
            created_files.append(csv_path)
        except Exception:
            failed_symbols.append(symbol)
            if not continue_on_error:
                raise

    return created_files, failed_symbols


def git_backup(
    csv_files: list[Path],
    push: bool = False,
    remote: str = "origin",
    branch: str | None = None,
    commit_message: str | None = None,
) -> None:
    """Track CSVs with Git LFS, commit, and optionally push."""
    if not csv_files:
        print("No files to backup. Skipping git steps.")
        return

    run_command(["git", "lfs", "install"])
    run_command(["git", "lfs", "track", "*.csv"])
    run_command(["git", "add", ".gitattributes"])
    run_command(["git", "add", "data/"])

    final_message = commit_message or f"data backup: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')} UTC"

    status = run_command(["git", "status", "--porcelain"], check=False)
    if not status.stdout.strip():
        print("No git changes detected after fetch. Nothing to commit.")
        return

    run_command(["git", "commit", "-m", final_message])

    if push:
        if branch is None:
            branch_result = run_command(["git", "rev-parse", "--abbrev-ref", "HEAD"])
            branch = branch_result.stdout.strip()
        run_command(["git", "push", remote, branch])
        print(f"Push complete: {remote}/{branch}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fetch historical stock data and back up via Git LFS")
    parser.add_argument("--symbols", nargs="*", default=[], help="Ticker symbols (e.g. AAPL TSLA 005930.KS)")
    parser.add_argument(
        "--krx-markets",
        nargs="*",
        default=[],
        help="Auto-load all symbols in specified markets via pykrx (KOSPI, KOSDAQ)",
    )
    parser.add_argument("--start-date", default="2026-01-01", help="Start date (YYYY-MM-DD)")
    parser.add_argument("--end-date", default=None, help="End date (YYYY-MM-DD, default=today)")
    parser.add_argument("--data-dir", default="data", help="Output directory for CSV files")
    parser.add_argument("--retries", type=int, default=3, help="Retries per symbol")
    parser.add_argument("--retry-delay", type=float, default=2.0, help="Base retry delay seconds")
    parser.add_argument("--push", action="store_true", help="Push commit after creating it")
    parser.add_argument("--remote", default="origin", help="Git remote name for push")
    parser.add_argument("--branch", default=None, help="Git branch for push (defaults to current branch)")
    parser.add_argument("--commit-message", default=None, help="Custom commit message")
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    symbols = [s.strip().upper() for s in args.symbols if s.strip()]
    if args.krx_markets:
        symbols.extend(krx_symbols(args.krx_markets))

    # Deduplicate while preserving order
    deduped_symbols = list(dict.fromkeys(symbols))
    if not deduped_symbols:
        raise RuntimeError("No symbols provided. Use --symbols and/or --krx-markets")

    files, failed = fetch_historical_data(
        symbols=deduped_symbols,
        output_dir=Path(args.data_dir),
        start_date=args.start_date,
        end_date=args.end_date,
        retries=args.retries,
        retry_delay_seconds=args.retry_delay,
        continue_on_error=True,
    )

    print(f"Fetched {len(files)} symbols. Failed: {len(failed)}")
    if failed:
        print("Failed symbols sample:", ", ".join(failed[:20]))

    git_backup(
        files,
        push=args.push,
        remote=args.remote,
        branch=args.branch,
        commit_message=args.commit_message,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
