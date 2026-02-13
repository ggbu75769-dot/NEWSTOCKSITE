#!/usr/bin/env python3
"""Generate an offline strategy variance report from Tier-1 candidate CSV.

This script is intentionally offline-only and does not change runtime services.
It evaluates cross-sectional signal consistency so we can compare robustness of
candidate picks before exposing additional UI/API blocks.
"""

from __future__ import annotations

import argparse
import json
import math
import re
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd


CSV_RE = re.compile(r"^tier1_buy_candidates_(\d{8}_\d{6})\.csv$")
REQUIRED_COLS = [
    "ticker",
    "date",
    "tier1_composite_score",
    "ret_1d",
    "ret_5d",
    "rvol20",
    "breakout_dist_20",
    "natr14",
]


@dataclass(frozen=True)
class OutputPaths:
    candidates_csv: Path
    summary_json: Path
    report_md: Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Offline strategy variance explorer report")
    parser.add_argument("--logs-dir", default="logs", help="Directory containing tier1 candidate csv files")
    parser.add_argument("--source-file", default="", help="Optional explicit source CSV filename")
    parser.add_argument("--top-n", type=int, default=30, help="Top rows to include in output CSV")
    return parser.parse_args()


def pick_source_csv(logs_dir: Path, source_file: str) -> Path:
    if source_file:
        path = logs_dir / source_file
        if not path.exists():
            raise FileNotFoundError(f"Source CSV does not exist: {path}")
        return path

    candidates: list[tuple[str, Path]] = []
    for p in logs_dir.glob("tier1_buy_candidates_*.csv"):
        m = CSV_RE.match(p.name)
        if m:
            candidates.append((m.group(1), p))

    if not candidates:
        raise FileNotFoundError(f"No tier1 candidate CSV found in: {logs_dir}")

    candidates.sort(key=lambda x: x[0], reverse=True)
    for _, p in candidates:
        # Skip empty header-only files.
        try:
            df = pd.read_csv(p)
            if not df.empty:
                return p
        except Exception:
            continue

    raise ValueError(f"All tier1 candidate CSV files in {logs_dir} are empty or unreadable")


def _to_numeric(df: pd.DataFrame, cols: list[str]) -> None:
    for col in cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")


def _rank_pct(series: pd.Series, ascending: bool = True) -> pd.Series:
    if series.isna().all():
        return pd.Series(np.nan, index=series.index, dtype="float64")
    return series.rank(method="average", pct=True, ascending=ascending)


