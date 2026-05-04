"""Reconstrucción de posiciones lote a lote (FIFO) usando la etiqueta 'Cierre de posición'.

Cada Compra/Venta solo trae monto USD; estimamos shares usando el precio yfinance del día.
Cuando una venta tiene `is_close=True`, la posición acumulada vuelve a 0 (autoritativo del broker).
"""
from __future__ import annotations
from dataclasses import dataclass, field
from collections import deque, defaultdict
import pandas as pd

from .loader import CASH_ASSET, load_transactions, stock_tickers
from .prices import fetch_prices, price_on


@dataclass
class Lot:
    fecha: pd.Timestamp
    shares: float
    cost_usd: float

    @property
    def cost_per_share(self) -> float:
        return self.cost_usd / self.shares if self.shares else 0.0


@dataclass
class TickerState:
    lots: deque[Lot] = field(default_factory=deque)
    realized_pnl_usd: float = 0.0
    dividends_usd: float = 0.0
    total_bought_usd: float = 0.0
    total_sold_usd: float = 0.0
    closed: bool = False

    @property
    def shares(self) -> float:
        return sum(l.shares for l in self.lots)

    @property
    def cost_basis_usd(self) -> float:
        return sum(l.cost_usd for l in self.lots)

    @property
    def avg_cost(self) -> float:
        s = self.shares
        return self.cost_basis_usd / s if s > 1e-9 else 0.0


def build_states(tx: pd.DataFrame, prices: pd.DataFrame) -> dict[str, TickerState]:
    """Recorre transacciones por orden cronológico, devuelve estado final por ticker."""
    states: dict[str, TickerState] = defaultdict(TickerState)

    for _, row in tx.iterrows():
        t = row["activo"]
        if t == CASH_ASSET:
            continue
        st = states[t]
        amt = float(row["monto_usd"])
        date = pd.Timestamp(row["fecha"]).normalize()
        tipo = row["tipo"]

        if tipo == "Compra":
            px = price_on(t, date, prices)
            if px is None or px <= 0:
                continue
            shares = amt / px
            st.lots.append(Lot(fecha=date, shares=shares, cost_usd=amt))
            st.total_bought_usd += amt
            st.closed = False

        elif tipo == "Venta":
            st.total_sold_usd += amt
            if row["is_close"]:
                # Autoritativo: cierra todo
                cost = st.cost_basis_usd
                st.realized_pnl_usd += (amt - cost)
                st.lots.clear()
                st.closed = True
            else:
                # Venta parcial: estimar shares vendidas con precio del día
                px = price_on(t, date, prices)
                if px is None or px <= 0:
                    continue
                shares_to_sell = amt / px
                cost_removed = 0.0
                remaining = shares_to_sell
                while remaining > 1e-9 and st.lots:
                    lot = st.lots[0]
                    if lot.shares <= remaining + 1e-9:
                        cost_removed += lot.cost_usd
                        remaining -= lot.shares
                        st.lots.popleft()
                    else:
                        frac = remaining / lot.shares
                        cost_removed += lot.cost_usd * frac
                        lot.shares -= remaining
                        lot.cost_usd *= (1 - frac)
                        remaining = 0
                st.realized_pnl_usd += (amt - cost_removed)

        elif tipo == "Dividendo":
            st.dividends_usd += amt

        # 'Ganancia' y 'Compensación' se aplican sobre Dólares (cash); ignorados a nivel ticker

    return states


