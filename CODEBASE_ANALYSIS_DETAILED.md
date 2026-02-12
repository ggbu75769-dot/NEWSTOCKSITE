# 코드베이스 상세 분석 (Detailed)

작성일: 2026-02-12  
분석 범위: `app/`, `components/`, `lib/`, `tests/`, 루트 Python/SQL/운영 스크립트

## 1. 프로젝트 개요
- 프로젝트 성격: Next.js 기반 웹 앱 + Python 기반 데이터 파이프라인 혼합 저장소
- 현재 공존 중인 아키텍처:
  - 웹 서비스: Supabase(Postgres) 기반 인증/조회
  - 데이터 엔진: R2 + DuckDB 기반 서버리스 분석 파이프라인
  - 보조 트랙: 관계형 ETL 실험 스크립트(`relational_*`, `kospi_full_market_etl.py`)도 존재

## 2. 디렉터리/파일 책임
- 프론트/서버 라우트:
  - `app/page.tsx`: 메인 페이지, `daily_rankings_public` 조회
  - `app/login/page.tsx`, `app/dashboard/page.tsx`: 인증/대시보드
  - `app/api/search/route.ts`: 검색 API
  - `app/auth/callback/route.ts`: OAuth 콜백 및 `profiles` upsert
- UI 컴포넌트:
  - `components/HomeView.tsx`, `components/LoginView.tsx`, `components/DashboardView.tsx` 등
- i18n:
  - `app/i18n/client.ts`: ko/en 리소스 인라인 정의
- Supabase 연동:
  - `lib/supabase/server.ts`, `lib/supabase/client.ts`, `lib/searchStock.ts`
- DB 스키마:
  - `supabase.sql`: RLS, 정책, 뷰, 함수(RPC) 포함
- 데이터 파이프라인(R2/DuckDB):
  - `run_data_pipeline.py`: 오케스트레이션
  - `daily_eod_update.py`: 증분 수집/업로드/리포트
  - `duckdb_r2_analytics.py`: 분석 레이어
  - `postgres_to_r2_parquet.py`: 초기 마이그레이션
  - `purge_r2_dataset.py`: R2 데이터셋 삭제
- 운영 문서/스크립트:
  - `R2_DUCKDB_SETUP.md`, `register_daily_tasks.ps1`

## 3. 웹 애플리케이션 분석
### 3.1 데이터 접근 패턴
- 홈(`app/page.tsx`)은 서버 컴포넌트에서 Supabase 뷰 `daily_rankings_public`을 조회.
- 조회 실패/빈 결과 시 하드코딩 fallback을 사용.
- 검색 API(`app/api/search/route.ts`)는 RPC `search_stock_public` 호출.

### 3.2 인증/세션
- `app/auth/callback/route.ts`에서 `exchangeCodeForSession` 후 `profiles` upsert 수행.
- `lib/supabase/server.ts`는 서버 컴포넌트와 라우트 핸들러용 클라이언트를 분리.

### 3.3 UI/국제화
- `HomeView`/`DashboardView` 중심으로 랜딩 + 실시간 대시보드 구조.
- `app/i18n/client.ts`에 다국어 번역을 인라인으로 보관 (규모 커지면 분리 필요).

### 3.4 테스트
- `tests/api-search.test.ts`는 `lib/searchStock.ts` 단위 테스트만 존재.
- 라우트/인증/대시보드 상태 관리에 대한 통합 테스트는 부재.

## 4. Supabase 스키마 분석 (`supabase.sql`)
- 핵심 테이블:
  - `stocks`, `historical_prices`, `daily_rankings`, `profiles`
- 보안:
  - RLS 활성화 + role 기반 policy 구성
- 읽기 계층:
  - `latest_prices` 뷰
  - `daily_rankings_public` 뷰/함수
  - `search_stock_public` RPC
- 특징:
  - 익명 사용자에는 `MYST` 마스킹 반환
  - 인증 사용자만 실제 티커 확인 가능

## 5. R2 + DuckDB 파이프라인 분석
### 5.1 오케스트레이션 (`run_data_pipeline.py`)
- 모드:
  - `all`, `serverless`, `initial_load`, `daily_update`, `analytics`
- 환경 로딩:
  - `.env.r2.local` -> `.env.local` -> `.env`
- 역할:
  - 초기 적재/증분 적재/분석 실행 통합