def load_and_score(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    missing = [col for col in REQUIRED_COLS if col not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns: {', '.join(missing)}")

    out = df.copy()
    _to_numeric(
        out,
        [
            "tier1_composite_score",
            "ret_1d",
            "ret_5d",
            "rvol20",
            "breakout_dist_20",
            "natr14",
        ],
    )

    out = out.dropna(subset=["ticker", "tier1_composite_score", "ret_5d", "rvol20", "breakout_dist_20", "natr14"]).copy()
    if out.empty:
        raise ValueError(f"No usable rows after cleaning: {path}")

    out["momentum_pct"] = _rank_pct(out["ret_5d"], ascending=True)
    out["breakout_pct"] = _rank_pct(out["breakout_dist_20"], ascending=True)
    out["volume_pct"] = _rank_pct(np.log1p(out["rvol20"].clip(lower=0)), ascending=True)
    out["volatility_pct"] = _rank_pct(-out["natr14"], ascending=True)
    out["composite_pct"] = _rank_pct(out["tier1_composite_score"], ascending=True)

    # Weighted quality score: how strong and balanced the signal profile is.
    out["quality_raw"] = (
        out["composite_pct"] * 0.40
        + out["momentum_pct"] * 0.22
        + out["breakout_pct"] * 0.16
        + out["volume_pct"] * 0.14
        + out["volatility_pct"] * 0.08
    )

    factor_cols = ["momentum_pct", "breakout_pct", "volume_pct", "volatility_pct"]
    out["factor_dispersion"] = out[factor_cols].std(axis=1, ddof=0)
    out["stability_raw"] = 1.0 - _rank_pct(out["factor_dispersion"], ascending=True)

    out["quality_score"] = (out["quality_raw"] * 100.0).round(1)
    out["stability_score"] = (out["stability_raw"] * 100.0).round(1)
    out["final_score"] = (out["quality_score"] * 0.72 + out["stability_score"] * 0.28).round(1)

    out["momentum_bucket"] = pd.cut(
        out["ret_5d"],
        bins=[-np.inf, 0.03, 0.10, 0.20, np.inf],
        labels=["weak", "building", "strong", "extreme"],
    )
    out["volume_bucket"] = pd.cut(
        out["rvol20"],
        bins=[-np.inf, 1.2, 2.0, 5.0, np.inf],
        labels=["normal", "active", "high", "surge"],
    )
    out["risk_bucket"] = pd.cut(
        out["natr14"],
        bins=[-np.inf, 0.03, 0.05, 0.08, np.inf],
        labels=["low", "moderate", "elevated", "high"],
    )

    return out.sort_values(["final_score", "tier1_composite_score"], ascending=False).reset_index(drop=True)


def make_outputs(logs_dir: Path) -> OutputPaths:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    return OutputPaths(
        candidates_csv=logs_dir / f"strategy_variance_candidates_{ts}.csv",
        summary_json=logs_dir / f"strategy_variance_summary_{ts}.json",
        report_md=logs_dir / f"strategy_variance_report_{ts}.md",
    )


def build_summary(df: pd.DataFrame, source_file: str) -> dict:
    def _safe_mean(col: str) -> float:
        s = df[col]
        return round(float(s.mean()), 4) if not s.empty else math.nan

    summary = {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "source_file": source_file,
        "rows": int(len(df)),
        "date": str(df["date"].iloc[0]) if "date" in df.columns and not df.empty else "",
        "final_score": {
            "min": float(df["final_score"].min()),
            "median": float(df["final_score"].median()),
            "max": float(df["final_score"].max()),
            "mean": _safe_mean("final_score"),
        },
        "factor_means": {
            "ret_1d": _safe_mean("ret_1d"),
            "ret_5d": _safe_mean("ret_5d"),
            "rvol20": _safe_mean("rvol20"),
            "breakout_dist_20": _safe_mean("breakout_dist_20"),
            "natr14": _safe_mean("natr14"),
        },
    }

    top_group = (
        df.head(20)[["ticker", "final_score", "quality_score", "stability_score", "ret_5d", "rvol20", "breakout_dist_20", "natr14"]]
        .to_dict(orient="records")
    )
    summary["top20"] = top_group

    return summary


def build_markdown(summary: dict, df: pd.DataFrame) -> str:
    top10 = df.head(10)
    bucket_table = (
        df.groupby(["momentum_bucket", "volume_bucket"], observed=True)
        .agg(
            count=("ticker", "count"),
            avg_final=("final_score", "mean"),
            avg_ret5d=("ret_5d", "mean"),
        )
        .reset_index()
        .sort_values(["avg_final", "count"], ascending=[False, False])
    )

    lines: list[str] = []
    lines.append("# Strategy Variance Explorer (Offline)")
    lines.append("")
    lines.append(f"- Generated at: `{summary['generated_at']}`")
    lines.append(f"- Source file: `{summary['source_file']}`")
    lines.append(f"- Candidate rows: `{summary['rows']}`")
    lines.append(f"- Trade date: `{summary['date']}`")
    lines.append("")
    lines.append("## Score Distribution")
    lines.append(
        f"- Final score range: `{summary['final_score']['min']:.1f}` ~ `{summary['final_score']['max']:.1f}` "
        f"(median `{summary['final_score']['median']:.1f}`)"
    )
    lines.append("")
    lines.append("## Top 10 by Final Score")
    lines.append("")
    lines.append("| Ticker | Final | Quality | Stability | 5D Ret | RVOL20 | Breakout20 | NATR14 |")
    lines.append("|---|---:|---:|---:|---:|---:|---:|---:|")
    for _, row in top10.iterrows():
        lines.append(
            "| "
            f"{row['ticker']} | {row['final_score']:.1f} | {row['quality_score']:.1f} | {row['stability_score']:.1f} | "
            f"{row['ret_5d'] * 100:.1f}% | {row['rvol20']:.2f} | {row['breakout_dist_20'] * 100:.1f}% | {row['natr14'] * 100:.2f}% |"
        )
    lines.append("")
    lines.append("## Momentum x Volume Buckets")
    lines.append("")
    lines.append("| Momentum | Volume | Count | Avg Final | Avg 5D Return |")
    lines.append("|---|---|---:|---:|---:|")
    for _, row in bucket_table.head(20).iterrows():
        lines.append(
            f"| {row['momentum_bucket']} | {row['volume_bucket']} | {int(row['count'])} | "
            f"{row['avg_final']:.1f} | {row['avg_ret5d'] * 100:.1f}% |"
        )
    lines.append("")
    lines.append("## Notes")
    lines.append("- `quality_score`: weighted rank score across composite/momentum/breakout/volume/volatility.")
    lines.append("- `stability_score`: inverse rank of factor dispersion (higher = more balanced factors).")
    lines.append("- `final_score`: `0.72 * quality + 0.28 * stability` for practical shortlist ordering.")
    return "\n".join(lines) + "\n"


def main() -> int:
    args = parse_args()
    logs_dir = Path(args.logs_dir).resolve()
    logs_dir.mkdir(parents=True, exist_ok=True)

    src = pick_source_csv(logs_dir, args.source_file.strip())
    scored = load_and_score(src)

    outputs = make_outputs(logs_dir)
    shortlist = scored.head(max(1, args.top_n)).copy()
    shortlist.to_csv(outputs.candidates_csv, index=False, encoding="utf-8-sig")

    summary = build_summary(scored, src.name)
    outputs.summary_json.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    outputs.report_md.write_text(build_markdown(summary, scored), encoding="utf-8")

    print(f"[ok] source={src.name}")
    print(f"[ok] candidates={outputs.candidates_csv}")
    print(f"[ok] summary={outputs.summary_json}")
    print(f"[ok] report={outputs.report_md}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
