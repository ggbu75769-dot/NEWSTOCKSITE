#!/usr/bin/env python3
"""Multi-Agent AutoQuant command center for strategy discovery.

Mission:
- Simulate 4 specialized AI agents for 1-hour collaborative optimization.
- Search for high-Sharpe long-only strategies over 2021-2025 OHLCV data.
- Persist top strategies to best_logic.json during the run.

Agents:
- LogicExpertAgent: creates and mutates strategy genomes (GA-style).
- QAEngineerAgent: backtests candidates and rejects weak/risky logic.
- LeadDeveloperAgent: hardens execution, catches faults, persists best results.
- ProjectManagerAgent: controls runtime and mutation intensity under stagnation.
"""

from __future__ import annotations

import argparse
import heapq
import json
import math
import random
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import pandas as pd


def _safe_float(v: Any, default: float = 0.0) -> float:
    try:
        x = float(v)
        if math.isfinite(x):
            return x
    except Exception:
        pass
    return default


def _safe_int(v: Any, default: int = 0) -> int:
    try:
        return int(v)
    except Exception:
        return default


def _rolling_mean(arr: np.ndarray, window: int) -> np.ndarray:
    return pd.Series(arr).rolling(window=window, min_periods=window).mean().to_numpy(dtype=float)


def _rolling_std(arr: np.ndarray, window: int) -> np.ndarray:
    return pd.Series(arr).rolling(window=window, min_periods=window).std(ddof=0).to_numpy(dtype=float)


def _rolling_max(arr: np.ndarray, window: int) -> np.ndarray:
    return pd.Series(arr).rolling(window=window, min_periods=window).max().to_numpy(dtype=float)


def _compute_rsi(close: np.ndarray, period: int) -> np.ndarray:
    delta = np.diff(close, prepend=np.nan)
    gain = np.where(delta > 0, delta, 0.0)
    loss = np.where(delta < 0, -delta, 0.0)
    avg_gain = pd.Series(gain).rolling(window=period, min_periods=period).mean()
    avg_loss = pd.Series(loss).rolling(window=period, min_periods=period).mean()
    rs = avg_gain / avg_loss.replace(0.0, np.nan)
    rsi = 100.0 - (100.0 / (1.0 + rs))
    return rsi.to_numpy(dtype=float)


@dataclass(frozen=True)
class StrategyGenome:
    rsi_period: int
    rsi_entry: float
    rsi_exit: float
    bb_period: int
    bb_std: float
    vol_period: int
    vol_ratio_min: float
    breakout_lookback: int
    trend_ma: int
    hold_days: int
    stop_loss: float
    take_profit: float

    def key(self) -> tuple[Any, ...]:
        return (
            self.rsi_period,
            round(self.rsi_entry, 2),
            round(self.rsi_exit, 2),
            self.bb_period,
            round(self.bb_std, 3),
            self.vol_period,
            round(self.vol_ratio_min, 3),
            self.breakout_lookback,
            self.trend_ma,
            self.hold_days,
            round(self.stop_loss, 4),
            round(self.take_profit, 4),
        )


@dataclass
class StrategyMetrics:
    sharpe: float
    max_drawdown: float
    win_rate: float
    trades: int
    cagr: float
    profit_factor: float
    avg_trade_return: float


@dataclass
class StrategyResult:
    genome: StrategyGenome
    metrics: StrategyMetrics
    fitness: float


