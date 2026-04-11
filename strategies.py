"""
strategies.py
-------------
Four hedge fund strategy implementations.
All strategies use only past data at each decision point — zero look-ahead bias.
"""

import numpy as np
import pandas as pd
from itertools import combinations
from data import SECTOR_MAP

try:
    from statsmodels.tsa.stattools import coint
    HAS_STATSMODELS = True
except ImportError:
    HAS_STATSMODELS = False


# ══════════════════════════════════════════════════════════════════════════════
# STRATEGY 1 — CROSS-SECTIONAL MOMENTUM
# ══════════════════════════════════════════════════════════════════════════════

def strategy_momentum(prices: pd.DataFrame,
                      returns: pd.DataFrame,
                      lookback: int = 252,
                      skip: int = 21,
                      top_pct: float = 0.20) -> tuple[pd.Series, pd.DataFrame]:
    """
    Cross-sectional momentum: long top X%, short bottom X% by 12-1m return.

    Parameters
    ----------
    lookback : trading days for momentum window (default 252 = ~1 year)
    skip     : days to skip at end to avoid short-term reversal (default 21 = ~1 month)
    top_pct  : fraction of universe to hold long/short (default 0.20 = top/bottom 20%)

    Returns
    -------
    (daily_pnl Series, weights DataFrame)
    """
    rebal_dates = prices.resample("ME").last().index
    weights_ts  = pd.DataFrame(0.0, index=prices.index, columns=prices.columns)

    for i in range(1, len(rebal_dates) - 1):
        rd  = rebal_dates[i]
        idx = prices.index.get_indexer([rd], method="ffill")[0]

        if idx < lookback + skip:
            continue

        # 12-1 month return: end price is 'skip' days before today
        p_end   = prices.iloc[idx - skip]
        p_start = prices.iloc[idx - lookback]
        mom     = (p_end / p_start) - 1.0

        rank    = mom.rank()
        n       = len(rank)
        q       = max(1, int(n * top_pct))

        long_mask  = rank >= (n - q + 1)
        short_mask = rank <= q

        w = pd.Series(0.0, index=prices.columns)
        if long_mask.sum() > 0:
            w[long_mask]  =  1.0 / long_mask.sum()
        if short_mask.sum() > 0:
            w[short_mask] = -1.0 / short_mask.sum()

        next_rd = rebal_dates[i + 1]
        mask    = (prices.index > rd) & (prices.index <= next_rd)
        weights_ts.loc[mask] = w.values

    pnl = (weights_ts.shift(1) * returns).sum(axis=1)
    return pnl.rename("Momentum"), weights_ts


# ══════════════════════════════════════════════════════════════════════════════
# STRATEGY 2 — MEAN REVERSION
# ══════════════════════════════════════════════════════════════════════════════

def strategy_mean_reversion(prices: pd.DataFrame,
                             returns: pd.DataFrame,
                             window: int = 20,
                             z_entry: float = 1.5) -> tuple[pd.Series, pd.DataFrame, pd.DataFrame]:
    """
    Bollinger Band z-score mean reversion.

    Parameters
    ----------
    window  : rolling window for mean/std (default 20 days)
    z_entry : z-score threshold to enter a trade (default 1.5σ)

    Returns
    -------
    (daily_pnl Series, weights DataFrame, z_scores DataFrame)
    """
    roll_mean = prices.rolling(window).mean()
    roll_std  = prices.rolling(window).std()
    z_score   = (prices - roll_mean) / roll_std.replace(0, np.nan)

    # Signal: negative of z-score (buy cheap / sell expensive)
    raw_signal = -z_score.copy()
    raw_signal[z_score.abs() < z_entry] = 0.0   # dead-band filter

    long_s    = raw_signal.clip(lower=0)
    short_s   = raw_signal.clip(upper=0)
    long_sum  = long_s.sum(axis=1).replace(0, np.nan)
    short_sum = (-short_s).sum(axis=1).replace(0, np.nan)

    weights = pd.DataFrame(0.0, index=prices.index, columns=prices.columns)
    weights[raw_signal > 0] = long_s.div(long_sum, axis=0)[raw_signal > 0]
    weights[raw_signal < 0] = short_s.div(short_sum, axis=0)[raw_signal < 0]
    weights = weights.fillna(0)

    pnl = (weights.shift(1) * returns).sum(axis=1)
    return pnl.rename("MeanReversion"), weights, z_score


# ══════════════════════════════════════════════════════════════════════════════
# STRATEGY 3 — STATISTICAL ARBITRAGE (PAIRS TRADING)
# ══════════════════════════════════════════════════════════════════════════════

