"""Portafolio-Manager — Dashboard Streamlit.

Run:
    streamlit run app.py
"""
from __future__ import annotations
from datetime import date
import pandas as pd
import streamlit as st
import plotly.graph_objects as go
import plotly.express as px

from src.loader import load_transactions, stock_tickers, TX_PATH, CASH_ASSET
from src.prices import fetch_prices, price_on, live_quotes
from src.fx import fetch_fx, latest_rate
from src.portfolio import (
    build_states, closed_positions,
    daily_holdings, portfolio_value_series,
)
from src.analytics import cash_flows, benchmark_voo, drawdown, per_ticker_summary
from src.logos import logo_urls
from src.storage import save_transactions

try:
    from streamlit_autorefresh import st_autorefresh
    _HAS_AUTOREFRESH = True
except ImportError:
    _HAS_AUTOREFRESH = False


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
    header[data-testid="stHeader"] {display: none !important;}
    div[data-testid="stToolbar"] {display: none !important;}
    div[data-testid="stDecoration"] {display: none !important;}
    div[data-testid="stStatusWidget"] {display: none !important;}
    #MainMenu {display: none !important;}
    footer {display: none !important;}

    .block-container {
        padding-top: 1.8rem !important;
        padding-bottom: 2rem !important;
        max-width: 1400px;
    }

    section[data-testid="stSidebar"] {display: none !important;}
    div[data-testid="collapsedControl"] {display: none !important;}

    h1 {font-size: 1.7rem !important; margin: 0 !important; padding: 0 !important; line-height: 1.2 !important;}
    h2 {font-size: 1.2rem !important; margin-top: 0.5rem !important;}
    h3 {font-size: 1.05rem !important;}

    [data-testid="stMetric"] {
        background: rgba(127,127,127,0.06);
        border: 1px solid rgba(127,127,127,0.18);
        border-radius: 10px;
        padding: 14px 16px;
        min-height: 108px;
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
        min-height: 1.2em;
    }

    .stTabs [data-baseweb="tab-list"] {gap: 4px;}
    .stTabs [data-baseweb="tab"] {
        padding: 8px 18px;
        font-weight: 500;
    }

    [data-testid="stPlotlyChart"] {margin-top: -0.3rem;}

    .stButton > button {
        height: 38px;
        border-radius: 8px;
    }

    /* Indicador "Live" del refresh */
    .live-badge {
        display: inline-block;
        background: #1f7a3d;
        color: #d4f5dd;
        padding: 2px 8px;
        border-radius: 999px;
        font-size: 0.72rem;
        font-weight: 600;
        letter-spacing: 0.02em;
        margin-left: 6px;
    }
    .live-badge .dot {
        display: inline-block; width: 7px; height: 7px;
        background: #4ade80; border-radius: 50%;
        margin-right: 5px; vertical-align: middle;
        animation: pulse 1.4s ease-in-out infinite;
    }
    @keyframes pulse {0%,100%{opacity:1;}50%{opacity:0.35;}}
    </style>
    """,
    unsafe_allow_html=True,
)


# ──────────────── Cache helpers ────────────────
@st.cache_data(ttl=60, show_spinner="Cargando transacciones…")
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


@st.cache_data(ttl=60, show_spinner=False)
def _live(tickers, _bucket):
    """Cotizaciones intradía. `_bucket` invalida la cache cada N segundos."""
    return live_quotes(list(tickers))


def _gh_secrets() -> dict | None:
    try:
        gh = st.secrets.get("github", None)
        if gh and gh.get("token") and gh.get("repo"):
            return dict(gh)
    except (FileNotFoundError, KeyError, AttributeError):
        pass
    return None


# ──────────────── Estado de UI ────────────────
if "live_enabled" not in st.session_state:
    st.session_state.live_enabled = True
if "live_interval" not in st.session_state:
    st.session_state.live_interval = 60


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

# Live quotes (solo posiciones abiertas, ahorra tiempo)
open_tickers = [t for t, s in states.items() if s.shares > 1e-6]
live = {}
if st.session_state.live_enabled and open_tickers:
    bucket = int(pd.Timestamp.now().timestamp() // st.session_state.live_interval)
    try:
        live = _live(tuple(sorted(open_tickers)), bucket)
    except Exception as ex:
        live = {}
        st.warning(f"Live quotes no disponibles: {ex}")

ph = per_ticker_summary(states, prices, fx_rate=fx_rate, live=live)
total_mv_usd = ph["market_value_usd"].sum() if not ph.empty else 0
total_cost_usd = ph["cost_basis_usd"].sum() if not ph.empty else 0
total_unreal = ph["unrealized_usd"].sum() if not ph.empty else 0
cf = cash_flows(tx)
cp = closed_positions(states)
realized = cp["realized_pnl"].sum() if not cp.empty else 0
divs_total = sum(s.dividends_usd for s in states.values())


# ──────────────── Header ────────────────
hdr_l, hdr_r = st.columns([0.62, 0.38])
with hdr_l:
    badge = ('<span class="live-badge"><span class="dot"></span>LIVE</span>'
             if st.session_state.live_enabled and live else "")
    st.markdown(f"# 📈 Portafolio-Manager{badge}", unsafe_allow_html=True)
    st.caption(
        f"Fuente: `{TX_PATH.name}` · "
        f"USD/CLP: **${fx_rate:,.2f}** · "
        f"Última actualización: {pd.Timestamp.now():%Y-%m-%d %H:%M:%S}"
    )
with hdr_r:
    c1, c2, c3, c4 = st.columns([0.28, 0.32, 0.20, 0.20])
    with c1:
        st.session_state.live_enabled = st.toggle(
            "🔴 Live", value=st.session_state.live_enabled,
            help="Refresca precios intradía cada N segundos",
        )
    with c2:
        st.session_state.live_interval = st.selectbox(
            "Intervalo", [30, 60, 120, 300],
            index=[30, 60, 120, 300].index(st.session_state.live_interval),
            format_func=lambda s: f"{s}s" if s < 60 else f"{s//60}min",
            label_visibility="collapsed",
        )
    with c3:
        show_clp = st.toggle("CLP", value=True)
    with c4:
        if st.button("🔄", help="Forzar refresh completo", use_container_width=True):
            st.cache_data.clear()
            st.rerun()

# Auto-refresh JS
if _HAS_AUTOREFRESH and st.session_state.live_enabled:
    st_autorefresh(interval=st.session_state.live_interval * 1000, key="live_refresh")

st.markdown("")

# ──────────────── KPIs ────────────────
unreal_pct = (total_unreal / total_cost_usd * 100) if total_cost_usd else 0
total_pnl = total_unreal + realized + divs_total

k1, k2, k3, k4, k5, k6 = st.columns(6)
k1.metric("Valor de mercado", f"US$ {total_mv_usd:,.2f}",
          f"CLP $ {total_mv_usd * fx_rate:,.0f}" if show_clp else None)
k2.metric("Costo invertido", f"US$ {total_cost_usd:,.2f}")
k3.metric("Unrealized P&L", f"US$ {total_unreal:+,.2f}", f"{unreal_pct:+.2f}%")
k4.metric("Realized P&L", f"US$ {realized:+,.2f}")
k5.metric("Dividendos", f"US$ {divs_total:,.2f}")
k6.metric("P&L total", f"US$ {total_pnl:+,.2f}")


# ──────────────── Tabs ────────────────
tab_overview, tab_positions, tab_history, tab_benchmark, tab_closed, tab_manage = st.tabs(
    ["Overview", "Posiciones", "Histórico", "vs VOO", "Cerradas", "⚙️ Gestionar"]
)


def _with_logo(df: pd.DataFrame, logos: dict) -> pd.DataFrame:
    df = df.copy()
    df.insert(0, "logo", df["ticker"].map(lambda t: logos.get(t, "")))
    return df


PLOT_LAYOUT = dict(
    margin=dict(l=10, r=10, t=40, b=10),
    plot_bgcolor="rgba(0,0,0,0)",
    paper_bgcolor="rgba(0,0,0,0)",
    font=dict(size=12, color="#e6edf3"),
)


# ─── Overview ───
with tab_overview:
    if ph.empty:
        st.warning("No hay posiciones abiertas.")
    else:
        col_pie, col_tbl = st.columns([1.05, 1])

        with col_pie:
            st.markdown("**Distribución por ticker**")
            ph_sorted = ph.sort_values("market_value_usd", ascending=False).copy()

            # Etiquetas: solo en slices >= 4% (las pequeñas se ven en el legend / hover)
            total = ph_sorted["market_value_usd"].sum()
            ph_sorted["pct"] = ph_sorted["market_value_usd"] / total * 100
            ph_sorted["text"] = ph_sorted.apply(
                lambda r: f"{r['ticker']}<br>{r['pct']:.1f}%" if r["pct"] >= 4 else "",
                axis=1,
            )

            fig = go.Figure(go.Pie(
                labels=ph_sorted["ticker"],
                values=ph_sorted["market_value_usd"],
                hole=0.55,
                text=ph_sorted["text"],
                textinfo="text",
                textposition="inside",
                insidetextorientation="horizontal",
                hovertemplate="<b>%{label}</b><br>$ %{value:,.2f} · %{percent}<extra></extra>",
                marker=dict(line=dict(color="rgba(0,0,0,0)", width=0)),
                sort=False,
                direction="clockwise",
            ))
            # Anotación central con totals
            fig.add_annotation(
                text=f"<b>US$ {total:,.0f}</b><br><span style='font-size:11px;opacity:0.7'>{len(ph_sorted)} posiciones</span>",
                showarrow=False, font=dict(size=16, color="#e6edf3"),
                x=0.5, y=0.5, xanchor="center", yanchor="middle",
            )
            fig.update_layout(
                showlegend=True,
                legend=dict(
                    orientation="v", yanchor="middle", y=0.5,
                    xanchor="left", x=1.02,
                    font=dict(size=11),
                    itemsizing="constant",
                ),
                height=520,
                margin=dict(l=10, r=120, t=10, b=10),
                plot_bgcolor="rgba(0,0,0,0)",
                paper_bgcolor="rgba(0,0,0,0)",
                font=dict(color="#e6edf3"),
                uniformtext_minsize=10, uniformtext_mode="hide",
            )
            st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

        with col_tbl:
            st.markdown("**Top posiciones**")
            mini = _with_logo(
                ph[["ticker", "market_value_usd", "unrealized_pct"]].copy(),
                logos,
            )
            mini.columns = ["logo", "Ticker", "MV (USD)", "%"]
            st.dataframe(
                mini, hide_index=True, use_container_width=True, height=520,
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

        if not sh.empty:
            today_sh = sh.iloc[-1]
            contrib = []
            for t in today_sh.index:
                if today_sh[t] > 1e-6 and t in prices.columns:
                    p = live.get(t) or price_on(t, sh.index[-1], prices)
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
        # Best/worst por valor absoluto
        cp_by_usd = cp.sort_values("realized_pnl", ascending=False)
        best_usd = cp_by_usd.iloc[0]
        worst_usd = cp_by_usd.iloc[-1]
        # Best por porcentaje
        cp_by_pct = cp.sort_values("realized_pnl_pct", ascending=False)
        best_pct = cp_by_pct.iloc[0]

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Mejor trade (USD)", best_usd["ticker"],
                  f"$ {best_usd['realized_pnl']:+,.2f} · {best_usd['realized_pnl_pct']:+.1f}%")
        c2.metric("Mejor trade (%)", best_pct["ticker"],
                  f"$ {best_pct['realized_pnl']:+,.2f} · {best_pct['realized_pnl_pct']:+.1f}%")
        c3.metric("Peor trade (USD)", worst_usd["ticker"],
                  f"$ {worst_usd['realized_pnl']:+,.2f} · {worst_usd['realized_pnl_pct']:+.1f}%")
        c4.metric("# posiciones cerradas", f"{len(cp)}")

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


# ─── Gestionar transacciones ───
with tab_manage:
    gh = _gh_secrets()
    if gh:
        st.success(
            f"🔗 Sincronización GitHub activa → `{gh['repo']}@{gh.get('branch','main')}`. "
            "Los cambios se commitean al repo y la app se redespliega automáticamente."
        )
    else:
        st.info(
            "💾 Modo local: los cambios se guardan en `data/transactions.xlsx` pero **no persisten** "
            "en Streamlit Cloud entre reinicios. Configura los secrets de GitHub para sync — "
            "ver instrucciones al final de esta tab."
        )

    st.markdown("### ➕ Agregar transacción")
    with st.form("add_tx_form", clear_on_submit=True):
        c1, c2, c3, c4 = st.columns([1, 1, 1, 1])
        f_fecha = c1.date_input("Fecha", value=date.today())
        f_tipo = c2.selectbox("Tipo", ["Compra", "Venta", "Dividendo", "Ganancia", "Compensación"])
        existing_assets = sorted(set(tx["activo"].unique().tolist() + [CASH_ASSET]))
        f_activo_pick = c3.selectbox("Activo", existing_assets + ["⊕ Nuevo ticker…"])
        f_activo_new = c3.text_input("Nuevo ticker", placeholder="ej. AAPL",
                                      label_visibility="collapsed",
                                      disabled=(f_activo_pick != "⊕ Nuevo ticker…"))
        f_monto = c4.number_input("Monto (USD)", min_value=0.0, step=0.01, format="%.2f")
        c5, c6 = st.columns([1, 3])
        f_cierre = c5.checkbox("Cierre de posición", value=False,
                                help="Marca esta venta como cierre completo de la posición.")
        f_etiqueta = c6.text_input("Etiqueta (opcional)",
                                    value="Cierre de posición" if False else "")
        submitted = st.form_submit_button("Guardar transacción", type="primary")

        if submitted:
            activo = f_activo_new.strip().upper() if f_activo_pick == "⊕ Nuevo ticker…" else f_activo_pick
            if not activo:
                st.error("Activo vacío.")
            elif f_monto <= 0:
                st.error("Monto debe ser > 0.")
            else:
                etiqueta = "Cierre de posición" if f_cierre else (f_etiqueta or "")
                new_row = pd.DataFrame([{
                    "fecha": pd.Timestamp(f_fecha),
                    "tipo": f_tipo,
                    "activo": activo,
                    "monto_usd": float(f_monto),
                    "etiqueta": etiqueta,
                    "is_close": bool(f_cierre or "Cierre" in etiqueta),
                }])
                tx_new = pd.concat([tx, new_row], ignore_index=True)
                tx_new = tx_new.sort_values(["fecha", "tipo"], kind="stable").reset_index(drop=True)
                ok, msg = save_transactions(
                    tx_new, gh_secrets=gh,
                    message=f"Add tx: {f_tipo} {activo} ${f_monto:.2f} ({f_fecha})",
                )
                if ok:
                    st.success(f"✅ {msg}")
                    st.cache_data.clear()
                    st.rerun()
                else:
                    st.error(f"❌ {msg}")

    st.divider()
    st.markdown("### ✏️ Editar / eliminar transacciones existentes")
    st.caption("Edita celdas o elimina filas (botón 🗑️ a la izquierda). Click 'Guardar cambios' al terminar.")

    edit_df = tx[["fecha", "tipo", "activo", "monto_usd", "etiqueta"]].copy()
    edit_df["fecha"] = pd.to_datetime(edit_df["fecha"]).dt.date

    edited = st.data_editor(
        edit_df, num_rows="dynamic", use_container_width=True, height=420,
        key="tx_editor",
        column_config={
            "fecha": st.column_config.DateColumn("Fecha", required=True),
            "tipo": st.column_config.SelectboxColumn(
                "Tipo", options=["Compra", "Venta", "Dividendo", "Ganancia", "Compensación"],
                required=True,
            ),
            "activo": st.column_config.TextColumn("Activo", required=True),
            "monto_usd": st.column_config.NumberColumn("Monto (USD)", format="%.2f", required=True),
            "etiqueta": st.column_config.TextColumn("Etiqueta"),
        },
    )

    csave, cdl, _ = st.columns([1, 1, 3])
    if csave.button("💾 Guardar cambios", type="primary"):
        edited2 = edited.copy()
        edited2["fecha"] = pd.to_datetime(edited2["fecha"])
        edited2["etiqueta"] = edited2["etiqueta"].fillna("").astype(str)
        ok, msg = save_transactions(
            edited2, gh_secrets=gh,
            message="Edit transactions via dashboard",
        )
        if ok:
            st.success(f"✅ {msg}")
            st.cache_data.clear()
            st.rerun()
        else:
            st.error(f"❌ {msg}")

    # Descarga de respaldo del Excel actual
    from src.storage import df_to_excel_bytes
    cdl.download_button(
        "⬇️ Descargar Excel",
        data=df_to_excel_bytes(tx),
        file_name=TX_PATH.name,
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )

    if not gh:
        with st.expander("🔧 Configurar sync con GitHub (instrucciones)"):
            st.markdown("""
**Para que los cambios desde la app desplegada persistan**, necesitas un Personal Access Token de GitHub
con permiso de escritura en este repo.

1. Ve a [github.com/settings/personal-access-tokens/new](https://github.com/settings/personal-access-tokens/new)
2. Crea un **fine-grained token**:
   - **Repository access:** Only select repositories → elegir `Portafolio-Manager`
   - **Repository permissions:** `Contents` → **Read and write**
   - Expiration: 90 días o más
3. Copia el token (`github_pat_...`).
4. En tu app de Streamlit Cloud → ⋮ Manage app → **Settings → Secrets**, pega:
   ```toml
   [github]
   token = "github_pat_xxxxx"
   repo = "luisnavarrof/Portafolio-Manager"
   branch = "main"
   file_path = "data/transactions.xlsx"
   ```
5. Guarda. La app se redesplegará automáticamente con sync activo.
            """)


st.markdown(
    "<div style='text-align:center; opacity:0.5; font-size:0.78rem; margin-top:1.2rem;'>"
    "Precios: yfinance · FX: mindicador.cl (BCCh) · "
    f"Auto-refresh: {st.session_state.live_interval}s"
    "</div>",
    unsafe_allow_html=True,
)
