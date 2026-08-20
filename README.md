# Investigación cuantitativa — ¿hay ventaja real en cripto?

Búsqueda sistemática de estrategias de trading con ventaja **fuera de muestra**
sobre BTC, ETH, SOL y LTC en marco diario. Long/flat, sin apalancamiento, con costes
realistas.

El objetivo no es maximizar el Sharpe de un backtest. Es determinar si queda algo
después de descontar costes, sesgo de selección y suerte. **"No hay ventaja" es un
resultado esperado y aceptable**; el informe final lo dirá sin adornos si es el caso.

Las reglas metodológicas están en [`CLAUDE.md`](CLAUDE.md) y son innegociables.

## Resumen del método

| Elemento | Decisión |
|---|---|
| Activos | Optimización: BTC, ETH · Test cross-asset (100 % fuera de muestra): SOL, LTC |
| Datos | Coinbase Exchange = ejecución · yfinance = detector de anomalías (>2 %) |
| Marco | Diario, OHLCV, UTC |
| Posición | Long/flat (0 o 1). Sin apalancamiento ni cortos |
| Ejecución | Señal del cierre de `t` → **cierre de `t+1`** (`ret = s.shift(2) * r`) |
| Costes | 0,10 % comisión por lado + 0,05 % slippage por operación |
| TRAIN | 2015-2020 — optimización libre |
| VALIDATION | 2021-2023 — solo confirmar |
| LOCKBOX | 2024-hoy — **una sola ejecución, al final** |
| Benchmark | Buy & hold, mismos costes |
| Contra el overfitting | CPCV N=10/k=2 (**9 caminos**), purgado derivado del lookback, DSR, PBO, block bootstrap |
| Pre-registro | `CRITERIOS_DE_ACEPTACION.md`, escrito antes del primer backtest |

## Instalación

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m pytest tests/ -q
```

## Estructura

```
data/raw/          OHLCV crudo, se descarga una vez
data/processed/    series limpias y validadas
src/config.py      constantes: costes, splits, semillas (única fuente de verdad)
src/data_loader.py descarga, caché, integridad, splits
src/indicators.py  indicadores, todos causales
src/backtest.py    motor vectorizado + métricas
src/strategies.py  universo de estrategias, cada una con su tesis económica
src/validation.py  CPCV purgado, robustez, subperiodos, block bootstrap
src/statistics.py  Deflated Sharpe, PBO, registro de configuraciones probadas
lockbox/           evaluación final aislada — ver su README antes de tocarlo
results/           métricas, gráficos, INFORME.md
tests/             motor, lookahead, costes
```

## Estado

- [x] **Fase 0** — Setup: estructura, entorno, reglas, guardia del lockbox
- [x] **Fase 1** — Datos: descarga, caché, validación de integridad
- [x] **Fase 2** — Motor de backtest + indicadores + CPCV, 138 tests en verde
- [ ] **Fase 3** — Universo de 15-25 estrategias con tesis económica
- [ ] **Fase 4** — CPCV purgado, robustez, DSR y PBO
- [ ] **Fase 5** — Lockbox (una sola vez)
- [ ] **Fase 6** — `results/INFORME.md` con veredicto explícito

## Métricas del motor

Retorno total y anualizado · Sharpe · Sortino · máximo drawdown y su duración ·
tasa de acierto · profit factor · número de operaciones · exposición temporal.

Todas se calculan también para el benchmark, en el mismo periodo y con los mismos
costes.