def find_cointegrated_pairs(prices_is: pd.DataFrame,
                             pvalue_thresh: float = 0.10) -> pd.DataFrame:
    """
    Engle-Granger cointegration test on same-sector pairs (in-sample only).
    Uses statsmodels.tsa.stattools.coint.

    Returns DataFrame with columns: StockA, StockB, HedgeRatio, Intercept, PValue
    """
    pairs = []

    for a, b in combinations(prices_is.columns, 2):
        if SECTOR_MAP.get(a) != SECTOR_MAP.get(b):
            continue

        log_a = np.log(prices_is[a].dropna())
        log_b = np.log(prices_is[b].dropna())
        idx   = log_a.index.intersection(log_b.index)
        log_a, log_b = log_a[idx], log_b[idx]

        if len(log_a) < 60:
            continue

        try:
            if HAS_STATSMODELS:
                _, pval, _ = coint(log_a, log_b)
            else:
                # Lightweight fallback ADF on OLS residuals
                X    = np.column_stack([np.ones(len(log_b)), log_b.values])
                beta = np.linalg.lstsq(X, log_a.values, rcond=None)[0]
                resid = log_a.values - X @ beta
                dy, yl = np.diff(resid), resid[:-1]
                Xr = np.column_stack([np.ones(len(yl)), yl])
                br = np.linalg.lstsq(Xr, dy, rcond=None)[0]
                err = dy - Xr @ br
                se  = np.sqrt(np.sum(err**2) / max(len(err)-2, 1) *
                              np.linalg.inv(Xr.T @ Xr)[1, 1])
                t   = br[1] / max(se, 1e-12)
                pval = 0.01 if t < -3.5 else (0.05 if t < -2.9 else 0.11)
        except Exception:
            continue

        if pval < pvalue_thresh:
            X    = np.column_stack([np.ones(len(log_b)), log_b.values])
            beta = np.linalg.lstsq(X, log_a.values, rcond=None)[0]
            pairs.append({
                "StockA":      a,
                "StockB":      b,
                "HedgeRatio":  round(float(beta[1]), 4),
                "Intercept":   round(float(beta[0]), 4),
                "PValue":      round(float(pval), 4),
                "Sector":      SECTOR_MAP.get(a, "—"),
            })

    if pairs:
        return pd.DataFrame(pairs).sort_values("PValue").reset_index(drop=True)
    return pd.DataFrame(columns=["StockA", "StockB", "HedgeRatio", "Intercept", "PValue", "Sector"])


def strategy_stat_arb(prices: pd.DataFrame,
                      returns: pd.DataFrame,
                      pairs_df: pd.DataFrame,
                      z_entry: float = 1.5,
                      z_exit: float = 0.3,
                      window: int = 60) -> tuple[pd.Series, dict]:
    """
    Pairs trading on cointegrated pairs found in-sample.
    Spread = log(A) - hedge_ratio * log(B) - intercept.

    Parameters
    ----------
    z_entry : z-score to enter trade
    z_exit  : z-score to exit trade
    window  : rolling window for spread normalisation (days)
    """
    daily_pnl  = pd.Series(0.0, index=returns.index)
    spread_data = {}

    if pairs_df.empty:
        return daily_pnl.rename("StatArb"), spread_data

    n_pairs = len(pairs_df)

    for _, row in pairs_df.iterrows():
        a, b   = row["StockA"], row["StockB"]
        hr     = row["HedgeRatio"]
        intcpt = row["Intercept"]

        if a not in prices.columns or b not in prices.columns:
            continue

        log_a  = np.log(prices[a])
        log_b  = np.log(prices[b])
        spread = log_a - hr * log_b - intcpt

        roll_m = spread.rolling(window).mean()
        roll_s = spread.rolling(window).std().replace(0, np.nan)
        z      = (spread - roll_m) / roll_s

        spread_data[f"{a} / {b}"] = z

        pos_a = pd.Series(0.0, index=prices.index)
        pos_b = pd.Series(0.0, index=prices.index)
        pos   = 0

        for t in range(1, len(z)):
            zt = z.iloc[t - 1]
            if np.isnan(zt):
                continue
            if pos == 0:
                if zt >  z_entry:   pos = -1
                elif zt < -z_entry: pos =  1
            elif pos ==  1 and zt > -z_exit: pos = 0
            elif pos == -1 and zt <  z_exit: pos = 0

            w = 1.0 / n_pairs
            pos_a.iloc[t] =  pos * w
            pos_b.iloc[t] = -pos * hr * w

        r_a = returns[a]
        r_b = returns[b]
        pnl_ab = (
            pos_a.shift(1).reindex(returns.index, fill_value=0) * r_a +
            pos_b.shift(1).reindex(returns.index, fill_value=0) * r_b
        ).fillna(0)
        daily_pnl = daily_pnl.add(pnl_ab, fill_value=0)

    return daily_pnl.rename("StatArb"), spread_data