class SymbolSeries:
    def __init__(self, symbol: str, frame: pd.DataFrame):
        self.symbol = symbol
        self.close = frame["close"].to_numpy(dtype=float)
        self.high = frame["high"].to_numpy(dtype=float)
        self.volume = frame["volume"].to_numpy(dtype=float)
        self.returns = np.zeros_like(self.close, dtype=float)
        if len(self.close) > 1:
            self.returns[1:] = np.diff(self.close) / self.close[:-1]
        self._sma_cache: dict[int, np.ndarray] = {}
        self._std_cache: dict[int, np.ndarray] = {}
        self._rsi_cache: dict[int, np.ndarray] = {}
        self._rmax_cache: dict[int, np.ndarray] = {}

    def sma(self, period: int) -> np.ndarray:
        cached = self._sma_cache.get(period)
        if cached is not None:
            return cached
        out = _rolling_mean(self.close, period)
        self._sma_cache[period] = out
        return out

    def std(self, period: int) -> np.ndarray:
        cached = self._std_cache.get(period)
        if cached is not None:
            return cached
        out = _rolling_std(self.close, period)
        self._std_cache[period] = out
        return out

    def rsi(self, period: int) -> np.ndarray:
        cached = self._rsi_cache.get(period)
        if cached is not None:
            return cached
        out = _compute_rsi(self.close, period)
        self._rsi_cache[period] = out
        return out

    def breakout_high(self, lookback: int) -> np.ndarray:
        cached = self._rmax_cache.get(lookback)
        if cached is not None:
            return cached
        out = _rolling_max(self.high, lookback)
        out = np.roll(out, 1)
        out[0] = np.nan
        self._rmax_cache[lookback] = out
        return out


class DataStore:
    def __init__(
        self,
        data_dir: Path,
        start_date: str,
        end_date: str,
        min_bars: int,
        max_symbols: int,
        max_scan_files: int,
        seed: int,
        allow_date_fallback: bool,
    ):
        self.data_dir = data_dir
        self.start_date = pd.Timestamp(start_date)
        self.end_date = pd.Timestamp(end_date)
        self.min_bars = min_bars
        self.max_symbols = max_symbols
        self.max_scan_files = max_scan_files
        self.seed = seed
        self.allow_date_fallback = allow_date_fallback
        self.series: list[SymbolSeries] = []

    @staticmethod
    def _normalize_columns(df: pd.DataFrame) -> dict[str, str]:
        out: dict[str, str] = {}
        for c in df.columns:
            key = "".join(ch for ch in c.lower() if ch.isalnum())
            out[key] = c
        return out

    def _load_file(self, file_path: Path, respect_date_range: bool) -> pd.DataFrame | None:
        try:
            df = pd.read_csv(file_path)
        except Exception:
            return None

        if df.empty:
            return None

        col_map = self._normalize_columns(df)
        date_col = col_map.get("date") or col_map.get("datetime") or col_map.get("timestamp")
        open_col = col_map.get("open")
        high_col = col_map.get("high")
        low_col = col_map.get("low")
        close_col = col_map.get("close")
        volume_col = col_map.get("volume")

        if not (date_col and open_col and high_col and low_col and close_col and volume_col):
            return None

        try:
            out = pd.DataFrame(
                {
                    "date": pd.to_datetime(df[date_col], errors="coerce", utc=True).dt.tz_convert(None),
                    "open": pd.to_numeric(df[open_col], errors="coerce"),
                    "high": pd.to_numeric(df[high_col], errors="coerce"),
                    "low": pd.to_numeric(df[low_col], errors="coerce"),
                    "close": pd.to_numeric(df[close_col], errors="coerce"),
                    "volume": pd.to_numeric(df[volume_col], errors="coerce").fillna(0.0),
                }
            )
        except Exception:
            return None

        out = out.dropna(subset=["date", "open", "high", "low", "close"]).sort_values("date")
        if respect_date_range:
            out = out[(out["date"] >= self.start_date) & (out["date"] <= self.end_date)]
        if len(out) < self.min_bars:
            return None
        return out.reset_index(drop=True)

    def _scan_once(self, files: list[Path], respect_date_range: bool) -> list[SymbolSeries]:
        keep_heap: list[tuple[float, int, str, pd.DataFrame]] = []
        keep_size = max(self.max_symbols * 3, self.max_symbols)
        scanned = 0
        usable = 0

        for idx, file_path in enumerate(files):
            scanned += 1
            frame = self._load_file(file_path, respect_date_range=respect_date_range)
            if frame is None:
                continue
            usable += 1
            symbol = file_path.stem.upper()
            tail = frame.tail(min(252, len(frame)))
            liquidity = float((tail["close"] * tail["volume"]).mean())
            item = (liquidity, idx, symbol, frame)
            if len(keep_heap) < keep_size:
                heapq.heappush(keep_heap, item)
            elif liquidity > keep_heap[0][0]:
                heapq.heapreplace(keep_heap, item)

        best = sorted(keep_heap, key=lambda x: x[0], reverse=True)[: self.max_symbols]
        series = [SymbolSeries(symbol=s, frame=f) for _, _, s, f in best]
        mode = "date-filtered" if respect_date_range else "fallback-full-range"
        print(f"[DataStore] mode={mode} scanned={scanned}, usable={usable}, loaded_symbols={len(series)}")
        return series

    def load(self) -> list[SymbolSeries]:
        files = list(self.data_dir.glob("*.csv"))
        if not files:
            raise RuntimeError(f"No CSV files found in {self.data_dir}")

        rnd = random.Random(self.seed)
        if self.max_scan_files > 0 and len(files) > self.max_scan_files:
            files = rnd.sample(files, self.max_scan_files)

        self.series = self._scan_once(files, respect_date_range=True)
        if not self.series and self.allow_date_fallback:
            print(
                "[DataStore] requested date range has no sufficient data. "
                "Falling back to full available history for stability."
            )
            self.series = self._scan_once(files, respect_date_range=False)

        print(
            f"[DataStore] final_loaded_symbols={len(self.series)}, "
            f"requested_range={self.start_date.date()}..{self.end_date.date()}"
        )
        return self.series


