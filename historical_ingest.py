"""
Historical data ingestion for Visual Stock.

Requirements:
  pip install pandas yfinance pykrx supabase

Env:
  SUPABASE_URL
  SUPABASE_SERVICE_ROLE_KEY
  VS_US_TICKERS (optional)
  VS_KR_TICKERS (optional)
  VS_MAX_RETRIES (optional)
  VS_RETRY_BACKOFF_SECONDS (optional)
  VS_BATCH_SIZE (optional)
  VS_SLEEP_BETWEEN_TICKERS (optional)
"""

import logging
import os
import time
from datetime import datetime
from typing import Dict, Iterable, List, Tuple

import pandas as pd
import yfinance as yf
from pykrx import stock as pykrx_stock
from supabase import create_client, Client

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_SERVICE_ROLE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")

US_TICKERS = os.environ.get(
    "VS_US_TICKERS",
    "AAPL,MSFT,NVDA,AMZN,GOOGL,META,TSLA,JPM,JNJ,XOM,AVGO,UNH,V,MA,PG,HD,LLY,KO,PEP,COST",
).split(",")

KR_TICKERS = os.environ.get(
    "VS_KR_TICKERS",
    "005930,000660,035420,035720,051910,005380,068270,207940,006400,012330,028260,105560,055550,066570,017670,034730,096770,000270,005490,035900",
).split(",")

MAX_RETRIES = int(os.environ.get("VS_MAX_RETRIES", "3"))
RETRY_BACKOFF_SECONDS = float(os.environ.get("VS_RETRY_BACKOFF_SECONDS", "1.5"))
BATCH_SIZE = int(os.environ.get("VS_BATCH_SIZE", "500"))
SLEEP_BETWEEN_TICKERS = float(os.environ.get("VS_SLEEP_BETWEEN_TICKERS", "0.2"))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)
logger = logging.getLogger("historical_ingest")


def rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = -delta.where(delta < 0, 0.0)
    avg_gain = gain.rolling(period).mean()
    avg_loss = loss.rolling(period).mean()
    rs = avg_gain / avg_loss.replace(0, pd.NA)
    return 100 - (100 / (1 + rs))


def fetch_us_ohlcv(ticker: str) -> pd.DataFrame:
    data = yf.download(ticker, period="max", auto_adjust=False, progress=False)
    if data.empty:
        return pd.DataFrame()

    df = data[["Open", "High", "Low", "Close", "Volume"]].copy()
    df.columns = ["open", "high", "low", "close", "volume"]
    df["rsi_14"] = rsi(df["close"])
    return df.dropna(subset=["open", "high", "low", "close"])


def fetch_kr_ohlcv(ticker: str) -> pd.DataFrame:
    start = "19800101"
    end = datetime.utcnow().strftime("%Y%m%d")
    df = pykrx_stock.get_market_ohlcv_by_date(start, end, ticker)
    if df.empty:
        return pd.DataFrame()

    df = df.rename(
        columns={
            "시가": "open",
            "고가": "high",
            "저가": "low",
            "종가": "close",
            "거래량": "volume",
        }
    )
    df["rsi_14"] = rsi(df["close"])
    return df[["open", "high", "low", "close", "volume", "rsi_14"]].dropna(subset=["open", "high", "low", "close"])


def get_supabase_client() -> Client:
    if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
        raise RuntimeError("Missing SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY")
    return create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)


def get_us_name(ticker: str) -> str:
    try:
        info = yf.Ticker(ticker).info
        name = info.get("shortName") or info.get("longName")
        return name or ticker
    except Exception:
        return ticker


def get_kr_name(ticker: str) -> str:
    try:
        return pykrx_stock.get_market_ticker_name(ticker)
    except Exception:
        return ticker


def get_kr_exchange_sets() -> Tuple[set, set]:
    try:
        kospi = set(pykrx_stock.get_market_ticker_list(market="KOSPI"))
        kosdaq = set(pykrx_stock.get_market_ticker_list(market="KOSDAQ"))
        return kospi, kosdaq
    except Exception:
        return set(), set()


