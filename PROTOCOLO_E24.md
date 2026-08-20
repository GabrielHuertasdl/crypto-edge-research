# Protocolo de E2.4 — validación fuera de cripto

**Sellado antes de ejecutar nada sobre las series externas.**

Aviso de honestidad sobre el sellado: este documento es posterior al primer trial
de la fase 4, así que **no** tiene el mismo estatus que
`CRITERIOS_DE_ACEPTACION.md`, que se escribió antes de existir ningún resultado.
Lo que sí garantiza es lo relevante aquí: **ninguna serie externa se ha evaluado
todavía**. `results/trials_log.csv` no contiene ni una fila con activo `GOLD`,
`SP500`, `EURUSD` o `USDJPY`, y puede comprobarse en el commit que introduce este
fichero.

---

## 1. Por qué se corre

El veredicto de la fase 4 es negativo pero **ambiguo entre dos hipótesis que se
parecen mucho en los datos y no se parecen nada en sus implicaciones**:

- **H1** — no hay ventaja: el seguimiento de tendencia no funciona en cripto.
- **H2** — hay ventaja pero cripto no tiene longitud de muestra para detectarla.

Potencia disponible para distinguirlas, con `SE(Sharpe) ≈ sqrt(periodos/T)`:

| Muestra | sesiones | SE(SR) | Potencia contra SR verdadero = 0,40 |
|---|---:|---:|---:|
| LOCKBOX cripto | 963 | 0,62 | ~16 % |
| VALIDATION cripto | 1.095 | 0,58 | ~18 % |
| Las cuatro series externas juntas | 23.776 | **0,10** | **~99 %** |

Con el lockbox, una estrategia con Sharpe verdadero de 0,40 pasa desapercibida
cinco de cada seis veces. Sobre las series externas se detecta casi siempre. E2.4
es lo único disponible que separa H1 de H2.

## 2. Configuraciones congeladas

**19 configuraciones, con sus parámetros exactos, fijadas antes de tocar nada.**
Salen de dos sitios, ambos de cripto:

- **E2.4**: por cada estrategia que dispara validación externa primaria
  (`lookback ≥ 100` o `warmup ≥ 200`), la parametrización con mejor Sharpe medio
  fuera de bloque en el TRAIN de BTC y ETH. Son 18 estrategias, no 7: el conteo
  anterior solo miraba las que disparan con **todas** sus parametrizaciones.
- **finalista**: las tres que salieron de la fase 4, con los parámetros con los
  que ya fallaron VALIDATION.

| # | estrategia | parámetros | origen | Sharpe medio TRAIN |
|---:|---|---|---|---:|
| 1 | `bollinger_reversion` | `{'k': 1.5, 'n': 50}` | E2.4 | 0.303 |
| 2 | `breakout_volume_confirmed` | `{'n': 55, 'vol_mult': 1.5, 'vol_n': 50}` | E2.4 | 1.416 |
| 3 | `donchian_atr_stop` | `{'atr_mult': 2.0, 'atr_n': 20, 'n_in': 55}` | E2.4 | 1.654 |
| 4 | `donchian_breakout` | `{'n_in': 20, 'n_out': 55}` | E2.4 | 1.468 |
| 5 | `donchian_vol_targeted` | `{'n_in': 55, 'n_out': 10, 'n_vol': 20, 'objetivo': 0.4}` | E2.4 | 1.578 |
| 6 | `ema_cross` | `{'fast': 12, 'slow': 100}` | E2.4 | 1.843 |
| 7 | `low_vol_filter` | `{'n': 60, 'ventana_mediana': 120}` | E2.4 | 1.171 |
| 8 | `ma_slope` | `{'n': 100}` | E2.4 | 1.729 |
| 9 | `macd_cross` | `{'fast': 12, 'signal_n': 18, 'slow': 50}` | finalista + E2.4 | 2.194 |
| 10 | `momentum_with_dd_stop` | `{'max_dd': 0.2, 'n': 60}` | E2.4 | 1.679 |
| 11 | `price_vs_sma` | `{'n': 100}` | E2.4 | 1.752 |
| 12 | `rsi_reversion_in_uptrend` | `{'n_rsi': 14, 'n_trend': 200, 'umbral': 35}` | E2.4 | 0.138 |
| 13 | `sma_cross` | `{'fast': 50, 'slow': 100}` | E2.4 | 1.717 |
| 14 | `trend_above_sma200` | `{'n_fast': 20, 'n_regime': 150}` | E2.4 | 1.947 |
| 15 | `trend_above_sma200` | `{'n_fast': 50, 'n_regime': 150}` | finalista | — |
| 16 | `trend_with_vol_filter` | `{'n_trend': 100, 'n_vol': 60, 'percentil': 0.9}` | finalista + E2.4 | 1.638 |
| 17 | `ts_momentum` | `{'n': 120}` | E2.4 | 1.759 |
| 18 | `vol_expansion_breakout` | `{'mult': 1.3, 'n_trend': 50, 'n_vol': 10}` | E2.4 | 1.852 |
| 19 | `zscore_reversion` | `{'n': 50, 'umbral': 1.0}` | E2.4 | 0.309 |
## 3. Prohibición de reoptimizar

