"""
One-time migration script: PostgreSQL -> partitioned Parquet on Cloudflare R2.

This avoids a database server at query time by exporting to data-lake files:
  s3://<bucket>/<prefix>/year=<YYYY>/ticker=<TICKER>/part-*.parquet

Requirements:
  pip install duckdb

Environment:
  PG_HOST, PG_PORT, PG_DATABASE, PG_USER, PG_PASSWORD
  R2_ENDPOINT, R2_BUCKET, R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY
Optional:
  R2_REGION=auto
  R2_DATASET_PREFIX=market_data
  PG_SCHEMA=public
  PG_TABLE=historical_prices
"""

from __future__ import annotations

import os
import sys

import duckdb


def required_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Missing required env var: {name}")
    return value


def configure_r2(con: duckdb.DuckDBPyConnection) -> None:
    endpoint = required_env("R2_ENDPOINT").replace("https://", "").replace("http://", "")
    con.execute("INSTALL httpfs")
    con.execute("LOAD httpfs")
    con.execute("SET s3_url_style='path'")
    con.execute("SET s3_endpoint = ?", [endpoint])
    con.execute("SET s3_access_key_id = ?", [required_env("R2_ACCESS_KEY_ID")])
    con.execute("SET s3_secret_access_key = ?", [required_env("R2_SECRET_ACCESS_KEY")])
    con.execute("SET s3_region = ?", [os.getenv("R2_REGION", "auto")])
    con.execute("SET s3_use_ssl = true")


def migrate() -> None:
    pg_host = required_env("PG_HOST")
    pg_port = os.getenv("PG_PORT", "5432")
    pg_db = required_env("PG_DATABASE")
    pg_user = required_env("PG_USER")
    pg_password = required_env("PG_PASSWORD")
    pg_schema = os.getenv("PG_SCHEMA", "public")
    pg_table = os.getenv("PG_TABLE", "historical_prices")

    bucket = required_env("R2_BUCKET")
    prefix = os.getenv("R2_DATASET_PREFIX", "market_data").strip("/")
    destination = f"s3://{bucket}/{prefix}"

    con = duckdb.connect(database=":memory:")
    con.execute("SET threads = 4")
    con.execute("SET temp_directory = './.duckdb_tmp'")

    con.execute("INSTALL postgres")
    con.execute("LOAD postgres")
    configure_r2(con)

    dsn = (
        f"host={pg_host} port={pg_port} dbname={pg_db} "
        f"user={pg_user} password={pg_password}"
    )
    con.execute(f"ATTACH '{dsn}' AS pg_src (TYPE postgres)")

    source_relation = f"pg_src.{pg_schema}.{pg_table}"

    # Export partitioned Parquet in one pass. Existing files are preserved by default.
    export_sql = f"""
    COPY (
        SELECT
            upper(trim(ticker))::VARCHAR AS ticker,
            date::TIMESTAMP AS date,
            open::DOUBLE AS open,
            high::DOUBLE AS high,
            low::DOUBLE AS low,
            close::DOUBLE AS close,
            volume::BIGINT AS volume,
            COALESCE(adj_close, close)::DOUBLE AS adj_close,
            EXTRACT(year FROM date)::INTEGER AS year
        FROM {source_relation}
        WHERE ticker IS NOT NULL
          AND date IS NOT NULL
          AND open IS NOT NULL
          AND high IS NOT NULL
          AND low IS NOT NULL
          AND close IS NOT NULL
    )
    TO '{destination}'
    (
        FORMAT PARQUET,
        PARTITION_BY (year, ticker),
        ROW_GROUP_SIZE 200000,
        COMPRESSION ZSTD,
        PER_THREAD_OUTPUT 1
    )
    """
    con.execute(export_sql)
    con.close()
    print(f"Migration complete: {destination}/year=*/ticker=*")


if __name__ == "__main__":
    try:
        migrate()
    except Exception as exc:
        print(f"Migration failed: {exc}", file=sys.stderr)
        raise

