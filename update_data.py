"""Script para refrescar todo el cache (precios + FX). Útil correr a diario.

Uso:
    python update_data.py            # incremental
    python update_data.py --force    # rebajar todo desde cero
"""
from __future__ import annotations
import sys
from src.loader import load_transactions, stock_tickers
from src.prices import fetch_prices
from src.fx import fetch_fx


def main(force: bool = False):
    tx = load_transactions()
    tickers = stock_tickers(tx)
    if "VOO" not in tickers:
        tickers.append("VOO")
    print(f"[update] {len(tickers)} tickers, force={force}")
    start = tx["fecha"].min()
    prices = fetch_prices(tickers, start=start, force=force)
    print(f"[update] precios: {prices.shape if not prices.empty else 'vacío'}")
    fx = fetch_fx(force=force)
    print(f"[update] FX rows: {len(fx)}, último={fx.index.max() if not fx.empty else 'n/a'}")
    print("[update] OK")


if __name__ == "__main__":
    force = "--force" in sys.argv
    main(force=force)
