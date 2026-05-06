"""Busqueda de tickers y datos fundamentales via Yahoo Finance / yfinance."""
from __future__ import annotations
import requests
import yfinance as yf
from .loader import yf_symbol


_SEARCH_URL = "https://query2.finance.yahoo.com/v1/finance/search"
_HEADERS = {"User-Agent": "Mozilla/5.0"}


def search_tickers(query: str, max_results: int = 8) -> list[dict]:
    """Busca tickers en Yahoo Finance por simbolo o nombre de empresa."""
    if not query or len(query) < 1:
        return []
    params = {
        "q": query,
        "quotesCount": max_results,
        "newsCount": 0,
        "listsCount": 0,
        "enableFuzzyQuery": True,
    }
    try:
        r = requests.get(_SEARCH_URL, params=params, headers=_HEADERS, timeout=5)
        r.raise_for_status()
        data = r.json()
    except Exception:
        return []

    results = []
    for q in data.get("quotes", []):
        qtype = q.get("quoteType", "")
        if qtype not in ("EQUITY", "ETF"):
            continue
        results.append({
            "symbol": q.get("symbol", ""),
            "name": q.get("shortname") or q.get("longname") or "",
            "exchange": q.get("exchDisp") or q.get("exchange") or "",
            "type": qtype,
        })
    return results


def fetch_stock_info(tickers: list[str]) -> dict[str, dict]:
    """Obtiene datos fundamentales de cada ticker via yfinance.

    Devuelve dict ticker -> {name, sector, industry, description, market_cap, ...}.
    Para ETFs usa 'category' en vez de 'sector'.
    """
    out: dict[str, dict] = {}
    for t in tickers:
        sym = yf_symbol(t)
        try:
            info = yf.Ticker(sym).info or {}
        except Exception:
            info = {}
        qtype = info.get("quoteType", "EQUITY")
        sector = info.get("sector", "")
        if not sector and qtype == "ETF":
            sector = info.get("category", "") or "ETF"
        out[t] = {
            "name": info.get("shortName") or info.get("longName") or t,
            "sector": sector or "Sin datos",
            "industry": info.get("industry", "") or ("ETF" if qtype == "ETF" else "Sin datos"),
            "description": info.get("longBusinessSummary", ""),
            "market_cap": info.get("marketCap") or 0,
            "country": info.get("country", ""),
            "website": info.get("website", ""),
            "quote_type": qtype,
        }
    return out
