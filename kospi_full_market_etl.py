"""
KOSPI Full-Market Historical Data ETL

Phase 1: KOSPI 전체 종목 동적 조회 (pykrx + FinanceDataReader)
Phase 2: 10년 OHLCV 수집 (FinanceDataReader)
Phase 3: 지표 계산 (RSI14, SMA20/60/120)
Phase 4: DB 배치 업서트 (PostgreSQL native upsert + 타 DB fallback)

지원 DB:
- PostgreSQL: ON CONFLICT (symbol, trade_date) DO UPDATE
- MSSQL/Oracle/기타: delete-then-insert fallback (동일 키 구간 재적재)

필수 패키지:
  pip install pandas pykrx finance-datareader sqlalchemy psycopg2-binary
"""

from __future__ import annotations

import argparse
import logging
import os
import time
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Dict, Iterable, List, Optional
from urllib.parse import quote_plus

import FinanceDataReader as fdr
import pandas as pd
from pykrx import stock as pykrx_stock
from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    Date,
    DateTime,
    Index,
    MetaData,
    Numeric,
    String,
    Table,
    and_,
    create_engine,
    delete,
)
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.engine import Engine


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)
logger = logging.getLogger("kospi_full_market_etl")


@dataclass
class ETLConfig:
    db_url: str
    lookback_years: int = 10
    sleep_seconds: float = 0.15
    batch_size: int = 20000
    max_retries: int = 3
    retry_backoff_seconds: float = 1.2
    table_name: str = "kospi_daily_prices"
    master_table_name: str = "kospi_symbol_master"


def env_required(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"필수 환경변수 누락: {name}")
    return value


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="KOSPI full-market ETL")
    parser.add_argument(
        "--db-url",
        default=os.getenv("DB_URL"),
        help="SQLAlchemy DB URL (예: postgresql+psycopg2://user:pass@host:5432/db)",
    )
    parser.add_argument("--lookback-years", type=int, default=int(os.getenv("LOOKBACK_YEARS", "10")))
    parser.add_argument("--sleep-seconds", type=float, default=float(os.getenv("SLEEP_SECONDS", "0.15")))
    parser.add_argument("--batch-size", type=int, default=int(os.getenv("BATCH_SIZE", "20000")))
    parser.add_argument("--max-retries", type=int, default=int(os.getenv("MAX_RETRIES", "3")))
    parser.add_argument(
        "--retry-backoff-seconds",
        type=float,
        default=float(os.getenv("RETRY_BACKOFF_SECONDS", "1.2")),
    )
    parser.add_argument("--table-name", default=os.getenv("TABLE_NAME", "kospi_daily_prices"))
    parser.add_argument("--master-table-name", default=os.getenv("MASTER_TABLE_NAME", "kospi_symbol_master"))
    return parser.parse_args()


def build_db_url_from_pg_env() -> Optional[str]:
    host = os.getenv("PG_HOST")
    database = os.getenv("PG_DATABASE")
    user = os.getenv("PG_USER")
    password = os.getenv("PG_PASSWORD")
    port = os.getenv("PG_PORT", "5432")

    required = [host, database, user, password]
    if any(v is None or str(v).strip() == "" for v in required):
        return None

    return (
        "postgresql+psycopg2://"
        f"{quote_plus(user)}:{quote_plus(password)}@{host}:{port}/{database}"
    )


def rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = -delta.where(delta < 0, 0.0)
    avg_gain = gain.rolling(period).mean()
    avg_loss = loss.rolling(period).mean().replace(0, pd.NA)
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def retry(func, max_retries: int, backoff_seconds: float, label: str):
    for attempt in range(1, max_retries + 1):
        try:
            return func()
        except Exception as exc:
            if attempt == max_retries:
                logger.error("실패 | %s | %s", label, exc)
                raise
            sleep_for = backoff_seconds * (2 ** (attempt - 1))
            logger.warning("재시도 | %s | attempt=%s | wait=%.2fs | %s", label, attempt, sleep_for, exc)
            time.sleep(sleep_for)
    return None


def get_kospi_universe() -> pd.DataFrame:
    tickers = pykrx_stock.get_market_ticker_list(market="KOSPI")
    listing = fdr.StockListing("KOSPI")
    listing = listing.rename(columns={"Symbol": "symbol", "Name": "company_name", "Sector": "sector"})
    listing["symbol"] = listing["symbol"].astype(str).str.zfill(6)

    listing_map: Dict[str, Dict[str, Optional[str]]] = {}
    for _, row in listing.iterrows():
        listing_map[row["symbol"]] = {
            "company_name": row.get("company_name"),
            "sector": row.get("sector"),
        }

    rows = []
    for t in tickers:
        symbol = str(t).zfill(6)
        meta = listing_map.get(symbol, {})
        company_name = meta.get("company_name")
        if not company_name:
            company_name = pykrx_stock.get_market_ticker_name(symbol)
        rows.append(
            {
                "symbol": symbol,
                "company_name": company_name,
                "sector": meta.get("sector"),
                "is_active": True,
            }
        )

    universe = pd.DataFrame(rows).drop_duplicates(subset=["symbol"]).sort_values("symbol")
    logger.info("KOSPI 유니버스 확보 완료 | symbols=%s", len(universe))
    return universe


