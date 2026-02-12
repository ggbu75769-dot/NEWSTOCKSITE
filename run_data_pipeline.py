"""
R2 + DuckDB master pipeline.

Modes:
- all: postgres -> r2 initial load + daily update + analytics
- serverless: daily update + analytics (no postgres)
- initial_load: postgres -> r2 initial load only
- daily_update: incremental append only
- analytics: run analytics query only
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path
from typing import Dict, List

from dotenv import load_dotenv

from daily_eod_update import resolve_tickers, run_daily_update
from duckdb_r2_analytics import StockDataAnalytic
from postgres_to_r2_parquet import migrate


ROOT = Path(__file__).resolve().parent
SQL_TEMPLATE_FILE = ROOT / "sql_templates_duckdb.sql"


def _required_env(keys: List[str]) -> List[str]:
    return [k for k in keys if not os.getenv(k)]


def validate_env(mode: str) -> None:
    r2_required = ["R2_ENDPOINT", "R2_BUCKET", "R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY"]
    pg_required = ["PG_HOST", "PG_DATABASE", "PG_USER", "PG_PASSWORD"]

    missing = set(_required_env(r2_required))
    if mode in {"all", "initial_load"}:
        missing.update(_required_env(pg_required))

    if missing:
        raise RuntimeError(
            "필수 환경변수 누락: "
            + ", ".join(sorted(missing))
            + "\nR2_DUCKDB_SETUP.md를 확인해 먼저 설정하세요."
        )


def run_initial_load() -> None:
    print("[1/3] 초기 적재 시작: PostgreSQL -> R2")
    migrate()
    print("[1/3] 초기 적재 완료")


def run_incremental_update(tickers: List[str]) -> Dict[str, int]:
    print("[2/3] 일일 증분 ETL 시작")
    result = run_daily_update(tickers=tickers)
    print(f"[2/3] 일일 증분 ETL 완료 | 총 적재 행 수: {sum(result.values())}")
    return result


def _split_sql_statements(script: str) -> List[str]:
    statements: List[str] = []
    current: List[str] = []
    in_single_quote = False
    for ch in script:
        if ch == "'":
            in_single_quote = not in_single_quote
        if ch == ";" and not in_single_quote:
            stmt = "".join(current).strip()
            if stmt:
                statements.append(stmt)
            current = []
            continue
        current.append(ch)
    tail = "".join(current).strip()
    if tail:
        statements.append(tail)
    return statements


def run_analytics(query_name: str = "high_low_52_week", limit: int = 20) -> None:
    print("[3/3] 분석 실행 시작")
    engine = StockDataAnalytic()
    try:
        templates = engine.sql_templates(engine.data_glob)
        if query_name in templates:
            df = engine.to_pandas(templates[query_name])
            print(f"[3/3] 템플릿 쿼리 결과 상위 {limit}건")
            print(df.head(limit).to_string(index=False))
            return

        if query_name == "from_file":
            if not SQL_TEMPLATE_FILE.exists():
                raise RuntimeError(f"SQL 템플릿 파일 없음: {SQL_TEMPLATE_FILE}")
            script = SQL_TEMPLATE_FILE.read_text(encoding="utf-8")
            statements = _split_sql_statements(script)
            last_df = None
            for stmt in statements:
                if "SELECT" in stmt.upper() or "WITH " in stmt.upper():
                    last_df = engine.to_pandas(stmt)
                else:
                    engine.con.execute(stmt)
            if last_df is not None:
                print(f"[3/3] 파일 기반 쿼리 결과 상위 {limit}건")
                print(last_df.head(limit).to_string(index=False))
            else:
                print("[3/3] 파일 기반 SQL 실행 완료 (조회 결과 없음)")
            return

        available = ", ".join(sorted(list(templates.keys()) + ["from_file"]))
        raise RuntimeError(f"지원하지 않는 analytics query: {query_name} | available: {available}")
    finally:
        engine.close()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="R2 + DuckDB 파이프라인")
    parser.add_argument(
        "--mode",
        choices=["all", "serverless", "initial_load", "daily_update", "analytics"],
        default="serverless",
    )
    parser.add_argument("--tickers", default=os.getenv("VS_TICKERS", "AAPL,MSFT,NVDA,AMZN,GOOGL"))
    parser.add_argument("--analytics-query", default="high_low_52_week")
    parser.add_argument("--analytics-limit", type=int, default=20)
    return parser.parse_args()


def main() -> None:
    # Load env files in priority order:
    # 1) .env.r2.local (R2 pipeline-specific)
    # 2) .env.local
    # 3) .env
    load_dotenv(ROOT / ".env.r2.local", override=False)
    load_dotenv(ROOT / ".env.local", override=False)
    load_dotenv(ROOT / ".env", override=False)

    args = parse_args()
    validate_env(args.mode)

    tickers = resolve_tickers(args.tickers.split(","))
    print(f"[PIPELINE] mode={args.mode} ticker_count={len(tickers)}")

    if args.mode == "all":
        run_initial_load()
        run_incremental_update(tickers)
        run_analytics(query_name=args.analytics_query, limit=args.analytics_limit)
    elif args.mode == "serverless":
        run_incremental_update(tickers)
        run_analytics(query_name=args.analytics_query, limit=args.analytics_limit)
    elif args.mode == "initial_load":
        run_initial_load()
    elif args.mode == "daily_update":
        run_incremental_update(tickers)
    elif args.mode == "analytics":
        run_analytics(query_name=args.analytics_query, limit=args.analytics_limit)
    else:
        raise RuntimeError(f"알 수 없는 mode: {args.mode}")


if __name__ == "__main__":
    main()
