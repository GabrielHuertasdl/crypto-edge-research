# Informe final — ¿hay ventaja real en criptomonedas?

Proyecto de investigación cuantitativa sobre BTC, ETH, SOL y LTC en marco diario,
long/flat, sin apalancamiento, con costes de 0,10 % de comisión por lado más
0,05 % de slippage por operación.

---

## Veredicto

> **No he encontrado ninguna estrategia con ventaja estadísticamente
> significativa.**

Ninguna de las tres finalistas superó la validación fuera de muestra. Fallaron por
cuatro vías independientes a la vez, no por un criterio apretado. **El lockbox
(2024 → hoy) no se ha abierto** y sigue sellado: el pre-registro lo prohíbe con
cero finalistas, y `lockbox/.lockbox_used` no existe.

Matiz que sí sostienen los datos, y que es distinto de "no hay nada":

> El seguimiento de tendencia **sí** aparece fuera de cripto. Sobre 13.709 sesiones
> de oro, S&P 500, EURUSD y USDJPY anteriores a 2015 —datos que ningún parámetro de
> este proyecto ha visto— las 19 configuraciones congeladas dan Sharpe conjunto
> positivo, 13 de ellas con intervalo de confianza que excluye el cero. Pero solo
> **2 de 19** superan el control de exposición equiparada, así que la mayor parte
> de ese Sharpe se explica por estar largo en un activo con deriva, no por acertar
> el momento.

---

## 1. Cuántas configuraciones se han probado

Registro append-only, escrito en el momento de cada evaluación
(`results/trials_log.csv`, `src/trial_registry.py`).

| | |
|---|---:|
| Evaluaciones totales | **685** |
| Configuraciones únicas | 678 |
| Repeticiones | 7 |

| split | descartadas | exploración | conservadas |
|---|---:|---:|---:|
| `train` | 0 | 299 | 0 |
| `validation` | 298 | 0 | 12 |
| `deep_oos` (externos) | 0 | 0 | 76 |

Universo: **23 estrategias, 149 configuraciones**, en 5 familias — tendencia (9),
reversión (4), volatilidad (3), régimen (5), calendario (2). Cada una con su tesis
económica escrita como requisito de entrada; `turn_of_month` entró
deliberadamente **SIN TESIS**, como control.

**Número efectivo de intentos independientes** (participación de autovalores,
`(Σλ)²/Σλ²` sobre la correlación entre configuraciones):

| activo | N | N_eff | cociente |
|---|---:|---:|---:|
| BTC | 149 | **3,7** | 40× |
| ETH | 149 | **4,5** | 33× |

El universo explora unas **4 apuestas independientes**, no 149. Es un dato
incómodo en las dos direcciones: suaviza la corrección por comparaciones
múltiples, y a la vez dice que la búsqueda fue mucho más estrecha de lo que
aparenta.

---

## 2. Finalistas frente a comprar y mantener

Parámetros congelados en TRAIN (2015-2020), aplicados sin tocar nada a
VALIDATION (2021-2023). Sharpe con IC del 95 % por stationary block bootstrap.

| estrategia | activo | Sharpe | IC 95 % | ret. total | B&H Sharpe | ops | C12 |
|---|---|---:|---|---:|---:|---:|:--:|
| `macd_cross(12,50,18)` | BTC | 0,15 | [−1,27 · 1,61] | −5,5 % | 0,46 | 21 | no |
| | ETH | 0,58 | [−0,67 · 1,74] | 50,8 % | 0,85 | 19 | no |
| | SOL | 0,82 | [−0,84 · 2,29] | 92,0 % | 0,92 | 14 | no |
| | LTC | −0,03 | [−1,17 · 1,08] | −40,0 % | 0,24 | 22 | no |
| `trend_above_sma200(50,150)` | BTC | 0,81 | [−0,51 · 1,88] | 47,5 % | 0,46 | 12 | no |
| | ETH | 0,02 | [−1,04 · 1,18] | −12,4 % | 0,85 | 18 | no |
| | SOL | 1,25 | [−0,74 · 2,92] | 155,6 % | 0,92 | 15 | no |
| | LTC | −0,18 | [−1,33 · 0,82] | −32,1 % | 0,24 | 22 | no |
| `trend_with_vol_filter(100,60,0.9)` | BTC | 0,62 | [−1,10 · 2,05] | 31,3 % | 0,46 | 11 | no |
| | ETH | −0,51 | [−1,85 · 0,83] | −43,1 % | 0,85 | 18 | no |
| | SOL | 0,31 | [−1,67 · 2,21] | 3,7 % | 0,92 | 15 | no |
| | LTC | −0,24 | [−1,51 · 0,87] | −33,6 % | 0,24 | 26 | no |

