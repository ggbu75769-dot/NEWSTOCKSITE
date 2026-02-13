# Strategy Variance Explorer (Offline)

- Generated at: `2026-02-13 23:51:44`
- Source file: `tier1_buy_candidates_20260213_115717.csv`
- Candidate rows: `130`
- Trade date: `2026-02-11 15:00:00`

## Score Distribution
- Final score range: `8.9` ~ `93.4` (median `49.7`)

## Top 10 by Final Score

| Ticker | Final | Quality | Stability | 5D Ret | RVOL20 | Breakout20 | NATR14 |
|---|---:|---:|---:|---:|---:|---:|---:|
| 000890.KS | 93.4 | 92.3 | 96.2 | 17.4% | 14.45 | 16.0% | 2.71% |
| 034950.KQ | 86.6 | 82.6 | 96.9 | 15.0% | 5.69 | 7.0% | 2.02% |
| 057050.KS | 85.5 | 84.4 | 88.5 | 29.8% | 5.52 | 4.9% | 3.88% |
| 009450.KS | 83.1 | 79.2 | 93.1 | 14.8% | 5.08 | 9.5% | 3.62% |
| 031820.KS | 82.2 | 84.2 | 76.9 | 12.8% | 11.85 | 9.3% | 3.68% |
| 002870.KS | 79.0 | 76.5 | 85.4 | 19.6% | 3.69 | 6.2% | 4.31% |
| 010690.KS | 77.0 | 78.3 | 73.8 | 22.8% | 4.79 | 4.1% | 4.67% |
| 472850.KQ | 76.4 | 87.6 | 47.7 | 23.8% | 7.90 | 15.1% | 4.83% |
| 089470.KS | 75.7 | 90.2 | 38.5 | 27.0% | 8.55 | 17.1% | 5.04% |
| 175330.KS | 75.5 | 74.6 | 77.7 | 19.9% | 3.42 | 6.7% | 4.57% |

## Momentum x Volume Buckets

| Momentum | Volume | Count | Avg Final | Avg 5D Return |
|---|---|---:|---:|---:|
| strong | surge | 8 | 74.8 | 13.9% |
| extreme | surge | 9 | 71.7 | 27.7% |
| strong | high | 21 | 61.0 | 14.7% |
| extreme | high | 14 | 56.9 | 31.6% |
| extreme | active | 4 | 50.4 | 22.7% |
| building | surge | 8 | 49.6 | 6.0% |
| strong | active | 21 | 47.5 | 13.4% |
| building | high | 16 | 43.5 | 7.1% |
| strong | normal | 6 | 34.5 | 12.3% |
| building | normal | 1 | 33.6 | 9.5% |
| building | active | 22 | 30.4 | 6.4% |

## Notes
- `quality_score`: weighted rank score across composite/momentum/breakout/volume/volatility.
- `stability_score`: inverse rank of factor dispersion (higher = more balanced factors).
- `final_score`: `0.72 * quality + 0.28 * stability` for practical shortlist ordering.
