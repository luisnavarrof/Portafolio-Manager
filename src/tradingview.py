"""Integración con TradingView vía deep-links y widgets embebidos.

NOTA: TradingView no expone una API pública oficial para datos en tiempo real ni un MCP oficial.
Usamos:
  - URLs `tradingview.com/chart/?symbol=EXCHANGE:TICKER` para abrir charts en la app/web.
  - Widget embebido público (Advanced Chart) renderizable en HTML/iframe.

La detección de exchange es heurística — puedes editar `EXCHANGE_OVERRIDES`.
"""
from __future__ import annotations

# Exchange por defecto si no hay override
DEFAULT_EXCHANGE = "NASDAQ"

EXCHANGE_OVERRIDES: dict[str, str] = {
    # NYSE
    "TMO": "NYSE", "VST": "NYSE", "UHS": "NYSE", "QXO": "NYSE", "AU": "NYSE",
    "UBER": "NYSE", "BRK.B": "NYSE", "JPM": "NYSE", "V": "NYSE", "LLY": "NYSE",
    "UNH": "NYSE", "NKE": "NYSE", "WBD": "NASDAQ", "KKR": "NYSE", "MSI": "NYSE",
    "NOW": "NYSE", "PLTR": "NASDAQ", "OKLO": "NYSE", "NNE": "NASDAQ", "GRAB": "NASDAQ",
    "ARDX": "NASDAQ", "PANW": "NASDAQ", "INTU": "NASDAQ", "META": "NASDAQ",
    "MSFT": "NASDAQ", "NVDA": "NASDAQ", "NBIS": "NASDAQ", "KTOS": "NASDAQ",
    # ETFs / AMEX
    "XAR": "AMEX", "VOO": "AMEX", "QQQ": "NASDAQ", "SPY": "AMEX", "IVV": "AMEX",
    "GLD": "AMEX", "DYNF": "BATS", "QQQM": "NASDAQ", "VYM": "AMEX", "MAGS": "AMEX",
    "SPDW": "AMEX", "AVEM": "AMEX", "SMH": "NASDAQ", "VDC": "AMEX", "QTUM": "AMEX",
    "MCHI": "NASDAQ", "EWJ": "AMEX", "EWY": "AMEX", "CQQQ": "AMEX", "RKNG": "NASDAQ",
    "IBOT": "NASDAQ", "ASML": "NASDAQ", "DUOL": "NASDAQ", "CRWV": "NASDAQ",
    "GOOGL": "NASDAQ", "AMZN": "NASDAQ", "AAPL": "NASDAQ", "NFLX": "NASDAQ",
    "FIG": "NYSE", "CEG": "NASDAQ", "MU": "NASDAQ", "WSBC": "NASDAQ", "IBM": "NYSE",
}


def tv_symbol(ticker: str) -> str:
    ex = EXCHANGE_OVERRIDES.get(ticker, DEFAULT_EXCHANGE)
    return f"{ex}:{ticker.replace('.', '')}"  # BRK.B → BRKB en TV


def tv_chart_url(ticker: str) -> str:
    return f"https://www.tradingview.com/chart/?symbol={tv_symbol(ticker)}"


def tv_quote_url(ticker: str) -> str:
    return f"https://www.tradingview.com/symbols/{tv_symbol(ticker).replace(':','-')}/"


def tv_embed_html(ticker: str, height: int = 500) -> str:
    """HTML para iframe embebido (Streamlit components.html)."""
    sym = tv_symbol(ticker)
    return f"""
    <div class="tradingview-widget-container">
      <div id="tv_{ticker}"></div>
      <script type="text/javascript" src="https://s3.tradingview.com/tv.js"></script>
      <script type="text/javascript">
        new TradingView.widget({{
          "autosize": true,
          "symbol": "{sym}",
          "interval": "D",
          "timezone": "America/Santiago",
          "theme": "dark",
          "style": "1",
          "locale": "es",
          "container_id": "tv_{ticker}",
          "studies": ["MASimple@tv-basicstudies", "RSI@tv-basicstudies"],
          "hide_side_toolbar": false
        }});
      </script>
    </div>
    """
