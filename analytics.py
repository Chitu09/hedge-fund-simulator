"""
analytics.py
------------
Performance metrics, walk-forward validation, and risk decomposition.
"""

import numpy as np
import pandas as pd
from scipy import stats
from data import RF_DAILY


# ══════════════════════════════════════════════════════════════════════════════
# PERFORMANCE METRICS
# ══════════════════════════════════════════════════════════════════════════════

def compute_metrics(ret_series: pd.Series,
                    bench_ret: pd.Series = None,
                    rf_daily: float = RF_DAILY) -> dict:
    """
    Full suite of hedge fund performance metrics.

    Returns dict with keys ready for display in a Streamlit table.
    """
    r   = ret_series.dropna()
    ann = 252

    if len(r) < 20:
        return {}

    # ── Return metrics ────────────────────────────────────────────────────────
    total_ret = float((1 + r).prod() - 1)
    ann_ret   = float((1 + r).prod() ** (ann / len(r)) - 1)
    ann_vol   = float(r.std() * np.sqrt(ann))
    excess    = r.mean() - rf_daily
    sharpe    = float(excess / r.std() * np.sqrt(ann)) if r.std() > 0 else 0.0

    # ── Downside risk ─────────────────────────────────────────────────────────
    down_ret  = r[r < rf_daily]
    sortino   = float(excess / down_ret.std() * np.sqrt(ann)) if len(down_ret) > 1 else np.nan

    # ── Drawdown ──────────────────────────────────────────────────────────────
    cum      = (1 + r).cumprod()
    peak     = cum.cummax()
    dd       = (cum - peak) / peak
    max_dd   = float(dd.min())
    calmar   = float(ann_ret / abs(max_dd)) if max_dd != 0 else np.nan

    # Max drawdown duration (consecutive days underwater)
    in_dd, dur, max_dur = False, 0, 0
    for v in (dd < 0):
        dur = dur + 1 if v else 0
        max_dur = max(max_dur, dur)

    # ── Distribution ──────────────────────────────────────────────────────────
    skew   = float(stats.skew(r))
    kurt   = float(stats.kurtosis(r))
    var95  = float(np.percentile(r, 5))
    cvar95 = float(r[r <= var95].mean())

    # ── Trade stats ───────────────────────────────────────────────────────────
    hit_rate = float((r > 0).mean())
    wins     = r[r > 0].sum()
    losses   = abs(r[r < 0].sum())
    pf       = float(wins / losses) if losses > 0 else np.inf

    # ── Market exposure ───────────────────────────────────────────────────────
    beta_val, alpha_val = np.nan, np.nan
    if bench_ret is not None and len(bench_ret) > 20:
        b  = bench_ret.reindex(r.index).dropna()
        ra = r.reindex(b.index)
        if len(b) > 10:
            beta_val  = float(np.cov(ra, b)[0, 1] / np.var(b))
            alpha_val = float((ra.mean() - rf_daily - beta_val * (b.mean() - rf_daily)) * ann)

    return {
        "Total Return":        total_ret,
        "Ann. Return (CAGR)":  ann_ret,
        "Ann. Volatility":     ann_vol,
        "Sharpe Ratio":        sharpe,
        "Sortino Ratio":       sortino,
        "Calmar Ratio":        calmar,
        "Max Drawdown":        max_dd,
        "Max DD Duration (d)": max_dur,
        "Skewness":            skew,
        "Excess Kurtosis":     kurt,
        "VaR 95% (daily)":     var95,
        "CVaR 95% (daily)":    cvar95,
        "Hit Rate":            hit_rate,
        "Profit Factor":       pf,
        "Beta vs NIFTY":       beta_val,
        "Alpha (ann.)":        alpha_val,
    }