def fetch_history(symbol: str, start_date: date, end_date: date) -> pd.DataFrame:
    df = fdr.DataReader(symbol, start=start_date.isoformat(), end=end_date.isoformat())
    if df.empty:
        return df

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
    if "adj_close" not in df.columns:
        df["adj_close"] = df["close"]

    return df


def transform(df: pd.DataFrame, symbol: str, company_name: Optional[str], sector: Optional[str]) -> pd.DataFrame:
    if df.empty:
        return df

    required = ["trade_date", "open", "high", "low", "close", "adj_close", "volume"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        logger.warning("컬럼 누락으로 skip | %s | missing=%s", symbol, ",".join(missing))
        return pd.DataFrame()

    out = df.copy()
    out = out.dropna(subset=["trade_date", "open", "high", "low", "close", "adj_close"])
    if out.empty:
        return out

    out["trade_date"] = pd.to_datetime(out["trade_date"]).dt.date
    out["symbol"] = symbol
    out["company_name"] = company_name
    out["sector"] = sector
    out["volume"] = out["volume"].fillna(0).astype("int64")

    out["daily_return"] = out["adj_close"].pct_change() * 100
    out["rsi_14"] = rsi(out["adj_close"], 14)
    out["sma_20"] = out["adj_close"].rolling(20).mean()
    out["sma_60"] = out["adj_close"].rolling(60).mean()
    out["sma_120"] = out["adj_close"].rolling(120).mean()

    # Numeric(18,4) 저장 전 반올림
    for col in ["open", "high", "low", "close", "adj_close", "daily_return", "rsi_14", "sma_20", "sma_60", "sma_120"]:
        out[col] = out[col].round(4)

    cols = [
        "symbol",
        "trade_date",
        "company_name",
        "sector",
        "open",
        "high",
        "low",
        "close",
        "adj_close",
        "volume",
        "daily_return",
        "rsi_14",
        "sma_20",
        "sma_60",
        "sma_120",
    ]
    return out[cols]


def define_tables(metadata: MetaData, table_name: str, master_table_name: str):
    price_table = Table(
        table_name,
        metadata,
        Column("symbol", String(16), primary_key=True, nullable=False),
        Column("trade_date", Date, primary_key=True, nullable=False),
        Column("company_name", String(255), nullable=True),
        Column("sector", String(255), nullable=True),
        Column("open", Numeric(18, 4), nullable=False),
        Column("high", Numeric(18, 4), nullable=False),
        Column("low", Numeric(18, 4), nullable=False),
        Column("close", Numeric(18, 4), nullable=False),
        Column("adj_close", Numeric(18, 4), nullable=False),
        Column("volume", BigInteger, nullable=False),
        Column("daily_return", Numeric(18, 4), nullable=True),
        Column("rsi_14", Numeric(18, 4), nullable=True),
        Column("sma_20", Numeric(18, 4), nullable=True),
        Column("sma_60", Numeric(18, 4), nullable=True),
        Column("sma_120", Numeric(18, 4), nullable=True),
        Column("created_at", DateTime, nullable=False, default=datetime.utcnow),
        Column("updated_at", DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow),
    )

    Index(f"{table_name}_trade_date_idx", price_table.c.trade_date)

    master_table = Table(
        master_table_name,
        metadata,
        Column("symbol", String(16), primary_key=True, nullable=False),
        Column("company_name", String(255), nullable=True),
        Column("sector", String(255), nullable=True),
        Column("is_active", Boolean, nullable=False, default=True),
        Column("updated_at", DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow),
    )

    return price_table, master_table


def upsert_master(engine: Engine, master_table: Table, universe: pd.DataFrame) -> None:
    records = universe[["symbol", "company_name", "sector", "is_active"]].to_dict(orient="records")
    if not records:
        return
    with engine.begin() as conn:
        if engine.dialect.name == "postgresql":
            stmt = pg_insert(master_table).values(records)
            stmt = stmt.on_conflict_do_update(
                index_elements=["symbol"],
                set_={
                    "company_name": stmt.excluded.company_name,
                    "sector": stmt.excluded.sector,
                    "is_active": stmt.excluded.is_active,
                    "updated_at": datetime.utcnow(),
                },
            )
            conn.execute(stmt)
        else:
            symbols = [r["symbol"] for r in records]
            conn.execute(delete(master_table).where(master_table.c.symbol.in_(symbols)))
            conn.execute(master_table.insert(), records)


def _normalize_records(df: pd.DataFrame) -> List[Dict]:
    records = df.to_dict(orient="records")
    out: List[Dict] = []
    for r in records:
        row = dict(r)
        for key, value in row.items():
            if pd.isna(value):
                row[key] = None
        out.append(row)
    return out


def upsert_prices(engine: Engine, price_table: Table, frame: pd.DataFrame) -> int:
    if frame.empty:
        return 0
    records = _normalize_records(frame)
    with engine.begin() as conn:
        if engine.dialect.name == "postgresql":
            stmt = pg_insert(price_table).values(records)
            update_cols = {
                "company_name": stmt.excluded.company_name,
                "sector": stmt.excluded.sector,
                "open": stmt.excluded.open,
                "high": stmt.excluded.high,
                "low": stmt.excluded.low,
                "close": stmt.excluded.close,
                "adj_close": stmt.excluded.adj_close,
                "volume": stmt.excluded.volume,
                "daily_return": stmt.excluded.daily_return,
                "rsi_14": stmt.excluded.rsi_14,
                "sma_20": stmt.excluded.sma_20,
                "sma_60": stmt.excluded.sma_60,
                "sma_120": stmt.excluded.sma_120,
                "updated_at": datetime.utcnow(),
            }
            stmt = stmt.on_conflict_do_update(
                index_elements=["symbol", "trade_date"],
                set_=update_cols,
            )
            conn.execute(stmt)
            return len(records)

        # Generic fallback for MSSQL/Oracle/etc:
        # symbol 단위로 기존 날짜 구간 삭제 후 insert (동일 키 upsert 효과)
        flushed = 0
        grouped = frame.groupby("symbol", sort=False)
        for symbol, g in grouped:
            min_dt = g["trade_date"].min()
            max_dt = g["trade_date"].max()
            conn.execute(
                delete(price_table).where(
                    and_(
                        price_table.c.symbol == symbol,
                        price_table.c.trade_date >= min_dt,
                        price_table.c.trade_date <= max_dt,
                    )
                )
            )
            sub_records = _normalize_records(g)
            conn.execute(price_table.insert(), sub_records)
            flushed += len(sub_records)
        return flushed


def run_pipeline(config: ETLConfig) -> None:
    engine = create_engine(config.db_url, pool_pre_ping=True, future=True)
    metadata = MetaData()
    price_table, master_table = define_tables(metadata, config.table_name, config.master_table_name)
    metadata.create_all(engine)

    universe = get_kospi_universe()
    upsert_master(engine, master_table, universe)

    end_date = datetime.utcnow().date()
    start_date = end_date - timedelta(days=365 * config.lookback_years)
    logger.info("수집 기간 | %s -> %s", start_date, end_date)

    buffer_frames: List[pd.DataFrame] = []
    buffer_rows = 0
    total_written = 0

    for idx, row in universe.iterrows():
        symbol = row["symbol"]
        company_name = row.get("company_name")
        sector = row.get("sector")
        label = f"{symbol} ({idx + 1}/{len(universe)})"

        def _fetch():
            return fetch_history(symbol=symbol, start_date=start_date, end_date=end_date)

        try:
            raw = retry(
                _fetch,
                max_retries=config.max_retries,
                backoff_seconds=config.retry_backoff_seconds,
                label=f"fetch {label}",
            )
        except Exception:
            logger.warning("수집 실패 skip | %s", label)
            time.sleep(config.sleep_seconds)
            continue

        if raw is None or raw.empty:
            # 상장폐지/거래정지/데이터 미제공 등
            logger.warning("빈 데이터 skip | %s", label)
            time.sleep(config.sleep_seconds)
            continue

        transformed = transform(raw, symbol=symbol, company_name=company_name, sector=sector)
        if transformed.empty:
            logger.warning("변환 결과 없음 skip | %s", label)
            time.sleep(config.sleep_seconds)
            continue

        buffer_frames.append(transformed)
        buffer_rows += len(transformed)

        if buffer_rows >= config.batch_size:
            merged = pd.concat(buffer_frames, ignore_index=True)
            written = upsert_prices(engine, price_table, merged)
            total_written += written
            logger.info("배치 업서트 완료 | rows=%s | total=%s", written, total_written)
            buffer_frames = []
            buffer_rows = 0

        time.sleep(config.sleep_seconds)

    if buffer_rows > 0:
        merged = pd.concat(buffer_frames, ignore_index=True)
        written = upsert_prices(engine, price_table, merged)
        total_written += written
        logger.info("최종 배치 업서트 완료 | rows=%s | total=%s", written, total_written)

    logger.info("파이프라인 완료 | symbols=%s | total_rows=%s", len(universe), total_written)


def main() -> None:
    args = parse_args()
    db_url = args.db_url or os.getenv("DB_URL") or build_db_url_from_pg_env()
    if not db_url:
        raise RuntimeError(
            "DB URL이 필요합니다. --db-url 또는 DB_URL 환경변수를 설정하거나 "
            "PG_HOST/PG_PORT/PG_DATABASE/PG_USER/PG_PASSWORD를 설정하세요."
        )

    config = ETLConfig(
        db_url=db_url,
        lookback_years=args.lookback_years,
        sleep_seconds=args.sleep_seconds,
        batch_size=args.batch_size,
        max_retries=args.max_retries,
        retry_backoff_seconds=args.retry_backoff_seconds,
        table_name=args.table_name,
        master_table_name=args.master_table_name,
    )
    run_pipeline(config)


if __name__ == "__main__":
    main()
