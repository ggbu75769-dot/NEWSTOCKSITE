# TOP5 Stock Recommendation Logic

## 1) Scope

이 문서는 현재 서비스에서 사용하는 **일자별 TOP5 추천 로직**을 설명합니다.

- 생성 로직: `build_daily_top5_recommendations.py`
- 조회 로직: `lib/recommendations/daily.ts`
- API: `app/api/recommendations/daily/route.ts`
- UI: `components/RecommendationsView.tsx`
- 자동 갱신 훅: `daily_eod_update.py`의 `run_daily_top5_refresh()`

---

## 2) End-to-End Data Flow

1. `stock_data/korean_market_10y_with_indicators.parquet`에서 입력 데이터 로드
2. `logs/indicator_combo_optimizer/*/best_logic.json`에서 최신 최적 feature/weight 로드
3. feature별 확률 매퍼(`fit_prob_mapper`) 학습
4. 지정 기간(기본 `2026-01-01` ~ 최신 거래일) 모든 종목에 대해 일자별 확률 계산
5. 일자별 확률 내림차순 정렬 후 상위 N개(기본 5개) 추출
6. `logs/daily_top5_recommendations_*.csv`로 저장
7. API가 최신 CSV를 읽어 날짜별 payload 반환
8. 추천 페이지에서 날짜 선택 후 해당 일자의 TOP5만 렌더링

---

## 3) Model Inputs

### 3.1 Price/Indicator Source

- 파일: `stock_data/korean_market_10y_with_indicators.parquet`
- 필수 컬럼:
  - `Date`, `Ticker`, `Close`
  - `best_logic.json`에 정의된 `feature_names` 컬럼들

### 3.2 Strategy Definition

- 파일: `logs/indicator_combo_optimizer/<run>/best_logic.json`
- 사용 필드:
  - `feature_names`: 사용 지표 컬럼 목록
  - `weights`: 각 지표의 가중치

최신 run 폴더를 자동 선택하며, 필요하면 `--best-logic`으로 특정 파일 고정 가능.

---

## 4) Score Calculation

현재 최종 순위는 아래 3개 신호의 가중합입니다.

1. 거래대금 신호 (높을수록 우선)
2. 1일 상승률 신호 (높을수록 우선)
3. 기존 모델 확률 신호 (`prob_up_next_day`)

기본 가중치:

- 거래대금: `0.45`
- 상승률: `0.35`
- 기존 모델: `0.20`

가중치는 실행 인자로 조정 가능:

- `--weight-turnover`
- `--weight-ret1d`
- `--weight-model`

## 4.1 Label Construction (학습용)

각 티커의 다음날 종가 기반으로:

- `NextClose = groupby(Ticker).shift(-1)`
- `TargetUp = 1 if NextClose > Close else 0`
- 학습 샘플: `NextClose`가 존재하고 `Close > 0`인 행

## 4.2 Feature-to-Probability Mapping

각 feature에 대해:

1. 유효값(`isfinite`)만 사용
2. 분위수 bin (`n_bins`, 기본 20) 생성
3. 각 bin의 상승확률 추정 + 베이지안 스무딩

공식:

- `base = mean(TargetUp)`
- `prob_bin = (ups + alpha * base) / (count + alpha)` (`alpha` 기본 120)
- 최종 `prob_bin`은 `[1e-4, 1-1e-4]`로 clip

## 4.3 Combined Probability

일자/종목 행에 대해 각 feature 확률을 가중합:

- `prob_up_next_day = sum(weight_i * p_feature_i)`
- 이후 `[1e-4, 1-1e-4]`로 clip

## 4.4 Liquidity + Momentum + Model Composite

일자별로 cross-sectional 백분위 순위를 계산:

- `turnover_rank_pct = pct_rank(trading_value)`
- `ret1d_rank_pct = pct_rank(ret_1d)`
- `model_rank_pct = pct_rank(prob_up_next_day)`

최종 점수:

- `final_score = w_turnover * turnover_rank_pct + w_ret1d * ret1d_rank_pct + w_model * model_rank_pct`

정렬 기준:

1. `final_score` 내림차순
2. `prob_up_next_day` 내림차순
3. `Ticker` 오름차순

## 4.5 AI Score

전체 추론 구간의 확률 최소/최대(`p_min`, `p_max`)로 선형 스케일:

- `ai_score = round(70 + (p - p_min)/(p_max - p_min) * 29)`
- 범위 제한: `[0, 99]`
- 예외: `p_max <= p_min`이면 전부 `85`

---

## 5) Daily TOP5 Selection

각 날짜별로:

1. `final_score` 내림차순(동점 시 `prob_up_next_day` 보조), `Ticker` 오름차순 정렬
2. `rank = 1..N` 부여
3. 기본 `N=5`만 저장/응답

저장 CSV 컬럼:

- `Date`, `rank`, `Ticker`, `name`, `Close`, `trading_value`, `ret_1d`, `prob_up_next_day`, `final_score`, `ai_score`, `max_return_since_buy`, `max_return_peak_date`

추가 성과 지표:

- `max_return_since_buy`: 추천일 종가를 매수가로 가정했을 때, 이후 구간 `High` 기준 최대 수익률
- `max_return_peak_date`: 위 최대 수익률이 발생한 고점 일자

`name`은 `data/krx_symbol_master.csv`(`symbol`, `name_ko`)로 매핑.

---

## 6) Serving Layer

## 6.1 CSV Discovery

`lib/recommendations/daily.ts`에서 정규식으로 후보를 찾고 최신 파일 선택:

- 패턴: `daily_top5_recommendations_(\d{8})(?:_to_(\d{8}))?.csv`

## 6.2 API Parameters

`GET /api/recommendations/daily`

- `lang`: `ko` | `en`
- `startDate`: `YYYY-MM-DD`
- `endDate`: `YYYY-MM-DD`
- `limit`: 일자당 개수(기본 5)
- `file`: 특정 CSV 파일명 고정

## 6.3 UI Behavior

`components/RecommendationsView.tsx`

- 기본 조회: `startDate=2026-01-01`, `limitPerDay=5`
- 날짜 드롭다운에서 원하는 일자 선택
- 선택된 일자의 TOP5만 테이블 출력

---

## 7) Daily Auto Refresh

`daily_eod_update.py` 실행 순서:

1. EOD 데이터 갱신 (`run_daily_update`)
2. TOP5 CSV 재생성 (`run_daily_top5_refresh`)

환경변수:

- `VS_ENABLE_DAILY_TOP5_REFRESH` (기본 `true`)
- `VS_DAILY_TOP5_SCRIPT` (기본 `build_daily_top5_recommendations.py`)
- `VS_DAILY_TOP5_START_DATE` (기본 `2026-01-01`)
- `VS_DAILY_TOP5_END_DATE` (선택)
- `VS_DAILY_TOP5_OUT` (선택)
- `VS_DAILY_TOP5_WEIGHT_TURNOVER` (선택)
- `VS_DAILY_TOP5_WEIGHT_RET1D` (선택)
- `VS_DAILY_TOP5_WEIGHT_MODEL` (선택)

---

## 8) Operational Notes

- 현재 서비스는 **계산은 parquet 기반**, **조회는 CSV 캐시 기반**입니다.
- CSV 조회 구조라 API 응답은 빠르고 단순하지만, 최신 계산이 필요하면 재생성 스크립트 실행이 선행되어야 합니다.
- 기존 `tier1` 추천(`lib/recommendations/tier1.ts`)과 별개로, 추천 페이지는 현재 `daily` 경로를 사용합니다.
