#!/usr/bin/env python3
"""Build Tier-1 feature set from local OHLCV CSV files.

Tier-1 scope:
- Price trend/momentum: 1d/5d/20d returns, moving-average distance
- Participation: relative volume (RVOL), dollar-volume z-score
- Breakout context: distance to prior 20-day high
- Volatility state: ATR/NATR, 20-day realized volatility
- Compression state: Bollinger Band width and %B
- Market context: cross-sectional market return and breadth
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd


SQRT_252 = float(np.sqrt(252.0))


@dataclass(frozen=True)
class BuildResult:
    full_path: Path
    latest_path: Path
    candidates_path: Path
    summary_path: Path
    total_rows: int
    total_tickers: int
    latest_date: str


@dataclass(frozen=True)
class FilterConfig:
    min_dollar_volume: float
    max_natr14: float
    min_rvol20: float
    max_rvol20: float
    min_breakout_dist_20: float
    min_ret_5d: float
    max_ret_1d: float
    min_tier1_score: float
    allow_risk_off: bool


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build Tier-1 feature dataset from data/*.csv")
    parser.add_argument("--data-dir", default="data", help="Directory containing per-ticker CSV files")
    parser.add_argument("--out-dir", default="logs", help="Output directory")
    parser.add_argument("--top-n", type=int, default=20, help="Print top-N latest names by score")
    parser.add_argument(
        "--min-history",
        type=int,
        default=20,
        help="Minimum rows per ticker required to compute Tier-1 features",
    )
    parser.add_argument(
        "--min-dollar-volume",
        type=float,
        default=1_000_000_000.0,
        help="Minimum daily dollar volume (close*volume)",
    )
    parser.add_argument("--max-natr14", type=float, default=0.12, help="Maximum NATR(14)")
    parser.add_argument("--min-rvol20", type=float, default=1.1, help="Minimum RVOL(20)")
    parser.add_argument("--max-rvol20", type=float, default=20.0, help="Maximum RVOL(20)")
    parser.add_argument(
        "--min-breakout-dist-20",
        type=float,
        default=-0.02,
        help="Minimum breakout distance vs prior 20-day high",
    )
    parser.add_argument("--min-ret-5d", type=float, default=0.03, help="Minimum 5-day return")
    parser.add_argument(
        "--max-ret-1d",
        type=float,
        default=0.25,
        help="Maximum 1-day return to avoid overheated entries",
    )
    parser.add_argument(
        "--min-tier1-score",
        type=float,
        default=0.5,
        help="Minimum Tier-1 composite score for candidate selection",
    )
    parser.add_argument(
        "--allow-risk-off",
        action="store_true",
        help="Allow candidates when risk_on_regime == 0 (default requires risk_on_regime == 1)",
    )
    return parser.parse_args()


def _standardize_columns(df: pd.DataFrame) -> pd.DataFrame:
    renamed = {
        c: c.strip().lower().replace(" ", "_")
        for c in df.columns
    }
    return df.rename(columns=renamed)


def _safe_numeric(df: pd.DataFrame, columns: Iterable[str]) -> None:
    for col in columns:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")


def load_one_csv(path: Path) -> pd.DataFrame:
    raw = pd.read_csv(path)
    raw = _standardize_columns(raw)

    if "date" not in raw.columns:
        raise ValueError(f"Missing date column: {path}")

    required = {"open", "high", "low", "close", "volume"}
    missing = [c for c in required if c not in raw.columns]
    if missing:
        raise ValueError(f"Missing required columns in {path}: {', '.join(missing)}")

    if "adj_close" not in raw.columns:
        raw["adj_close"] = raw["close"]

    _safe_numeric(raw, ["open", "high", "low", "close", "adj_close", "volume"])
    raw["date"] = pd.to_datetime(raw["date"], utc=True, errors="coerce").dt.tz_convert(None)
    raw["ticker"] = path.stem.upper()

    cols = ["ticker", "date", "open", "high", "low", "close", "adj_close", "volume"]
    out = raw[cols].dropna(subset=["ticker", "date", "open", "high", "low", "close", "adj_close"])
    out = out.sort_values("date").drop_duplicates(subset=["date"], keep="last").reset_index(drop=True)
    return out


def compute_symbol_features(df: pd.DataFrame) -> pd.DataFrame:
    out = df.sort_values("date").copy()

    close = out["adj_close"]
    high = out["high"]
    low = out["low"]
    volume = out["volume"]
    prev_close = close.shift(1)

    out["ret_1d"] = close.pct_change(1)
    out["ret_5d"] = close.pct_change(5)
    out["ret_20d"] = close.pct_change(20)
    out["log_ret_1d"] = np.log(close).diff()

    out["sma20"] = close.rolling(20, min_periods=20).mean()
    out["sma60"] = close.rolling(60, min_periods=60).mean()
    out["dist_sma20"] = close / out["sma20"] - 1.0
    out["dist_sma60"] = close / out["sma60"] - 1.0

    tr_components = pd.concat(
        [(high - low), (high - prev_close).abs(), (low - prev_close).abs()],
        axis=1,
    )
    out["tr"] = tr_components.max(axis=1)
    out["atr14"] = out["tr"].rolling(14, min_periods=14).mean()
    out["natr14"] = out["atr14"] / close

    out["realized_vol20"] = out["log_ret_1d"].rolling(20, min_periods=20).std() * SQRT_252

    out["vol_ma20"] = volume.rolling(20, min_periods=20).mean()
    out["rvol20"] = volume / out["vol_ma20"]
    out["dollar_volume"] = close * volume
    dv_ma20 = out["dollar_volume"].rolling(20, min_periods=20).mean()
    dv_std20 = out["dollar_volume"].rolling(20, min_periods=20).std()
    out["dollar_volume_z20"] = (out["dollar_volume"] - dv_ma20) / dv_std20.replace(0, np.nan)

    high20_prev = high.rolling(20, min_periods=20).max().shift(1)
    out["breakout_dist_20"] = close / high20_prev - 1.0

    bb_mid = close.rolling(20, min_periods=20).mean()
    bb_std = close.rolling(20, min_periods=20).std()
    bb_upper = bb_mid + 2.0 * bb_std
    bb_lower = bb_mid - 2.0 * bb_std
    out["bb_mid20"] = bb_mid
    out["bb_upper20"] = bb_upper
    out["bb_lower20"] = bb_lower
    out["bb_width20"] = (bb_upper - bb_lower) / bb_mid.replace(0, np.nan)
    out["bb_percent_b20"] = (close - bb_lower) / (bb_upper - bb_lower).replace(0, np.nan)

    return out


def add_market_context(frame: pd.DataFrame) -> pd.DataFrame:
    out = frame.copy()
    valid = out.dropna(subset=["ret_1d"]).copy()
    if valid.empty:
        return out

    market_daily = valid.groupby("date", as_index=False).agg(
        market_ret_1d=("ret_1d", "mean"),
        breadth_up_ratio=("ret_1d", lambda x: float((x > 0).mean())),
        breadth_count=("ret_1d", "count"),
    )
    market_daily = market_daily.sort_values("date").reset_index(drop=True)
    market_index = (1.0 + market_daily["market_ret_1d"].fillna(0.0)).cumprod()
    market_daily["market_ret_5d"] = market_index.pct_change(5)
    market_daily["market_ret_20d"] = market_index.pct_change(20)

    out = out.merge(market_daily, on="date", how="left")
    out["rel_strength_5d"] = out["ret_5d"] - out["market_ret_5d"]
    out["rel_strength_20d"] = out["ret_20d"] - out["market_ret_20d"]
    out["risk_on_regime"] = (
        (out["market_ret_20d"] > 0.0) & (out["breadth_up_ratio"] >= 0.5)
    ).astype("int8")

    return out


def _cross_sectional_zscore(series: pd.Series) -> pd.Series:
    std = series.std(ddof=0)
    if pd.isna(std) or std == 0:
        return pd.Series(np.nan, index=series.index)
    return (series - series.mean()) / std


def add_composite_score(frame: pd.DataFrame) -> pd.DataFrame:
    out = frame.copy()
    grouped = out.groupby("date", group_keys=False)
    out["z_ret_5d"] = grouped["ret_5d"].transform(_cross_sectional_zscore)
    out["z_breakout_dist_20"] = grouped["breakout_dist_20"].transform(_cross_sectional_zscore)
    out["z_rvol20"] = grouped["rvol20"].transform(_cross_sectional_zscore)
    out["z_natr14"] = grouped["natr14"].transform(_cross_sectional_zscore)
    out["z_bb_width20"] = grouped["bb_width20"].transform(_cross_sectional_zscore)

    out["tier1_composite_score"] = (
        0.30 * out["z_ret_5d"].fillna(0.0)
        + 0.25 * out["z_breakout_dist_20"].fillna(0.0)
        + 0.20 * out["z_rvol20"].fillna(0.0)
        - 0.15 * out["z_natr14"].fillna(0.0)
        - 0.10 * out["z_bb_width20"].fillna(0.0)
    )
    return out


def select_buy_candidates(latest: pd.DataFrame, cfg: FilterConfig) -> pd.DataFrame:
    required = [
        "tier1_composite_score",
        "dollar_volume",
        "natr14",
        "rvol20",
        "breakout_dist_20",
        "ret_5d",
        "ret_1d",
        "sma20",
        "close",
        "risk_on_regime",
    ]
    out = latest.dropna(subset=required).copy()

    if not cfg.allow_risk_off:
        out = out[out["risk_on_regime"] == 1]
    # When history is short, sma60 can be null; keep a relaxed trend filter.
    out = out[out["close"] > out["sma20"]]
    out = out[out["sma60"].isna() | (out["sma20"] > out["sma60"])]
    out = out[out["dollar_volume"] >= cfg.min_dollar_volume]
    out = out[out["natr14"] <= cfg.max_natr14]
    out = out[out["rvol20"] >= cfg.min_rvol20]
    out = out[out["rvol20"] <= cfg.max_rvol20]
    out = out[out["breakout_dist_20"] >= cfg.min_breakout_dist_20]
    out = out[out["ret_5d"] >= cfg.min_ret_5d]
    out = out[out["ret_1d"] <= cfg.max_ret_1d]
    out = out[out["tier1_composite_score"] >= cfg.min_tier1_score]

    out = out.sort_values(["tier1_composite_score", "ret_5d", "breakout_dist_20"], ascending=False).copy()
    out.insert(0, "candidate_rank", range(1, len(out) + 1))
    return out


def build_tier1_features(
    data_dir: Path,
    out_dir: Path,
    min_history: int,
    top_n: int,
    cfg: FilterConfig,
) -> BuildResult:
    csv_files = sorted(data_dir.glob("*.csv"))
    if not csv_files:
        raise RuntimeError(f"No CSV files found in {data_dir}")

    frames: list[pd.DataFrame] = []
    skipped: list[str] = []
    for file_path in csv_files:
        try:
            one = load_one_csv(file_path)
        except Exception:
            skipped.append(file_path.name)
            continue
        if len(one) < min_history:
            skipped.append(file_path.name)
            continue
        frames.append(compute_symbol_features(one))

    if not frames:
        raise RuntimeError("No usable ticker frames after parsing/filtering")

    features = pd.concat(frames, ignore_index=True)
    features = add_market_context(features)
    features = add_composite_score(features)
    features = features.sort_values(["ticker", "date"]).reset_index(drop=True)

    out_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    full_path = out_dir / f"tier1_features_full_{ts}.parquet"
    latest_path = out_dir / f"tier1_features_latest_{ts}.csv"
    candidates_path = out_dir / f"tier1_buy_candidates_{ts}.csv"
    summary_path = out_dir / f"tier1_features_summary_{ts}.json"

    features.to_parquet(full_path, index=False)

    latest = features.sort_values("date").groupby("ticker", as_index=False).tail(1).copy()
    latest = latest.sort_values("tier1_composite_score", ascending=False)
    latest.to_csv(latest_path, index=False, encoding="utf-8-sig")
    candidates = select_buy_candidates(latest, cfg)
    candidates.to_csv(candidates_path, index=False, encoding="utf-8-sig")

    latest_date = (
        latest["date"].max().strftime("%Y-%m-%d")
        if not latest.empty and pd.notna(latest["date"].max())
        else ""
    )

    top_df = latest.head(top_n)[
        ["ticker", "date", "tier1_composite_score", "ret_5d", "breakout_dist_20", "rvol20"]
    ].copy()
    top_df["date"] = top_df["date"].astype(str)

    summary = {
        "run_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "data_dir": str(data_dir),
        "out_dir": str(out_dir),
        "input_csv_files": len(csv_files),
        "skipped_files": len(skipped),
        "usable_tickers": int(features["ticker"].nunique()),
        "feature_rows": int(len(features)),
        "latest_date": latest_date,
        "top_n": int(top_n),
        "candidate_count": int(len(candidates)),
        "candidate_filter": {
            "min_dollar_volume": cfg.min_dollar_volume,
            "max_natr14": cfg.max_natr14,
            "min_rvol20": cfg.min_rvol20,
            "max_rvol20": cfg.max_rvol20,
            "min_breakout_dist_20": cfg.min_breakout_dist_20,
            "min_ret_5d": cfg.min_ret_5d,
            "max_ret_1d": cfg.max_ret_1d,
            "min_tier1_score": cfg.min_tier1_score,
            "allow_risk_off": cfg.allow_risk_off,
            "trend_filter": "close > sma20 and (sma60 is null or sma20 > sma60)",
        },
        "top_tickers": top_df.to_dict(orient="records"),
        "top_candidates": candidates.head(top_n)[
            [
                "candidate_rank",
                "ticker",
                "date",
                "tier1_composite_score",
                "ret_1d",
                "ret_5d",
                "breakout_dist_20",
                "rvol20",
                "natr14",
                "dollar_volume",
            ]
        ].assign(date=lambda d: d["date"].astype(str)).to_dict(orient="records"),
    }
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    print(
        f"[TIER1] rows={summary['feature_rows']} tickers={summary['usable_tickers']} "
        f"latest_date={summary['latest_date']} skipped={summary['skipped_files']}"
    )
    print(f"[TIER1] full={full_path}")
    print(f"[TIER1] latest={latest_path}")
    print(f"[TIER1] candidates={candidates_path}")
    print(f"[TIER1] summary={summary_path}")
    print("\n[TIER1] Top names by composite score:")
    cols = ["ticker", "date", "tier1_composite_score", "ret_5d", "breakout_dist_20", "rvol20", "natr14"]
    print(latest.head(top_n)[cols].to_string(index=False))
    print(f"\n[TIER1] Buy candidates after filters: {len(candidates)}")
    candidate_cols = [
        "candidate_rank",
        "ticker",
        "date",
        "tier1_composite_score",
        "ret_1d",
        "ret_5d",
        "breakout_dist_20",
        "rvol20",
        "natr14",
        "dollar_volume",
    ]
    if candidates.empty:
        print("[TIER1] No candidates matched current filters.")
    else:
        print(candidates.head(top_n)[candidate_cols].to_string(index=False))

    return BuildResult(
        full_path=full_path,
        latest_path=latest_path,
        candidates_path=candidates_path,
        summary_path=summary_path,
        total_rows=int(len(features)),
        total_tickers=int(features["ticker"].nunique()),
        latest_date=latest_date,
    )


def main() -> None:
    args = parse_args()
    cfg = FilterConfig(
        min_dollar_volume=args.min_dollar_volume,
        max_natr14=args.max_natr14,
        min_rvol20=args.min_rvol20,
        max_rvol20=args.max_rvol20,
        min_breakout_dist_20=args.min_breakout_dist_20,
        min_ret_5d=args.min_ret_5d,
        max_ret_1d=args.max_ret_1d,
        min_tier1_score=args.min_tier1_score,
        allow_risk_off=args.allow_risk_off,
    )
    build_tier1_features(
        data_dir=Path(args.data_dir),
        out_dir=Path(args.out_dir),
        min_history=args.min_history,
        top_n=args.top_n,
        cfg=cfg,
    )


if __name__ == "__main__":
    main()