class StrategyBacktester:
    def __init__(self, universe: list[SymbolSeries], transaction_cost: float = 0.0005):
        self.universe = universe
        self.transaction_cost = transaction_cost

    @staticmethod
    def _fitness(metrics: StrategyMetrics) -> float:
        dd_penalty = max(0.0, (-metrics.max_drawdown - 0.15) * 4.0)
        return metrics.sharpe + 0.15 * metrics.profit_factor + 0.02 * (metrics.win_rate - 50.0) - dd_penalty

    def _evaluate_symbol(self, series: SymbolSeries, g: StrategyGenome) -> tuple[np.ndarray, list[float]]:
        close = series.close
        n = len(close)
        if n < max(g.trend_ma, g.breakout_lookback, g.bb_period, g.vol_period, g.rsi_period) + g.hold_days + 2:
            return np.array([], dtype=float), []

        rsi = series.rsi(g.rsi_period)
        bb_mid = series.sma(g.bb_period)
        bb_std = series.std(g.bb_period)
        bb_lower = bb_mid - g.bb_std * bb_std
        vol_ma = series.sma(g.vol_period)
        trend_ma = series.sma(g.trend_ma)
        breakout_high = series.breakout_high(g.breakout_lookback)

        vol_ratio = np.divide(series.volume, vol_ma, out=np.full(n, np.nan), where=np.isfinite(vol_ma) & (vol_ma > 0))
        cond_revert = (rsi <= g.rsi_entry) & (close <= bb_lower)
        cond_breakout = close >= breakout_high
        valid = np.isfinite(rsi) & np.isfinite(bb_mid) & np.isfinite(vol_ratio) & np.isfinite(trend_ma)
        entry = (cond_revert | cond_breakout) & (vol_ratio >= g.vol_ratio_min) & (close >= trend_ma) & valid

        position = np.zeros(n, dtype=np.int8)
        trade_returns: list[float] = []

        i = 1
        while i < n - 1:
            if entry[i] and position[i - 1] == 0:
                planned_exit = min(n - 1, i + g.hold_days)
                exit_idx = planned_exit
                j = i + 1
                while j <= planned_exit:
                    rr = close[j] / close[i] - 1.0
                    if rr <= -g.stop_loss or rr >= g.take_profit:
                        exit_idx = j
                        break
                    if np.isfinite(rsi[j]) and rsi[j] >= g.rsi_exit:
                        exit_idx = j
                        break
                    if np.isfinite(bb_mid[j]) and close[j] < bb_mid[j]:
                        exit_idx = j
                        break
                    j += 1

                trade_ret = float(np.clip(close[exit_idx] / close[i] - 1.0, -g.stop_loss, g.take_profit))
                trade_returns.append(trade_ret)
                position[i : exit_idx + 1] = 1
                i = exit_idx + 1
                continue
            i += 1

        daily = np.zeros(n, dtype=float)
        daily[1:] = position[:-1] * series.returns[1:]
        changes = np.abs(np.diff(position, prepend=0))
        daily -= changes * self.transaction_cost
        return daily, trade_returns

    def evaluate(self, genome: StrategyGenome) -> StrategyResult | None:
        all_daily: list[np.ndarray] = []
        all_trades: list[float] = []

        for s in self.universe:
            daily, trades = self._evaluate_symbol(s, genome)
            if daily.size == 0:
                continue
            all_daily.append(daily)
            all_trades.extend(trades)

        if not all_daily or len(all_trades) < 20:
            return None

        max_len = max(len(x) for x in all_daily)
        matrix = np.full((len(all_daily), max_len), np.nan, dtype=float)
        for i, arr in enumerate(all_daily):
            matrix[i, -len(arr) :] = arr
        portfolio_daily = np.nanmean(matrix, axis=0)
        portfolio_daily = portfolio_daily[np.isfinite(portfolio_daily)]

        if len(portfolio_daily) < 40:
            return None

        mu = float(np.mean(portfolio_daily))
        sd = float(np.std(portfolio_daily, ddof=1))
        sharpe = float(np.sqrt(252.0) * mu / sd) if sd > 1e-10 else 0.0

        equity = np.cumprod(1.0 + portfolio_daily)
        peak = np.maximum.accumulate(equity)
        drawdown = equity / peak - 1.0
        max_drawdown = float(np.min(drawdown)) if drawdown.size else 0.0

        years = max(len(portfolio_daily) / 252.0, 1.0 / 252.0)
        cagr = float(equity[-1] ** (1.0 / years) - 1.0) if equity.size else 0.0

        trades_arr = np.asarray(all_trades, dtype=float)
        wins = float(np.sum(trades_arr > 0))
        win_rate = float((wins / len(trades_arr)) * 100.0)
        avg_trade = float(np.mean(trades_arr))
        pos_sum = float(np.sum(trades_arr[trades_arr > 0]))
        neg_sum = float(np.sum(np.abs(trades_arr[trades_arr < 0])))
        profit_factor = float(pos_sum / neg_sum) if neg_sum > 1e-12 else 9.99

        metrics = StrategyMetrics(
            sharpe=sharpe,
            max_drawdown=max_drawdown,
            win_rate=win_rate,
            trades=int(len(trades_arr)),
            cagr=cagr,
            profit_factor=profit_factor,
            avg_trade_return=avg_trade,
        )
        return StrategyResult(genome=genome, metrics=metrics, fitness=self._fitness(metrics))


