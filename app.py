"""
app.py
------
Multi-Strategy Hedge Fund Simulation — Indian Markets
Streamlit Dashboard | 3rd Year College Project

Author  : [Your Name]
Roll No : [Your Roll Number]
College : [Your College Name]
Guide   : [Faculty Name]
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
import warnings
import datetime

warnings.filterwarnings("ignore")

# ── Page config (must be first Streamlit call) ────────────────────────────────
st.set_page_config(
    page_title  = "NSE Hedge Fund Simulator",
    page_icon   = "🏦",
    layout      = "wide",
    initial_sidebar_state = "expanded",
)

# ── Custom CSS ────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@300;400;600&family=IBM+Plex+Sans:wght@300;400;600;700&display=swap');

html, body, [class*="css"] {
    font-family: 'IBM Plex Sans', sans-serif;
}

/* Dark background */
.stApp { background-color: #0a0e17; }

/* Sidebar */
[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #0d1117 0%, #0a0e17 100%);
    border-right: 1px solid #1e2a3a;
}

/* Metric cards */
[data-testid="stMetric"] {
    background: #111827;
    border: 1px solid #1e2a3a;
    border-radius: 10px;
    padding: 16px 20px;
}
[data-testid="stMetricLabel"]  { color: #64748b !important; font-size: 0.78rem !important; letter-spacing: 0.08em; text-transform: uppercase; }
[data-testid="stMetricValue"]  { color: #f1f5f9 !important; font-family: 'IBM Plex Mono', monospace !important; font-size: 1.5rem !important; }
[data-testid="stMetricDelta"]  { font-family: 'IBM Plex Mono', monospace !important; }

/* Tab styling */
[data-testid="stTab"] { font-size: 0.9rem; font-weight: 600; letter-spacing: 0.04em; }

/* Dataframe */
[data-testid="stDataFrame"] { border: 1px solid #1e2a3a; border-radius: 8px; }

/* Headers */
h1 { font-family: 'IBM Plex Mono', monospace !important; color: #58a6ff !important; font-size: 1.8rem !important; letter-spacing: -0.02em; }
h2 { font-family: 'IBM Plex Mono', monospace !important; color: #c9d1d9 !important; font-size: 1.2rem !important; border-bottom: 1px solid #1e2a3a; padding-bottom: 8px; }
h3 { color: #8b949e !important; font-size: 1rem !important; font-weight: 600; }

/* Info boxes */
.info-box {
    background: #111827;
    border: 1px solid #1e2a3a;
    border-left: 3px solid #58a6ff;
    border-radius: 6px;
    padding: 12px 16px;
    margin: 8px 0;
    font-size: 0.88rem;
    color: #8b949e;
    line-height: 1.6;
}
.strategy-badge {
    display: inline-block;
    padding: 3px 10px;
    border-radius: 12px;
    font-size: 0.78rem;
    font-weight: 600;
    font-family: 'IBM Plex Mono', monospace;
    letter-spacing: 0.05em;
}

/* Success/warning overrides */
.stAlert { border-radius: 8px !important; }

/* Plotly chart containers */
.js-plotly-plot { border-radius: 10px; }
</style>
""", unsafe_allow_html=True)

# ── Local imports (after page config) ─────────────────────────────────────────
from data       import load_data, RF_ANNUAL, RF_DAILY, SECTOR_MAP
from strategies import (strategy_momentum, strategy_mean_reversion,
                        find_cointegrated_pairs, strategy_stat_arb,
                        strategy_vol_target, risk_parity_combine)
from analytics  import (build_metrics_table, walk_forward,
                        marginal_risk_contribution, drawdown_series,
                        compute_metrics, format_metrics)

# ── Colour palette ────────────────────────────────────────────────────────────
COLORS = {
    "Momentum":      "#58a6ff",
    "MeanReversion": "#3fb950",
    "StatArb":       "#d2a8ff",
    "VolTarget":     "#ffa657",
    "HedgeFund":     "#ffffff",
    "NIFTY 50":      "#f78166",
}
PLOTLY_LAYOUT = dict(
    paper_bgcolor = "rgba(0,0,0,0)",
    plot_bgcolor  = "#0d1117",
    font          = dict(family="IBM Plex Mono, monospace", color="#c9d1d9", size=11),
    xaxis         = dict(gridcolor="#1e2a3a", zerolinecolor="#1e2a3a", showgrid=True),
    yaxis         = dict(gridcolor="#1e2a3a", zerolinecolor="#1e2a3a", showgrid=True),
    legend        = dict(bgcolor="rgba(0,0,0,0)", bordercolor="#1e2a3a"),
    margin        = dict(l=50, r=30, t=50, b=40),
)


# ════════════════════════════════════════════════════════════════════════════════
# SIDEBAR
# ════════════════════════════════════════════════════════════════════════════════

