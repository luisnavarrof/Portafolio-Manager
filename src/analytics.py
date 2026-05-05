"""Métricas de rendimiento: TWR, vs benchmark VOO, drawdown, etc."""
from __future__ import annotations
import numpy as np
import pandas as pd

from .loader import CASH_ASSET, load_transactions
from .prices import fetch_prices, price_on


def cash_flows(tx: pd.DataFrame) -> pd.DataFrame:
    """Flujos de capital al portafolio (compras netas de USD).

    Compra Dólares  → flujo positivo (entrada de capital)
    Venta Dólares   → flujo negativo (retiro)
    """
    cash = tx[tx["activo"] == CASH_ASSET].copy()
    cash["flow"] = cash.apply(
        lambda r: r["monto_usd"] if r["tipo"] == "Compra" else (-r["monto_usd"] if r["tipo"] == "Venta" else 0.0),
        axis=1,
    )
    return cash[["fecha", "tipo", "flow"]].rename(columns={"fecha": "date"})


def benchmark_voo(tx: pd.DataFrame, prices: pd.DataFrame) -> pd.Series:
    """Simula: cada Compra Dólares se invierte íntegramente en VOO; cada Venta Dólares
    vende VOO al precio del día. Devuelve serie diaria de market value de esa cartera VOO.
    """
    cf = cash_flows(tx)
    if "VOO" not in prices.columns:
        prices = fetch_prices(["VOO"], start=tx["fecha"].min())
    voo = prices["VOO"].dropna()
    if voo.empty:
        return pd.Series(dtype=float)
    days = pd.date_range(tx["fecha"].min(), pd.Timestamp.today().normalize(), freq="D")
    voo_daily = voo.reindex(days).ffill()

    shares = 0.0
    sh_series = []
    flows_by_day = cf.groupby(cf["date"].dt.normalize())["flow"].sum()
    for d in days:
        if d in flows_by_day.index:
            flow = flows_by_day.loc[d]
            px = voo_daily.loc[d]
            if pd.notna(px) and px > 0:
                shares += flow / px
        sh_series.append(shares)
    sh = pd.Series(sh_series, index=days)
    mv = sh * voo_daily
    return mv


def twr(value_series: pd.Series, flows: pd.Series) -> pd.Series:
    """Time-weighted return: encadena retornos diarios eliminando el efecto de los flujos.

    flows: serie alineada con value_series; positivo=aporte, negativo=retiro.
    """
    v = value_series.dropna()
    v = v[v > 0]  # skip days with zero NAV (missing prices / portfolio not yet started)
    f = flows.reindex(v.index).fillna(0.0)
    rets = []
    prev = None
    for i, (d, val) in enumerate(v.items()):
        if prev is None:
            rets.append(0.0)
        else:
            denom = prev_val + f.iloc[i]
            if denom > 0 and val > 0:
                r = (val - denom) / denom
            else:
                # NAV=0 significa precios no disponibles ese día, no pérdida real
                r = 0.0
            rets.append(r)
        prev = d
        prev_val = val
    cum = (1 + pd.Series(rets, index=v.index)).cumprod() - 1
    return cum


def drawdown(value_series: pd.Series) -> pd.Series:
    peak = value_series.cummax()
    return (value_series - peak) / peak


def per_ticker_summary(states_dict, prices: pd.DataFrame, fx_rate: float = 1.0,
                       live: dict[str, float] | None = None) -> pd.DataFrame:
    """Resumen por ticker incluyendo histórico (rendimiento absoluto y %).

    Si `live` está disponible (dict ticker→precio), usa la cotización intradía
    en lugar del último cierre.
    """
    rows = []
    today = pd.Timestamp.today().normalize()
    for t, st in states_dict.items():
        if st.shares <= 1e-6:
            continue
        last_px = (live or {}).get(t)
        if last_px is None:
            last_px = price_on(t, today, prices)
        if last_px is None:
            continue
        mv = st.shares * last_px
        cb = st.cost_basis_usd
        unrealized = mv - cb
        rows.append({
            "ticker": t,
            "shares": round(st.shares, 4),
            "avg_cost_usd": round(st.avg_cost, 2),
            "last_price_usd": round(last_px, 2),
            "cost_basis_usd": round(cb, 2),
            "market_value_usd": round(mv, 2),
            "market_value_clp": round(mv * fx_rate, 0),
            "unrealized_usd": round(unrealized, 2),
            "unrealized_pct": round(unrealized / cb * 100, 2) if cb else 0,
            "dividends_usd": round(st.dividends_usd, 2),
        })
    df = pd.DataFrame(rows).sort_values("market_value_usd", ascending=False).reset_index(drop=True)
    return df