class LogicExpertAgent:
    """Agent A: Quant strategist / generator."""

    def __init__(self, seed: int):
        self.rng = random.Random(seed)

    def _random_genome(self, intensity: float = 1.0) -> StrategyGenome:
        r = self.rng
        return StrategyGenome(
            rsi_period=r.randint(6, 28),
            rsi_entry=r.uniform(20, 45),
            rsi_exit=r.uniform(52, 78),
            bb_period=r.randint(10, 40),
            bb_std=r.uniform(1.5, 3.0),
            vol_period=r.randint(10, 40),
            vol_ratio_min=r.uniform(0.9, min(3.5, 1.5 + intensity)),
            breakout_lookback=r.randint(10, 60),
            trend_ma=r.randint(20, 120),
            hold_days=r.randint(2, 15),
            stop_loss=r.uniform(0.01, 0.12),
            take_profit=r.uniform(0.02, 0.25),
        )

    def _mutate(self, g: StrategyGenome, intensity: float) -> StrategyGenome:
        r = self.rng
        scale = max(0.5, intensity)

        def jit(v: float, step: float, lo: float, hi: float) -> float:
            return min(hi, max(lo, v + r.uniform(-step, step) * scale))

        out = StrategyGenome(
            rsi_period=int(min(28, max(6, g.rsi_period + r.randint(-3, 3)))),
            rsi_entry=jit(g.rsi_entry, 6.0, 18.0, 48.0),
            rsi_exit=jit(g.rsi_exit, 7.0, 50.0, 85.0),
            bb_period=int(min(45, max(8, g.bb_period + r.randint(-5, 5)))),
            bb_std=jit(g.bb_std, 0.45, 1.2, 3.5),
            vol_period=int(min(50, max(8, g.vol_period + r.randint(-5, 5)))),
            vol_ratio_min=jit(g.vol_ratio_min, 0.6, 0.6, 4.0),
            breakout_lookback=int(min(80, max(8, g.breakout_lookback + r.randint(-8, 8)))),
            trend_ma=int(min(150, max(10, g.trend_ma + r.randint(-12, 12)))),
            hold_days=int(min(25, max(1, g.hold_days + r.randint(-3, 3)))),
            stop_loss=jit(g.stop_loss, 0.03, 0.005, 0.20),
            take_profit=jit(g.take_profit, 0.05, 0.01, 0.40),
        )

        # keep exit above entry
        if out.rsi_exit <= out.rsi_entry + 4:
            out = StrategyGenome(**{**asdict(out), "rsi_exit": min(90.0, out.rsi_entry + 8.0)})
        if out.take_profit <= out.stop_loss:
            out = StrategyGenome(**{**asdict(out), "take_profit": out.stop_loss + 0.02})
        return out

    def _crossover(self, a: StrategyGenome, b: StrategyGenome) -> StrategyGenome:
        r = self.rng
        aa = asdict(a)
        bb = asdict(b)
        child = {k: (aa[k] if r.random() < 0.5 else bb[k]) for k in aa.keys()}
        return StrategyGenome(**child)

    def propose_batch(
        self,
        elites: list[StrategyResult],
        batch_size: int,
        intensity: float,
    ) -> list[StrategyGenome]:
        out: list[StrategyGenome] = []
        seen: set[tuple[Any, ...]] = set()
        elite_genomes = [e.genome for e in elites[:20]]

        while len(out) < batch_size:
            if not elite_genomes:
                g = self._random_genome(intensity)
            else:
                p = self.rng.random()
                if p < 0.35:
                    a, b = self.rng.sample(elite_genomes, 2) if len(elite_genomes) >= 2 else (elite_genomes[0], elite_genomes[0])
                    g = self._mutate(self._crossover(a, b), intensity)
                elif p < 0.85:
                    g = self._mutate(self.rng.choice(elite_genomes), intensity)
                else:
                    g = self._random_genome(intensity)

            k = g.key()
            if k in seen:
                continue
            seen.add(k)
            out.append(g)
        return out