**Los doce intervalos de confianza incluyen el cero.** Por la regla de
interpretación pre-registrada (Enmienda 1, E1.1) eso es NO CONCLUYENTE, nunca
"cumple".

Fallos, por criterio:

- **C1b** (Sharpe ≥ 0,70): fallan 9 de 12 en el punto estimado; las 3 que lo pasan
  tienen el cero dentro del intervalo.
- **C4** (≥ 50 operaciones): fallan **las doce**. Entre 11 y 26 operaciones. El
  pre-registro ya avisaba de que este criterio sesga contra la baja frecuencia;
  aquí ha mordido de lleno.
- **C8a** (Sharpe ≥ 0,40 en SOL y LTC): LTC sale negativo en las tres.
- **C12** (superar el nulo de exposición equiparada): **ninguna, en ningún activo**.

### Curvas de capital y drawdown

![Finalistas en VALIDATION](figures/validation_btc.png)

---

## 3. Deflated Sharpe y PBO

Sobre TRAIN, con la mejor configuración de cada activo y la matriz completa de
149 configuraciones:

| activo | PBO | p-valor PBO | C6 | DSR | p-valor DSR | C5 |
|---|---:|---:|:--:|---:|---:|:--:|
| BTC | 17,1 % | 0,000 | cumple | 1,000 | 0,000 | cumple |
| ETH | 17,7 % | 0,033 | cumple | 0,995 | 0,000 | cumple |

**C5 y C6 se cumplen y no significan lo que parece.** Ambos se calculan sobre
TRAIN, y en TRAIN el listón está roto por la deriva del activo: señales
**aleatorias** con 55 % de exposición y rotación realista alcanzan Sharpe ≥ 0,70
el **90,5 %** de las veces en el TRAIN de BTC (CAGR 134 %). Sobre la misma serie
sin deriva, el 0,8 %. Un DSR de 1,000 en ese contexto dice que la estrategia no es
un artefacto de haber probado muchas cosas; no dice que tenga ventaja.

CPCV sobre el **procedimiento de selección** (no sobre una configuración fija):
mediana de los 9 caminos = 1,57 en BTC y 1,67 en ETH, frente a un buy & hold de
1,51 y 1,35. Es decir: en TRAIN, seleccionar la mejor de la rejilla apenas bate a
no hacer nada.

---

## 4. Resultado sobre datos sintéticos

**C9 — stationary block bootstrap** de los retornos reales (bloque geométrico de
media 20 días, que conserva colas gruesas y agrupamiento de volatilidad), 400
caminos, VALIDATION de BTC:

| estrategia | Sharpe real | p95 del nulo | percentil | C9 |
|---|---:|---:|---:|:--:|
| `macd_cross` | 0,15 | 1,39 | 46,0 % | no |
| `trend_above_sma200` | 0,81 | 1,55 | 71,5 % | no |
| `trend_with_vol_filter` | 0,62 | 1,56 | 66,5 % | no |

Ninguna se distingue del ruido con la misma distribución marginal.

**C12 — nulo de exposición equiparada**, el control que más informó de todo el
proyecto. Rotaciones circulares de la propia senda de posiciones: conserva
exposición, rotación y duración de las operaciones exactamente, y solo destruye la
alineación con los retornos. Ninguna finalista lo supera en ningún activo.

---

## 5. Lockbox

**NO ABIERTO.** `lockbox/.lockbox_used` no existe; puede comprobarse en el
repositorio. El pre-registro (§2) dice: *"Si superan cero, el proyecto termina con
veredicto negativo y el lockbox no se abre"*. Superaron cero.

Abrirlo ahora no aportaría información y sí destruiría el único tramo de datos
limpio que queda para un proyecto futuro.

---

## 6. E2.4 — validación fuera de cripto