def format_metrics(metrics: dict) -> pd.Series:
    """Formats raw metric values into display strings."""
    pct_keys  = {"Total Return", "Ann. Return (CAGR)", "Ann. Volatility",
                 "Max Drawdown", "VaR 95% (daily)", "CVaR 95% (daily)",
                 "Hit Rate", "Alpha (ann.)"}
    int_keys  = {"Max DD Duration (d)"}
    two_dec   = {"Sharpe Ratio", "Sortino Ratio", "Calmar Ratio",
                 "Skewness", "Excess Kurtosis", "Beta vs NIFTY", "Profit Factor"}

    out = {}
    for k, v in metrics.items():
        if v is None or (isinstance(v, float) and np.isnan(v)):
            out[k] = "N/A"
        elif k in pct_keys:
            out[k] = f"{v:.2%}"
        elif k in int_keys:
            out[k] = str(int(v))
        elif k in two_dec:
            out[k] = "∞" if np.isinf(v) else f"{v:.2f}"
        else:
            out[k] = f"{v:.4f}"
    return pd.Series(out, name="Value")


def build_metrics_table(all_returns: pd.DataFrame, bench_ret: pd.Series) -> pd.DataFrame:
    """Build a wide metrics table for all strategies + benchmark."""
    rows = {}
    for col in all_returns.columns:
        raw = compute_metrics(all_returns[col], bench_ret)
        rows[col] = format_metrics(raw)
    bench_raw    = compute_metrics(bench_ret, bench_ret)
    rows["NIFTY 50"] = format_metrics(bench_raw)
    return pd.DataFrame(rows)


# ══════════════════════════════════════════════════════════════════════════════
# WALK-FORWARD VALIDATION
# ══════════════════════════════════════════════════════════════════════════════

def walk_forward(strat_ret: pd.Series,
                 train_months: int = 18,
                 test_months: int = 6) -> pd.DataFrame:
    """
    Rolling walk-forward: train on 'train_months', test on next 'test_months'.
    Returns DataFrame with IS / OOS Sharpe and returns per fold.
    """
    results = []
    periods = pd.period_range(
        pd.Timestamp(strat_ret.index[0]).to_period("M") + train_months,
        pd.Timestamp(strat_ret.index[-1]).to_period("M") - test_months,
        freq="M",
    )

    def sharpe(r):
        return float((r.mean() - RF_DAILY) / r.std() * np.sqrt(252)) if r.std() > 0 else 0.0

    for fold_start in periods:
        is_r = strat_ret[
            (strat_ret.index >= (fold_start - train_months).start_time) &
            (strat_ret.index <  fold_start.start_time)
        ]
        oos_r = strat_ret[
            (strat_ret.index >= fold_start.start_time) &
            (strat_ret.index <  (fold_start + test_months).start_time)
        ]
        if len(is_r) < 40 or len(oos_r) < 10:
            continue

        results.append({
            "Period":         str(fold_start),
            "IS Sharpe":      round(sharpe(is_r),  2),
            "OOS Sharpe":     round(sharpe(oos_r), 2),
            "IS Ann. Return": f"{(1+is_r).prod()**(12/train_months)-1:.2%}",
            "OOS Ann. Return":f"{(1+oos_r).prod()**(12/test_months)-1:.2%}",
        })

    return pd.DataFrame(results)


# ══════════════════════════════════════════════════════════════════════════════
# RISK DECOMPOSITION
# ══════════════════════════════════════════════════════════════════════════════

def marginal_risk_contribution(weights: np.ndarray, cov: np.ndarray) -> np.ndarray:
    """
    Compute % risk contribution of each strategy to total portfolio risk.
    Returns array summing to 1.0.
    """
    w   = np.array(weights)
    sig = np.sqrt(float(w @ cov @ w))
    if sig < 1e-10:
        return np.ones(len(w)) / len(w)
    mrc = (cov @ w) / sig
    prc = w * mrc
    return prc / prc.sum() if prc.sum() > 0 else prc


def drawdown_series(ret: pd.Series) -> pd.Series:
    cum  = (1 + ret.dropna()).cumprod()
    peak = cum.cummax()
    return (cum - peak) / peak
