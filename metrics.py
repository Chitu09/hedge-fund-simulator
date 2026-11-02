"""
metrics.py
----------
Prometheus metrics for the Streamlit app.

Streamlit has no /metrics endpoint, so we start prometheus_client's own
HTTP server on port 8000 exactly once per process (st.cache_resource makes
sure reruns don't try to bind the port again).

Usage in app.py (near the top, after st.set_page_config):

    from metrics import init_metrics, PAGE_VIEWS, STRATEGY_RUNS, RUN_SECONDS, DATA_ERRORS
    init_metrics()
    PAGE_VIEWS.inc()
"""

import os
import streamlit as st
from prometheus_client import Counter, Histogram, Gauge, start_http_server

METRICS_PORT = int(os.getenv("METRICS_PORT", "8000"))

PAGE_VIEWS = Counter(
    "hfsim_page_views_total", "Streamlit script reruns (page views / interactions)")

STRATEGY_RUNS = Counter(
    "hfsim_strategy_runs_total", "Full strategy pipeline executions (cache misses)")

RUN_SECONDS = Histogram(
    "hfsim_strategy_run_seconds", "Time to run the full strategy pipeline",
    buckets=(1, 2, 5, 10, 20, 30, 60, 120))

DATA_ERRORS = Counter(
    "hfsim_data_download_errors_total", "Failed Yahoo Finance downloads")

PORTFOLIO_SHARPE = Gauge(
    "hfsim_portfolio_sharpe", "Sharpe ratio of the combined portfolio in the last run")


@st.cache_resource
def init_metrics() -> bool:
    try:
        start_http_server(METRICS_PORT)
    except OSError:
        # Port already bound (e.g. hot reload in dev) — metrics server is up.
        pass
    return True