Motivo: el veredicto negativo era **ambiguo entre dos hipótesis**. Con 963
sesiones de lockbox el error estándar del Sharpe es 0,62 y una estrategia con
Sharpe verdadero de 0,40 se detecta ~16 % de las veces. Las series externas tienen
décadas.

Protocolo sellado en git **antes** de tocar ningún dato externo
(`PROTOCOLO_E24.md`): 19 configuraciones congeladas con parámetros exactos
procedentes solo del TRAIN de cripto, cero reoptimización, y regla de
interpretación escrita de antemano.

| mercado | sesiones `deep_oos` | periodo | B&H Sharpe |
|---|---:|---|---:|
| S&P 500 | 13.304 | 1962-2014 | 0,47 |
| USDJPY | 4.693 | 1996-2014 | 0,08 |
| Oro | 2.925 | 2000-2014 | 0,71 |
| EURUSD | 2.854 | 2003-2014 | 0,07 |

Resultado de las 19 congeladas sobre la cartera equiponderada de los cuatro
mercados (13.709 sesiones de calendario unido):

- **19 de 19 tienen Sharpe conjunto positivo.** Mediana 0,46.
- **13 de 19 tienen IC del 95 % que excluye el cero.**
- **Solo 2 de 19 superan el nulo de exposición equiparada** (`ts_momentum(120)` y
  `breakout_volume_confirmed(55,50,1.5)`).
- Las tres finalistas de cripto dan 0,32 / 0,49 / 0,42 conjunto, y **ninguna**
  supera C12.

![Series externas](figures/externos.png)

### Sensibilidad al coste

Sharpe conjunto, variando el coste por rotación de ×0,5 a ×7,5 sobre el base
(el ×7,5 lleva al S&P y a las divisas hasta el coste de cripto):

| multiplicador | ×0,5 | ×1,0 | ×2,0 | ×5,0 | ×7,5 |
|---|---:|---:|---:|---:|---:|
| coste S&P por rotación | 0,010 % | 0,020 % | 0,040 % | 0,100 % | 0,150 % |
| **mediana del Sharpe conjunto** | 0,48 | 0,46 | 0,43 | 0,35 | 0,28 |
| configuraciones con Sharpe > 0 | 18/18 | 18/18 | 18/18 | 18/18 | 18/18 |

**La conclusión no depende del coste.** Aguanta un rango de 15× y sigue siendo
positiva incluso cobrando comisiones de cripto en el S&P. Solo
`trend_above_sma200(20,150)` cruza el cero, y solo al multiplicador máximo.

### Lectura permitida

Según la regla escrita antes de ejecutarlo: **el fenómeno de la tendencia es real
y cripto no tiene longitud de muestra para detectarlo** (hipótesis H2). Esto **no**
autoriza a operarlo en cripto, y no reabre el veredicto. Con el matiz importante de
que ni siquiera fuera de cripto la mayoría de las configuraciones supera el control
de exposición equiparada: lo que sobrevive con más solidez es la deriva del activo,
no la sincronización.

---

## 7. Por qué esto podría estar equivocado

Los argumentos más fuertes **en contra de mis propias conclusiones**. Registro
completo en `POR_QUE_PODRIA_ESTAR_EQUIVOCADO.md` (D1-D8).

### 7.1 El proyecto puede estar diciendo "no" por falta de potencia, no por falta de ventaja

Es la objeción más seria. Con `SE(Sharpe) ≈ sqrt(365/T)`, VALIDATION tiene SE de
0,58. Una estrategia con Sharpe verdadero de **0,70** —que sería excelente— se
detecta solo la mitad de las veces. Los doce intervalos de confianza incluyen el
cero, pero **también incluyen valores de 1,5 y 2,0**. Este proyecto no ha
demostrado que no haya ventaja: ha demostrado que **con estos datos no se puede
distinguir de cero**, que es una afirmación mucho más débil.

### 7.2 C4 puede haber matado a las supervivientes legítimas

Exigir ≥ 50 operaciones en 3 años obliga a más de una operación cada tres semanas.
El seguimiento de tendencia lento —la familia con **mejor** evidencia documentada
fuera de muestra, y la que E2.4 confirma— opera mucho menos que eso. El criterio
estaba pre-registrado y no se ha tocado, pero es posible que haya descartado justo
lo que funciona. Las doce finalistas fallaron C4.