with st.sidebar:
    st.markdown("## 🏦 NSE Hedge Fund")
    st.markdown("<div class='info-box'>Real NSE data · Yahoo Finance · NIFTY 50 Universe</div>", unsafe_allow_html=True)
    st.markdown("---")

    # Date range
    st.markdown("### 📅 Backtest Period")
    col1, col2 = st.columns(2)
    with col1:
        start_date = st.date_input("Start", value=pd.Timestamp("2018-01-01"),
                                   min_value=pd.Timestamp("2015-01-01"),
                                   max_value=pd.Timestamp("2022-01-01"))
    with col2:
        end_date = st.date_input("End", value=pd.Timestamp(datetime.date.today()),
                                 min_value=pd.Timestamp("2016-01-01"),
                                 max_value=pd.Timestamp(datetime.date.today()))

    st.markdown("---")
    st.markdown("### ⚙️ Strategy Parameters")

    with st.expander("📈 Momentum"):
        mom_lookback = st.slider("Lookback (days)",  126, 504, 252, 21,
                                  help="12-1 month = 252 days is the classic academic setting")
        mom_skip     = st.slider("Skip (days)",        5,  63,  21, 1,
                                  help="Days to skip at end to avoid short-term reversal")
        mom_top_pct  = st.slider("Top/Bottom %",       0.10, 0.40, 0.20, 0.05,
                                  help="Fraction of stocks to hold long and short")

    with st.expander("📉 Mean Reversion"):
        mr_window   = st.slider("Rolling window (days)", 5, 60, 20, 1)
        mr_z_entry  = st.slider("Z-score entry",         0.5, 3.0, 1.5, 0.1)

    with st.expander("🔁 Stat Arb"):
        sa_pval     = st.slider("Cointegration p-value threshold", 0.01, 0.20, 0.10, 0.01)
        sa_z_entry  = st.slider("Spread z-score entry",             0.5, 3.0, 1.5, 0.1)
        sa_window   = st.slider("Spread window (days)",             20, 120, 60, 5)
        is_end_date = st.date_input("In-sample end (pair discovery)",
                                    value=pd.Timestamp("2019-12-31"))

    with st.expander("🎯 Vol Targeting"):
        vt_vol_window  = st.slider("Vol estimation window (days)", 21, 126, 63, 5)
        vt_target_vol  = st.slider("Target annual vol (%)",         5, 25, 10, 1) / 100
        vt_max_lev     = st.slider("Max leverage (x)",              1.0, 3.0, 1.5, 0.1)

    with st.expander("🏛️ Portfolio Combination"):
        port_target_vol = st.slider("Portfolio target vol (%)", 5, 25, 12, 1) / 100

    st.markdown("---")
    run_btn = st.button("▶  Run Backtest", type="primary", use_container_width=True)
    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown("<div class='info-box'>📚 3rd Year Project · Quant Finance<br>Data: Yahoo Finance (NSE)<br>Benchmark: NIFTY 50 (^NSEI)</div>", unsafe_allow_html=True)


# ════════════════════════════════════════════════════════════════════════════════
# HEADER
# ════════════════════════════════════════════════════════════════════════════════

st.markdown("# 🏦 Multi-Strategy Hedge Fund Simulation")
st.markdown("### Design & Backtesting · Indian Markets (NSE) · Real Market Data")

tab_overview, tab_strategies, tab_portfolio, tab_risk, tab_walkfwd, tab_about = st.tabs([
    "📊 Overview",
    "📈 Strategies",
    "🏛️ Portfolio",
    "⚠️ Risk Analysis",
    "🔄 Walk-Forward",
    "📖 About",
])


# ════════════════════════════════════════════════════════════════════════════════
# DATA LOADING & COMPUTATION
# ════════════════════════════════════════════════════════════════════════════════

@st.cache_data(show_spinner=False, ttl=3600)
def run_all_strategies(start_str, end_str, is_end_str,
                       mom_lookback, mom_skip, mom_top_pct,
                       mr_window, mr_z_entry,
                       sa_pval, sa_z_entry, sa_window,
                       vt_vol_window, vt_target_vol, vt_max_lev,
                       port_target_vol):
    """Run full pipeline — cached so re-runs are instant unless params change."""
    prices, benchmark, returns, bench_ret = load_data(start_str,datetime.date.today() )

    # ── Strategy 1: Momentum ──────────────────────────────────────────────────
    mom_ret, mom_w = strategy_momentum(
        prices, returns, lookback=mom_lookback, skip=mom_skip, top_pct=mom_top_pct)

    # ── Strategy 2: Mean Reversion ────────────────────────────────────────────
    mr_ret, mr_w, z_scores = strategy_mean_reversion(
        prices, returns, window=mr_window, z_entry=mr_z_entry)

    # ── Strategy 3: Stat Arb ──────────────────────────────────────────────────
    prices_is = prices.loc[:is_end_str]
    pairs_df  = find_cointegrated_pairs(prices_is, pvalue_thresh=sa_pval)
    sa_ret, spread_data = strategy_stat_arb(
        prices, returns, pairs_df, z_entry=sa_z_entry, window=sa_window)

    # ── Strategy 4: Vol Target ────────────────────────────────────────────────
    vt_ret, vt_w = strategy_vol_target(
        prices, returns, vol_window=vt_vol_window,
        target_vol=vt_target_vol, max_leverage=vt_max_lev)

    # ── Combine ───────────────────────────────────────────────────────────────
    strat_ret = pd.concat([mom_ret, mr_ret, sa_ret, vt_ret], axis=1).dropna()
    bench_al  = bench_ret.reindex(strat_ret.index).dropna()
    strat_ret = strat_ret.reindex(bench_al.index)

    hf_ret, combo_w = risk_parity_combine(strat_ret, target_vol=port_target_vol)

    all_ret = pd.concat([strat_ret, hf_ret], axis=1)

    return (prices, benchmark, returns, bench_al,
            all_ret, combo_w, z_scores, pairs_df, spread_data)


# ── Run on button press or first load ─────────────────────────────────────────
if "results" not in st.session_state or run_btn:
    with st.spinner("⏳  Downloading real NSE data & running backtest…"):
        try:
            results = run_all_strategies(
                str(start_date), str(end_date), str(is_end_date),
                mom_lookback, mom_skip, mom_top_pct,
                mr_window, mr_z_entry,
                sa_pval, sa_z_entry, sa_window,
                vt_vol_window, vt_target_vol, vt_max_lev,
                port_target_vol,
            )
            st.session_state.results = results
            st.session_state.params  = dict(
                start=str(start_date), end=str(end_date))
        except Exception as e:
            st.error(f"❌ Error: {e}\n\nCheck your internet connection — live NSE data required.")
            st.stop()

