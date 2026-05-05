# Portafolio-Manager — Knowledge Base (CLAUDE.md)

> **INSTRUCCIÓN PERMANENTE:** Actualizar este archivo al final de cada sesión de trabajo. Registrar cambios de arquitectura, bugs encontrados/resueltos, decisiones tomadas, permisos configurados, y cualquier hecho no derivable del código o git log. Si no se actualiza, el contexto se pierde entre sesiones.

Conocimiento del proyecto para futuras sesiones de Claude. Léelo siempre antes de trabajar acá.

## Qué es esto

Dashboard personal del usuario (cuenta Fintual Acciones USA) para:
- Ver posiciones abiertas, cerradas, P&L realizado/no realizado.
- NAV histórico, drawdown, comparación contra VOO (benchmark S&P 500).
- Conversión USD↔CLP automática (Banco Central de Chile vía mindicador.cl).
- Charts interactivos (Plotly) y deep-links a TradingView.
- Logos de acciones en todas las tablas (parqet.com, sin API key, cacheados en `data/logos_cache.json`).

Stack: Python 3.13 · pandas · yfinance · streamlit · plotly · openpyxl · requests.

## Arquitectura

```
data/transactions.xlsx    ← FUENTE DE VERDAD (editado a mano por el usuario)
data/prices_cache.parquet ← cache yfinance
data/fx_cache.parquet     ← cache USD/CLP

src/loader.py    Carga/normaliza el Excel. Mapea tickers Fintual→yfinance (BRK.B → BRK-B).
src/prices.py    Descarga incremental de cierres yfinance, cacheada en parquet.
src/fx.py        USD/CLP. Primario: mindicador.cl (gratis, sin auth). Fallback: yfinance USDCLP=X.
src/portfolio.py FIFO lote-a-lote. "Cierre de posición" es autoritativo (resetea a 0 shares).
src/analytics.py NAV, drawdown, TWR, benchmark VOO, summary por ticker.
src/tradingview.py Deep links + widget HTML embebible. NO hay MCP oficial de TradingView.
src/logos.py      URLs de logos vía parqet.com (fallback clearbit). Cache en data/logos_cache.json.

app.py            Streamlit — 6 tabs: Overview, Posiciones, Histórico, vs VOO, Cerradas, TradingView.
reconcile.py      Herramienta CLI para comparar cálculo vs snapshot del broker (fuera del dashboard).
update_data.py    Refresca cache. Correr a diario o on-demand.
reconcile.py      Compara cálculo vs portafolio reportado por el broker.
```

## Reglas de oro del esquema de datos

El Excel `transactions.xlsx` tiene 5 columnas: **Fecha, Tipo, Activo, Monto (USD), Etiqueta**.

- **Fintual sólo registra montos USD, NO cantidades de acciones.** Para reconstruir shares dividimos `monto_usd / precio_cierre_yfinance(fecha)`. Error típico <1%, pero puede ser mayor si la ejecución fue lejos del cierre.
- `Tipo` ∈ `{Compra, Venta, Dividendo, Ganancia, Compensación}`.
- `Activo` = ticker (ej. `NVDA`) o el string literal `Dólares` para conversiones CLP↔USD.
- `Etiqueta = "Cierre de posición"` es **autoritativo**: cuando aparece en una venta, la posición vuelve a 0 shares y el delta USD es P&L realizado puro. Sin esta marca, una venta es parcial y se aplica FIFO sobre los lotes existentes.
- Cash USD: en Fintual cada compra de acción tiene una `Compra Dólares` espejo del mismo día. El balance USD interno siempre converge a ~0. Lo ignoramos a nivel de portafolio.
- Aportes netos (deposits): se derivan como `sum(Compra Dólares) - sum(Venta Dólares)` por día — esto es lo que entra/sale del bolsillo CLP del usuario.

## Mapeos a tener en cuenta

- `BRK.B` (Fintual) ↔ `BRK-B` (yfinance) — ya en `loader.TICKER_OVERRIDES`.
- TradingView: BRK.B → `BRKB` (sin punto). Otros tickers usan exchange por defecto NASDAQ; overrides en `tradingview.EXCHANGE_OVERRIDES`.

## Encoding gotcha

El Excel original venía mostrando `D�lares` por mojibake en terminal Windows (cp1252) — pero la string en disco es Unicode correcta `Dólares` (U+00F3). **No "arreglar" el encoding**, ya está bien; el problema es solo de renderizado en la consola. Análogamente con `Compensación` y `Cierre de posición`. **No usar emojis en archivos Python que vayan a `print()` en Windows** (charmap encoder explota); reservados para Streamlit.

## Tickers actualmente activos (snapshot 2026-05-04, 20 posiciones)

`META, NOW, MSFT, TMO, NVDA, VST, INTU, GRAB, XAR, KTOS, NBIS, UHS, QXO, PANW, PLTR, ARDX, OKLO, NNE, UBER, AU`

Total ≈ US$ 2,816 · aportes netos ≈ US$ 2,613 · variación histórica ≈ US$ 203.

## Cómo agregar/corregir transacciones

1. Editar `data/transactions.xlsx` en Excel/LibreOffice.
2. Insertar filas nuevas con la fecha real. El loader las ordena cronológicamente.
3. Si la transacción cierra completamente la posición, poner `Cierre de posición` en Etiqueta — **crítico para que el cálculo sea correcto**.
4. (opcional) `python update_data.py` para refrescar precios/FX si la fecha es nueva.
5. `python reconcile.py` para chequear contra el snapshot del broker.

