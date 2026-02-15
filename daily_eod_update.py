"""
Incremental EOD updater for partitioned Parquet on Cloudflare R2.

Writes only new partition objects (no full rewrite):
  s3://<bucket>/<prefix>/year=<YYYY>/ticker=<TICKER>/part-<YYYY-MM-DD>-<stamp>.parquet

Requirements:
  pip install duckdb boto3 pandas yfinance pyarrow pykrx finance-datareader
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple
from uuid import uuid4

import boto3
import duckdb
import FinanceDataReader as fdr
import pandas as pd
import yfinance as yf
from dotenv import load_dotenv
from pykrx import stock as pykrx_stock


@dataclass(frozen=True)
class R2Settings:
    endpoint: str
    bucket: str
    access_key_id: str
    secret_access_key: str
    region: str = "auto"
    dataset_prefix: str = "market_data"

    @property
    def endpoint_no_scheme(self) -> str:
        return self.endpoint.replace("https://", "").replace("http://", "")


def env_required(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Missing required env var: {name}")
    return value


def load_settings() -> R2Settings:
    return R2Settings(
        endpoint=env_required("R2_ENDPOINT"),
        bucket=env_required("R2_BUCKET"),
        access_key_id=env_required("R2_ACCESS_KEY_ID"),
        secret_access_key=env_required("R2_SECRET_ACCESS_KEY"),
        region=os.getenv("R2_REGION", "auto"),
        dataset_prefix=os.getenv("R2_DATASET_PREFIX", "market_data").strip("/"),
    )


def make_s3_client(settings: R2Settings):
    return boto3.client(
        "s3",
        endpoint_url=settings.endpoint,
        aws_access_key_id=settings.access_key_id,
        aws_secret_access_key=settings.secret_access_key,
        region_name=settings.region,
    )


def make_duckdb(settings: R2Settings) -> duckdb.DuckDBPyConnection:
    con = duckdb.connect(database=":memory:")
    con.execute("INSTALL httpfs")
    con.execute("LOAD httpfs")
    con.execute("SET s3_url_style='path'")
    con.execute("SET s3_endpoint = ?", [settings.endpoint_no_scheme])
    con.execute("SET s3_access_key_id = ?", [settings.access_key_id])
    con.execute("SET s3_secret_access_key = ?", [settings.secret_access_key])
    con.execute("SET s3_region = ?", [settings.region])
    con.execute("SET s3_use_ssl = true")
    return con


def dataset_glob(settings: R2Settings) -> str:
    return (
        f"s3://{settings.bucket}/{settings.dataset_prefix}/"
        "year=*/ticker=*/part-*.parquet"
    )


def latest_trade_date(con: duckdb.DuckDBPyConnection, settings: R2Settings, ticker: str) -> Optional[pd.Timestamp]:
    q = f"""
    SELECT max(date) AS max_date
    FROM read_parquet('{dataset_glob(settings)}', hive_partitioning=1)
    WHERE ticker = ?
    """
    try:
        out = con.execute(q, [ticker]).df()
    except duckdb.IOException as exc:
        if "No files found that match the pattern" in str(exc):
            return None
        raise
    if out.empty or pd.isna(out.loc[0, "max_date"]):
        return None
    return pd.Timestamp(out.loc[0, "max_date"])


def latest_trade_date_map(con: duckdb.DuckDBPyConnection, settings: R2Settings) -> Dict[str, pd.Timestamp]:
    q = f"""
    SELECT ticker, max(date) AS max_date
    FROM read_parquet('{dataset_glob(settings)}', hive_partitioning=1)
    GROUP BY ticker
    """
    try:
        out = con.execute(q).df()
    except duckdb.IOException as exc:
        if "No files found that match the pattern" in str(exc):
            return {}
        raise
    if out.empty:
        return {}
    out = out.dropna(subset=["ticker", "max_date"])
    return {str(r["ticker"]).upper(): pd.Timestamp(r["max_date"]) for _, r in out.iterrows()}


def normalize_ohlcv(df: pd.DataFrame, ticker: str) -> pd.DataFrame:
    if df.empty:
        return df
    out = df.rename(
        columns={
            "Date": "date",
            "Open": "open",
            "High": "high",
            "Low": "low",
            "Close": "close",
            "Volume": "volume",
            "Adj Close": "adj_close",
        }
    ).copy()
    out["ticker"] = ticker
    if "adj_close" not in out.columns:
        out["adj_close"] = out["close"]
    out["date"] = pd.to_datetime(out["date"], utc=True).dt.tz_convert(None)
    out = out[["ticker", "date", "open", "high", "low", "close", "volume", "adj_close"]]
    return out.dropna(subset=["date", "open", "high", "low", "close"])


def fetch_incremental_eod(ticker: str, start_date: datetime, end_date: datetime) -> pd.DataFrame:
    # Korean 6-digit symbols are handled by FinanceDataReader.
    if ticker.isdigit() and len(ticker) == 6:
        raw = fdr.DataReader(ticker, start=start_date.date().isoformat(), end=end_date.date().isoformat())
        if raw.empty:
            return pd.DataFrame()
        raw = raw.reset_index().rename(
            columns={
                "Date": "date",
                "Open": "open",
                "High": "high",
                "Low": "low",
                "Close": "close",
                "Adj Close": "adj_close",
                "Volume": "volume",
            }
        )
        if "adj_close" not in raw.columns:
            raw["adj_close"] = raw["close"]
        raw["ticker"] = ticker
        raw["date"] = pd.to_datetime(raw["date"], utc=True).dt.tz_convert(None)
        raw = raw[["ticker", "date", "open", "high", "low", "close", "volume", "adj_close"]]
        return raw.dropna(subset=["date", "open", "high", "low", "close"])

    raw = yf.download(
        ticker,
        start=start_date.date().isoformat(),
        end=(end_date.date() + timedelta(days=1)).isoformat(),
        auto_adjust=False,
        progress=False,
    ).reset_index()
    return normalize_ohlcv(raw, ticker=ticker)


def resolve_tickers(default_tickers: Iterable[str]) -> List[str]:
    if os.getenv("VS_KOSPI_ALL", "false").lower() == "true":
        return sorted(pykrx_stock.get_market_ticker_list(market="KOSPI"))
    return [t.strip().upper() for t in default_tickers if t.strip()]


def upload_new_rows(
    s3,
    settings: R2Settings,
    ticker: str,
    rows: pd.DataFrame,
    tmp_dir: Path,
) -> int:
    if rows.empty:
        return 0
    uploaded = 0
    rows = rows.copy()
    rows["year"] = rows["date"].dt.year
    rows["ds"] = rows["date"].dt.strftime("%Y-%m-%d")

    for (year, ds), chunk in rows.groupby(["year", "ds"], sort=True):
        stamp = int(time.time() * 1000)
        filename = f"part-{ds}-{stamp}-{uuid4().hex[:8]}.parquet"
        local_path = tmp_dir / filename
        chunk.drop(columns=["year", "ds"]).to_parquet(local_path, index=False)
        key = (
            f"{settings.dataset_prefix}/"
            f"year={year}/ticker={ticker}/{filename}"
        )
        s3.upload_file(str(local_path), settings.bucket, key)
        uploaded += len(chunk)
    return uploaded


def list_keys_with_prefix(s3, bucket: str, prefix: str) -> List[str]:
    keys: List[str] = []
    token = None
    while True:
        kwargs = {"Bucket": bucket, "Prefix": prefix}
        if token:
            kwargs["ContinuationToken"] = token
        resp = s3.list_objects_v2(**kwargs)
        for obj in resp.get("Contents", []):
            keys.append(obj["Key"])
        if not resp.get("IsTruncated"):
            break
        token = resp.get("NextContinuationToken")
    return keys


def delete_prefix(s3, bucket: str, prefix: str) -> int:
    keys = list_keys_with_prefix(s3, bucket, prefix)
    if not keys:
        return 0
    deleted = 0
    for i in range(0, len(keys), 1000):
        chunk = keys[i : i + 1000]
        s3.delete_objects(
            Bucket=bucket,
            Delete={"Objects": [{"Key": k} for k in chunk], "Quiet": True},
        )
        deleted += len(chunk)
    return deleted


def upload_yearly_compacted(
    s3,
    settings: R2Settings,
    ticker: str,
    rows: pd.DataFrame,
    tmp_dir: Path,
) -> int:
    if rows.empty:
        return 0
    rows = rows.copy()
    rows["year"] = rows["date"].dt.year
    written = 0
    for year, chunk in rows.groupby("year", sort=True):
        prefix = f"{settings.dataset_prefix}/year={year}/ticker={ticker}/"
        delete_prefix(s3, settings.bucket, prefix)
        filename = f"part-{year}-{uuid4().hex[:8]}.parquet"
        local_path = tmp_dir / filename
        chunk = chunk.drop(columns=["year"]).sort_values("date")
        chunk.to_parquet(local_path, index=False)
        key = f"{prefix}{filename}"
        s3.upload_file(str(local_path), settings.bucket, key)
        written += len(chunk)
    return written


def process_single_ticker(
    ticker: str,
    latest_map: Dict[str, pd.Timestamp],
    now: datetime,
    s3,
    settings: R2Settings,
    tmp_dir: Path,
) -> Tuple[str, int, Optional[str]]:
    max_date = latest_map.get(ticker)

    if max_date is None:
        # Bootstrap: full 10-year history -> compact yearly files.
        start = now - timedelta(days=3650)
    else:
        # Incremental: rewrite current year shard only (keeps one file/year).
        start = datetime(now.year, 1, 1)

    if start.date() > now.date():
        return ticker, 0, None

    df = fetch_incremental_eod(ticker=ticker, start_date=start, end_date=now)
    count = upload_yearly_compacted(s3, settings, ticker=ticker, rows=df, tmp_dir=tmp_dir)
    return ticker, count, None


def run_daily_update(tickers: Iterable[str]) -> Dict[str, int]:
    settings = load_settings()
    s3 = make_s3_client(settings)
    con = make_duckdb(settings)

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    results: Dict[str, int] = {}
    failures: Dict[str, str] = {}
    started_at = time.time()
    request_sleep = float(os.getenv("VS_REQUEST_SLEEP", "0.03"))
    max_workers = max(1, int(os.getenv("VS_MAX_WORKERS", "6")))
    resolved = [s.strip().upper() for s in tickers if s.strip()]

    print(f"[ETL] ticker_count={len(resolved)} workers={max_workers} sleep={request_sleep}s")
    latest_map = latest_trade_date_map(con, settings)
    print(f"[ETL] existing_tickers_in_r2={len(latest_map)}")

    with tempfile.TemporaryDirectory(prefix="eod_upload_") as d:
        tmp_dir = Path(d)
        total = len(resolved)
        completed = 0
        with ThreadPoolExecutor(max_workers=max_workers) as ex:
            futures = {}
            for ticker in resolved:
                fut = ex.submit(process_single_ticker, ticker, latest_map, now, s3, settings, tmp_dir)
                futures[fut] = ticker
                if request_sleep > 0:
                    time.sleep(request_sleep)

            for fut in as_completed(futures):
                ticker = futures[fut]
                completed += 1
                pct = (completed / total) * 100 if total else 100.0
                try:
                    _, count, _ = fut.result()
                    results[ticker] = count
                    status = "updated" if count > 0 else "no-change"
                    print(f"[{pct:6.2f}%] [{completed}/{total}] {ticker}: {status}, rows={count}")
                except Exception as exc:
                    results[ticker] = 0
                    failures[ticker] = str(exc)
                    print(f"[{pct:6.2f}%] [{completed}/{total}] {ticker}: failed ({exc})")

                if completed % 25 == 0 or completed == total:
                    elapsed = max(0.001, time.time() - started_at)
                    rate = completed / elapsed
                    remain = total - completed
                    eta = round(remain / rate, 1)
                    print(
                        f"[PROGRESS {pct:6.2f}%] completed={completed}/{total} "
                        f"rate={rate:.2f} tickers/s eta={eta}s "
                        f"rows={sum(results.values())} failures={len(failures)}"
                    )

    con.close()
    elapsed = round(time.time() - started_at, 2)
    updated = {k: v for k, v in results.items() if v > 0}
    summary = {
        "run_at_utc": datetime.utcnow().isoformat(timespec="seconds"),
        "elapsed_seconds": elapsed,
        "processed_tickers": len(results),
        "updated_tickers": len(updated),
        "failed_tickers": len(failures),
        "total_rows_appended": int(sum(results.values())),
        "top_updated": sorted(updated.items(), key=lambda x: x[1], reverse=True)[:20],
        "failures": failures,
    }
    print(
        "[ETL SUMMARY] "
        f"processed={summary['processed_tickers']} "
        f"updated={summary['updated_tickers']} "
        f"failed={summary['failed_tickers']} "
        f"rows={summary['total_rows_appended']} "
        f"elapsed={summary['elapsed_seconds']}s"
    )

    report_dir = Path(os.getenv("VS_ETL_REPORT_DIR", "logs"))
    report_dir.mkdir(parents=True, exist_ok=True)
    report_path = report_dir / f"etl_result_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"
    report_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[ETL REPORT] {report_path}")

    return results


def run_daily_top5_refresh() -> None:
    enabled = os.getenv("VS_ENABLE_DAILY_TOP5_REFRESH", "true").strip().lower()
    if enabled in {"0", "false", "no", "off"}:
        print("[TOP5] skipped: VS_ENABLE_DAILY_TOP5_REFRESH is disabled")
        return

    script_path = Path(os.getenv("VS_DAILY_TOP5_SCRIPT", "build_daily_top5_recommendations.py"))
    if not script_path.exists():
        raise FileNotFoundError(f"[TOP5] script not found: {script_path}")

    cmd: List[str] = [
        sys.executable,
        str(script_path),
        "--start-date",
        os.getenv("VS_DAILY_TOP5_START_DATE", "2026-01-01"),
    ]

    end_date = os.getenv("VS_DAILY_TOP5_END_DATE", "").strip()
    if end_date:
        cmd.extend(["--end-date", end_date])

    out_path = os.getenv("VS_DAILY_TOP5_OUT", "").strip()
    if out_path:
        cmd.extend(["--out", out_path])

    weight_turnover = os.getenv("VS_DAILY_TOP5_WEIGHT_TURNOVER", "").strip()
    if weight_turnover:
        cmd.extend(["--weight-turnover", weight_turnover])

    weight_ret1d = os.getenv("VS_DAILY_TOP5_WEIGHT_RET1D", "").strip()
    if weight_ret1d:
        cmd.extend(["--weight-ret1d", weight_ret1d])

    weight_model = os.getenv("VS_DAILY_TOP5_WEIGHT_MODEL", "").strip()
    if weight_model:
        cmd.extend(["--weight-model", weight_model])

    print(f"[TOP5] running: {' '.join(cmd)}")
    completed = subprocess.run(cmd, capture_output=True, text=True, check=True)
    if completed.stdout.strip():
        print(completed.stdout.strip())
    if completed.stderr.strip():
        print(completed.stderr.strip())
    print("[TOP5] daily recommendations refresh complete")


if __name__ == "__main__":
    load_dotenv(".env.r2.local", override=False)
    load_dotenv(".env.local", override=False)
    load_dotenv(".env", override=False)
    tickers = resolve_tickers(os.getenv("VS_TICKERS", "AAPL,MSFT,NVDA,AMZN,GOOGL").split(","))
    run_daily_update(tickers)
    run_daily_top5_refresh()
