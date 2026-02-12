"""
DuckDB analytics layer for partitioned Parquet data on Cloudflare R2.

Schema:
  ticker      VARCHAR
  date        TIMESTAMP
  open        DOUBLE
  high        DOUBLE
  low         DOUBLE
  close       DOUBLE
  volume      BIGINT
  adj_close   DOUBLE

Default partition layout (Hive-style):
  s3://<bucket>/<prefix>/year=<YYYY>/ticker=<TICKER>/part-*.parquet
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Dict, Iterable, Optional

import duckdb
import pandas as pd

try:
    import polars as pl
except ImportError:  # pragma: no cover - optional dependency
    pl = None


@dataclass(frozen=True)
class R2Config:
    endpoint: str
    bucket: str
    access_key_id: str
    secret_access_key: str
    region: str = "auto"
    dataset_prefix: str = "market_data"
    use_ssl: bool = True
    session_token: Optional[str] = None

    @property
    def endpoint_no_scheme(self) -> str:
        return self.endpoint.replace("https://", "").replace("http://", "")


class StockDataAnalytic:
    def __init__(
        self,
        config: Optional[R2Config] = None,
        db_path: str = ":memory:",
        temp_directory: Optional[str] = None,
        threads: int = max((os.cpu_count() or 4) - 1, 1),
    ) -> None:
        self.config = config or self._from_env()
        self.con = duckdb.connect(database=db_path)
        self._bootstrap(temp_directory=temp_directory, threads=threads)

    @staticmethod
    def _from_env() -> R2Config:
        required = {
            "R2_ENDPOINT": os.getenv("R2_ENDPOINT"),
            "R2_BUCKET": os.getenv("R2_BUCKET"),
            "R2_ACCESS_KEY_ID": os.getenv("R2_ACCESS_KEY_ID"),
            "R2_SECRET_ACCESS_KEY": os.getenv("R2_SECRET_ACCESS_KEY"),
        }
        missing = [k for k, v in required.items() if not v]
        if missing:
            raise RuntimeError(f"Missing required env vars: {', '.join(missing)}")
        return R2Config(
            endpoint=required["R2_ENDPOINT"] or "",
            bucket=required["R2_BUCKET"] or "",
            access_key_id=required["R2_ACCESS_KEY_ID"] or "",
            secret_access_key=required["R2_SECRET_ACCESS_KEY"] or "",
            region=os.getenv("R2_REGION", "auto"),
            dataset_prefix=os.getenv("R2_DATASET_PREFIX", "market_data"),
            use_ssl=(os.getenv("R2_USE_SSL", "true").lower() == "true"),
            session_token=os.getenv("R2_SESSION_TOKEN"),
        )

    def _bootstrap(self, temp_directory: Optional[str], threads: int) -> None:
        if temp_directory:
            os.makedirs(temp_directory, exist_ok=True)
            self.con.execute(f"SET temp_directory = '{temp_directory}'")
        self.con.execute(f"SET threads = {threads}")
        self.con.execute("INSTALL httpfs")
        self.con.execute("LOAD httpfs")
        self.con.execute("SET enable_http_metadata_cache = true")
        self.con.execute("SET s3_url_style = 'path'")
        self.con.execute("SET s3_endpoint = ?", [self.config.endpoint_no_scheme])
        self.con.execute("SET s3_access_key_id = ?", [self.config.access_key_id])
        self.con.execute("SET s3_secret_access_key = ?", [self.config.secret_access_key])
        self.con.execute("SET s3_region = ?", [self.config.region])
        self.con.execute("SET s3_use_ssl = ?", [str(self.config.use_ssl).lower()])
        if self.config.session_token:
            self.con.execute("SET s3_session_token = ?", [self.config.session_token])

    @property
    def data_glob(self) -> str:
        return (
            f"s3://{self.config.bucket}/{self.config.dataset_prefix}/"
            "year=*/ticker=*/part-*.parquet"
        )

    def sql(self, query: str, params: Optional[Iterable[Any]] = None) -> pd.DataFrame:
        if params is None:
            return self.con.sql(query).to_df()
        return self.con.execute(query, list(params)).df()

    def to_pandas(self, query: str, params: Optional[Iterable[Any]] = None) -> pd.DataFrame:
        if params is None:
            return self.con.sql(query).to_df()
        return self.con.execute(query, list(params)).df()

    def to_polars(self, query: str, params: Optional[Iterable[Any]] = None):
        if pl is None:
            raise RuntimeError("Polars is not installed. pip install polars")
        df = self.to_pandas(query, params=params)
        return pl.from_pandas(df)

    def get_prices(
        self,
        ticker: str,
        start_date: str,
        end_date: str,
        as_polars: bool = False,
    ):
        query = f"""
        SELECT ticker, date, open, high, low, close, volume, adj_close
        FROM read_parquet('{self.data_glob}', hive_partitioning=1)
        WHERE ticker = ?
          AND date >= ?::TIMESTAMP
          AND date < ?::TIMESTAMP
        ORDER BY date
        """
        if as_polars:
            return self.to_polars(query, params=[ticker, start_date, end_date])
        return self.to_pandas(query, params=[ticker, start_date, end_date])

    def with_indicators_pandas(self, ticker: str, start_date: str, end_date: str) -> pd.DataFrame:
        df = self.get_prices(ticker=ticker, start_date=start_date, end_date=end_date)
        if df.empty:
            return df
        close = df["close"]
        delta = close.diff()
        gains = delta.clip(lower=0.0)
        losses = (-delta).clip(lower=0.0)
        avg_gain = gains.rolling(14).mean()
        avg_loss = losses.rolling(14).mean().replace(0, pd.NA)
        rs = avg_gain / avg_loss
        df["rsi_14"] = 100 - (100 / (1 + rs))

        ema_fast = close.ewm(span=12, adjust=False).mean()
        ema_slow = close.ewm(span=26, adjust=False).mean()
        df["macd"] = ema_fast - ema_slow
        df["macd_signal"] = df["macd"].ewm(span=9, adjust=False).mean()
        df["macd_hist"] = df["macd"] - df["macd_signal"]
        return df

    def with_indicators_polars(self, ticker: str, start_date: str, end_date: str):
        if pl is None:
            raise RuntimeError("Polars is not installed. pip install polars")
        df = self.get_prices(ticker=ticker, start_date=start_date, end_date=end_date, as_polars=True)
        if df.is_empty():
            return df
        return df.with_columns(
            [
                pl.col("close").ewm_mean(span=12).alias("ema_12"),
                pl.col("close").ewm_mean(span=26).alias("ema_26"),
            ]
        ).with_columns(
            [
                (pl.col("ema_12") - pl.col("ema_26")).alias("macd"),
                pl.col("close").diff().alias("delta"),
            ]
        ).with_columns(
            [
                pl.when(pl.col("delta") > 0).then(pl.col("delta")).otherwise(0.0).rolling_mean(14).alias("avg_gain"),
                pl.when(pl.col("delta") < 0).then(-pl.col("delta")).otherwise(0.0).rolling_mean(14).alias("avg_loss"),
            ]
        ).with_columns(
            [
                (100 - (100 / (1 + (pl.col("avg_gain") / pl.col("avg_loss"))))).alias("rsi_14"),
                pl.col("macd").ewm_mean(span=9).alias("macd_signal"),
            ]
        ).with_columns((pl.col("macd") - pl.col("macd_signal")).alias("macd_hist")).drop(
            ["ema_12", "ema_26", "delta", "avg_gain", "avg_loss"]
        )

    @staticmethod
    def sql_templates(data_glob: str) -> Dict[str, str]:
        return {
            "ohlcv_slice": f"""
                SELECT ticker, date, open, high, low, close, volume, adj_close
                FROM read_parquet('{data_glob}', hive_partitioning=1)
                WHERE ticker = ?
                  AND date BETWEEN ?::TIMESTAMP AND ?::TIMESTAMP
                ORDER BY date
            """,
            "high_low_52_week": f"""
                WITH last_year AS (
                    SELECT ticker, date, high, low
                    FROM read_parquet('{data_glob}', hive_partitioning=1)
                    WHERE date >= current_date - INTERVAL 365 DAY
                )
                SELECT
                    ticker,
                    max(high) AS high_52w,
                    min(low) AS low_52w
                FROM last_year
                GROUP BY ticker
                ORDER BY ticker
            """,
            "cross_section_momentum": f"""
                WITH rets AS (
                    SELECT
                        ticker,
                        date,
                        close / lag(close, 20) OVER (PARTITION BY ticker ORDER BY date) - 1 AS ret_1m
                    FROM read_parquet('{data_glob}', hive_partitioning=1)
                )
                SELECT ticker, date, ret_1m
                FROM rets
                WHERE ret_1m IS NOT NULL
                QUALIFY row_number() OVER (PARTITION BY ticker ORDER BY date DESC) = 1
                ORDER BY ret_1m DESC
            """,
        }

    def close(self) -> None:
        self.con.close()
