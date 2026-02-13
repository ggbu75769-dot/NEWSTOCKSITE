# AI 추천 시스템 데이터 연동 문서 (실데이터 반영)

이 문서는 `Visual Stock`에서 추천 UI가 **mock 데이터가 아닌 Tier-1 실데이터**를 사용하도록 반영된 현재 구조를 설명합니다.

## 1) 현재 상태 요약

- 완료: `tier1_buy_candidates_*.csv` -> API -> UI 연동
- 완료: 홈/대시보드/추천 페이지의 mock 의존 제거
- 결과: 추천 목록은 최신 Tier-1 후보 CSV를 기준으로 렌더링

## 2) 실데이터 소스

### 2-1. 원천 데이터
- 입력 CSV: `data/*.csv`
- 생성 스크립트: `build_tier1_features.py`

### 2-2. 추천 후보 산출물
- 최종 후보 파일: `logs/tier1_buy_candidates_*.csv`
- 최신 파일 자동 선택 규칙:
  - 파일명 패턴 `tier1_buy_candidates_YYYYMMDD_HHMMSS.csv`
  - 타임스탬프가 가장 큰 파일 1개를 사용

## 3) 백엔드 연동 구조

### 3-1. API Route
- 파일: `app/api/recommendations/route.ts`
- 엔드포인트: `GET /api/recommendations`
- Query:
  - `lang`: `ko | en` (기본 `ko`)
  - `limit`: 양수 정수 (선택)

### 3-2. 서비스 로직
- 파일: `lib/recommendations/tier1.ts`
- 역할:
  1. `logs/`에서 최신 `tier1_buy_candidates_*.csv` 탐색
  2. CSV 파싱 후 후보 행 정렬/매핑
  3. `latest_prices` 테이블에서 `ticker -> name` 보강
  4. UI 모델(`StockRecommendation`)로 변환 후 반환

### 3-3. 반환 타입
- 파일: `lib/recommendations/types.ts`

```ts
export type StockRecommendation = {
  id: string;
  symbol: string;
  name: string;
  currentPrice: number;
  aiScore: number;
  fluctuationRate: number;
  reasoning: string;
};
```

## 4) 실데이터 -> UI 필드 매핑

CSV 기준 핵심 매핑:
- `symbol` <- `ticker`
- `currentPrice` <- `close`
- `fluctuationRate` <- `ret_1d * 100`
- `aiScore` <- `tier1_composite_score` 정규화 점수

### 4-1. AI 점수 정규화
- 입력: `tier1_composite_score`
- 구간: 최신 후보 파일 내 min/max 기준
- 출력: 70~99 스케일로 선형 변환 후 반올림
- 목적: UI에서 직관적인 0~100형 점수로 표현

### 4-2. 추천 근거(reasoning)
- 데이터 사용 컬럼:
  - `breakout_dist_20`
  - `rvol20`
  - `ret_5d`
  - `natr14`
- `lang`에 따라 한국어/영어 문장으로 동적 생성

## 5) 프론트 연동 지점

### 5-1. 클라이언트 fetch 유틸
- 파일: `lib/recommendations/client.ts`
- 동작: `/api/recommendations` 호출 후 `items` 반환

### 5-2. UI 적용 컴포넌트
- `components/HomeView.tsx`
  - Top 3: `fetchRecommendations({ language, limit: 3 })`
- `components/DashboardView.tsx`
  - Top 3: `fetchRecommendations({ language, limit: 3 })`
- `components/RecommendationsView.tsx`
  - 전체: `fetchRecommendations({ language })`

## 6) DB 보강 로직

- 테이블: `latest_prices`
- 조회 컬럼: `ticker, name`
- 목적: CSV에 없는 종목명을 UI에 표기
- 실패 시 fallback: `name = ticker`

## 7) 장애/예외 처리

- 최신 후보 CSV가 없거나 파싱 실패 시:
  - API는 빈 배열 `items: []` 반환
- `limit` 파라미터가 비정상 값이면:
  - HTTP 400 반환
- 내부 예외 발생 시:
  - HTTP 500 반환

## 8) 검증 결과

반영 후 아래 검증 통과:
- `npm run typecheck`
- `npm run build`

참고: `/dashboard`, `/login`, `/recommendations`의 `cookies` 기반 동적 렌더 경고는 기존 인증 구조로 인한 Next.js 동작 메시지이며, 이번 추천 데이터 연동 기능과는 별개입니다.

## 9) 운영 절차

1. 최신 시장 데이터 수집 (`data/*.csv` 갱신)
2. Tier-1 생성 실행
3. `logs/tier1_buy_candidates_*.csv` 생성 확인
4. UI는 별도 배포 없이 최신 파일 기준으로 자동 반영

실행 예시:
```bash
python build_tier1_features.py --data-dir data --out-dir logs --top-n 20 --min-history 20
```

## 10) 현재 결론

추천 UI의 데이터 소스는 더 이상 mock이 아니며, 현재는 **Tier-1 실데이터 CSV 기반 API 응답**을 사용합니다.