class QAEngineerAgent:
    """Agent B: strict validator / backtester."""

    def __init__(self, backtester: StrategyBacktester):
        self.backtester = backtester

    def validate_batch(self, batch: Iterable[StrategyGenome]) -> tuple[list[StrategyResult], int, int]:
        accepted: list[StrategyResult] = []
        rejected = 0
        errors = 0

        for genome in batch:
            try:
                result = self.backtester.evaluate(genome)
                if result is None:
                    rejected += 1
                    continue
                if result.metrics.max_drawdown < -0.15:
                    rejected += 1
                    continue
                if result.metrics.win_rate < 55.0:
                    rejected += 1
                    continue
                accepted.append(result)
            except Exception:
                errors += 1

        accepted.sort(key=lambda x: (x.metrics.sharpe, x.fitness), reverse=True)
        return accepted, rejected, errors


class LeadDeveloperAgent:
    """Agent C: persistence, fault tolerance, execution hygiene."""

    def __init__(self, output_path: Path, top_keep: int = 30):
        self.output_path = output_path
        self.top_keep = top_keep
        self.best_by_key: dict[tuple[Any, ...], StrategyResult] = {}

    def update_and_persist(
        self,
        candidates: list[StrategyResult],
        iteration: int,
        elapsed_seconds: float,
        metadata: dict[str, Any],
    ) -> None:
        try:
            for c in candidates[:10]:
                k = c.genome.key()
                cur = self.best_by_key.get(k)
                if cur is None or c.metrics.sharpe > cur.metrics.sharpe:
                    self.best_by_key[k] = c

            ranked = sorted(self.best_by_key.values(), key=lambda x: (x.metrics.sharpe, x.fitness), reverse=True)[
                : self.top_keep
            ]
            payload = {
                "updated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                "iteration": iteration,
                "elapsed_seconds": round(elapsed_seconds, 2),
                "metadata": metadata,
                "strategies": [
                    {
                        "rank": idx + 1,
                        "fitness": round(s.fitness, 6),
                        "metrics": {
                            "sharpe": round(s.metrics.sharpe, 6),
                            "max_drawdown": round(s.metrics.max_drawdown, 6),
                            "win_rate": round(s.metrics.win_rate, 4),
                            "trades": s.metrics.trades,
                            "cagr": round(s.metrics.cagr, 6),
                            "profit_factor": round(s.metrics.profit_factor, 6),
                            "avg_trade_return": round(s.metrics.avg_trade_return, 6),
                        },
                        "params": asdict(s.genome),
                    }
                    for idx, s in enumerate(ranked)
                ],
            }
            self.output_path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.output_path.with_suffix(".tmp")
            tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
            tmp.replace(self.output_path)
        except Exception as exc:
            print(f"[Agent C] persist warning: {exc}")


