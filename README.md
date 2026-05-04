# Portafolio-Manager

Dashboard personal para monitorear el portafolio de Fintual (Acciones USA), comparar contra VOO y mantenerlo sincronizado con la realidad del broker.

## Quickstart

```bash
pip install -r requirements.txt
python update_data.py          # descarga precios y FX
streamlit run app.py
```

Se abre en http://localhost:8501

## Workflow al hacer un movimiento en el broker

1. Edita `data/transactions.xlsx` agregando la nueva fila:
   - **Fecha** (YYYY-MM-DD)
   - **Tipo**: `Compra` / `Venta` / `Dividendo` / `Ganancia` / `Compensación`
   - **Activo**: ticker (ej. `NVDA`) o `Dólares` para conversiones CLP↔USD
   - **Monto (USD)**: monto en USD (positivo siempre)
   - **Etiqueta**: `Cierre de posición` cuando vendes el 100% del ticker (¡crítico!)
2. (opcional) `python update_data.py` para refrescar precios.
3. Refresca el dashboard (botón "Forzar refresh" en sidebar) o `streamlit run app.py`.

## Estructura

```
Portafolio-Manager/
├── app.py                  # Dashboard Streamlit
├── update_data.py          # Refresca cache (precios + FX)
├── reconcile.py            # Compara cálculo vs broker
├── requirements.txt
├── CLAUDE.md               # Conocimiento del proyecto (para Claude)
├── data/
│   ├── transactions.xlsx   # ← TU FUENTE DE VERDAD
│   ├── prices_cache.parquet
│   └── fx_cache.parquet
└── src/
    ├── loader.py           # Carga + normaliza Excel
    ├── prices.py           # yfinance con cache
    ├── fx.py               # USD/CLP (mindicador.cl)
    ├── portfolio.py        # FIFO + posiciones
    ├── analytics.py        # NAV, TWR, drawdown, benchmark
    └── tradingview.py      # Deep links TradingView
```

## Notas

- **Aproximación de shares**: el Excel solo trae montos USD, no cantidades. Los shares se infieren con el precio de cierre de yfinance del día. Error típico <1%.
- **"Cierre de posición"** es **autoritativo**: cuando aparece, la posición vuelve a 0 shares y la diferencia USD se trata como P&L realizado.
- **Cash USD** se ignora (Fintual convierte CLP↔USD just-in-time, balance siempre ~0).
- **VOO benchmark**: simula el escenario contrafactual donde cada aporte CLP→USD compra VOO y cada retiro vende VOO.