def current_holdings(states: dict[str, TickerState], prices: pd.DataFrame,
                     as_of: pd.Timestamp | None = None) -> pd.DataFrame:
    """Tabla con posiciones abiertas y métricas actuales."""
    if as_of is None:
        as_of = pd.Timestamp.today().normalize()
    rows = []
    for t, st in states.items():
        if st.closed or st.shares <= 1e-6:
            continue
        last_px = price_on(t, as_of, prices)
        if last_px is None:
            continue
        market_value = st.shares * last_px
        pnl = market_value - st.cost_basis_usd
        pnl_pct = pnl / st.cost_basis_usd * 100 if st.cost_basis_usd else 0
        rows.append({
            "ticker": t,
            "shares": st.shares,
            "avg_cost": st.avg_cost,
            "last_price": last_px,
            "cost_basis": st.cost_basis_usd,
            "market_value": market_value,
            "unrealized_pnl": pnl,
            "unrealized_pnl_pct": pnl_pct,
            "dividends": st.dividends_usd,
            "realized_pnl_legacy": st.realized_pnl_usd,
        })
    df = pd.DataFrame(rows).sort_values("market_value", ascending=False).reset_index(drop=True)
    return df


def closed_positions(states: dict[str, TickerState]) -> pd.DataFrame:
    """Posiciones cerradas con su P&L realizado."""
    rows = []
    for t, st in states.items():
        if st.closed or (st.shares <= 1e-6 and st.total_bought_usd > 0):
            rows.append({
                "ticker": t,
                "total_bought": st.total_bought_usd,
                "total_sold": st.total_sold_usd,
                "dividends": st.dividends_usd,
                "realized_pnl": st.realized_pnl_usd,
                "realized_pnl_pct": st.realized_pnl_usd / st.total_bought_usd * 100 if st.total_bought_usd else 0,
            })
    return pd.DataFrame(rows).sort_values("realized_pnl", ascending=False).reset_index(drop=True)


def daily_holdings(tx: pd.DataFrame, prices: pd.DataFrame) -> pd.DataFrame:
    """Devuelve un DataFrame ancho con shares por ticker en cada día (forward-filled)."""
    tickers = stock_tickers(tx)
    if not tickers:
        return pd.DataFrame()

    start = tx["fecha"].min()
    end = pd.Timestamp.today().normalize()
    all_days = pd.date_range(start, end, freq="D")

    states: dict[str, TickerState] = defaultdict(TickerState)
    snapshots: list[dict] = []

    tx_by_day = tx.groupby(tx["fecha"].dt.normalize())

    for day in all_days:
        if day in tx_by_day.groups:
            day_tx = tx_by_day.get_group(day)
            for _, row in day_tx.iterrows():
                t = row["activo"]
                if t == CASH_ASSET:
                    continue
                st = states[t]
                amt = float(row["monto_usd"])
                tipo = row["tipo"]
                if tipo == "Compra":
                    px = price_on(t, day, prices)
                    if px is None or px <= 0:
                        continue
                    st.lots.append(Lot(day, amt / px, amt))
                    st.closed = False
                elif tipo == "Venta":
                    if row["is_close"]:
                        st.lots.clear()
                        st.closed = True
                    else:
                        px = price_on(t, day, prices)
                        if px is None or px <= 0:
                            continue
                        shares_to_sell = amt / px
                        rem = shares_to_sell
                        while rem > 1e-9 and st.lots:
                            lot = st.lots[0]
                            if lot.shares <= rem + 1e-9:
                                rem -= lot.shares
                                st.lots.popleft()
                            else:
                                frac = rem / lot.shares
                                lot.shares -= rem
                                lot.cost_usd *= (1 - frac)
                                rem = 0

        snap = {"date": day}
        for t in tickers:
            snap[t] = states[t].shares
        snapshots.append(snap)

    return pd.DataFrame(snapshots).set_index("date")


def portfolio_value_series(daily_shares: pd.DataFrame, prices: pd.DataFrame) -> pd.Series:
    """Serie diaria de market value total del portafolio."""
    if daily_shares.empty:
        return pd.Series(dtype=float)
    common_idx = daily_shares.index
    px = prices.reindex(common_idx).ffill()
    aligned_cols = [c for c in daily_shares.columns if c in px.columns]
    sh = daily_shares[aligned_cols]
    px = px[aligned_cols]
    mv = (sh * px).sum(axis=1)
    return mv
