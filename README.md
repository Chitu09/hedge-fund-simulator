# Multi-Strategy Hedge Fund Simulator

Streamlit app that backtests four strategies on 20 NSE large caps (real Yahoo Finance data) and combines them with risk parity:
momentum, mean reversion, cointegration stat-arb and volatility targeting, benchmarked against NIFTY 50.

![CI/CD](../../actions/workflows/ci-cd.yml/badge.svg)

## Run locally

```bash
pip install -r requirements.txt
streamlit run app.py
```

or with Docker + monitoring:

```bash
docker compose up --build
# app :8501 · metrics :8000/metrics · Prometheus :9090 · Grafana :3000
```

## DevOps

GitHub Actions CI/CD, Docker, Kubernetes (AKS), Terraform (Azure), Prometheus + Grafana — see [SETUP.md](SETUP.md).
