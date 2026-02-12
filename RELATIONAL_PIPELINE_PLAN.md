# Historical Stock Data Pipeline (PostgreSQL) 실행 계획

## 1) 목표
- 일봉 주가(OHLCV + adj_close)와 파생 지표(daily_return, rsi_14, sma_20/60/120)를 PostgreSQL에 저장
- `(symbol, trade_date)` 복합 PK로 중복 방지
- `trade_date` 인덱스로 시계열 조회 성능 확보
- 배치 업서트와 검증 레이어로 안정적인 대량 적재

## 2) 구성 파일
- 스키마: `relational_stock_schema.sql`
- ETL 본체: `relational_stock_etl.py`
- 마스터 실행: `run_relational_pipeline.py`
- 의존성: `requirements_relational.txt`

## 3) 사전 설정
환경변수:
```powershell
$env:PG_HOST="127.0.0.1"
$env:PG_PORT="5432"
$env:PG_DATABASE="stocks"
$env:PG_USER="postgres"
$env:PG_PASSWORD="your_password"
$env:VS_TICKERS="AAPL,TSLA,MSFT,NVDA,AMZN"
```

패키지 설치:
```bash
pip install -r requirements_relational.txt
```

## 4) 실행 시나리오
초기 부트스트랩(스키마 생성 + 전체 적재):
```bash
python run_relational_pipeline.py --mode bootstrap_full --start-date 2016-01-01
```

일일 증분 적재(운영):
```bash
python run_relational_pipeline.py --mode incremental
```

스키마만 적용:
```bash
python run_relational_pipeline.py --mode schema_only
```

## 5) ETL 처리 로직
1. 심볼별 데이터 다운로드(yfinance)
2. 필수 컬럼/결측 검증
3. `adj_close` 기준 파생 지표 계산
   - `daily_return = pct_change(adj_close) * 100`
   - `rsi_14`, `sma_20`, `sma_60`, `sma_120`
4. `DECIMAL(18,4)` 정밀도로 변환
5. 배치 업서트(`ON CONFLICT (symbol, trade_date) DO UPDATE`)

## 6) 운영 권장사항
- 스케줄: 영업일 장마감 이후 1회(`incremental`)
- 배치 크기: 기본 1000, 부하에 따라 조정(`--batch-size`)
- 장애 대응:
  - API 실패 심볼은 로그로 남기고 다음 심볼 계속 처리
  - 결측/파싱 실패 행은 커밋 전 제외