(prices, benchmark, returns, bench_al,
 all_ret, combo_w, z_scores, pairs_df, spread_data) = st.session_state.results

STRAT_NAMES = ["Momentum", "MeanReversion", "StatArb", "VolTarget"]
cum_all     = (1 + all_ret).cumprod()
cum_bench   = (1 + bench_al).cumprod()
hf_metrics  = compute_metrics(all_ret["HedgeFund"], bench_al)


# ════════════════════════════════════════════════════════════════════════════════
# TAB 1 — OVERVIEW
# ════════════════════════════════════════════════════════════════════════════════

with tab_overview:

    # ── Key metric cards ──────────────────────────────────────────────────────
    st.markdown("## Key Performance Indicators")
    c1, c2, c3, c4, c5, c6 = st.columns(6)

    ann_r  = hf_metrics.get("Ann. Return (CAGR)", 0)
    ann_v  = hf_metrics.get("Ann. Volatility", 1)
    sharpe = hf_metrics.get("Sharpe Ratio", 0)
    max_dd = hf_metrics.get("Max Drawdown", 0)
    alpha  = hf_metrics.get("Alpha (ann.)", 0)
    beta   = hf_metrics.get("Beta vs NIFTY", 0)

    b_ann  = float(compute_metrics(bench_al).get("Ann. Return (CAGR)", 0))

    c1.metric("Ann. Return",   f"{ann_r:.2%}",  f"{ann_r - b_ann:+.2%} vs NIFTY")
    c2.metric("Ann. Volatility", f"{ann_v:.2%}")
    c3.metric("Sharpe Ratio",  f"{sharpe:.2f}",  "Higher is better")
    c4.metric("Max Drawdown",  f"{max_dd:.2%}",  "Lower is better")
    c5.metric("Alpha (ann.)",  f"{alpha:.2%}" if not np.isnan(alpha) else "N/A")
    c6.metric("Beta vs NIFTY", f"{beta:.2f}"  if not np.isnan(beta)  else "N/A",
              "Low = market-neutral")

    st.markdown("---")

    # ── Cumulative returns chart ───────────────────────────────────────────────
    st.markdown("## Cumulative Returns — Real NSE Data")

    fig = go.Figure()
    for col in STRAT_NAMES:
        fig.add_trace(go.Scatter(
            x=cum_all.index, y=cum_all[col],
            name=col, line=dict(color=COLORS[col], width=1.2),
            opacity=0.65, hovertemplate=f"<b>{col}</b><br>%{{y:.3f}}<extra></extra>"
        ))
    fig.add_trace(go.Scatter(
        x=cum_all.index, y=cum_all["HedgeFund"],
        name="Hedge Fund", line=dict(color=COLORS["HedgeFund"], width=2.8),
        hovertemplate="<b>Hedge Fund</b><br>₹%{y:.3f}<extra></extra>"
    ))
    fig.add_trace(go.Scatter(
        x=cum_bench.index, y=cum_bench,
        name="NIFTY 50", line=dict(color=COLORS["NIFTY 50"], width=1.8, dash="dash"),
        hovertemplate="<b>NIFTY 50</b><br>₹%{y:.3f}<extra></extra>"
    ))
    fig.add_hline(y=1, line_dash="dot", line_color="#30363d", line_width=1)
    fig.update_layout(**PLOTLY_LAYOUT,
        title=dict(text="Growth of ₹1 Invested · 2018–2023 · NSE Real Data",
                   font=dict(size=14, color="#58a6ff")),
        height=430, hovermode="x unified",
        yaxis_title="Portfolio Value (₹)", xaxis_title="")
    st.plotly_chart(fig, use_container_width=True)

    # ── Drawdown + rolling Sharpe ──────────────────────────────────────────────
    col_a, col_b = st.columns(2)

    with col_a:
        st.markdown("## Drawdown")
        fig_dd = go.Figure()
        dd_hf  = drawdown_series(all_ret["HedgeFund"])
        dd_bn  = drawdown_series(bench_al)
        fig_dd.add_trace(go.Scatter(
            x=dd_hf.index, y=dd_hf * 100,
            fill="tozeroy", fillcolor="rgba(247,129,102,0.15)",
            line=dict(color=COLORS["HedgeFund"], width=1.5),
            name="Hedge Fund", hovertemplate="%{y:.2f}%<extra>Hedge Fund</extra>"
        ))
        fig_dd.add_trace(go.Scatter(
            x=dd_bn.index, y=dd_bn * 100,
            line=dict(color=COLORS["NIFTY 50"], width=1.2, dash="dash"),
            name="NIFTY 50", hovertemplate="%{y:.2f}%<extra>NIFTY 50</extra>"
        ))
        fig_dd.update_layout(**PLOTLY_LAYOUT, height=300,
            title="Underwater Chart (%)", yaxis_title="Drawdown (%)")
        st.plotly_chart(fig_dd, use_container_width=True)

    with col_b:
        st.markdown("## Rolling 63-Day Sharpe")
        fig_sh = go.Figure()
        for col in STRAT_NAMES + ["HedgeFund"]:
            rs = all_ret[col].rolling(63)
            sh = (rs.mean() - RF_DAILY) / rs.std() * np.sqrt(252)
            fig_sh.add_trace(go.Scatter(
                x=sh.index, y=sh,
                name=col, line=dict(color=COLORS[col], width=1.2),
                opacity=0.8 if col != "HedgeFund" else 1.0,
            ))
        fig_sh.add_hline(y=0, line_dash="dot", line_color="#30363d")
        fig_sh.add_hline(y=1, line_dash="dot", line_color="#1e2a3a")
        fig_sh.update_layout(**PLOTLY_LAYOUT, height=300,
            title="Rolling Sharpe (63-Day Window)", yaxis_title="Sharpe")
        st.plotly_chart(fig_sh, use_container_width=True)

    # ── Monthly heatmap ────────────────────────────────────────────────────────
    st.markdown("## Monthly Returns Heatmap — Hedge Fund")
    monthly = all_ret["HedgeFund"].resample("ME").apply(lambda x: (1+x).prod()-1)
    pivot   = pd.DataFrame({
        "Year": monthly.index.year,
        "Month": monthly.index.month,
        "R": monthly.values * 100
    }).pivot(index="Year", columns="Month", values="R")
    pivot.columns = ["Jan","Feb","Mar","Apr","May","Jun",
                     "Jul","Aug","Sep","Oct","Nov","Dec"]

    fig_hm = px.imshow(
        pivot, text_auto=".1f",
        color_continuous_scale=[(0,"#f85149"),(0.5,"#161b22"),(1,"#3fb950")],
        color_continuous_midpoint=0,
        labels=dict(color="Return %"),
        aspect="auto",
    )
    fig_hm.update_layout(**PLOTLY_LAYOUT, height=280,
        title="Monthly Return (%) — Green = Profit, Red = Loss",
        coloraxis_colorbar=dict(title="Ret %"))
    fig_hm.update_traces(textfont=dict(size=10, family="IBM Plex Mono"))
    st.plotly_chart(fig_hm, use_container_width=True)


