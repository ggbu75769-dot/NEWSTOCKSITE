# DuckDB + Cloudflare R2 Configuration Guide

## 1) Bucket Layout (Recommended)
Use Hive-style partitions for pruning and low I/O:

`s3://<bucket>/market_data/year=<YYYY>/ticker=<TICKER>/part-*.parquet`

Why:
- `year` partition reduces scan scope for long lookbacks.
- `ticker` partition makes single-name reads fast.
- Daily appends create new `part-*.parquet` files in existing `year/ticker` partitions.

## 2) Cloudflare R2 Setup
1. Create bucket (example: `stock-lake`).
2. Create API token/key pair with object read+write permission for this bucket.
3. Note your S3 endpoint:
   `https://<accountid>.r2.cloudflarestorage.com`

## 3) Required Environment Variables
```powershell
$env:R2_ENDPOINT="https://<accountid>.r2.cloudflarestorage.com"
$env:R2_BUCKET="stock-lake"
$env:R2_ACCESS_KEY_ID="<access-key-id>"
$env:R2_SECRET_ACCESS_KEY="<secret-access-key>"
```

또는 프로젝트 루트의 `.env.r2.local`에 저장 후 사용:
```text
R2_ENDPOINT=...
R2_BUCKET=...
R2_ACCESS_KEY_ID=...
R2_SECRET_ACCESS_KEY=...
```

Optional:
```powershell
$env:R2_REGION="auto"
$env:R2_DATASET_PREFIX="market_data"
$env:VS_TICKERS="AAPL,MSFT,NVDA,AMZN,GOOGL"
$env:VS_KOSPI_ALL="true"
```

For migration from PostgreSQL:
```powershell
$env:PG_HOST="<host>"
$env:PG_PORT="5432"
$env:PG_DATABASE="<db>"
$env:PG_USER="<user>"
$env:PG_PASSWORD="<password>"
$env:PG_SCHEMA="public"
$env:PG_TABLE="historical_prices"
```

## 4) Install Dependencies
```bash
pip install duckdb boto3 pandas yfinance pyarrow polars
```

## 5) Migration (One-time)
```bash
python postgres_to_r2_parquet.py
```

## 6) Daily Append (Incremental)
```bash
python daily_eod_update.py
```

## 7) Analytics Usage
```python
from duckdb_r2_analytics import StockDataAnalytic

engine = StockDataAnalytic()
df = engine.get_prices("AAPL", "2024-01-01", "2025-01-01")
ind = engine.with_indicators_pandas("AAPL", "2024-01-01", "2025-01-01")
engine.close()
```

## 8) Master Automation Script
단일 스크립트로 전체 실행 가능:

```bash
python run_data_pipeline.py --mode all
```

PostgreSQL 없이 R2 전용 실행:
```bash
python run_data_pipeline.py --mode serverless
```

모드별 실행:
```bash
python run_data_pipeline.py --mode initial_load
python run_data_pipeline.py --mode daily_update --tickers AAPL,MSFT,NVDA
python run_data_pipeline.py --mode analytics --analytics-query high_low_52_week
python run_data_pipeline.py --mode analytics --analytics-query from_file
```

## 9) Zero-Cost Optimization Notes
- Keep compute local (DuckDB in-memory, no DB server).
- Prefer query-time partition pruning (`year`, `ticker` filters).
- Use ZSTD compression and larger row groups to reduce object size.
- Keep object count reasonable: one file per ticker/day is simple; periodically compact old partitions if object count grows too high.

## 10) Windows Task Scheduler (자동 실행)
일일 증분 ETL + 분석 작업 등록:

```powershell
.\register_daily_tasks.ps1 `
  -TaskPrefix "OpenCode" `
  -PythonExe "python" `
  -Tickers "AAPL,MSFT,NVDA,AMZN,GOOGL" `
  -DailyTime "18:30" `
  -AnalyticsTime "18:40" `
  -AnalyticsQuery "high_low_52_week"
```

분석 작업 없이 ETL만 등록:

```powershell
.\register_daily_tasks.ps1 -CreateAnalyticsTask:$false
```

즉시 테스트 실행:

```powershell
schtasks /Run /TN "OpenCode_DailyUpdate"
schtasks /Run /TN "OpenCode_Analytics"
```

작업 삭제:

```powershell
schtasks /Delete /F /TN "OpenCode_DailyUpdate"
schtasks /Delete /F /TN "OpenCode_Analytics"
```
