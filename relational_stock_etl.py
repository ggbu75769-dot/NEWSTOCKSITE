"""
관계형 DB(PostgreSQL)용 주식 히스토리 ETL

요구사항 반영:
- 필수 컬럼: symbol, trade_date, OHLCV, adj_close
- 파생 컬럼: daily_return, rsi_14, sma_20, sma_60, sma_120
- 업서트: (symbol, trade_date) 충돌 시 update
- 배치 처리: execute_values 기반 bulk upsert
- 검증 레이어: NaN/누락 컬럼/API 실패 처리

사전 준비:
1) relational_stock_schema.sql 적용
2) 환경변수 설정:
   PG_HOST, PG_PORT, PG_DATABASE, PG_USER, PG_PASSWORD
3) 설치:
   pip install pandas yfinance psycopg2-binary
"""

from __future__ import annotations

import argparse
import logging
import os
from datetime import date, datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP, InvalidOperation
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

import pandas as pd
import yfinance as yf
from psycopg2 import connect
from psycopg2.extras import execute_values


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)
logger = logging.getLogger("relational_stock_etl")

Q4 = Decimal("0.0001")


def env_required(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"필수 환경변수 누락: {name}")
    return value


def db_connect():
    return connect(
        host=env_required("PG_HOST"),
        port=os.getenv("PG_PORT", "5432"),
        dbname=env_required("PG_DATABASE"),
        user=env_required("PG_USER"),
        password=env_required("PG_PASSWORD"),
    )


def rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = -delta.where(delta < 0, 0.0)
    avg_gain = gain.rolling(period).mean()
    avg_loss = loss.rolling(period).mean().replace(0, pd.NA)
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def to_decimal_4(value: object) -> Optional[Decimal]:
    if value is None or pd.isna(value):
        return None
    try:
        return Decimal(str(value)).quantize(Q4, rounding=ROUND_HALF_UP)
    except (InvalidOperation, ValueError, TypeError):
        return None


def fetch_history(symbol: str, start_date: date, end_date: date) -> pd.DataFrame:
    try:
        df = yf.download(
            symbol,
            start=start_date.isoformat(),
            end=(end_date + timedelta(days=1)).isoformat(),
            auto_adjust=False,
            progress=False,
        )
    except Exception as exc:
        logger.error("API 오류 | %s | %s", symbol, exc)
        return pd.DataFrame()

    if df.empty:
        logger.warning("데이터 없음 | %s", symbol)
        return df

    if isinstance(df.columns, pd.MultiIndex):
        df.columns = [c[0] for c in df.columns]

    df = df.reset_index().rename(
        columns={
            "Date": "trade_date",
            "Open": "open",
            "High": "high",
            "Low": "low",
            "Close": "close",
            "Adj Close": "adj_close",
            "Volume": "volume",
        }
    )

    required = {"trade_date", "open", "high", "low", "close", "adj_close", "volume"}
    missing = required - set(df.columns)
    if missing:
        logger.error("컬럼 누락 | %s | %s", symbol, ",".join(sorted(missing)))
        return pd.DataFrame()

    # Validation layer: 필수 값 누락 행 제거
    df = df.dropna(subset=["trade_date", "open", "high", "low", "close", "adj_close"])
    if df.empty:
        logger.warning("검증 후 유효 데이터 없음 | %s", symbol)
        return df

    df["volume"] = df["volume"].fillna(0)
    df["trade_date"] = pd.to_datetime(df["trade_date"]).dt.date

    # Derived metrics (adj_close 기준)
    df["daily_return"] = df["adj_close"].pct_change() * 100
    df["rsi_14"] = rsi(df["adj_close"], 14)
    df["sma_20"] = df["adj_close"].rolling(20).mean()
    df["sma_60"] = df["adj_close"].rolling(60).mean()
    df["sma_120"] = df["adj_close"].rolling(120).mean()

    return df


def to_rows(symbol: str, df: pd.DataFrame) -> List[Tuple]:
    rows: List[Tuple] = []
    for _, r in df.iterrows():
        open_v = to_decimal_4(r["open"])
        high_v = to_decimal_4(r["high"])
        low_v = to_decimal_4(r["low"])
        close_v = to_decimal_4(r["close"])
        adj_close_v = to_decimal_4(r["adj_close"])

        # Validation layer: 가격 필드 파싱 실패 시 skip
        if None in (open_v, high_v, low_v, close_v, adj_close_v):
            continue

        rows.append(
            (
                symbol,
                r["trade_date"],
                open_v,
                high_v,
                low_v,
                close_v,
                adj_close_v,
                int(r["volume"]) if not pd.isna(r["volume"]) else 0,
                to_decimal_4(r["daily_return"]),
                to_decimal_4(r["rsi_14"]),
                to_decimal_4(r["sma_20"]),
                to_decimal_4(r["sma_60"]),
                to_decimal_4(r["sma_120"]),
            )
        )
    return rows