class ProjectManagerAgent:
    """Agent D: runtime / progress / mutation control."""

    def __init__(self, runtime_seconds: float, report_every_seconds: float = 8.0):
        self.runtime_seconds = runtime_seconds
        self.report_every_seconds = report_every_seconds
        self._last_report_ts = 0.0

    def should_continue(self, start_ts: float) -> bool:
        return (time.time() - start_ts) < self.runtime_seconds

    def mutation_intensity(self, iteration: int, last_improve_iter: int) -> float:
        stagnation = iteration - last_improve_iter
        if stagnation < 40:
            return 1.0
        if stagnation < 120:
            return 1.5
        if stagnation < 240:
            return 2.3
        return 3.2

    def maybe_report(
        self,
        start_ts: float,
        iteration: int,
        best: StrategyResult | None,
        accepted: int,
        rejected: int,
        errors: int,
        intensity: float,
    ) -> None:
        now = time.time()
        if now - self._last_report_ts < self.report_every_seconds:
            return
        self._last_report_ts = now
        elapsed = now - start_ts
        if best is None:
            print(
                f"[PM] iter={iteration} elapsed={elapsed:7.1f}s accepted={accepted} "
                f"rejected={rejected} errors={errors} intensity={intensity:.2f} best=NONE"
            )
            return
        m = best.metrics
        print(
            f"[PM] iter={iteration} elapsed={elapsed:7.1f}s accepted={accepted} rejected={rejected} "
            f"errors={errors} intensity={intensity:.2f} best_sharpe={m.sharpe:.3f} "
            f"wr={m.win_rate:.1f}% mdd={m.max_drawdown:.3f} trades={m.trades}"
        )


