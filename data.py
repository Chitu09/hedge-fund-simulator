"""
data.py
-------
Downloads and cleans real NSE stock data via Yahoo Finance.
All prices are split-adjusted and dividend-adjusted closing prices.
"""

import yfinance as yf
import pandas as pd
import numpy as np
import streamlit as st

# ── Universe ──────────────────────────────────────────────────────────────────
NSE_TICKERS = {
    "RELIANCE.NS":    "Energy",
    "TCS.NS":         "IT",
    "INFY.NS":        "IT",
    "HDFCBANK.NS":    "Banking",
    "ICICIBANK.NS":   "Banking",
    "AXISBANK.NS":    "Banking",
    "SBIN.NS":        "Banking",
    "WIPRO.NS":       "IT",
    "HCLTECH.NS":     "IT",
    "BHARTIARTL.NS":  "Telecom",
    "ITC.NS":         "FMCG",
    "HINDUNILVR.NS":  "FMCG",
    "BAJFINANCE.NS":  "NBFC",
    "KOTAKBANK.NS":   "Banking",
    "LT.NS":          "Infra",
    "ASIANPAINT.NS":  "Consumer",
    "MARUTI.NS":      "Auto",
    "TATAMOTORS.NS":  "Auto",
    "SUNPHARMA.NS":   "Pharma",
    "DRREDDY.NS":     "Pharma",
}

BENCHMARK_TICKER = "^NSEI"
RF_ANNUAL        = 0.065   # RBI repo rate proxy
RF_DAILY         = RF_ANNUAL / 252

SECTOR_MAP = {k.replace(".NS", ""): v for k, v in NSE_TICKERS.items()}


@st.cache_data(show_spinner=False, ttl=3600)
def load_data(start_date: str, end_date: str):
    """
    Downloads adjusted close prices for all NSE tickers + NIFTY 50 benchmark.
    Cleans: drops >10% missing, forward-fills up to 5 days, drops remaining NaN rows.
    Returns: prices (DataFrame), benchmark (Series), returns (DataFrame), bench_ret (Series)
    """
    tickers = list(NSE_TICKERS.keys()) + [BENCHMARK_TICKER]

    raw = yf.download(
        tickers,
        start=start_date,
        end=end_date,
        auto_adjust=True,
        progress=False,
    )["Close"]

    raw.index = pd.to_datetime(raw.index)

    # Flatten MultiIndex columns if present
    if isinstance(raw.columns, pd.MultiIndex):
        raw.columns = [c[0] if isinstance(c, tuple) else c for c in raw.columns]

    # Separate benchmark
    benchmark_raw = raw[BENCHMARK_TICKER].copy()
    raw = raw.drop(columns=[BENCHMARK_TICKER], errors="ignore")

    # Remove .NS suffix
    raw.columns = [c.replace(".NS", "") for c in raw.columns]

    # Drop stocks with >10% missing
    missing_pct = raw.isna().mean()
    drop_cols   = missing_pct[missing_pct > 0.10].index.tolist()
    if drop_cols:
        raw = raw.drop(columns=drop_cols)

    # Forward fill (exchange holidays / halts) then drop remaining NaN
    prices    = raw.ffill(limit=5).dropna()
    benchmark = benchmark_raw.reindex(prices.index).ffill().dropna()
    prices    = prices.reindex(benchmark.index).dropna()

    returns   = prices.pct_change().dropna()
    bench_ret = benchmark.pct_change().dropna()

    # Align all to common index
    common    = returns.index.intersection(bench_ret.index)
    returns   = returns.loc[common]
    bench_ret = bench_ret.loc[common]
    prices    = prices.loc[common]
    benchmark = benchmark.loc[common]

    return prices, benchmark, returns, bench_ret