# ══════════════════════════════════════════════════════════════════════════════
# STRATEGY 4 — VOLATILITY TARGETING (RISK PARITY)
# ══════════════════════════════════════════════════════════════════════════════

def strategy_vol_target(prices: pd.DataFrame,
                        returns: pd.DataFrame,
                        vol_window: int = 63,
                        target_vol: float = 0.10,
                        max_leverage: float = 1.5) -> tuple[pd.Series, pd.DataFrame]:
    """
    Inverse-volatility weighted portfolio scaled to a target annual volatility.

    Parameters
    ----------
    vol_window   : trailing days for volatility estimate (default 63 = ~3 months)
    target_vol   : annual volatility target (default 0.10 = 10%)
    max_leverage : maximum portfolio leverage cap (default 1.5x)
    """
    rebal_dates = prices.resample("W-FRI").last().index
    weights_ts  = pd.DataFrame(0.0, index=prices.index, columns=prices.columns)

    for i in range(1, len(rebal_dates) - 1):
        rd  = rebal_dates[i]
        idx = prices.index.get_indexer([rd], method="ffill")[0]

        if idx < vol_window:
            continue

        hist = returns.iloc[idx - vol_window: idx]
        vols = hist.std() * np.sqrt(252)
        vols = vols.replace(0, np.nan)
        if vols.isna().all():
            continue
        vols = vols.fillna(vols.median())

        inv_vol = 1.0 / vols
        raw_w   = inv_vol / inv_vol.sum()

        # Scale to hit target vol using covariance matrix
        cov      = hist.cov() * 252
        port_var = float(raw_w.values @ cov.values @ raw_w.values)
        port_vol = np.sqrt(max(port_var, 1e-10))
        scale    = min(target_vol / port_vol, max_leverage)
        w_final  = (raw_w * scale).clip(lower=0)

        next_rd = rebal_dates[i + 1]
        mask    = (prices.index > rd) & (prices.index <= next_rd)
        weights_ts.loc[mask] = w_final.values

    pnl = (weights_ts.shift(1) * returns).sum(axis=1)
    return pnl.rename("VolTarget"), weights_ts


# ══════════════════════════════════════════════════════════════════════════════
# PORTFOLIO COMBINATION — RISK PARITY ACROSS STRATEGIES
# ══════════════════════════════════════════════════════════════════════════════

def risk_parity_combine(strat_ret: pd.DataFrame,
                        vol_window: int = 63,
                        target_vol: float = 0.12) -> tuple[pd.Series, pd.DataFrame]:
    """
    Combines strategy return streams using Risk Parity (inverse-vol weighting).
    Scales combined portfolio to target_vol annual volatility.
    """
    rebal_dates = strat_ret.resample("W-FRI").last().index
    weights_ts  = pd.DataFrame(0.25, index=strat_ret.index, columns=strat_ret.columns)

    for i in range(1, len(rebal_dates) - 1):
        rd  = rebal_dates[i]
        idx = strat_ret.index.get_indexer([rd], method="ffill")[0]

        if idx < vol_window:
            continue

        hist = strat_ret.iloc[idx - vol_window: idx]
        vols = hist.std() * np.sqrt(252)
        vols = vols.replace(0, np.nan)
        if vols.isna().all():
            continue
        vols = vols.fillna(vols.median() + 1e-6)

        inv_vol = 1.0 / vols
        raw_w   = inv_vol / inv_vol.sum()

        cov      = hist.cov() * 252
        port_var = float(raw_w.values @ cov.values @ raw_w.values)
        port_vol = np.sqrt(max(port_var, 1e-10))
        scale    = min(target_vol / port_vol, 2.0)
        w_final  = (raw_w * scale).clip(lower=0)
        if w_final.sum() > 0:
            w_final /= w_final.sum()

        next_rd = rebal_dates[i + 1]
        mask    = (strat_ret.index > rd) & (strat_ret.index <= next_rd)
        weights_ts.loc[mask] = w_final.values

    port_ret = (weights_ts.shift(1) * strat_ret).sum(axis=1).rename("HedgeFund")
    return port_ret, weights_ts
