"""
관계형 주식 데이터 파이프라인 마스터 스크립트

기능:
1) 스키마 적용(relational_stock_schema.sql)
2) 초기 전체 적재(full load)
3) 일일 증분 적재(incremental)
"""

from __future__ import annotations

import argparse
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import List

from psycopg2 import connect

from relational_stock_etl import run_etl


ROOT = Path(__file__).resolve().parent
SCHEMA_SQL = ROOT / "relational_stock_schema.sql"


def env_required(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"필수 환경변수 누락: {name}")
    return value


def validate_env() -> None:
    required = ["PG_HOST", "PG_DATABASE", "PG_USER", "PG_PASSWORD"]
    missing = [k for k in required if not os.getenv(k)]
    if missing:
        raise RuntimeError(f"필수 환경변수 누락: {', '.join(missing)}")


def db_connect():
    return connect(
        host=env_required("PG_HOST"),
        port=os.getenv("PG_PORT", "5432"),
        dbname=env_required("PG_DATABASE"),
        user=env_required("PG_USER"),
        password=env_required("PG_PASSWORD"),
    )


def apply_schema() -> None:
    if not SCHEMA_SQL.exists():
        raise RuntimeError(f"스키마 파일을 찾을 수 없습니다: {SCHEMA_SQL}")

    sql = SCHEMA_SQL.read_text(encoding="utf-8")
    with db_connect() as conn:
        with conn.cursor() as cur:
            cur.execute(sql)
        conn.commit()
    print("[완료] 스키마 적용 완료")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="PostgreSQL stock data pipeline master")
    parser.add_argument(
        "--mode",
        choices=["bootstrap_full", "incremental", "full_only", "schema_only"],
        default="incremental",
        help=(
            "bootstrap_full: 스키마+full 적재, "
            "incremental: 스키마+증분 적재, "
            "full_only: full 적재만, "
            "schema_only: 스키마만"
        ),
    )
    parser.add_argument(
        "--symbols",
        default=os.getenv("VS_TICKERS", "AAPL,TSLA,MSFT,NVDA,AMZN"),
        help="쉼표 구분 티커 목록",
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
    validate_env()

    symbols: List[str] = [s.strip().upper() for s in args.symbols.split(",") if s.strip()]
    start_date = datetime.strptime(args.start_date, "%Y-%m-%d").date()
    end_date = datetime.strptime(args.end_date, "%Y-%m-%d").date()

    if args.mode == "schema_only":
        apply_schema()
        return

    if args.mode in {"bootstrap_full", "incremental"}:
        apply_schema()

    if args.mode in {"bootstrap_full", "full_only"}:
        run_etl(
            symbols=symbols,
            mode="full",
            full_start_date=start_date,
            end_date=end_date,
            batch_size=args.batch_size,
        )
        print("[완료] Full Load 완료")
        return

    if args.mode == "incremental":
        run_etl(
            symbols=symbols,
            mode="incremental",
            full_start_date=start_date,
            end_date=end_date,
            batch_size=args.batch_size,
        )
        print("[완료] Incremental Load 완료")
        return

    raise RuntimeError(f"알 수 없는 mode: {args.mode}")


if __name__ == "__main__":
    main()

