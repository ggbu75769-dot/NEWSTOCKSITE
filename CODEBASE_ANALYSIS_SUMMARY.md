# 코드베이스 요약 분석 (Summary)

## 한 줄 요약
- 현재 프로젝트는 **Supabase 웹앱**과 **R2+DuckDB 데이터 파이프라인**이 공존하는 구조이며, 운영은 R2+DuckDB 중심으로 수렴 중입니다.

## 현재 구조
1. 웹 서비스 (Next.js + Supabase)
- 홈/로그인/대시보드/검색 API 제공
- Supabase RLS, 뷰, RPC(`search_stock_public`) 사용

2. 데이터 파이프라인 (Python)
- `run_data_pipeline.py`: 통합 실행
- `daily_eod_update.py`: 증분 ETL, KOSPI 전체 동적 수집, 진행률/리포트 제공
- `duckdb_r2_analytics.py`: R2 Parquet 직접 분석
- `postgres_to_r2_parquet.py`: 초기 이관
- `purge_r2_dataset.py`: R2 데이터 정리

## 강점
- 서버리스 분석 경로(R2 + DuckDB)가 구축됨
- KOSPI 전체 자동 수집 가능
- ETL 퍼센트 진행률/ETA/리포트 JSON 제공
- 연단위 compaction 전략으로 비용 리스크 완화

## 주요 리스크
1. 인코딩 깨짐 문자열 존재
- 일부 파일 로그 메시지 가독성 저하

2. 구조 복잡도
- 관계형 보조 스크립트와 서버리스 스크립트가 함께 있어 경로 혼선 가능

3. 테스트 부족
- 핵심 ETL/라우트 회귀 테스트가 충분하지 않음

## 권장 운영 경로 (현시점)
1. `.env.r2.local` 관리
2. `run_data_pipeline.py --mode daily_update` 중심 운영
3. 필요 시 `--mode analytics` 분리 실행
4. 주기적으로 ETL 리포트(`logs/etl_result_*.json`) 모니터링

## 즉시 개선 우선순위
1. 인코딩 UTF-8 정리
2. ETL/분석 경로 테스트 추가
3. 파괴적 스크립트(`purge_r2_dataset.py`)에 dry-run/이중확인 추가

상세 내용은 `CODEBASE_ANALYSIS_DETAILED.md` 참고.

