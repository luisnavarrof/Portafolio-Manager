"""Tipo de cambio USD/CLP. Fuente primaria: mindicador.cl (Banco Central de Chile, sin auth).

Fallback: yfinance ticker 'USDCLP=X' (cobertura mundial pero menos oficial).
"""
from __future__ import annotations
from pathlib import Path
from datetime import datetime
import pandas as pd
import requests
import yfinance as yf

from .loader import DATA

FX_CACHE = DATA / "fx_cache.parquet"
MINDICADOR = "https://mindicador.cl/api/dolar"


def _load() -> pd.DataFrame:
    if FX_CACHE.exists():
        return pd.read_parquet(FX_CACHE)
    return pd.DataFrame(columns=["date", "clp_per_usd"])


def _save(df: pd.DataFrame) -> None:
    df.to_parquet(FX_CACHE, index=False)


def fetch_fx(force: bool = False) -> pd.DataFrame:
    """Serie diaria USD→CLP. Index=fecha, columna 'clp_per_usd'."""
    cache = _load()
    if not force and not cache.empty and cache["date"].max() >= pd.Timestamp(datetime.now()).normalize() - pd.Timedelta(days=1):
        return cache.set_index("date").sort_index()

    rows: list[dict] = []
    try:
        r = requests.get(MINDICADOR, timeout=10)
        r.raise_for_status()
        data = r.json().get("serie", [])
        for item in data:
            rows.append({"date": pd.Timestamp(item["fecha"]).tz_localize(None).normalize(),
                         "clp_per_usd": float(item["valor"])})
    except Exception as ex:
        print(f"[fx] mindicador falló: {ex}, usando yfinance")

    # Complementar con yfinance para fechas anteriores
    if not rows or pd.Timestamp(min(r["date"] for r in rows)) > pd.Timestamp("2020-01-01"):
        try:
            yh = yf.Ticker("USDCLP=X").history(period="5y", auto_adjust=False)
            for d, px in zip(yh.index, yh["Close"]):
                rows.append({"date": pd.Timestamp(d).tz_localize(None).normalize(), "clp_per_usd": float(px)})
        except Exception as ex:
            print(f"[fx] yfinance falló: {ex}")

    if rows:
        new = pd.DataFrame(rows)
        all_df = pd.concat([cache, new], ignore_index=True)
        all_df = all_df.drop_duplicates("date", keep="last").sort_values("date")
        _save(all_df)
        cache = all_df
    return cache.set_index("date").sort_index()


def usd_to_clp(usd_value: float, date: pd.Timestamp | None = None, fx: pd.DataFrame | None = None) -> float:
    """Convierte USD a CLP en una fecha (default: hoy)."""
    if fx is None:
        fx = fetch_fx()
    if fx.empty:
        return float("nan")
    if date is None:
        rate = float(fx["clp_per_usd"].iloc[-1])
    else:
        d = pd.Timestamp(date).normalize()
        s = fx["clp_per_usd"][fx.index <= d]
        rate = float(s.iloc[-1]) if not s.empty else float(fx["clp_per_usd"].iloc[0])
    return usd_value * rate


def latest_rate(fx: pd.DataFrame | None = None) -> float:
    if fx is None:
        fx = fetch_fx()
    return float(fx["clp_per_usd"].iloc[-1]) if not fx.empty else float("nan")