- **Cero reoptimización sobre series externas.** Los parámetros salen del TRAIN de
  cripto y se aplican tal cual.
- **No se elige entre las 19 mirando resultados externos.** Las 19 se reportan
  todas, ganen o pierdan. En cuanto se seleccione una mirando `deep_oos`, eso deja
  de ser validación y pasa a ser conjunto de selección, según la definición que ya
  está escrita en `config.EXTERNAL_SPLITS`.
- **La dirección no se invierte nunca**: no se ajusta en oro para aplicar en BTC.
- Los 19 × 4 mercados = 76 evaluaciones se registran en `trial_registry` como
  cualquier otro trial.

## 4. Costes por mercado

`COST_PER_TURN = 0,15 %` está calibrado para cripto minorista y penalizaría
injustamente al S&P. Costes por rotación declarados en `config.MARKET_COST_PER_TURN`:

| Mercado | coste/rotación | instrumento supuesto |
|---|---:|---|
| Cripto | 0,150 % | exchange minorista (0,10 % comisión + 0,05 % slippage) |
| S&P 500 | 0,020 % | SPY o futuro ES |
| Oro | 0,030 % | GLD o futuro GC |
| EURUSD | 0,020 % | spot, horquilla ~1 pb |
| USDJPY | 0,020 % | spot, horquilla ~1 pb |

Son estimaciones, no datos de ejecución. Por eso el **análisis de sensibilidad es
obligatorio**: se reporta el resultado con multiplicadores ×0,5, ×1, ×2, ×5 y
×7,5 sobre el coste base (el ×7,5 lleva al S&P y a las divisas hasta el coste de
cripto). **Si la conclusión cambia dentro de ese rango, la conclusión es que
depende del coste**, y así se escribirá.

## 5. Regla de interpretación — escrita antes de ver un solo número

**E2.4 no reabre el veredicto sobre cripto bajo ningún resultado.**

| Resultado en las series externas | Conclusión permitida | Conclusión PROHIBIDA |
|---|---|---|
| La tendencia funciona | "El fenómeno es real y cripto no tiene longitud de muestra para detectarlo" (H2) | "Por tanto opérala en cripto" |
| La tendencia no funciona | "Ni siquiera con 23.776 sesiones aparece: refuerza H1" | — |
| Resultado mixto | "No concluyente; se reportan los cuatro mercados por separado" | Quedarse con el mercado que salga bien |

Motivos, para que no haya que fiarse de la buena voluntad:

1. Oro, S&P y divisas **no son el activo que se quiere operar**. Que una familia
   funcione ahí demuestra que no es un artefacto estadístico, no que vaya a
   funcionar en un mercado con otra microestructura, otros participantes, otra
   volatilidad y otro régimen de costes.
2. Las tres finalistas ya **fallaron VALIDATION en cripto** por cuatro vías
   independientes. Ningún resultado externo borra ese fallo.
3. **El lockbox sigue sellado.** El pre-registro (§2) prohíbe abrirlo con cero
   finalistas, y E2.4 no crea finalistas: no puede, porque no se selecciona nada
   con él.

El veredicto del proyecto sobre cripto ya está fijado y es: **no he encontrado
ninguna estrategia con ventaja estadísticamente significativa**. E2.4 solo puede
cambiar la *explicación* de ese resultado, nunca el resultado.
