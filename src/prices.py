"""Descarga y cachea precios históricos de cierre vía yfinance."""
from __future__ import annotations
from pathlib import Path
from datetime import datetime, timedelta
import pandas as pd
import yfinance as yf

from .loader import DATA, yf_symbol

CACHE = DATA / "prices_cache.parquet"


def _load_cache() -> pd.DataFrame:
    if CACHE.exists():
        return pd.read_parquet(CACHE)
    return pd.DataFrame(columns=["date", "ticker", "close"])


def _save_cache(df: pd.DataFrame) -> None:
    df.to_parquet(CACHE, index=False)


def fetch_prices(tickers: list[str], start: str | datetime, end: str | datetime | None = None,
                 force: bool = False) -> pd.DataFrame:
    """Devuelve un DataFrame ancho: index=fecha, columns=ticker, valores=precio cierre.

    Cachea en parquet. Si `force`, rebaja todo de yfinance.
    """
    if end is None:
        end = datetime.now()
    start = pd.Timestamp(start).normalize()
    end = pd.Timestamp(end).normalize()

    cache = _load_cache()
    needed_per_ticker: dict[str, tuple[pd.Timestamp, pd.Timestamp]] = {}
    for t in tickers:
        if force or cache.empty:
            needed_per_ticker[t] = (start, end)
            continue
        sub = cache[cache["ticker"] == t]
        if sub.empty:
            needed_per_ticker[t] = (start, end)
            continue
        max_d = sub["date"].max()
        min_d = sub["date"].min()
        # Re-descarga si falta cola o cabeza
        if max_d < end - pd.Timedelta(days=1):
            needed_per_ticker[t] = (max_d + pd.Timedelta(days=1), end)
        if min_d > start:
            existing = needed_per_ticker.get(t, (None, None))
            needed_per_ticker[t] = (start, existing[1] or end)

    new_rows: list[pd.DataFrame] = []
    for t, (s, e) in needed_per_ticker.items():
        sym = yf_symbol(t)
        try:
            hist = yf.Ticker(sym).history(start=s, end=e + pd.Timedelta(days=1), auto_adjust=False)
        except Exception as ex:
            print(f"[prices] error {t} ({sym}): {ex}")
            continue
        if hist.empty:
            print(f"[prices] sin datos para {t}")
            continue
        chunk = pd.DataFrame({
            "date": hist.index.tz_localize(None).normalize(),
            "ticker": t,
            "close": hist["Close"].values,
        })
        new_rows.append(chunk)

    if new_rows:
        cache = pd.concat([cache] + new_rows, ignore_index=True)
        cache = cache.drop_duplicates(["date", "ticker"], keep="last").sort_values(["ticker", "date"])
        _save_cache(cache)

    out = cache[cache["ticker"].isin(tickers)].copy()
    if out.empty:
        return pd.DataFrame()
    wide = out.pivot(index="date", columns="ticker", values="close").sort_index()
    return wide


def price_on(ticker: str, date: pd.Timestamp, prices: pd.DataFrame | None = None) -> float | None:
    """Precio en `date` (o el último previo disponible)."""
    if prices is None or ticker not in prices.columns:
        prices = fetch_prices([ticker], start=date - pd.Timedelta(days=10), end=date + pd.Timedelta(days=2))
    if prices.empty or ticker not in prices.columns:
        return None
    s = prices[ticker].dropna()
    if s.empty:
        return None
    s = s[s.index <= pd.Timestamp(date).normalize()]
    if s.empty:
        return None
    return float(s.iloc[-1])
