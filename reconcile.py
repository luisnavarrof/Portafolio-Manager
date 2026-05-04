"""Reporte de reconciliación: compara estado calculado vs portafolio reportado.

Uso:
    python reconcile.py
"""
from __future__ import annotations
from src.loader import load_transactions, stock_tickers
from src.prices import fetch_prices
from src.fx import latest_rate
from src.portfolio import build_states
from src.analytics import per_ticker_summary

# Snapshot reportado por el usuario (mantener sincronizado con el broker)
REPORTED = {
    'META': 266.34, 'NOW': 220.57, 'MSFT': 212.77, 'TMO': 179.15, 'NVDA': 166.08,
    'VST': 155.13, 'INTU': 137.26, 'GRAB': 133.14, 'XAR': 128.95, 'KTOS': 128.86,
    'NBIS': 128.42, 'UHS': 122.11, 'QXO': 117.97, 'PANW': 113.78, 'PLTR': 110.91,
    'ARDX': 108.44, 'OKLO': 105.64, 'NNE': 104.75, 'UBER': 101.63, 'AU': 74.59,
}


def main():
    tx = load_transactions()
    prices = fetch_prices(stock_tickers(tx), start=tx['fecha'].min())
    states = build_states(tx, prices)
    fx = latest_rate()
    ph = per_ticker_summary(states, prices, fx_rate=fx)
    calc = dict(zip(ph['ticker'], ph['market_value_usd']))

    print(f"\n{'TKR':<6} {'CALC':>10} {'REPORTED':>10} {'DIFF':>10} {'DIFF%':>8}  STATUS")
    print("-" * 60)
    issues = []
    for t, rep in REPORTED.items():
        c = calc.get(t, 0.0)
        diff = rep - c
        pct = diff / rep * 100 if rep else 0
        status = "OK" if abs(diff) < 15 else ("REVISAR" if abs(diff) < 50 else "INCOHERENCIA")
        if abs(diff) >= 15:
            issues.append((t, c, rep, diff))
        print(f"{t:<6} {c:>10.2f} {rep:>10.2f} {diff:>+10.2f} {pct:>+7.2f}%  {status}")

    print("-" * 60)
    print(f"{'TOT':<6} {sum(calc.values()):>10.2f} {sum(REPORTED.values()):>10.2f} "
          f"{sum(REPORTED.values())-sum(calc.values()):>+10.2f}")

    if issues:
        print(f"\n[!] {len(issues)} ticker(s) con incoherencias relevantes:")
        for t, c, r, d in issues:
            print(f"   {t}: calculado=${c:.2f}, reportado=${r:.2f}, faltante~={d:+.2f}  -> revisar transacciones en data/transactions.xlsx")
    else:
        print("\n[OK] Todo reconcilia.")


if __name__ == "__main__":
    main()