# ════════════════════════════════════════════════════════════════════════════════
# TAB 2 — STRATEGIES
# ════════════════════════════════════════════════════════════════════════════════

with tab_strategies:

    # ── Per-strategy metrics strip ─────────────────────────────────────────────
    st.markdown("## Individual Strategy Performance")

    scols = st.columns(4)
    for i, s in enumerate(STRAT_NAMES):
        m  = compute_metrics(all_ret[s], bench_al)
        ar = m.get("Ann. Return (CAGR)", 0)
        sh = m.get("Sharpe Ratio", 0)
        dd = m.get("Max Drawdown", 0)
        scols[i].markdown(f"""
        <div style='background:#111827;border:1px solid #1e2a3a;border-top:3px solid {COLORS[s]};
                    border-radius:10px;padding:14px 16px;'>
            <div style='color:#64748b;font-size:0.72rem;letter-spacing:0.1em;text-transform:uppercase;
                        font-family:"IBM Plex Mono",monospace;'>{s}</div>
            <div style='color:#f1f5f9;font-size:1.3rem;font-family:"IBM Plex Mono",monospace;
                        margin:6px 0;'>{ar:.2%}</div>
            <div style='color:#8b949e;font-size:0.8rem;'>Sharpe: {sh:.2f} &nbsp;|&nbsp; MaxDD: {dd:.2%}</div>
        </div>""", unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Momentum deep-dive ────────────────────────────────────────────────────
    with st.expander("📈 Strategy 1 — Cross-Sectional Momentum", expanded=True):
        st.markdown("""<div class='info-box'>
        <b>Academic basis:</b> Jegadeesh &amp; Titman (1993) — stocks that outperformed over the past
        12 months (skipping the last 1 month) tend to continue outperforming in the next 3–12 months.<br>
        <b>How it works:</b> Every month, rank all NSE stocks by their 12-1m return.
        Buy top 20%, short bottom 20%. Dollar-neutral (market direction doesn't matter).
        </div>""", unsafe_allow_html=True)

        fig_m = go.Figure()
        fig_m.add_trace(go.Scatter(
            x=cum_all.index, y=cum_all["Momentum"],
            fill="tozeroy", fillcolor="rgba(88,166,255,0.08)",
            line=dict(color=COLORS["Momentum"], width=2),
            name="Momentum Cumulative Return"
        ))
        fig_m.add_trace(go.Scatter(
            x=cum_bench.index, y=cum_bench,
            line=dict(color=COLORS["NIFTY 50"], width=1.4, dash="dash"),
            name="NIFTY 50"
        ))
        fig_m.update_layout(**PLOTLY_LAYOUT, height=280,
            title="Momentum Strategy vs NIFTY 50 (Growth of ₹1)")
        st.plotly_chart(fig_m, use_container_width=True)

    # ── Mean Reversion deep-dive ──────────────────────────────────────────────
    with st.expander("📉 Strategy 2 — Mean Reversion (Bollinger Band)"):
        st.markdown("""<div class='info-box'>
        <b>Academic basis:</b> DeBondt &amp; Thaler (1985) — extreme price moves tend to reverse.
        When a stock moves more than 1.5σ from its 20-day mean, bet on a reversion to the mean.<br>
        <b>How it works:</b> Compute z-score = (price − 20d MA) / 20d std.
        Long if z &lt; −1.5, short if z &gt; +1.5. Exit when |z| &lt; 0.3.
        </div>""", unsafe_allow_html=True)

        stock_choice = st.selectbox("Select stock to view z-score signal:",
                                    prices.columns.tolist(), index=1)

        fig_mr = make_subplots(rows=2, cols=1, shared_xaxes=True,
                               row_heights=[0.6, 0.4], vertical_spacing=0.05)
        z_s  = z_scores[stock_choice]
        p_s  = prices[stock_choice]
        ma   = p_s.rolling(mr_window).mean()
        std  = p_s.rolling(mr_window).std()

        fig_mr.add_trace(go.Scatter(x=p_s.index, y=p_s,
            line=dict(color=COLORS["MeanReversion"], width=1.5), name="Price"), row=1, col=1)
        fig_mr.add_trace(go.Scatter(x=ma.index, y=ma,
            line=dict(color="white", width=1, dash="dot"), name="20d MA"), row=1, col=1)
        fig_mr.add_trace(go.Scatter(x=ma.index, y=ma + mr_z_entry*std,
            line=dict(color="#f85149", width=0.8, dash="dash"), name=f"+{mr_z_entry}σ"), row=1, col=1)
        fig_mr.add_trace(go.Scatter(x=ma.index, y=ma - mr_z_entry*std,
            line=dict(color="#3fb950", width=0.8, dash="dash"), name=f"−{mr_z_entry}σ"), row=1, col=1)
        fig_mr.add_trace(go.Scatter(x=z_s.index, y=z_s,
            line=dict(color=COLORS["MeanReversion"], width=1.3), name="Z-Score"), row=2, col=1)
        fig_mr.add_hline(y= mr_z_entry, line_dash="dash", line_color="#f85149", row=2, col=1)
        fig_mr.add_hline(y=-mr_z_entry, line_dash="dash", line_color="#3fb950", row=2, col=1)
        fig_mr.add_hline(y=0, line_dash="dot", line_color="#30363d", row=2, col=1)
        fig_mr.update_layout(**PLOTLY_LAYOUT, height=380,
            title=f"{stock_choice} — Price with Bollinger Bands & Z-Score Signal (Real NSE)")
        st.plotly_chart(fig_mr, use_container_width=True)

    # ── Stat Arb deep-dive ────────────────────────────────────────────────────
    with st.expander("🔁 Strategy 3 — Statistical Arbitrage (Pairs Trading)"):
        st.markdown("""<div class='info-box'>
        <b>Academic basis:</b> Gatev, Goetzmann &amp; Rouwenhorst (2006) — cointegrated stock pairs
        exhibit mean-reverting spread behaviour that can be profitably traded.<br>
        <b>How it works:</b> Find NSE pairs that are statistically cointegrated (Engle-Granger test, p &lt; threshold).
        When the spread widens beyond 1.5σ, short the expensive stock and buy the cheap one. Exit at 0.3σ.
        </div>""", unsafe_allow_html=True)

        if pairs_df.empty:
            st.warning(f"No cointegrated pairs found at p < {sa_pval}. Try increasing the p-value threshold in the sidebar.")
        else:
            st.markdown(f"**{len(pairs_df)} cointegrated pairs identified (in-sample ≤ {is_end_date})**")
            st.dataframe(pairs_df.style.format({"HedgeRatio": "{:.4f}",
                                                 "Intercept":  "{:.4f}",
                                                 "PValue":     "{:.4f}"}),
                         use_container_width=True)

            if spread_data:
                pair_choice = st.selectbox("View spread z-score:", list(spread_data.keys()))
                z_spread    = spread_data[pair_choice].reindex(returns.index)

                fig_sa = go.Figure()
                fig_sa.add_trace(go.Scatter(
                    x=z_spread.index, y=z_spread,
                    fill="tozeroy", fillcolor="rgba(210,168,255,0.07)",
                    line=dict(color=COLORS["StatArb"], width=1.3), name="Spread Z-Score"
                ))
                fig_sa.add_hline(y= sa_z_entry, line_dash="dash", line_color="#f85149",
                                 annotation_text=f"Short entry +{sa_z_entry}σ")
                fig_sa.add_hline(y=-sa_z_entry, line_dash="dash", line_color="#3fb950",
                                 annotation_text=f"Long entry −{sa_z_entry}σ")
                fig_sa.add_hline(y=0, line_dash="dot", line_color="#30363d")
                fig_sa.update_layout(**PLOTLY_LAYOUT, height=300,
                    title=f"Pair: {pair_choice} — Spread Z-Score (Real NSE Prices)")
                st.plotly_chart(fig_sa, use_container_width=True)

    # ── Vol Target deep-dive ──────────────────────────────────────────────────
    with st.expander("🎯 Strategy 4 — Volatility Targeting (Risk Parity)"):
        st.markdown("""<div class='info-box'>
        <b>Academic basis:</b> Qian (2005), Asness et al. (2012) — Risk Parity portfolios that
        weight by inverse-volatility achieve better risk-adjusted returns than cap-weighted indices.<br>
        <b>How it works:</b> Each stock weight ∝ 1/σ_i (63-day trailing vol).
        Portfolio scaled so total vol = 10% annual. Rebalanced every Friday.
        </div>""", unsafe_allow_html=True)

        fig_vt = go.Figure()
        fig_vt.add_trace(go.Scatter(
            x=cum_all.index, y=cum_all["VolTarget"],
            fill="tozeroy", fillcolor="rgba(255,166,87,0.08)",
            line=dict(color=COLORS["VolTarget"], width=2), name="Vol Target"
        ))
        fig_vt.add_trace(go.Scatter(
            x=cum_bench.index, y=cum_bench,
            line=dict(color=COLORS["NIFTY 50"], width=1.4, dash="dash"), name="NIFTY 50"
        ))
        fig_vt.update_layout(**PLOTLY_LAYOUT, height=280,
            title="Volatility Targeting Strategy vs NIFTY 50")
        st.plotly_chart(fig_vt, use_container_width=True)


# ════════════════════════════════════════════════════════════════════════════════
# TAB 3 — PORTFOLIO
# ════════════════════════════════════════════════════════════════════════════════

with tab_portfolio:
    st.markdown("## Portfolio Construction — Risk Parity Combination")
    st.markdown("""<div class='info-box'>
    All four strategy PnL streams are combined using <b>Risk Parity</b>:
    each strategy is weighted inversely proportional to its trailing 63-day realised volatility,
    then the combined portfolio is scaled to the target annual volatility.
    This prevents any single strategy from dominating portfolio risk.
    </div>""", unsafe_allow_html=True)

    # ── Strategy weights stacked area ─────────────────────────────────────────
    st.markdown("### Dynamic Strategy Weights (Risk-Parity Allocation)")
    w_plot = combo_w.reindex(all_ret.index).ffill().fillna(0.25)

    fig_w = go.Figure()
    for col in STRAT_NAMES:
        fig_w.add_trace(go.Scatter(
            x=w_plot.index, y=w_plot[col] * 100,
            stackgroup="one", name=col,
            fillcolor=COLORS[col].replace(")", ", 0.7)").replace("rgb", "rgba")
                        if "rgb" in COLORS[col] else COLORS[col],
            line=dict(color=COLORS[col], width=0.5),
            hovertemplate=f"{col}: %{{y:.1f}}%<extra></extra>"
        ))
    fig_w.update_layout(**PLOTLY_LAYOUT, height=300,
        title="Strategy Allocation Over Time (%)",
        yaxis_title="Weight (%)", yaxis_range=[0, 100])
    st.plotly_chart(fig_w, use_container_width=True)

    # ── Full metrics table ─────────────────────────────────────────────────────
    st.markdown("### Full Performance Metrics Table")
    metrics_tbl = build_metrics_table(all_ret, bench_al)

    # Highlight HedgeFund column
    def highlight_hf(col):
        return ["background-color: #111827; color: #58a6ff; font-weight: bold"
                if col.name == "HedgeFund" else "" for _ in col]

    st.dataframe(
        metrics_tbl.style.apply(highlight_hf, axis=0),
        use_container_width=True, height=580
    )

    # ── Annual return comparison ───────────────────────────────────────────────
    st.markdown("### Annual Returns Comparison (%)")
    ann = pd.concat([all_ret, bench_al.rename("NIFTY 50")], axis=1)\
            .resample("YE").apply(lambda x: (1+x).prod()-1) * 100

    fig_ann = go.Figure()
    for col in list(STRAT_NAMES) + ["HedgeFund", "NIFTY 50"]:
        if col in ann.columns:
            fig_ann.add_trace(go.Bar(
                x=[str(d.year) for d in ann.index],
                y=ann[col],
                name=col,
                marker_color=COLORS.get(col, "#8b949e"),
                opacity=0.85,
            ))
    fig_ann.add_hline(y=0, line_color="#30363d", line_width=1)
    fig_ann.update_layout(**PLOTLY_LAYOUT, height=380, barmode="group",
        title="Annual Returns by Strategy & Year (%)",
        yaxis_title="Return (%)")
    st.plotly_chart(fig_ann, use_container_width=True)


# ════════════════════════════════════════════════════════════════════════════════
# TAB 4 — RISK ANALYSIS
# ════════════════════════════════════════════════════════════════════════════════

with tab_risk:
    st.markdown("## Risk Analysis")

    col_l, col_r = st.columns(2)

    # ── Return distribution ───────────────────────────────────────────────────
    with col_l:
        st.markdown("### Return Distribution — Hedge Fund")
        r_hf = all_ret["HedgeFund"].dropna() * 100
        fig_dist = go.Figure()
        fig_dist.add_trace(go.Histogram(
            x=r_hf, nbinsx=80,
            marker_color=COLORS["HedgeFund"], opacity=0.6,
            name="Daily Returns", histnorm="probability density"
        ))
        # Normal overlay
        mu_r, sd_r = r_hf.mean(), r_hf.std()
        xr = np.linspace(mu_r - 4*sd_r, mu_r + 4*sd_r, 300)
        from scipy.stats import norm
        fig_dist.add_trace(go.Scatter(
            x=xr, y=norm.pdf(xr, mu_r, sd_r),
            line=dict(color=COLORS["NIFTY 50"], width=2, dash="dash"),
            name="Normal Fit"
        ))
        var95 = float(np.percentile(r_hf, 5))
        fig_dist.add_vline(x=var95, line_dash="dash", line_color=COLORS["StatArb"],
                           annotation_text=f"VaR 95%: {var95:.2f}%")
        fig_dist.update_layout(**PLOTLY_LAYOUT, height=330,
            title="Daily Return Distribution vs Normal", xaxis_title="Return (%)")
        st.plotly_chart(fig_dist, use_container_width=True)

    # ── Inter-strategy correlation ─────────────────────────────────────────────
    with col_r:
        st.markdown("### Inter-Strategy Correlation")
        corr = all_ret[STRAT_NAMES].corr()
        mask_upper = np.triu(np.ones_like(corr, dtype=bool), k=1)
        corr_masked = corr.copy()
        corr_masked[mask_upper] = np.nan

        fig_corr = px.imshow(
            corr_masked, text_auto=".2f",
            color_continuous_scale=[(0,"#f85149"),(0.5,"#161b22"),(1,"#3fb950")],
            color_continuous_midpoint=0, zmin=-1, zmax=1,
            labels=dict(color="Correlation"),
        )
        fig_corr.update_layout(**PLOTLY_LAYOUT, height=330,
            title="Pairwise Strategy Correlations (lower triangle)")
        fig_corr.update_traces(textfont=dict(size=13, family="IBM Plex Mono"))
        st.plotly_chart(fig_corr, use_container_width=True)

    # ── Risk contribution ─────────────────────────────────────────────────────
    col_l2, col_r2 = st.columns(2)

    with col_l2:
        st.markdown("### % Risk Contribution by Strategy")
        mean_w  = combo_w.mean().values
        cov_mat = all_ret[STRAT_NAMES].cov().values * 252
        prc     = marginal_risk_contribution(mean_w, cov_mat)

        fig_pie = go.Figure(go.Pie(
            labels=STRAT_NAMES, values=prc * 100,
            marker=dict(colors=[COLORS[s] for s in STRAT_NAMES],
                        line=dict(color="#0d1117", width=2)),
            textinfo="label+percent",
            textfont=dict(family="IBM Plex Mono", size=11),
            hole=0.4,
        ))
        fig_pie.update_layout(**PLOTLY_LAYOUT, height=330,
            title="Risk Budget Allocation (Marginal Risk Contribution)")
        st.plotly_chart(fig_pie, use_container_width=True)

    with col_r2:
        st.markdown("### Rolling Correlation with NIFTY 50")
        fig_rc = go.Figure()
        for col in STRAT_NAMES + ["HedgeFund"]:
            rc = all_ret[col].rolling(63).corr(bench_al)
            fig_rc.add_trace(go.Scatter(
                x=rc.index, y=rc,
                name=col, line=dict(color=COLORS[col], width=1.2),
                opacity=0.85 if col != "HedgeFund" else 1.0,
            ))
        fig_rc.add_hline(y=0, line_dash="dot", line_color="#30363d")
        fig_rc.update_layout(**PLOTLY_LAYOUT, height=330,
            title="Rolling 63-Day Correlation vs NIFTY 50 (low = market-neutral)",
            yaxis_title="Correlation", yaxis_range=[-1, 1])
        st.plotly_chart(fig_rc, use_container_width=True)

    # ── VaR / CVaR table ──────────────────────────────────────────────────────
    st.markdown("### Value at Risk Summary")
    var_data = {}
    for col in list(STRAT_NAMES) + ["HedgeFund"]:
        r = all_ret[col].dropna()
        v95 = float(np.percentile(r, 5))
        v99 = float(np.percentile(r, 1))
        cv95 = float(r[r <= v95].mean())
        cv99 = float(r[r <= v99].mean())
        var_data[col] = {
            "VaR 95% (daily)":  f"{v95:.3%}",
            "VaR 99% (daily)":  f"{v99:.3%}",
            "CVaR 95% (daily)": f"{cv95:.3%}",
            "CVaR 99% (daily)": f"{cv99:.3%}",
            "VaR 95% (annual)": f"{v95 * np.sqrt(252):.2%}",
        }
    st.dataframe(pd.DataFrame(var_data), use_container_width=True)


# ════════════════════════════════════════════════════════════════════════════════
# TAB 5 — WALK-FORWARD
# ════════════════════════════════════════════════════════════════════════════════

with tab_walkfwd:
    st.markdown("## Walk-Forward Out-of-Sample Validation")
    st.markdown("""<div class='info-box'>
    <b>What is this?</b> We simulate how the strategy would have been deployed in real life.
    Train on 18 months of data → trade the next 6 months (never touching future data) → repeat.
    If Out-of-Sample (OOS) Sharpe is consistently close to In-Sample (IS) Sharpe,
    the strategy is <b>robust</b>. A large IS/OOS gap means over-fitting.
    </div>""", unsafe_allow_html=True)

    col_wf1, col_wf2 = st.columns(2)
    with col_wf1:
        wf_train = st.slider("Training window (months)", 12, 36, 18, 3)
    with col_wf2:
        wf_test  = st.slider("Testing window (months)",   3, 12,  6, 1)

    wf_df = walk_forward(all_ret["HedgeFund"],
                         train_months=wf_train, test_months=wf_test)

    if wf_df.empty:
        st.warning("Not enough data for walk-forward with these window sizes.")
    else:
        # ── Bar chart ─────────────────────────────────────────────────────────
        fig_wf = go.Figure()
        fig_wf.add_trace(go.Bar(
            x=wf_df["Period"], y=wf_df["IS Sharpe"],
            name="In-Sample Sharpe", marker_color=COLORS["Momentum"],
            opacity=0.85, offsetgroup=0,
        ))
        fig_wf.add_trace(go.Bar(
            x=wf_df["Period"], y=wf_df["OOS Sharpe"],
            name="Out-of-Sample Sharpe", marker_color=COLORS["MeanReversion"],
            opacity=0.85, offsetgroup=1,
        ))
        fig_wf.add_hline(y=0, line_color="#30363d")
        fig_wf.add_hline(y=1, line_dash="dot", line_color="#1e2a3a",
                         annotation_text="Sharpe = 1")
        fig_wf.update_layout(**PLOTLY_LAYOUT, height=360, barmode="group",
            title=f"Walk-Forward: IS vs OOS Sharpe ({wf_train}m train / {wf_test}m test)",
            xaxis_tickangle=-45, yaxis_title="Sharpe Ratio")
        st.plotly_chart(fig_wf, use_container_width=True)

        # ── Scatter ───────────────────────────────────────────────────────────
        col_s1, col_s2 = st.columns(2)
        with col_s1:
            fig_sc = go.Figure()
            fig_sc.add_trace(go.Scatter(
                x=wf_df["IS Sharpe"], y=wf_df["OOS Sharpe"],
                mode="markers+text",
                text=wf_df["Period"], textposition="top center",
                textfont=dict(size=8, color="#8b949e"),
                marker=dict(color=COLORS["HedgeFund"], size=10,
                            line=dict(color="#58a6ff", width=1.5)),
                name="Folds"
            ))
            mn = min(wf_df[["IS Sharpe","OOS Sharpe"]].min().min(), 0) - 0.2
            mx = max(wf_df[["IS Sharpe","OOS Sharpe"]].max().max(), 1) + 0.2
            fig_sc.add_trace(go.Scatter(
                x=[mn, mx], y=[mn, mx],
                line=dict(color="#f85149", dash="dash", width=1),
                name="IS = OOS (perfect)", mode="lines"
            ))
            fig_sc.add_hline(y=0, line_color="#30363d")
            fig_sc.add_vline(x=0, line_color="#30363d")
            fig_sc.update_layout(**PLOTLY_LAYOUT, height=350,
                title="IS vs OOS Sharpe (points near red = robust)",
                xaxis_title="In-Sample Sharpe", yaxis_title="OOS Sharpe")
            st.plotly_chart(fig_sc, use_container_width=True)

        with col_s2:
            st.markdown("### Walk-Forward Summary")
            st.markdown(f"""
            | Metric | Value |
            |---|---|
            | Folds analysed | {len(wf_df)} |
            | Avg IS Sharpe  | {wf_df['IS Sharpe'].mean():.2f} |
            | Avg OOS Sharpe | {wf_df['OOS Sharpe'].mean():.2f} |
            | IS/OOS Ratio   | {wf_df['IS Sharpe'].mean() / max(abs(wf_df['OOS Sharpe'].mean()), 0.01):.2f}x |
            | Positive OOS folds | {(wf_df['OOS Sharpe'] > 0).sum()} / {len(wf_df)} |
            | Correlation (IS vs OOS) | {wf_df['IS Sharpe'].corr(wf_df['OOS Sharpe']):.2f} |
            """)
            st.markdown("<br>", unsafe_allow_html=True)
            st.dataframe(wf_df, use_container_width=True)


# ════════════════════════════════════════════════════════════════════════════════
# TAB 6 — ABOUT
# ════════════════════════════════════════════════════════════════════════════════

with tab_about:
    st.markdown("## About This Project")

    col_a1, col_a2 = st.columns(2)

    with col_a1:
        st.markdown("""
### Project Details
| | |
|---|---|
| **Title** | Multi-Strategy Hedge Fund Simulation — Indian Markets |
| **Course** | Quantitative Finance / Financial Engineering |
| **Year** | 3rd Year, B.Tech / BMS / MBA (Finance) |
| **Data Source** | Yahoo Finance · NSE (Real Adjusted Prices) |
| **Benchmark** | NIFTY 50 Index (^NSEI) |
| **Backtest Period** | 2018 – 2023 |

---

### Strategy Summary

| Strategy | Type | Rebalance | Key Parameter |
|---|---|---|---|
| **Momentum** | Long/Short | Monthly | 12-1 month signal |
| **Mean Reversion** | Long/Short | Daily | 20-day Bollinger Band |
| **Statistical Arbitrage** | Pair trades | Daily | Engle-Granger cointegration |
| **Vol Targeting** | Long-only | Weekly | Inverse-vol weights |

---

### Key Metrics Explained

| Metric | What it measures |
|---|---|
| **Sharpe Ratio** | Return per unit of total risk (higher = better) |
| **Sortino Ratio** | Return per unit of *downside* risk only |
| **Calmar Ratio** | Annual return ÷ Max Drawdown |
| **Max Drawdown** | Largest peak-to-trough loss in the period |
| **VaR 95%** | Daily loss exceeded only 5% of the time |
| **CVaR 95%** | Average loss on the worst 5% of days |
| **Alpha** | Return above what CAPM predicts (market-adjusted) |
| **Beta** | Sensitivity to NIFTY 50 market moves |
        """)

    with col_a2:
        st.markdown("""
### References

1. **Jegadeesh & Titman (1993)** — *Returns to Buying Winners and Selling Losers*
   — Foundation paper for momentum strategy. Journal of Finance.

2. **DeBondt & Thaler (1985)** — *Does the Stock Market Overreact?*
   — Mean reversion in long-term returns. Journal of Finance.

3. **Gatev, Goetzmann & Rouwenhorst (2006)** — *Pairs Trading: Performance of a Relative Value Arbitrage Rule*
   — Statistical arbitrage / pairs trading. Review of Financial Studies.

4. **Qian (2005)** — *Risk Parity Portfolios*
   — Inverse-volatility weighting. Panagora Asset Management.

5. **Asness, Frazzini & Pedersen (2012)** — *Leverage Aversion and Risk Parity*
   — Risk Parity theory. Financial Analysts Journal.

6. **Engle & Granger (1987)** — *Co-Integration and Error Correction*
   — Cointegration framework used in Stat Arb. Econometrica.

---

### Technology Stack

| Component | Library |
|---|---|
| Data download | `yfinance` |
| Data processing | `pandas`, `numpy` |
| Statistical tests | `statsmodels` |
| Visualisation | `plotly` |
| Web app | `streamlit` |
| Risk/stats | `scipy` |

---

### Data Disclaimer

All prices are **real, split-adjusted, dividend-adjusted** closing prices
from Yahoo Finance (NSE suffix `.NS`). No synthetic or simulated data
is used anywhere in this application. The NIFTY 50 index (^NSEI) is used
as the benchmark. Past performance does not guarantee future results.
        """)