### 5.2 증분 적재 (`daily_eod_update.py`)
- 티커 소스:
  - 기본 `VS_TICKERS`
  - `VS_KOSPI_ALL=true`면 KOSPI 전체 동적 조회
- 데이터 소스:
  - KR 6자리 종목: FinanceDataReader
  - 그 외: yfinance
- 저장 전략(최신 변경 반영):
  - 연단위 compaction(`year/ticker`당 1파일 유지 방향)
  - 업로드 전 prefix 삭제 후 재업로드
- 성능:
  - `ThreadPoolExecutor` 병렬 처리
  - 퍼센트 진행률/ETA 출력
- 산출물:
  - `logs/etl_result_*.json` 리포트

### 5.3 분석 레이어 (`duckdb_r2_analytics.py`)
- DuckDB `httpfs`로 R2 직접 쿼리
- Pandas/Polars 반환 지원
- RSI/MACD 계산 유틸 제공
- SQL 템플릿 포함(52주 고저, 모멘텀 등)

### 5.4 초기 이관 (`postgres_to_r2_parquet.py`)
- DuckDB postgres extension으로 소스 Postgres attach 후 COPY export
- 파티션: `PARTITION_BY (year, ticker)`

### 5.5 데이터 정리 (`purge_r2_dataset.py`)
- 지정 prefix 전체 삭제 (파괴적 명령)
- `--yes` 강제 플래그 있음

## 6. 현재 코드 상태의 주요 이슈/리스크
### 6.1 인코딩(문자 깨짐) 이슈
- 일부 Python/PowerShell 출력 문자열이 깨져 보임:
  - `run_data_pipeline.py`
  - `register_daily_tasks.ps1`
- 기능 자체보다 운영 가독성/유지보수성에 영향.

### 6.2 이중 아키텍처 공존
- Supabase 기반 웹 + R2/DuckDB 기반 파이프라인 + 관계형 보조 스크립트가 함께 있어 온보딩 복잡도 상승.
- 실제 운영 경로를 문서에서 단일화할 필요.

### 6.3 파괴적 작업의 보호장치
- `purge_r2_dataset.py`는 `--yes`는 있으나, bucket/prefix 재확인 인터랙션은 없음.
- 운영 중 실수 시 데이터 전량 삭제 가능.

### 6.4 테스트 커버리지 부족
- 프론트 라우트, 인증 콜백, 파이프라인 핵심 함수에 대한 자동 테스트 부족.
- ETL 로직 변경 시 회귀 위험 높음.

### 6.5 비용/성능 관리 포인트
- 연단위 compaction 전략으로 개선됐지만, 초기 백필 시 네트워크/API/연산 시간이 큼.
- `VS_MAX_WORKERS`, `VS_REQUEST_SLEEP` 튜닝 가이드 필요.

## 7. 운영 플로우(권장)
1. `.env.r2.local`에 R2 관련 변수 설정
2. 필요 시 초기 R2 정리: `python purge_r2_dataset.py --yes`
3. 증분/백필 실행: `python run_data_pipeline.py --mode daily_update`
4. 분석 실행: `python run_data_pipeline.py --mode analytics`
5. 스케줄링: `register_daily_tasks.ps1`

## 8. 개선 권장사항 (우선순위)
### P1
- 인코딩 깨짐 파일 UTF-8 정리 (`run_data_pipeline.py`, `register_daily_tasks.ps1`, 일부 문서)
- ETL 실패 재시도 정책/에러 분류 강화 (네트워크, 공급자 rate-limit, 데이터 품질)

### P2
- 파이프라인 핵심 테스트 추가:
  - 티커 분기(kr/us)
  - 파일 파티션 생성/삭제
  - 요약 리포트 생성
- 파괴적 명령에 안전장치 추가:
  - `--bucket`, `--prefix` 이중 확인
  - dry-run 모드

### P3
- i18n 리소스를 파일 분리(`app/i18n/locales/*.json`)
- 아키텍처 문서에서 운영 경로를 `R2 + DuckDB` 단일 기준으로 명확화

## 9. 분석 결론
- 현재 저장소는 “웹 서비스 + 데이터 플랫폼”이 결합된 상태이며, 기능은 충분히 동작 가능한 수준.
- 다만 운영 관점에서는 인코딩 정리, 테스트 보강, 경로 단순화가 필요.
- 무료 티어 목표에 맞춰 최근 적용한 연단위 compaction 방향은 타당함.