class AutoQuantSquad:
    def __init__(
        self,
        data_dir: Path,
        output_path: Path,
        start_date: str = "2021-01-01",
        end_date: str = "2025-12-31",
        runtime_minutes: float = 60.0,
        batch_size: int = 48,
        max_symbols: int = 120,
        max_scan_files: int = 1200,
        min_bars: int = 400,
        seed: int = 7,
        allow_date_fallback: bool = True,
    ):
        self.runtime_minutes = runtime_minutes
        self.batch_size = batch_size
        self.seed = seed
        self.data_store = DataStore(
            data_dir=data_dir,
            start_date=start_date,
            end_date=end_date,
            min_bars=min_bars,
            max_symbols=max_symbols,
            max_scan_files=max_scan_files,
            seed=seed,
            allow_date_fallback=allow_date_fallback,
        )
        self.universe = self.data_store.load()
        backtester = StrategyBacktester(self.universe)
        self.agent_a = LogicExpertAgent(seed=seed)
        self.agent_b = QAEngineerAgent(backtester=backtester)
        self.agent_c = LeadDeveloperAgent(output_path=output_path)
        self.agent_d = ProjectManagerAgent(runtime_seconds=runtime_minutes * 60.0)

    def run(self) -> StrategyResult | None:
        if not self.universe:
            print("[AutoQuantSquad] No usable symbols loaded. Exiting safely.")
            return None

        print("[AutoQuantSquad] Command center online. Mission: maximize Sharpe under strict QA gates.")
        start_ts = time.time()
        iteration = 0
        elites: list[StrategyResult] = []
        best: StrategyResult | None = None
        last_improve_iter = 0

        while self.agent_d.should_continue(start_ts):
            iteration += 1
            try:
                intensity = self.agent_d.mutation_intensity(iteration=iteration, last_improve_iter=last_improve_iter)
                batch = self.agent_a.propose_batch(elites=elites, batch_size=self.batch_size, intensity=intensity)
                accepted, rejected, errors = self.agent_b.validate_batch(batch)

                if accepted:
                    elites = sorted(elites + accepted, key=lambda x: (x.metrics.sharpe, x.fitness), reverse=True)[:30]
                    if best is None or accepted[0].metrics.sharpe > best.metrics.sharpe:
                        best = accepted[0]
                        last_improve_iter = iteration

                elapsed = time.time() - start_ts
                self.agent_c.update_and_persist(
                    candidates=accepted,
                    iteration=iteration,
                    elapsed_seconds=elapsed,
                    metadata={
                        "runtime_minutes": self.runtime_minutes,
                        "batch_size": self.batch_size,
                        "universe_size": len(self.universe),
                        "seed": self.seed,
                    },
                )
                self.agent_d.maybe_report(
                    start_ts=start_ts,
                    iteration=iteration,
                    best=best,
                    accepted=len(accepted),
                    rejected=rejected,
                    errors=errors,
                    intensity=intensity,
                )
            except Exception as exc:
                print(f"[AutoQuantSquad] iteration={iteration} recovered from exception: {exc}")
                continue

        if best is None:
            print("[AutoQuantSquad] No valid strategy passed QA gates.")
            return None

        m = best.metrics
        print(
            "[AutoQuantSquad] Mission complete | "
            f"Sharpe={m.sharpe:.4f}, WinRate={m.win_rate:.2f}%, MDD={m.max_drawdown:.4f}, "
            f"Trades={m.trades}, CAGR={m.cagr:.4f}"
        )
        return best


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Multi-Agent AutoQuant command center")
    parser.add_argument("--data-dir", default="data", help="Directory containing OHLCV CSV files")
    parser.add_argument("--output", default="best_logic.json", help="Output JSON path")
    parser.add_argument("--start-date", default="2021-01-01", help="Backtest start date (YYYY-MM-DD)")
    parser.add_argument("--end-date", default="2025-12-31", help="Backtest end date (YYYY-MM-DD)")
    parser.add_argument("--runtime-minutes", type=float, default=60.0, help="Run time budget in minutes")
    parser.add_argument("--batch-size", type=int, default=48, help="Population per iteration")
    parser.add_argument("--max-symbols", type=int, default=120, help="Max symbols kept in active universe")
    parser.add_argument("--max-scan-files", type=int, default=1200, help="Max CSV files scanned at load stage")
    parser.add_argument("--min-bars", type=int, default=400, help="Minimum bars required per symbol")
    parser.add_argument("--seed", type=int, default=7, help="Random seed")
    parser.add_argument(
        "--allow-date-fallback",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Fallback to full history if target date range has insufficient data (default: enabled)",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    squad = AutoQuantSquad(
        data_dir=Path(args.data_dir),
        output_path=Path(args.output),
        start_date=args.start_date,
        end_date=args.end_date,
        runtime_minutes=args.runtime_minutes,
        batch_size=args.batch_size,
        max_symbols=args.max_symbols,
        max_scan_files=args.max_scan_files,
        min_bars=args.min_bars,
        seed=args.seed,
        allow_date_fallback=args.allow_date_fallback,
    )
    squad.run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
