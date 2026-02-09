# Visual Stock - Daily Analysis Job
# Requirements: pandas, yfinance, supabase
# pip install pandas yfinance supabase

import os
from datetime import datetime, timedelta
from typing import List, Dict

import pandas as pd
import yfinance as yf
from supabase import create_client, Client

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_SERVICE_ROLE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")

TICKERS = os.environ.get("VS_TICKERS", "AAPL,MSFT,NVDA,AMZN,GOOGL,META,TSLA,JPM,JNJ,XOM,AVGO,UNH,V,MA,PG,HD,LLY,KO,PEP,COST").split(",")
LOOKBACK_YEARS = int(os.environ.get("VS_LOOKBACK_YEARS", "10"))
HOLD_DAYS = int(os.environ.get("VS_HOLD_DAYS", "7"))
TOP_N = int(os.environ.get("VS_TOP_N", "3"))


def rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = -delta.where(delta < 0, 0.0)
    avg_gain = gain.rolling(period).mean()
    avg_loss = loss.rolling(period).mean()
    rs = avg_gain / avg_loss.replace(0, pd.NA)
    return 100 - (100 / (1 + rs))


def macd(series: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> pd.DataFrame:
    ema_fast = series.ewm(span=fast, adjust=False).mean()
    ema_slow = series.ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    hist = macd_line - signal_line
    return pd.DataFrame({"macd": macd_line, "signal": signal_line, "hist": hist})


def seasonality_win_rate(df: pd.DataFrame, month: int, day: int, hold_days: int) -> float:
    if df.empty:
        return 0.0
    df = df.copy()
    df["date"] = df.index.date
    df["year"] = df.index.year

    wins = 0
    total = 0

    for year in df["year"].unique():
        try:
            target_date = datetime(year, month, day).date()
        except ValueError:
            # Skip invalid dates (e.g., Feb 29 on non-leap years)
            continue

        if target_date not in df["date"].values:
            # Find next trading day after the target date
            next_row = df[df["date"] > target_date].head(1)
            if next_row.empty:
                continue
            entry_idx = next_row.index[0]
        else:
            entry_idx = df[df["date"] == target_date].index[0]

        entry_pos = df.index.get_loc(entry_idx)
        exit_pos = entry_pos + hold_days
        if exit_pos >= len(df):
            continue

        entry_price = df.iloc[entry_pos]["Close"]
        exit_price = df.iloc[exit_pos]["Close"]
        total += 1
        if exit_price > entry_price:
            wins += 1

    if total == 0:
        return 0.0
    return round((wins / total) * 100, 2)


def analyze_ticker(ticker: str, month: int, day: int) -> Dict:
    end = datetime.utcnow().date()
    start = end - timedelta(days=LOOKBACK_YEARS * 365)

    data = yf.download(ticker, start=start.isoformat(), end=end.isoformat(), auto_adjust=True, progress=False)
    if data.empty:
        return {
            "ticker": ticker,
            "win_rate": 0.0,
            "avg_return": 0.0,
            "confluence_score": 0.0,
        }

    data = data.dropna()
    win_rate = seasonality_win_rate(data, month, day, HOLD_DAYS)

    # Average return for the same setup
    returns = []
    data_dates = pd.Series(data.index.date)
    for year in data.index.year.unique():
        try:
            target_date = datetime(year, month, day).date()
        except ValueError:
            continue

        if target_date not in data_dates.values:
            next_row = data[data_dates > target_date].head(1)
            if next_row.empty:
                continue
            entry_idx = next_row.index[0]
        else:
            entry_idx = data[data_dates == target_date].index[0]

        entry_pos = data.index.get_loc(entry_idx)
        exit_pos = entry_pos + HOLD_DAYS
        if exit_pos >= len(data):
            continue

        entry_price = data.iloc[entry_pos]["Close"]
        exit_price = data.iloc[exit_pos]["Close"]
        returns.append((exit_price - entry_price) / entry_price * 100)

    avg_return = round(float(pd.Series(returns).mean()) if returns else 0.0, 2)

    close = data["Close"]
    latest_rsi = float(rsi(close).iloc[-1]) if len(close) >= 15 else 50.0
    macd_df = macd(close)
    macd_bullish = macd_df.iloc[-1]["hist"] > 0

    confluence = win_rate
    if latest_rsi < 30:
        confluence += 5
    if macd_bullish:
        confluence += 5

    return {
        "ticker": ticker,
        "win_rate": round(win_rate, 2),
        "avg_return": avg_return,
        "confluence_score": round(confluence, 2),
    }


def get_supabase_client() -> Client:
    if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
        raise RuntimeError("Missing SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY")
    return create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)


def upsert_rankings(results: List[Dict], ranking_date: str):
    supabase = get_supabase_client()
    payload = []
    for i, item in enumerate(results, start=1):
        payload.append({
            "ranking_date": ranking_date,
            "rank": i,
            "ticker": item["ticker"],
            "win_rate": item["win_rate"],
            "avg_return": item["avg_return"],
            "confluence_score": item["confluence_score"],
        })

    supabase.table("daily_rankings").upsert(payload, on_conflict="ranking_date,rank").execute()


if __name__ == "__main__":
    today = datetime.utcnow().date()
    month, day = today.month, today.day

    analyses = []
    for t in TICKERS:
        try:
            analyses.append(analyze_ticker(t.strip(), month, day))
        except Exception:
            # Skip ticker on error, but keep job running
            continue

    analyses = sorted(analyses, key=lambda x: x["confluence_score"], reverse=True)[:TOP_N]
    upsert_rankings(analyses, today.isoformat())
    print(f"Upserted {len(analyses)} rankings for {today.isoformat()}")
