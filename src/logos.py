"""URLs de logos de acciones. Usa parqet como fuente primaria (gratis, sin API key).
Cache local en data/logos_cache.json para no hacer requests repetidos.
"""
from __future__ import annotations
import json
from pathlib import Path
import requests

from .loader import DATA

CACHE_PATH = DATA / "logos_cache.json"

# Parqet sirve logos por símbolo para la mayoría de acciones US
_PARQET = "https://assets.parqet.com/logos/symbol/{ticker}?format=jpg"

# Clearbit fallback con dominio conocido
_CLEARBIT_DOMAINS: dict[str, str] = {
    "META": "meta.com", "MSFT": "microsoft.com", "NVDA": "nvidia.com",
    "GOOGL": "google.com", "AMZN": "amazon.com", "AAPL": "apple.com",
    "NFLX": "netflix.com", "UBER": "uber.com", "PLTR": "palantir.com",
    "PANW": "paloaltonetworks.com", "INTU": "intuit.com", "TMO": "thermofisher.com",
    "NOW": "servicenow.com", "VST": "vistracorp.com", "UHS": "uhsinc.com",
    "KTOS": "kratosdefense.com", "GRAB": "grab.com", "ARDX": "ardelyx.com",
    "OKLO": "oklo.com", "NNE": "nanonuclearenergy.com", "QXO": "qxo.com",
    "NBIS": "nebius.com", "AU": "anglogoldashanti.com", "XAR": "ssga.com",
    "VOO": "vanguard.com", "QQQ": "invesco.com", "GLD": "spdrgoldshares.com",
    "ASML": "asml.com", "LLY": "lilly.com", "JPM": "jpmorganchase.com",
    "IBM": "ibm.com", "MU": "micron.com", "DUOL": "duolingo.com",
    "NKE": "nike.com", "V": "visa.com", "KKR": "kkr.com",
}


def _load_cache() -> dict[str, str]:
    if CACHE_PATH.exists():
        return json.loads(CACHE_PATH.read_text())
    return {}


def _save_cache(c: dict) -> None:
    CACHE_PATH.write_text(json.dumps(c, indent=2))


def logo_url(ticker: str) -> str:
    """Devuelve URL del logo. Prioridad: parqet → clearbit → vacío."""
    cache = _load_cache()
    if ticker in cache:
        return cache[ticker]

    # Intentar parqet primero (sin validar — el cliente hace lazy-load)
    url = _PARQET.format(ticker=ticker)
    try:
        r = requests.head(url, timeout=4, allow_redirects=True)
        if r.status_code == 200:
            cache[ticker] = url
            _save_cache(cache)
            return url
    except Exception:
        pass

    # Fallback clearbit
    domain = _CLEARBIT_DOMAINS.get(ticker)
    if domain:
        url = f"https://logo.clearbit.com/{domain}"
        cache[ticker] = url
        _save_cache(cache)
        return url

    cache[ticker] = ""
    _save_cache(cache)
    return ""


def logo_urls(tickers: list[str]) -> dict[str, str]:
    """Batch: devuelve dict ticker→url."""
    return {t: logo_url(t) for t in tickers}
