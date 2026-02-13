# Competitive Gap Audit (2026-02-13)

## Goal
- Analyze leading trading platforms.
- Identify concrete gaps vs `Visual Stock`.
- Apply only **no-runtime-impact** changes while background jobs keep running.

## Benchmarks (Official Sources)
- TradingView features/alerts:
  - https://www.tradingview.com/features/
  - https://www.tradingview.com/support/solutions/43000529348-how-to-configure-webhook-alerts/
- TrendSpider strategy variance explorer:
  - https://help.trendspider.com/kb/strategy-tester/strategy-variance-explorer
- MetaTrader 5 strategy tester:
  - https://www.metatrader5.com/en/automated-trading/strategy-tester
- Interactive Brokers Risk Navigator:
  - https://www.interactivebrokers.com/en/trading/risk-navigator.php

## What They Do Better
1. Signal operations layer:
- TradingView supports robust alert delivery paths and webhook integration.

2. Strategy robustness exploration:
- TrendSpider provides variant table + bubble-chart style comparison for multiple strategy/symbol/timeframe combinations.

3. Overfit defense tooling:
- MetaTrader exposes forward testing and distributed optimization as first-class capabilities.

4. Portfolio risk context:
- IBKR shows risk slices and what-if scenario analysis at portfolio level.

## Current Gaps in Visual Stock
1. Recommendation robustness visibility:
- Recommendations show score/reasoning, but no stability report across symbols/windows.

2. Forward/out-of-sample evidence:
- Tier1 pipeline output is strong, but no explicit forward-split validation artifact is surfaced.

3. Alert-to-action workflow:
- Recommendation API is present, but no webhook-style handoff layer.

4. Portfolio-aware risk:
- Current UI focuses single-name picks; portfolio concentration/risk slices are not exposed.

## Applied Now (No Runtime Impact)
1. Added offline variance report script:
- `strategy_variance_explorer_report.py`
- Purpose: emulate a lightweight Strategy Variance Explorer using Tier1 CSV.
- Output: sortable variance and bucket summaries for review.

2. Added isolated 1-hour audit agent runner:
- `continuous_audit_agent.py` (in isolated worktree)
- Performs cyclical code-health checks without touching active runtime workflow.

## Applied Artifacts (Generated)
1. Variance explorer outputs from real Tier1 CSV:
- `logs/strategy_variance_candidates_20260213_235144.csv`
- `logs/strategy_variance_summary_20260213_235144.json`
- `logs/strategy_variance_report_20260213_235144.md`

2. Isolated continuous audit loop (120s interval, 1 hour target):
- `logs/isolated_audit_checkpoints_20260213_235011.log`
- `logs/isolated_audit_results_20260213_235011.json`

## Isolated Audit Findings (Current)
1. Health checks:
- Typecheck, tests, python compile: `OK` on repeated cycles.

2. Build verification:
- `npm run build` completed successfully in isolated worktree.
- Observed `DYNAMIC_SERVER_USAGE` logs for routes using `cookies` (`/dashboard`, `/login`, `/recommendations`).
- This is not a build blocker now, but should be treated as expected dynamic rendering behavior and monitored when tuning static rendering policy.

## Next Safe Step (Feature-Flag Recommended)
1. Add `/api/recommendations/quality` read-only endpoint with:
- run_id, source_file, oos_tag, stability_score, drawdown_bucket

2. Add `robustness_panel` flag for recommendations page:
- hidden by default (no behavior change), enabled only when validated.

3. Add nightly offline jobs:
- forward split score
- cross-symbol stability score
- alert readiness score
