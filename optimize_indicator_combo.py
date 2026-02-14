#!/usr/bin/env python3
"""Optimize indicator combinations for next-day up probability on KRX data.

Pipeline summary:
1) Load daily indicator parquet
2) Build next-day up label per ticker
3) Create walk-forward validation folds
4) Convert each indicator into fold-wise probability features via train-only binning
5) Search indicator combinations in parallel with ProcessPoolExecutor (time-budgeted)
6) Fit best combo on full labeled data and rank latest tickers by next-day up probability
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import os
import time
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


# Worker globals (loaded once per process)
_WORKER_FOLD_PREDS: list[np.ndarray] = []
_WORKER_FOLD_Y: list[np.ndarray] = []


@dataclass
class FoldSpec:
    train_end_date: np.datetime64
    val_end_date: np.datetime64


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="4-hour indicator-combo optimizer")
    parser.add_argument(
        "--input",
        type=Path,
        default=Path("stock_data/korean_market_10y_with_indicators.parquet"),
        help="Input parquet path with Date/Ticker/OHLCV + indicators",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("logs/indicator_combo_optimizer"),
        help="Directory for checkpoints and final outputs",
    )
    parser.add_argument("--max-hours", type=float, default=4.0, help="Search time budget in hours")
    parser.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 4) - 1), help="Process workers")
    parser.add_argument("--batch-size", type=int, default=240, help="Candidates per iteration")
    parser.add_argument("--n-bins", type=int, default=20, help="Quantile bins per indicator")
    parser.add_argument("--alpha", type=float, default=120.0, help="Bayesian smoothing strength")
    parser.add_argument("--top-n", type=int, default=25, help="Number of final ticker picks")
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    return parser.parse_args()


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _log(msg: str) -> None:
    print(f"[{_now()}] {msg}", flush=True)


def load_data(path: Path) -> tuple[pd.DataFrame, pd.DataFrame, list[str]]:
    if not path.exists():
        raise FileNotFoundError(f"Input parquet not found: {path}")

    _log(f"Loading parquet: {path}")
    raw = pd.read_parquet(path)

    required = {"Date", "Ticker", "Close"}
    missing = required - set(raw.columns)
    if missing:
        raise ValueError(f"Missing required columns: {sorted(missing)}")

    raw["Date"] = pd.to_datetime(raw["Date"]).dt.tz_localize(None)
    raw["Ticker"] = raw["Ticker"].astype("string")

    # Keep latest rows (with unknown next-day target) for final ranking.
    # Restrict to the latest market date so stale/suspended tickers do not leak in.
    latest_market_date = raw["Date"].max()
    latest_rows = (
        raw.sort_values(["Ticker", "Date"], kind="mergesort")
        .groupby("Ticker", observed=True, sort=False)
        .tail(1)
        .loc[:, ["Date", "Ticker", "Close"] + [c for c in raw.columns if c not in {"Date", "Ticker", "Open", "High", "Low", "Close", "Volume"}]]
    )
    latest_rows = latest_rows.loc[latest_rows["Date"] == latest_market_date].reset_index(drop=True)

    # Build label on sorted frame.
    df = raw.sort_values(["Ticker", "Date"], kind="mergesort").reset_index(drop=True)
    df["NextClose"] = df.groupby("Ticker", observed=True, sort=False)["Close"].shift(-1)

    labeled_mask = df["NextClose"].notna() & df["Close"].gt(0)
    df = df.loc[labeled_mask].copy()
    df["TargetUp"] = (df["NextClose"] > df["Close"]).astype(np.uint8)
    df["FwdRet1D"] = (df["NextClose"] / df["Close"] - 1.0).astype(np.float32)

    base_cols = {"Date", "Ticker", "Open", "High", "Low", "Close", "Volume", "NextClose", "TargetUp", "FwdRet1D"}
    feature_cols = [c for c in df.columns if c not in base_cols]

    if not feature_cols:
        raise ValueError("No indicator feature columns found")

    for col in feature_cols:
        if pd.api.types.is_float_dtype(df[col]):
            df[col] = df[col].astype(np.float32)

    df = df.sort_values(["Date", "Ticker"], kind="mergesort").reset_index(drop=True)
    latest_rows = latest_rows.sort_values(["Date", "Ticker"], kind="mergesort").reset_index(drop=True)

    _log(
        "Loaded rows="
        f"{len(df):,}, tickers={df['Ticker'].nunique():,}, dates={df['Date'].nunique():,}, features={len(feature_cols)}"
    )
    return df, latest_rows, feature_cols


def build_folds(dates: np.ndarray) -> list[FoldSpec]:
    unique_dates = np.unique(dates)
    if unique_dates.size < 400:
        raise ValueError("Not enough dates for robust walk-forward validation")

    plans = [
        (0.55, 0.10),
        (0.65, 0.10),
        (0.75, 0.10),
        (0.85, 0.10),
    ]

    folds: list[FoldSpec] = []
    n = unique_dates.size
    for train_frac, val_frac in plans:
        train_end_i = int(n * train_frac)
        val_end_i = min(n - 1, int(n * (train_frac + val_frac)))
        if train_end_i < 120 or val_end_i <= train_end_i:
            continue
        folds.append(
            FoldSpec(
                train_end_date=unique_dates[train_end_i - 1],
                val_end_date=unique_dates[val_end_i - 1],
            )
        )

    if not folds:
        raise ValueError("Failed to build validation folds")

    return folds


def fit_prob_mapper(
    x_train: np.ndarray,
    y_train: np.ndarray,
    n_bins: int,
    alpha: float,
) -> tuple[np.ndarray | None, np.ndarray, float]:
    valid = np.isfinite(x_train)
    if valid.sum() < 600:
        base = float(y_train.mean()) if y_train.size else 0.5
        return None, np.array([base], dtype=np.float32), base

    xv = x_train[valid].astype(np.float64, copy=False)
    yv = y_train[valid].astype(np.float64, copy=False)
    base = float(yv.mean()) if yv.size else 0.5

    q = np.linspace(0, 1, n_bins + 1)
    edges = np.quantile(xv, q)
    edges = np.unique(edges)

    if edges.size < 4:
        return None, np.array([base], dtype=np.float32), base

    inner = edges[1:-1]
    n_states = edges.size - 1

    bins = np.searchsorted(inner, xv, side="right")
    counts = np.bincount(bins, minlength=n_states).astype(np.float64)
    ups = np.bincount(bins, weights=yv, minlength=n_states).astype(np.float64)

    probs = (ups + alpha * base) / (counts + alpha)
    probs = np.clip(probs, 1e-4, 1 - 1e-4).astype(np.float32)
    return inner.astype(np.float32), probs, base


def apply_prob_mapper(x: np.ndarray, inner: np.ndarray | None, probs: np.ndarray, base: float) -> np.ndarray:
    out = np.full(x.shape[0], np.float32(base), dtype=np.float32)
    valid = np.isfinite(x)
    if not valid.any():
        return out

    if inner is None:
        out[valid] = probs[0]
        return out

    bins = np.searchsorted(inner, x[valid], side="right")
    bins = np.clip(bins, 0, probs.shape[0] - 1)
    out[valid] = probs[bins]
    return out


def prepare_fold_artifacts(
    df: pd.DataFrame,
    feature_cols: list[str],
    folds: list[FoldSpec],
    n_bins: int,
    alpha: float,
    output_dir: Path,
) -> list[Path]:
    dates = df["Date"].to_numpy()
    y_all = df["TargetUp"].to_numpy(dtype=np.uint8, copy=False)
    feature_arrays = [df[c].to_numpy(dtype=np.float32, copy=False) for c in feature_cols]

    artifact_paths: list[Path] = []

    for fold_idx, fold in enumerate(folds, start=1):
        train_mask = dates <= fold.train_end_date
        val_mask = (dates > fold.train_end_date) & (dates <= fold.val_end_date)

        train_idx = np.flatnonzero(train_mask)
        val_idx = np.flatnonzero(val_mask)

        if train_idx.size < 200_000 or val_idx.size < 20_000:
            _log(
                f"Fold {fold_idx} skipped (train={train_idx.size:,}, val={val_idx.size:,})"
            )
            continue

        y_train = y_all[train_idx]
        y_val = y_all[val_idx]

        pred_matrix = np.empty((val_idx.size, len(feature_cols)), dtype=np.float32)

        for fi, x_all in enumerate(feature_arrays):
            inner, probs, base = fit_prob_mapper(
                x_train=x_all[train_idx],
                y_train=y_train,
                n_bins=n_bins,
                alpha=alpha,
            )
            pred_matrix[:, fi] = apply_prob_mapper(
                x=x_all[val_idx],
                inner=inner,
                probs=probs,
                base=base,
            )

        path = output_dir / f"fold_{fold_idx}.npz"
        np.savez_compressed(path, preds=pred_matrix, y=y_val)
        artifact_paths.append(path)
        _log(
            f"Prepared fold {fold_idx}: train={train_idx.size:,}, val={val_idx.size:,}, file={path.name}"
        )

    if not artifact_paths:
        raise ValueError("No usable folds were prepared")

    return artifact_paths


def _worker_init(paths: list[str]) -> None:
    global _WORKER_FOLD_PREDS, _WORKER_FOLD_Y
    _WORKER_FOLD_PREDS = []
    _WORKER_FOLD_Y = []
    for p in paths:
        data = np.load(p)
        _WORKER_FOLD_PREDS.append(data["preds"].astype(np.float32, copy=False))
        _WORKER_FOLD_Y.append(data["y"].astype(np.uint8, copy=False))


def _safe_logloss(y: np.ndarray, p: np.ndarray) -> float:
    p = np.clip(p, 1e-5, 1 - 1e-5)
    y_f = y.astype(np.float32)
    return float(-np.mean(y_f * np.log(p) + (1.0 - y_f) * np.log(1.0 - p)))


def evaluate_candidate(candidate: tuple[list[int], list[float]]) -> dict[str, Any]:
    idx, weights = candidate
    idx_arr = np.asarray(idx, dtype=np.int32)
    w = np.asarray(weights, dtype=np.float32)

    fold_scores: list[float] = []
    fold_top_hits: list[float] = []
    fold_lifts: list[float] = []
    fold_briers: list[float] = []
    fold_logloss: list[float] = []

    for preds, y in zip(_WORKER_FOLD_PREDS, _WORKER_FOLD_Y):
        p = preds[:, idx_arr] @ w
        p = np.clip(p, 1e-4, 1 - 1e-4)

        y_f = y.astype(np.float32)
        base_rate = float(y_f.mean())

        brier = float(np.mean((p - y_f) ** 2))
        logloss = _safe_logloss(y, p)

        top_k = max(1, int(p.size * 0.10))
        threshold = float(np.partition(p, -top_k)[-top_k])
        top_mask = p >= threshold
        top_hit = float(y_f[top_mask].mean()) if top_mask.any() else base_rate
        lift = (top_hit / base_rate) if base_rate > 0 else 1.0

        # Higher is better.
        score = top_hit + 0.40 * lift - 0.80 * brier - 0.20 * logloss

        fold_scores.append(score)
        fold_top_hits.append(top_hit)
        fold_lifts.append(lift)
        fold_briers.append(brier)
        fold_logloss.append(logloss)

    score_mean = float(np.mean(fold_scores))
    score_std = float(np.std(fold_scores))
    stability_penalty = 0.25 * score_std

    return {
        "features": idx,
        "weights": [float(x) for x in w],
        "score": score_mean - stability_penalty,
        "score_mean": score_mean,
        "score_std": score_std,
        "top_hit_mean": float(np.mean(fold_top_hits)),
        "lift_mean": float(np.mean(fold_lifts)),
        "brier_mean": float(np.mean(fold_briers)),
        "logloss_mean": float(np.mean(fold_logloss)),
    }


def make_random_candidate(
    rng: np.random.Generator,
    n_features: int,
    elite: list[dict[str, Any]],
) -> tuple[list[int], list[float]]:
    use_elite_mutation = bool(elite) and rng.random() < 0.35

    if use_elite_mutation:
        base = elite[int(rng.integers(0, len(elite)))]
        idx = list(base["features"])

        if idx and rng.random() < 0.6:
            drop_i = int(rng.integers(0, len(idx)))
            idx.pop(drop_i)

        add_count = int(rng.integers(1, 3))
        pool = [i for i in range(n_features) if i not in idx]
        if pool:
            add = rng.choice(pool, size=min(add_count, len(pool)), replace=False).tolist()
            idx.extend(add)

        k = len(idx)
        if k < 4:
            idx = rng.choice(n_features, size=4, replace=False).tolist()
        elif k > 14:
            idx = rng.choice(idx, size=14, replace=False).tolist()

    else:
        k = int(rng.integers(4, min(15, n_features + 1)))
        idx = rng.choice(n_features, size=k, replace=False).tolist()

    idx = sorted(set(idx))
    if len(idx) < 2:
        idx = sorted(rng.choice(n_features, size=4, replace=False).tolist())

    w = rng.dirichlet(np.ones(len(idx), dtype=np.float64)).astype(np.float32)
    return idx, w.tolist()


def save_checkpoint(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def fit_full_mappers(
    df: pd.DataFrame,
    feature_cols: list[str],
    n_bins: int,
    alpha: float,
) -> dict[str, dict[str, Any]]:
    y = df["TargetUp"].to_numpy(dtype=np.uint8, copy=False)
    out: dict[str, dict[str, Any]] = {}

    for col in feature_cols:
        x = df[col].to_numpy(dtype=np.float32, copy=False)
        inner, probs, base = fit_prob_mapper(x, y, n_bins=n_bins, alpha=alpha)
        out[col] = {
            "inner": inner.tolist() if inner is not None else None,
            "probs": probs.tolist(),
            "base": float(base),
        }

    return out


def predict_latest(
    latest_rows: pd.DataFrame,
    feature_cols: list[str],
    best: dict[str, Any],
    mappers: dict[str, dict[str, Any]],
    top_n: int,
) -> pd.DataFrame:
    out = latest_rows[["Date", "Ticker", "Close"]].copy()
    probs = np.zeros(len(out), dtype=np.float32)

    idx = best["features"]
    weights = np.asarray(best["weights"], dtype=np.float32)

    for pos, fi in enumerate(idx):
        col = feature_cols[fi]
        spec = mappers[col]

        inner = np.asarray(spec["inner"], dtype=np.float32) if spec["inner"] is not None else None
        p_bins = np.asarray(spec["probs"], dtype=np.float32)
        base = float(spec["base"])

        x = latest_rows[col].to_numpy(dtype=np.float32, copy=False)
        p_feat = apply_prob_mapper(x, inner=inner, probs=p_bins, base=base)
        probs += weights[pos] * p_feat

    probs = np.clip(probs, 1e-4, 1 - 1e-4)
    out["prob_up_next_day"] = probs
    out = out.sort_values("prob_up_next_day", ascending=False).reset_index(drop=True)
    out.insert(0, "rank", np.arange(1, len(out) + 1))
    return out.head(top_n)


def save_top_csv(path: Path, top_df: pd.DataFrame) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    top_df.to_csv(path, index=False, encoding="utf-8-sig", quoting=csv.QUOTE_MINIMAL)


def main() -> int:
    args = parse_args()
    started = time.time()
    deadline = started + args.max_hours * 3600.0

    run_tag = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = args.output_dir / run_tag
    out_dir.mkdir(parents=True, exist_ok=True)

    df, latest_rows, feature_cols = load_data(args.input)

    folds = build_folds(df["Date"].to_numpy())
    _log(f"Using {len(folds)} walk-forward folds")

    artifact_paths = prepare_fold_artifacts(
        df=df,
        feature_cols=feature_cols,
        folds=folds,
        n_bins=args.n_bins,
        alpha=args.alpha,
        output_dir=out_dir,
    )

    rng = np.random.default_rng(args.seed)

    best_results: list[dict[str, Any]] = []
    seen: set[tuple[int, ...]] = set()

    checkpoint_path = out_dir / "best_logic.json"

    _log(
        f"Start search: workers={args.workers}, batch_size={args.batch_size}, max_hours={args.max_hours:.2f}"
    )

    iteration = 0
    with ProcessPoolExecutor(
        max_workers=args.workers,
        initializer=_worker_init,
        initargs=([str(p) for p in artifact_paths],),
    ) as executor:
        while time.time() < deadline:
            iteration += 1

            batch: list[tuple[list[int], list[float]]] = []
            while len(batch) < args.batch_size:
                cand = make_random_candidate(rng, len(feature_cols), elite=best_results[:20])
                key = tuple(cand[0])
                if key in seen:
                    continue
                seen.add(key)
                batch.append(cand)

            results = list(executor.map(evaluate_candidate, batch, chunksize=8))
            results.sort(key=lambda x: x["score"], reverse=True)

            best_results.extend(results)
            best_results.sort(key=lambda x: x["score"], reverse=True)
            best_results = best_results[:120]

            elapsed = time.time() - started
            best = best_results[0]
            top_feats = [feature_cols[i] for i in best["features"]]
            _log(
                f"iter={iteration:04d} elapsed={elapsed/60:.1f}m "
                f"best_score={best['score']:.6f} top_hit={best['top_hit_mean']:.4f} "
                f"lift={best['lift_mean']:.4f} features={len(top_feats)}"
            )

            checkpoint = {
                "updated_at": _now(),
                "iteration": iteration,
                "elapsed_seconds": round(elapsed, 2),
                "input": str(args.input),
                "max_hours": args.max_hours,
                "batch_size": args.batch_size,
                "workers": args.workers,
                "feature_count": len(feature_cols),
                "searched_unique_combos": len(seen),
                "best": {
                    **best,
                    "feature_names": top_feats,
                },
                "top_strategies": [
                    {
                        **r,
                        "feature_names": [feature_cols[i] for i in r["features"]],
                    }
                    for r in best_results[:30]
                ],
            }
            save_checkpoint(checkpoint_path, checkpoint)

    if not best_results:
        raise RuntimeError("Search finished without valid result")

    best = best_results[0]
    best_named = {
        **best,
        "feature_names": [feature_cols[i] for i in best["features"]],
    }

    _log("Fitting full-data mappers for latest ranking")
    mappers = fit_full_mappers(df, feature_cols, n_bins=args.n_bins, alpha=args.alpha)

    top_df = predict_latest(
        latest_rows=latest_rows,
        feature_cols=feature_cols,
        best=best,
        mappers=mappers,
        top_n=args.top_n,
    )

    top_csv_path = out_dir / "top_candidates.csv"
    save_top_csv(top_csv_path, top_df)

    final_report = {
        "completed_at": _now(),
        "elapsed_seconds": round(time.time() - started, 2),
        "input": str(args.input),
        "output_dir": str(out_dir),
        "best_strategy": best_named,
        "top_candidates_path": str(top_csv_path),
    }
    save_checkpoint(out_dir / "final_report.json", final_report)

    _log("Search complete")
    _log(f"Best strategy score={best_named['score']:.6f}")
    _log("Best feature names: " + ", ".join(best_named["feature_names"]))
    _log(f"Top candidates saved: {top_csv_path}")

    # Also print top candidates to stdout.
    print("\nTop candidates:")
    print(top_df.to_string(index=False))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