### 7.3 El seguimiento de tendencia lento ni siquiera era evaluable

Con lookback 200 y calentamiento 400, el purgado del CPCV se come el 42,2 % de
TRAIN y la configuración queda **inviable**. La familia con mejor respaldo previo
está estructuralmente excluida del análisis en cripto por longitud de datos. Lo
que quedó evaluable es el conjunto complementario: horizontes cortos, evidencia
previa más débil, mayor sensibilidad a costes.

### 7.4 N_eff = 3,7 significa que apenas se buscó

149 configuraciones que son ~4 apuestas independientes. Un universo con familias
de verdad distintas —cross-sectional entre activos, datos on-chain,
microestructura, financiación de perpetuos— podría encontrar algo que este
universo no puede ver. "No hay ventaja" aquí significa "no hay ventaja en estas
cuatro apuestas".

### 7.5 Los cuatro activos son uno

D4: BTC, ETH, SOL y LTC comparten factor de mercado. "Falla en cuatro activos"
está más cerca de "falla en uno" que de "falla en cuatro". La confirmación
cross-asset del resultado negativo es más débil de lo que sugiere la tabla.

### 7.6 Sesgo de supervivencia, y va en contra del veredicto negativo

D5: los cuatro activos existen hoy porque sobrevivieron. Eso **favorece** a las
estrategias de comprar y mantener y a las de reversión en el backtest. Que aun con
ese viento a favor no aparezca ventaja refuerza el veredicto — pero también
significa que el buy & hold contra el que se comparó está inflado, así que el
listón fue más alto de lo que habría sido en tiempo real.

### 7.7 El régimen 2015-2017 contamina TRAIN

D1: en 2017, Coinbase y yfinance discrepan más de un 2 % en el cierre en 118 días
solo en LTC. Si dos fuentes no se ponen de acuerdo en cuál era el precio, el
backtest de esa era depende de qué fuente elijas. Los parámetros de las finalistas
se ajustaron con esos datos dentro.

### 7.8 El coste podría estar mal en la otra dirección

0,15 % por rotación es razonable para un minorista en Coinbase, pero no incluye
impacto de mercado ni el diferencial real en momentos de estrés, que es
precisamente cuando estas estrategias operan. El coste realista podría ser peor,
lo que empeoraría el resultado, no lo mejoraría.

### 7.9 Errores míos que sí ocurrieron durante el proyecto

Para calibrar cuánta confianza merece el resto:

- Reporté un PBO del 36 % sobre ruido como si fuera un sesgo del estimador. Era
  **una sola matriz**: el estimador está centrado en 0,50 y su desviación típica
  bajo la nula es 0,20.
- Dije que 7 estrategias disparaban validación externa. Eran **18**.
- Un test de causalidad mío daba por bueno un canal de Donchian sin `shift(1)`,
  porque el sesgo de misma vela no es una violación de causalidad. Hizo falta un
  test de especificación aparte.
- La tolerancia del test de perturbación estuvo en 1e-6 cuando la cota derivada es
  1,3e-11: nueve órdenes de magnitud donde se podía esconder una dependencia real.

Los cuatro se detectaron y corrigieron, tres de ellos a instancias del revisor. Es
razonable suponer que quedan errores del mismo tipo sin detectar.

---

## 8. Qué haría falta para cambiar el veredicto

- Un universo con familias **de verdad** independientes (N_eff alto), no 149
  variaciones de la misma idea.
- Datos que cripto sí tiene y aquí no se usaron: financiación de perpetuos,
  profundidad de libro, flujos on-chain. Ahí puede haber primas estructurales sin
  equivalente en mercados tradicionales.
- Marco temporal intradiario, donde el número de observaciones cuasi-independientes
  es órdenes de magnitud mayor y el problema de D2 se atenúa.
- Aceptar de antemano que con 10 años de historia diaria y cuatro activos
  correlacionados, **la potencia estadística disponible no permite validar una
  ventaja moderada**. Ese es el resultado estructural del proyecto.

---

*Todo lo anterior es reproducible: `.venv/bin/python -m pytest tests/ -q`
(698 tests), `results/trials_log.csv` (685 evaluaciones registradas),
y el historial de git, donde el pre-registro y sus tres enmiendas son anteriores
al primer trial.*
