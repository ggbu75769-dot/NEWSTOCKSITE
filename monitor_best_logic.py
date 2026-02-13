#!/usr/bin/env python3
"""Monitor best_logic.json and write periodic summaries."""

from __future__ import annotations

import argparse
import json
import subprocess
import time
from datetime import datetime
from pathlib import Path
from typing import Any


def is_pid_alive(pid: int) -> bool:
    try:
        result = subprocess.run(
            ["tasklist", "/FI", f"PID eq {pid}"],
            capture_output=True,
            text=True,
            check=False,
        )
        text = (result.stdout or "").lower()
        return str(pid) in text and "no tasks are running" not in text
    except Exception:
        return True


def _f(v: Any, nd: int = 3) -> str:
    try:
        x = float(v)
        return f"{x:.{nd}f}"
    except Exception:
        return "-"


def build_summary(payload: dict[str, Any], now: str) -> str:
    iteration = payload.get("iteration", "-")
    elapsed = payload.get("elapsed_seconds", "-")
    updated_at = payload.get("updated_at", "-")
    strategies = payload.get("strategies") or []
    count = len(strategies)

    if count > 0:
        best = strategies[0]
        m = best.get("metrics", {})
        return (
            f"[{now}] updated_at={updated_at} iter={iteration} elapsed={elapsed}s "
            f"strategies={count} best_sharpe={_f(m.get('sharpe'))} "
            f"win_rate={_f(m.get('win_rate'), 2)}% mdd={_f(m.get('max_drawdown'))} "
            f"cagr={_f(m.get('cagr'))} trades={m.get('trades', '-')}"
        )

    return f"[{now}] updated_at={updated_at} iter={iteration} elapsed={elapsed}s strategies=0 (no survivor yet)"


def run_monitor(json_path: Path, out_path: Path, interval_sec: int, pid: int | None) -> int:
    out_path.parent.mkdir(parents=True, exist_ok=True)

    while True:
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        if json_path.exists():
            try:
                payload = json.loads(json_path.read_text(encoding="utf-8"))
                line = build_summary(payload, now)
            except Exception as exc:
                line = f"[{now}] parse_error={exc}"
        else:
            line = f"[{now}] waiting_for_file={json_path}"

        print(line, flush=True)
        with out_path.open("a", encoding="utf-8") as f:
            f.write(line + "\n")

        if pid is not None and not is_pid_alive(pid):
            end_line = f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] target_pid={pid} ended; monitor stop"
            print(end_line, flush=True)
            with out_path.open("a", encoding="utf-8") as f:
                f.write(end_line + "\n")
            return 0

        time.sleep(max(5, interval_sec))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Monitor best_logic.json")
    parser.add_argument("--json", required=True, help="Path to best_logic json")
    parser.add_argument("--out", required=True, help="Path to append summary log")
    parser.add_argument("--interval-sec", type=int, default=600, help="Summary interval in seconds")
    parser.add_argument("--pid", type=int, default=None, help="Target process id to watch")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    return run_monitor(
        json_path=Path(args.json),
        out_path=Path(args.out),
        interval_sec=args.interval_sec,
        pid=args.pid,
    )


if __name__ == "__main__":
    raise SystemExit(main())