def last_trade_date(cur, symbol: str) -> Optional[date]:
    cur.execute(
        """
        select max(trade_date)
        from public.stock_daily_prices
        where symbol = %s
        """,
        (symbol,),
    )
    value = cur.fetchone()[0]
    return value


def upsert_batch(cur, rows: Sequence[Tuple], batch_size: int) -> int:
    if not rows:
        return 0

    sql = """
    insert into public.stock_daily_prices (
      symbol, trade_date, open, high, low, close, adj_close, volume,
      daily_return, rsi_14, sma_20, sma_60, sma_120, updated_at
    )
    values %s
    on conflict (symbol, trade_date) do update set
      open = excluded.open,
      high = excluded.high,
      low = excluded.low,
      close = excluded.close,
      adj_close = excluded.adj_close,
      volume = excluded.volume,
      daily_return = excluded.daily_return,
      rsi_14 = excluded.rsi_14,
      sma_20 = excluded.sma_20,
      sma_60 = excluded.sma_60,
      sma_120 = excluded.sma_120,
      updated_at = now()
    """

    total = 0
    for i in range(0, len(rows), batch_size):
        chunk = rows[i : i + batch_size]
        execute_values(cur, sql, chunk, page_size=batch_size)
        total += len(chunk)
    return total


def run_etl(
    symbols: Iterable[str],
    mode: str,
    full_start_date: date,
    end_date: date,
    batch_size: int,
) -> Dict[str, int]:
    results: Dict[str, int] = {}
    with db_connect() as conn:
        with conn.cursor() as cur:
            for raw in symbols:
                symbol = raw.strip().upper()
                if not symbol:
                    continue

                if mode == "incremental":
                    max_dt = last_trade_date(cur, symbol)
                    start_date = (max_dt + timedelta(days=1)) if max_dt else full_start_date
                else:
                    start_date = full_start_date

                if start_date > end_date:
                    results[symbol] = 0
                    logger.info("skip | %s | 최신 데이터", symbol)
                    continue

                logger.info("fetch | %s | %s -> %s", symbol, start_date, end_date)
                df = fetch_history(symbol, start_date, end_date)
                if df.empty:
                    results[symbol] = 0
                    continue

                rows = to_rows(symbol, df)
                if not rows:
                    results[symbol] = 0
                    logger.warning("검증 후 업서트 대상 없음 | %s", symbol)
                    continue

                written = upsert_batch(cur, rows, batch_size=batch_size)
                conn.commit()
                results[symbol] = written
                logger.info("upsert 완료 | %s | %s rows", symbol, written)
    return results


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="PostgreSQL historical stock ETL")
    parser.add_argument(
        "--symbols",
        default=os.getenv("VS_TICKERS", "AAPL,TSLA,MSFT,NVDA,AMZN"),
        help="쉼표 구분 티커 목록",
    )
    parser.add_argument(
        "--mode",
        choices=["full", "incremental"],
        default="incremental",
        help="full: 지정 시작일부터 전체 적재 / incremental: DB max(trade_date) 이후만 적재",
    )
    parser.add_argument(
        "--start-date",
        default=(datetime.utcnow().date() - timedelta(days=3650)).isoformat(),
        help="full 모드 시작일 (YYYY-MM-DD)",
    )
    parser.add_argument(
        "--end-date",
        default=datetime.utcnow().date().isoformat(),
        help="종료일 (YYYY-MM-DD)",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=int(os.getenv("VS_BATCH_SIZE", "1000")),
        help="업서트 배치 크기",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    symbols = [s.strip().upper() for s in args.symbols.split(",") if s.strip()]
    start_date = datetime.strptime(args.start_date, "%Y-%m-%d").date()
    end_date = datetime.strptime(args.end_date, "%Y-%m-%d").date()
    results = run_etl(
        symbols=symbols,
        mode=args.mode,
        full_start_date=start_date,
        end_date=end_date,
        batch_size=args.batch_size,
    )
    total = sum(results.values())
    logger.info("ETL 완료 | symbols=%s | total_rows=%s", len(results), total)


if __name__ == "__main__":
    main()