## Incoherencias históricas resueltas (corregidas en el Excel)

- **QQQ** (2026-01-22): la fila original era `Compra QQQ 212.63` (incorrecto); debe ser `Venta QQQ 212.63 Cierre de posición`. Corregido el tipo.
- **NOW**: faltaban dos compras: 2026-04-24 ($60) y 2026-04-28 ($50). Agregadas.
- **META** 2026-04-30: el monto era $51.00, pero la compra real fue $121.00 (dip post-earnings). Corregido.
- **NVDA** 2026-04-29: la venta debía ser `Cierre de posición`. La compra de NVDA del 2026-05-01 abre posición nueva post-caídas. Marcado.
- **QTUM** 2026-01-26: la fila era `Venta 38.31` (incorrecto); debe ser `Compra`. Corregido.
- **TMO** 2026-04-24: primera compra del día era $30.00; el monto real fue $40.03. Corregido.

Si vuelven a aparecer mismatches >$15 USD entre cálculo y broker, sospechar de una transacción faltante.

## Comandos cotidianos

```bash
pip install -r requirements.txt
python update_data.py            # refresca cache de precios/FX
python reconcile.py              # chequea consistencia
streamlit run app.py             # abre dashboard en localhost:8501
```

## Decisiones de diseño y trade-offs

- **Streamlit en vez de FastAPI+frontend**: el usuario es solo, dashboard local, no necesita auth/multi-user. Streamlit acelera 10x el desarrollo.
- **Parquet en vez de SQLite**: caches read-mostly, columnar, libre de schema migrations.
- **mindicador.cl** (BCCh) en vez de exchangerate.host: oficial chileno, sin auth, datos diarios. Fallback yfinance `USDCLP=X` si falla.
- **TradingView**: no hay API/MCP público. Solucionamos con deep-links (`tradingview.com/chart/?symbol=...`) y widget JS embebido vía `streamlit.components.v1.html`. Si el usuario quiere análisis automatizado en TV (alertas, screeners), necesitará la app desktop manualmente.
- **Aproximación shares = monto / close**: alternativa sería el precio de apertura o VWAP. Para la magnitud de los montos (~$50–$200 por trade) y volatilidad típica diaria, el error es <1% — aceptable. Si llega a importar más, considerar pedir al usuario que ingrese shares manualmente.
- **Benchmark VOO contrafactual**: se simula que cada `Compra Dólares` compra VOO al close del día y cada `Venta Dólares` vende VOO. No es perfecto (el usuario en realidad invierte en distintos tickers, no en cash), pero responde la pregunta correcta: "si me hubiera quedado en VOO, ¿cómo me iría?".

## Pendientes / mejoras posibles

- Tasa de cambio histórica para calcular CLP histórico día a día (actualmente solo el snapshot actual). Ya cacheamos la serie completa en `fx_cache.parquet`, falta usarla en `daily_holdings`.
- Integración con bróker: scraping de Fintual sería contra ToS. La edición manual del Excel es el contrato.
- Alertas (precio objetivo, drawdown threshold) — fácil de añadir como tab nuevo en `app.py`.
- TWR vs MWR — está implementado TWR pero no expuesto en dashboard. Agregar como métrica en tab "Histórico".
- Tests automatizados con pytest — no hay aún.

## Permisos y flujo de trabajo git/GitHub

El usuario otorga **permiso absoluto** para modificar tanto el PC como el repositorio GitHub sin pedir confirmación.

- **Push directo a main** para cambios simples (fixes, ajustes menores).
- **Para cambios via worktree/PR**: crear PR y hacer merge inmediato: `gh pr merge <N> --merge --delete-branch`.
- No preguntar ni esperar aprobación manual para ninguna operación git/gh (commit, push, merge, branch, etc.).
- `credential.https://github.com.username = luisnavarrof` configurado en `.git/config` del proyecto — sin prompts de cuenta.
- `defaultMode: bypassPermissions` en `.claude/settings.local.json` — sin prompts de permiso en Claude Code.

## Cambios recientes (2026-05-05)

- **Fix crash ZeroDivisionError** (`analytics.py` + `app.py`): `twr()` filtra días con NAV=0 (`v = v[v > 0]`) para evitar que el cumprod llegue a 0. Guard defensivo en `_period_return`: `denom = 1 + twr_start; if abs(denom) < 1e-9: return None`.
- **Color en métricas de período** (Overview): las tarjetas 1D/1W/1M/etc. ahora muestran delta verde/rojo.
- **Git credential**: `git config credential.https://github.com.username luisnavarrof` para evitar prompt de selección de cuenta.
- **Permisos Claude Code**: `defaultMode: bypassPermissions` en `.claude/settings.local.json`.
- **Fix UX form Gestionar**: al seleccionar "Compra/Venta de dólares", el selectbox Activo muestra automáticamente "Dólares" (index dinámico). Antes mostraba el ticker previo aunque deshabilitado.

## Estilo del usuario

- Prefiere comunicación en español, técnicamente densa, sin redundancia.
- Quiere automatización total: ningún paso manual, ninguna confirmación. Claude ejecuta de inicio a fin.
- Aprecia que se le notifiquen incoherencias inmediatamente.
- Tiene TradingView desktop instalado.
