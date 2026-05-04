"""Portafolio-Manager — Dashboard Streamlit.

Run:
    streamlit run app.py
"""
from __future__ import annotations
import pandas as pd
import streamlit as st
import plotly.graph_objects as go
import plotly.express as px

from src.loader import load_transactions, stock_tickers, TX_PATH
from src.prices import fetch_prices, price_on
from src.fx import fetch_fx, latest_rate
from src.portfolio import (
    build_states, closed_positions,
    daily_holdings, portfolio_value_series,
)
from src.analytics import cash_flows, benchmark_voo, drawdown, per_ticker_summary
from src.logos import logo_urls

st.set_page_config(
    page_title="Portafolio-Manager",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="collapsed",
)


# ──────────────── Estilos ────────────────
st.markdown(
    """
    <style>
    /* Ocultar toolbar superior de Streamlit (Deploy / hamburguesa) y status */
    header[data-testid="stHeader"] {display: none !important;}
    div[data-testid="stToolbar"] {display: none !important;}
    div[data-testid="stDecoration"] {display: none !important;}
    div[data-testid="stStatusWidget"] {display: none !important;}
    #MainMenu {display: none !important;}
    footer {display: none !important;}

    /* Contenedor principal: padding-top suficiente para que nada quede tapado */
    .block-container {
        padding-top: 1.8rem !important;
        padding-bottom: 2rem !important;
        max-width: 1400px;
    }

    /* Ocultar sidebar y su botón colapsador */
    section[data-testid="stSidebar"] {display: none !important;}
    div[data-testid="collapsedControl"] {display: none !important;}

    /* Tipografía compacta */
    h1 {font-size: 1.7rem !important; margin: 0 !important; padding: 0 !important; line-height: 1.2 !important;}
    h2 {font-size: 1.2rem !important; margin-top: 0.5rem !important;}
    h3 {font-size: 1.05rem !important;}

    /* Métricas: tarjetas uniformes */
    [data-testid="stMetric"] {
        background: rgba(127,127,127,0.06);
        border: 1px solid rgba(127,127,127,0.18);
        border-radius: 10px;
        padding: 14px 16px;
        min-height: 108px;          /* todas las tarjetas con la misma altura */
        display: flex;
        flex-direction: column;
        justify-content: center;
    }
    [data-testid="stMetricLabel"] {
        font-size: 0.78rem !important;
        opacity: 0.75;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
    }
    [data-testid="stMetricLabel"] > div {
        font-size: 0.78rem !important;
        white-space: nowrap;
    }
    [data-testid="stMetricValue"] {
        font-size: 1.35rem !important;
        font-weight: 600 !important;
        line-height: 1.3 !important;
    }
    [data-testid="stMetricDelta"] {
        font-size: 0.82rem !important;
        min-height: 1.2em;          /* reserva espacio aun cuando no hay delta */
    }

    /* Tabs más limpias */
    .stTabs [data-baseweb="tab-list"] {gap: 4px;}
    .stTabs [data-baseweb="tab"] {
        padding: 8px 18px;
        font-weight: 500;
    }

    /* Espaciado de gráficos */
    [data-testid="stPlotlyChart"] {margin-top: -0.3rem;}

    /* Botones en la fila de header con altura consistente */
    .stButton > button {
        height: 38px;
        border-radius: 8px;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


# ──────────────── Cache helpers ────────────────
@st.cache_data(ttl=900, show_spinner="Cargando transacciones…")
def _load_tx():
    return load_transactions()


@st.cache_data(ttl=900, show_spinner="Descargando precios…")
def _prices(tickers, start):
    return fetch_prices(list(tickers), start=start)


@st.cache_data(ttl=3600)
def _fx():
    return fetch_fx()


@st.cache_data(ttl=86400, show_spinner="Cargando logos…")
def _logos(tickers):
    return logo_urls(list(tickers))


# ──────────────── Carga ────────────────
tx = _load_tx()
tickers = stock_tickers(tx)
if "VOO" not in tickers:
    tickers.append("VOO")
prices = _prices(tickers, tx["fecha"].min())
fx = _fx()
fx_rate = latest_rate(fx)
states = build_states(tx, prices)
logos = _logos(tickers)

ph = per_ticker_summary(states, prices, fx_rate=fx_rate)
total_mv_usd = ph["market_value_usd"].sum() if not ph.empty else 0
total_cost_usd = ph["cost_basis_usd"].sum() if not ph.empty else 0
total_unreal = ph["unrealized_usd"].sum() if not ph.empty else 0
cf = cash_flows(tx)
cp = closed_positions(states)
realized = cp["realized_pnl"].sum() if not cp.empty else 0
divs_total = sum(s.dividends_usd for s in states.values())


# ──────────────── Header ────────────────
hdr_l, hdr_r = st.columns([0.72, 0.28])
with hdr_l:
    st.title("📈 Portafolio-Manager")
    st.caption(
        f"Fuente: `{TX_PATH.name}` · "
        f"USD/CLP: **${fx_rate:,.2f}** · "
        f"Última actualización: {pd.Timestamp.now():%Y-%m-%d %H:%M}"
    )
with hdr_r:
    ctrl_l, ctrl_r = st.columns([0.55, 0.45])
    with ctrl_l:
        show_clp = st.toggle("Mostrar CLP", value=True)
    with ctrl_r:
        if st.button("🔄 Refrescar", use_container_width=True):
            st.cache_data.clear()
            st.rerun()

st.markdown("")  # pequeño respiro

# ──────────────── KPIs ────────────────
unreal_pct = (total_unreal / total_cost_usd * 100) if total_cost_usd else 0
total_pnl = total_unreal + realized + divs_total

k1, k2, k3, k4, k5, k6 = st.columns(6)
k1.metric(
    "Valor de mercado",
    f"US$ {total_mv_usd:,.2f}",
    f"CLP $ {total_mv_usd * fx_rate:,.0f}" if show_clp else None,
)
k2.metric("Costo invertido", f"US$ {total_cost_usd:,.2f}")
k3.metric(
    "Unrealized P&L",
    f"US$ {total_unreal:+,.2f}",
    f"{unreal_pct:+.2f}%",
)
k4.metric("Realized P&L", f"US$ {realized:+,.2f}")
k5.metric("Dividendos", f"US$ {divs_total:,.2f}")
k6.metric("P&L total", f"US$ {total_pnl:+,.2f}")


# ──────────────── Tabs ────────────────
tab_overview, tab_positions, tab_history, tab_benchmark, tab_closed = st.tabs(
    ["Overview", "Posiciones", "Histórico", "vs VOO", "Cerradas"]
)


def _with_logo(df: pd.DataFrame, logos: dict) -> pd.DataFrame:
    df = df.copy()
    df.insert(0, "logo", df["ticker"].map(lambda t: logos.get(t, "")))
    return df


PLOT_LAYOUT = dict(
    margin=dict(l=10, r=10, t=40, b=10),
    plot_bgcolor="rgba(0,0,0,0)",
    paper_bgcolor="rgba(0,0,0,0)",
    font=dict(size=12),
)


# ─── Overview ───
with tab_overview:
    if ph.empty:
        st.warning("No hay posiciones abiertas.")
    else:
        col_a, col_b = st.columns([1.15, 1])
        with col_a:
            fig = px.pie(
                ph, names="ticker", values="market_value_usd",
                hole=0.55,
            )
            fig.update_traces(
                textinfo="label+percent",
                textposition="outside",
                marker=dict(line=dict(color="rgba(0,0,0,0)", width=0)),
            )
            fig.update_layout(
                title=dict(text="Distribución por ticker", x=0.0, font=dict(size=14)),
                height=480, showlegend=False, **PLOT_LAYOUT,
            )
            st.plotly_chart(fig, use_container_width=True)

        with col_b:
            st.markdown("**Top posiciones**")
            mini = _with_logo(
                ph[["ticker", "market_value_usd", "unrealized_pct"]].copy(),
                logos,
            )
            mini.columns = ["logo", "Ticker", "MV (USD)", "%"]
            st.dataframe(
                mini, hide_index=True, use_container_width=True, height=480,
                column_config={
                    "logo": st.column_config.ImageColumn("", width="small"),
                    "Ticker": st.column_config.TextColumn("Ticker", width="small"),
                    "MV (USD)": st.column_config.NumberColumn(format="$ %.2f"),
                    "%": st.column_config.NumberColumn("Unreal %", format="%+.2f%%"),
                },
            )


# ─── Posiciones ───
with tab_positions:
    if ph.empty:
        st.info("Sin posiciones abiertas.")
    else:
        df = _with_logo(ph, logos)
        cols_show = ["logo", "ticker", "shares", "avg_cost_usd", "last_price_usd",
                     "cost_basis_usd", "market_value_usd", "unrealized_usd",
                     "unrealized_pct", "dividends_usd"]
        if show_clp:
            cols_show.append("market_value_clp")
        df = df[cols_show]
        st.dataframe(
            df, hide_index=True, use_container_width=True, height=620,
            column_config={
                "logo": st.column_config.ImageColumn("", width="small"),
                "ticker": st.column_config.TextColumn("Ticker", width="small"),
                "shares": st.column_config.NumberColumn("Shares", format="%.4f"),
                "avg_cost_usd": st.column_config.NumberColumn("Avg cost", format="$ %.2f"),
                "last_price_usd": st.column_config.NumberColumn("Último", format="$ %.2f"),
                "cost_basis_usd": st.column_config.NumberColumn("Costo", format="$ %.2f"),
                "market_value_usd": st.column_config.NumberColumn("MV USD", format="$ %.2f"),
                "market_value_clp": st.column_config.NumberColumn("MV CLP", format="$ %,.0f"),
                "unrealized_usd": st.column_config.NumberColumn("Unrealized", format="$ %+.2f"),
                "unrealized_pct": st.column_config.NumberColumn("%", format="%+.2f%%"),
                "dividends_usd": st.column_config.NumberColumn("Dividendos", format="$ %.2f"),
            },
        )


# ─── Histórico ───
with tab_history:
    with st.spinner("Calculando holdings diarios…"):
        sh = daily_holdings(tx, prices)
        mv = portfolio_value_series(sh, prices)

    if mv.empty:
        st.info("No hay datos suficientes.")
    else:
        flows_daily = cf.set_index("date")["flow"].resample("D").sum().reindex(mv.index).fillna(0)
        cum_invested = flows_daily.cumsum()
        dd = drawdown(mv)

        # Resumen rápido
        s1, s2, s3 = st.columns(3)
        s1.metric("NAV actual", f"US$ {mv.iloc[-1]:,.2f}")
        s2.metric("Capital aportado", f"US$ {cum_invested.iloc[-1]:,.2f}")
        s3.metric("Máx. drawdown", f"{dd.min()*100:.2f}%")

        col_l, col_r = st.columns([1.6, 1])
        with col_l:
            fig = go.Figure()
            fig.add_trace(go.Scatter(
                x=mv.index, y=mv.values, name="NAV",
                line=dict(color="#1f77b4", width=2.4),
                fill="tozeroy", fillcolor="rgba(31,119,180,0.08)",
            ))
            fig.add_trace(go.Scatter(
                x=cum_invested.index, y=cum_invested.values, name="Capital aportado",
                line=dict(color="#ff7f0e", dash="dash", width=2),
            ))
            fig.update_layout(
                title=dict(text="NAV diario vs capital aportado (USD)", x=0.0, font=dict(size=14)),
                height=420, hovermode="x unified",
                legend=dict(orientation="h", y=1.08, x=0),
                **PLOT_LAYOUT,
            )
            st.plotly_chart(fig, use_container_width=True)

        with col_r:
            fig2 = go.Figure()
            fig2.add_trace(go.Scatter(
                x=dd.index, y=dd.values * 100, fill="tozeroy",
                line=dict(color="#d62728", width=1.8), name="Drawdown",
            ))
            fig2.update_layout(
                title=dict(text="Drawdown (%)", x=0.0, font=dict(size=14)),
                height=420, yaxis_title="%", **PLOT_LAYOUT,
            )
            st.plotly_chart(fig2, use_container_width=True)

        # Contribución por ticker
        if not sh.empty:
            today_sh = sh.iloc[-1]
            contrib = []
            for t in today_sh.index:
                if today_sh[t] > 1e-6 and t in prices.columns:
                    p = price_on(t, sh.index[-1], prices)
                    if p:
                        contrib.append({"ticker": t, "mv": today_sh[t] * p})
            if contrib:
                cdf = pd.DataFrame(contrib).sort_values("mv", ascending=False).head(10)
                fig3 = px.bar(
                    cdf, x="ticker", y="mv", text_auto=".0f",
                    color="mv", color_continuous_scale="Blues",
                    labels={"mv": "USD", "ticker": ""},
                )
                fig3.update_layout(
                    title=dict(text="Contribución por ticker al valor total (top 10)",
                               x=0.0, font=dict(size=14)),
                    showlegend=False, coloraxis_showscale=False,
                    height=300, **PLOT_LAYOUT,
                )
                fig3.update_traces(textposition="outside")
                st.plotly_chart(fig3, use_container_width=True)


# ─── Benchmark vs VOO ───
with tab_benchmark:
    with st.spinner("Construyendo escenario VOO…"):
        sh2 = daily_holdings(tx, prices)
        mv_port = portfolio_value_series(sh2, prices)
        mv_voo = benchmark_voo(tx, prices)

    if mv_port.empty or mv_voo.empty:
        st.info("Faltan datos.")
    else:
        idx = mv_port.index.intersection(mv_voo.index)
        flows_daily2 = cf.set_index("date")["flow"].resample("D").sum().reindex(idx).fillna(0)
        cum2 = flows_daily2.cumsum()
        port_pnl = mv_port.reindex(idx) - cum2
        voo_pnl = mv_voo.reindex(idx) - cum2

        last_port = float(port_pnl.iloc[-1])
        last_voo = float(voo_pnl.iloc[-1])
        cap = float(cum2.iloc[-1])
        alpha = last_port - last_voo

        c1, c2, c3 = st.columns(3)
        c1.metric("P&L portafolio", f"$ {last_port:+,.2f}",
                  f"{last_port/cap*100:+.2f}%" if cap else None)
        c2.metric("P&L VOO simulado", f"$ {last_voo:+,.2f}",
                  f"{last_voo/cap*100:+.2f}%" if cap else None)
        c3.metric("Alpha vs VOO", f"$ {alpha:+,.2f}",
                  f"{alpha/cap*100:+.2f}%" if cap else None)

        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=idx, y=port_pnl, name="Portafolio",
            line=dict(color="#1f77b4", width=2.5),
        ))
        fig.add_trace(go.Scatter(
            x=idx, y=voo_pnl, name="Si todo fuera VOO",
            line=dict(color="#2ca02c", width=2.5, dash="dash"),
        ))
        fig.add_hline(y=0, line=dict(color="gray", dash="dot"))
        fig.update_layout(
            title=dict(text="P&L acumulado: portafolio vs benchmark VOO (USD)",
                       x=0.0, font=dict(size=14)),
            height=460, hovermode="x unified", yaxis_title="USD",
            legend=dict(orientation="h", y=1.08, x=0),
            **PLOT_LAYOUT,
        )
        st.plotly_chart(fig, use_container_width=True)

        st.caption(
            "Escenario VOO: cada 'Compra Dólares' compra VOO al close del día y "
            "cada 'Venta Dólares' vende VOO. Comparación apples-to-apples del capital aportado."
        )


# ─── Cerradas ───
with tab_closed:
    if cp.empty:
        st.info("No hay posiciones cerradas todavía.")
    else:
        best = cp.iloc[0]
        worst = cp.iloc[-1]
        c1, c2, c3 = st.columns(3)
        c1.metric("Mejor trade",
                  f"{best['ticker']}",
                  f"$ {best['realized_pnl']:+,.2f} · {best['realized_pnl_pct']:+.1f}%")
        c2.metric("Peor trade",
                  f"{worst['ticker']}",
                  f"$ {worst['realized_pnl']:+,.2f} · {worst['realized_pnl_pct']:+.1f}%")
        c3.metric("# posiciones cerradas", f"{len(cp)}")

        df_cp = _with_logo(cp, logos)
        st.dataframe(
            df_cp, hide_index=True, use_container_width=True, height=520,
            column_config={
                "logo": st.column_config.ImageColumn("", width="small"),
                "ticker": st.column_config.TextColumn("Ticker", width="small"),
                "total_bought": st.column_config.NumberColumn("Comprado", format="$ %.2f"),
                "total_sold": st.column_config.NumberColumn("Vendido", format="$ %.2f"),
                "dividends": st.column_config.NumberColumn("Dividendos", format="$ %.2f"),
                "realized_pnl": st.column_config.NumberColumn("P&L", format="$ %+.2f"),
                "realized_pnl_pct": st.column_config.NumberColumn("%", format="%+.2f%%"),
            },
        )


st.markdown(
    "<div style='text-align:center; opacity:0.5; font-size:0.78rem; margin-top:1.2rem;'>"
    "Precios: yfinance · FX: mindicador.cl (BCCh) · "
    "Editar transacciones manualmente en <code>data/transactions.xlsx</code>"
    "</div>",
    unsafe_allow_html=True,
)
