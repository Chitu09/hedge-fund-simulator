"""
Offline unit tests — no network, synthetic prices only, so CI never
depends on Yahoo Finance being up.
"""
import sys
import pathlib

import numpy as np
import pandas as pd

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from analytics import compute_metrics, drawdown_series  # noqa: E402
from strategies import strategy_momentum  # noqa: E402


def _synthetic_prices(n_days=600, n_stocks=10, seed=0):
    rng = np.random.default_rng(seed)
    idx = pd.bdate_range("2022-01-03", periods=n_days)
    rets = rng.normal(0.0004, 0.015, size=(n_days, n_stocks))
    prices = pd.DataFrame(100 * np.cumprod(1 + rets, axis=0), index=idx,
                          columns=[f"S{i}" for i in range(n_stocks)])
    return prices, prices.pct_change().dropna()


def test_drawdown_is_never_positive():
    _, returns = _synthetic_prices()
    dd = drawdown_series(returns.iloc[:, 0])
    assert (dd <= 1e-12).all()
    assert dd.min() < 0


def test_compute_metrics_returns_dict():
    _, returns = _synthetic_prices()
    m = compute_metrics(returns.iloc[:, 0])
    assert isinstance(m, dict) and len(m) > 0


def test_compute_metrics_short_series_empty():
    _, returns = _synthetic_prices()
    assert compute_metrics(returns.iloc[:10, 0]) == {}


def test_momentum_runs_on_synthetic_data():
    prices, returns = _synthetic_prices()
    strat_ret, weights = strategy_momentum(prices, returns, lookback=120, skip=10)
    assert isinstance(strat_ret, pd.Series)
    assert not strat_ret.dropna().empty
    assert np.isfinite(strat_ret.dropna()).all()
