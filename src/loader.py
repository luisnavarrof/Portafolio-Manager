"""Carga y normaliza el historial de transacciones de Fintual."""
from __future__ import annotations
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
TX_PATH = DATA / "transactions.xlsx"

CASH_ASSET = "Dólares"
CLOSE_LABEL = "Cierre de posición"

# Tickers que en Fintual tienen otro símbolo en yfinance (mapping override)
TICKER_OVERRIDES: dict[str, str] = {
    # "BRK.B" en Fintual ↔ "BRK-B" en Yahoo Finance
    "BRK.B": "BRK-B",
}


def load_transactions(path: Path | str = TX_PATH) -> pd.DataFrame:
    """Devuelve el historial limpio. Columnas: fecha, tipo, activo, monto_usd, etiqueta, is_close."""
    df = pd.read_excel(path)
    df = df.rename(columns={
        "Fecha": "fecha",
        "Tipo": "tipo",
        "Activo": "activo",
        "Monto (USD)": "monto_usd",
        "Etiqueta": "etiqueta",
    })
    df["fecha"] = pd.to_datetime(df["fecha"]).dt.normalize()
    df["etiqueta"] = df["etiqueta"].fillna("").astype(str)
    df["is_close"] = df["etiqueta"].str.contains("Cierre", case=False, na=False)
    df = df.sort_values(["fecha", "tipo"], kind="stable").reset_index(drop=True)
    return df


def yf_symbol(ticker: str) -> str:
    return TICKER_OVERRIDES.get(ticker, ticker)


def stock_tickers(df: pd.DataFrame) -> list[str]:
    """Tickers únicos que NO son cash."""
    return sorted(t for t in df["activo"].unique() if t != CASH_ASSET)