def retry(operation, label: str, max_retries: int = MAX_RETRIES):
    attempt = 0
    while True:
        try:
            return operation()
        except Exception as exc:
            attempt += 1
            if attempt > max_retries:
                logger.error("%s failed after %s attempts: %s", label, attempt, exc)
                raise
            sleep_for = RETRY_BACKOFF_SECONDS * (2 ** (attempt - 1))
            logger.warning("%s failed (attempt %s/%s). Retrying in %.2fs", label, attempt, max_retries, sleep_for)
            time.sleep(sleep_for)


def upsert_stocks(supabase: Client, rows: List[Dict]):
    if not rows:
        return

    def operation():
        supabase.table("stocks").upsert(rows, on_conflict="ticker").execute()

    retry(operation, "stocks upsert")


def upsert_prices(supabase: Client, rows: List[Dict], batch_size: int = BATCH_SIZE):
    if not rows:
        return
    for i in range(0, len(rows), batch_size):
        batch = rows[i : i + batch_size]

        def operation():
            supabase.table("historical_prices").upsert(batch, on_conflict="ticker,trade_date").execute()

        retry(operation, f"historical_prices upsert batch {i // batch_size + 1}")


def to_price_rows(ticker: str, df: pd.DataFrame) -> List[Dict]:
    rows = []
    for index, row in df.iterrows():
        trade_date = index.date().isoformat() if hasattr(index, "date") else str(index)
        if pd.isna(row["open"]) or pd.isna(row["high"]) or pd.isna(row["low"]) or pd.isna(row["close"]):
            continue
        rows.append(
            {
                "ticker": ticker,
                "trade_date": trade_date,
                "open": float(row["open"]),
                "high": float(row["high"]),
                "low": float(row["low"]),
                "close": float(row["close"]),
                "volume": int(row["volume"]) if pd.notna(row["volume"]) else None,
                "rsi_14": float(row["rsi_14"]) if pd.notna(row["rsi_14"]) else None,
            }
        )
    return rows


def ingest_market(
    supabase: Client,
    tickers: Iterable[str],
    market: str,
    currency: str,
    exchange_resolver=None,
    name_resolver=None,
    fetcher=None,
):
    for ticker in tickers:
        ticker = ticker.strip()
        if not ticker:
            continue

        name = name_resolver(ticker) if name_resolver else ticker
        exchange = exchange_resolver(ticker) if exchange_resolver else None
        logger.info("ingest | %s %s - %s", market, ticker, name)

        upsert_stocks(
            supabase,
            [
                {
                    "ticker": ticker,
                    "name": name,
                    "market": market,
                    "currency": currency,
                    "exchange": exchange,
                }
            ],
        )

        def fetch_operation():
            return fetcher(ticker) if fetcher else pd.DataFrame()

        try:
            df = retry(fetch_operation, f"fetch {market} {ticker}")
        except Exception:
            logger.error("fetch failed: %s %s", market, ticker)
            continue

        if df.empty:
            logger.warning("no data: %s %s", market, ticker)
            continue

        rows = to_price_rows(ticker, df)
        upsert_prices(supabase, rows)
        logger.info("upserted %s rows for %s", len(rows), ticker)
        if SLEEP_BETWEEN_TICKERS:
            time.sleep(SLEEP_BETWEEN_TICKERS)


def main():
    logger.info("starting ingestion")
    supabase = get_supabase_client()

    kospi_set, kosdaq_set = get_kr_exchange_sets()

    def kr_exchange_resolver(ticker: str) -> str:
        if ticker in kospi_set:
            return "KOSPI"
        if ticker in kosdaq_set:
            return "KOSDAQ"
        return "KRX"

    ingest_market(
        supabase,
        US_TICKERS,
        market="US",
        currency="USD",
        exchange_resolver=None,
        name_resolver=get_us_name,
        fetcher=fetch_us_ohlcv,
    )

    ingest_market(
        supabase,
        KR_TICKERS,
        market="KR",
        currency="KRW",
        exchange_resolver=kr_exchange_resolver,
        name_resolver=get_kr_name,
        fetcher=fetch_kr_ohlcv,
    )

    logger.info("ingestion complete")


if __name__ == "__main__":
    main()
