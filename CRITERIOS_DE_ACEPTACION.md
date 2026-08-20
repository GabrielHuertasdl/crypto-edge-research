# Criterios de aceptación — PRE-REGISTRO

**Escrito antes de ejecutar un solo backtest.** Fija qué significa "hay ventaja"
*antes* de ver resultados, para que el umbral no se mueva luego hasta abrazar lo
que haya salido.

**Este fichero no se modifica.** Si más adelante hay motivo real para cambiar un
umbral, el cambio queda en el historial de git y **aparece citado en el informe
final**, con su fecha y su justificación. Un criterio cambiado después de ver
resultados no es un criterio: es una racionalización, y el informe lo tratará como
tal.

Versionado en git junto al centinela del lockbox (`lockbox/.lockbox_used`).

---

## 0. Qué cuenta como "una configuración probada"

Cada combinación (estrategia × conjunto de parámetros × activo) evaluada sobre
TRAIN cuenta como **un trial**, se conserve o se descarte. Todos van a
`results/trials_log.csv`. Ese contador `N` alimenta el Deflated Sharpe Ratio.

No se descuenta ningún trial por "es que ese ni lo miré". Si el código lo evaluó,
cuenta.

## 1. Umbrales para pasar de VALIDATION a finalista

Se evalúan sobre VALIDATION (2021-2023), con costes (0,10 % por lado + 0,05 %
slippage) y con el lag oficial de 2 días. **Todos** son necesarios; ninguno es
compensable con otro.

| # | Criterio | Umbral |
|---|---|---|
| C1 | Sharpe neto anualizado | **≥ 0,70** |
| C2 | Supera al buy & hold del mismo activo y periodo, en Sharpe | **Sharpe_est > Sharpe_B&H** |
| C3 | Máximo drawdown | **≤ 50 %** y **≤ 0,80 × MDD del B&H** |
| C4 | Nº de operaciones cerradas en VALIDATION | **≥ 50** |
| C5 | Deflated Sharpe Ratio (Bailey & López de Prado) | **≥ 0,95** |
| C6 | Probability of Backtest Overfitting (PBO, por caminos CPCV) | **≤ 0,20** |
| C7 | Sensibilidad paramétrica: mediana del Sharpe en el vecindario ±25 % de cada parámetro | **≥ 0,60 × Sharpe del pico** |
| C8 | Estabilidad cross-asset: Sharpe neto en SOL **y** en LTC (jamás optimizados) | **> 0 en ambos** |
| C9 | Prueba de nulidad: Sharpe real frente a la distribución del stationary block bootstrap | **> percentil 95** |
| C10 | Robustez al lag: Sharpe con lag 2 frente a lag 1 | **Sharpe(lag2) ≥ 0,70 × Sharpe(lag1)** |
| C11 | Régimen: Sharpe neto calculado **excluyendo 2015-2017** | **≥ 0,50** |

Notas sobre por qué esos números y no otros:

- **C1 = 0,70**: por debajo de eso, con 3 años de datos, el intervalo de confianza
  del Sharpe incluye el cero holgadamente. No es un objetivo de rentabilidad, es el
  mínimo para poder distinguirlo del ruido.
- **C4 = 50 operaciones**: con menos, el Sharpe lo decide un puñado de días y las
  métricas por operación (tasa de acierto, profit factor) no tienen grados de
  libertad. Sesga el proyecto contra estrategias de muy baja frecuencia; es
  deliberado y es consecuencia directa de D2 (pocos ciclos independientes).
- **C5 = 0,95**: el DSR es la probabilidad de que el Sharpe verdadero sea > 0 tras
  descontar `N` trials, la asimetría y la curtosis. Se exige el estándar habitual.
- **C6 = 0,20**: PBO por encima de eso significa que la configuración ganadora
  in-sample cae bajo la mediana out-of-sample una de cada cinco veces o más.
- **C11**: aplica D1. Si el alpha vive en la era pre-CME, no sirve para operar hoy.

## 2. Cuántas finalistas

**Máximo 3.** Si más de tres superan la sección 1, pasan las tres con mejor DSR y
el informe declara explícitamente cuántas quedaron fuera y por qué. Si superan
cero, el proyecto termina con veredicto negativo y **el lockbox no se abre**.

## 3. Qué exijo del LOCKBOX (2024 → hoy)

Una sola ejecución. Sin reajustes posteriores. Para que una finalista se declare
**con ventaja**, en el lockbox debe cumplir **todo** lo siguiente:

| # | Criterio | Umbral |
|---|---|---|
| L1 | Sharpe neto anualizado | **> 0,50** |
| L2 | Supera al buy & hold del mismo activo y periodo en Sharpe | **Sharpe_est > Sharpe_B&H** |
| L3 | Máximo drawdown | **≤ MDD del B&H** |
| L4 | Nº de operaciones cerradas | **≥ 30** |
| L5 | Retorno neto total | **> 0** |
| L6 | Degradación frente a VALIDATION: Sharpe_lockbox | **≥ 0,50 × Sharpe_validation** |

L1 es más laxo que C1 a propósito: 2024-hoy son ~2,6 años y un solo régimen
dominante. Exigir 0,70 ahí sería exigir suerte. L6 vigila lo contrario: una caída
de más de la mitad del Sharpe indica que VALIDATION ya estaba sobreajustado.

## 4. Veredicto

- **HAY VENTAJA** solo si al menos una finalista cumple las secciones 1 y 3
  enteras. El informe indicará en qué activo, con qué parámetros y con qué
  intervalo de confianza del Sharpe.
- **NO HAY VENTAJA** en cualquier otro caso. Incluye el caso de una estrategia que
  cumple 10 de los 11 criterios de la sección 1. Diez de once no es aprobado; es
  suspenso con buena nota.
- Si el veredicto es negativo, el informe dirá **"no he encontrado ninguna
  estrategia con ventaja estadísticamente significativa"** en esas palabras, sin
  atenuantes, sin "pero con más datos quizá" y sin destacar la menos mala como si
  fuera un hallazgo.

## 5. Compromisos de procedimiento

1. El lockbox no se abre hasta tener entre 1 y 3 finalistas con parámetros
   congelados por escrito en el informe.
2. Si el lockbox falla, **no** se busca una variante que lo pase. El proyecto
   termina con ese resultado.
3. Todo trial cuenta, incluidos los abandonados a media implementación.
4. Cualquier bug encontrado en el motor después de haber generado resultados
   obliga a re-ejecutar y a documentar el cambio de cifras en el informe.

---

# Enmienda 1 — 2026-08-20

**Anterior a la ejecución del primer backtest de una estrategia.** No hay ningún
resultado que pueda haber motivado estos cambios: el registro de intentos
(`results/trials_log.csv`) está vacío en el commit que introduce esta enmienda, y
así puede comprobarse en el historial de git.

Los cinco cambios **endurecen** los criterios o especifican lo que estaba
ambiguo. Ninguno relaja nada.

## E1.1 · Todos los Sharpe se reportan con intervalo de confianza

Los umbrales de la sección 1 no tenían potencia estadística y hay que decirlo con
números. El error estándar del Sharpe anualizado es ≈ `sqrt(365/T)`:

| Muestra | T (días) | SE(Sharpe) | IC 95 % de un Sharpe puntual de 0,70 |
|---|---:|---:|---|
| TRAIN (BTC) | 1.992 | 0,43 | [−0,14, +1,54] |
| VALIDATION | 1.095 | 0,58 | [−0,43, +1,83] |
| LOCKBOX | 963 | 0,62 | [−0,51, +1,91] |
| Un bloque CPCV (2 grupos) | 398 | 0,96 | [−1,18, +2,58] |

Consecuencias que estaban ocultas en la versión original:

- **C1 (≥ 0,70) tiene ~50 % de potencia** contra un Sharpe verdadero de 0,70. La
  mitad de las estrategias que de verdad valen 0,70 lo suspenden.
- **Una estrategia sin ninguna ventaja lo aprueba por azar el 5-13 %** de las
  veces, según la muestra.
- **L1 (> 0,50 en el lockbox) con SE 0,62 da un IC de [−0,71, +1,71]**: un
  resultado compatible tanto con una buena estrategia como con nada.

Por tanto:

1. **Ningún Sharpe se reporta como punto.** Siempre `punto [IC 95 %]`, calculado
   con el mismo stationary block bootstrap de C9
   (`statistics.sharpe_confidence_interval`), que hereda la autocorrelación y la
   curtosis de la serie en lugar de suponer normalidad. Se reporta además el SE
   analítico de Lo (2002) como contraste.
2. **Regla de interpretación, vinculante:** si el punto estimado supera el umbral
   pero **el IC del 95 % incluye el cero**, el veredicto de ese criterio es
   **NO CONCLUYENTE**, nunca "cumple". Una finalista con cualquier criterio en NO
   CONCLUYENTE no puede declararse "con ventaja"; el veredicto global del proyecto
   pasa a **NO CONCLUYENTE** en lugar de "hay ventaja".
3. Esta regla se aplica igual en el lockbox. Dado el SE de 0,62, es previsible que
   **cualquier** resultado del lockbox con Sharpe menor que ~1,2 caiga en NO
   CONCLUYENTE. Queda escrito de antemano para que no se lea como decepción
   posterior: es lo que la longitud de la muestra permite concluir.

## E1.2 · C1 se mide sobre la mediana out-of-fold del CPCV

Redacción anterior: "Sharpe neto anualizado ≥ 0,70". Ambigua sobre qué serie.

**C1 (nuevo enunciado):** la **mediana** del Sharpe neto anualizado sobre los
**9 caminos out-of-fold del CPCV** debe ser ≥ 0,70. Mediana y no media: con 9
caminos, una media la mueve un solo camino afortunado.

Se añade **C1b**: Sharpe neto anualizado en VALIDATION (pasada única, parámetros
congelados en TRAIN) ≥ 0,70. C1 y C1b son ambos necesarios.

Ambos con la regla de intervalos de E1.1.

## E1.3 · C8 sube de umbral y añade evidencia efectiva

Redacción anterior: "Sharpe neto > 0 en SOL y en LTC". Es casi vacío — son
activos que subieron, y D4 explica por qué "funciona en 4 activos" está más cerca
de "funciona en 1".

**C8 (nuevo enunciado), las tres partes son necesarias:**

- **C8a** — Sharpe neto ≥ **0,40** en SOL **y** en LTC (antes: > 0).
- **C8b** — En SOL y en LTC la estrategia debe **batir al buy & hold de ese mismo
  activo en Sharpe**. Sin esto, C8a se puede aprobar cobrando beta de mercado.
- **C8c** — Se calcula la correlación media `ρ̄` entre las series de retornos
  diarios de la estrategia en los cuatro activos, y el número efectivo de activos
  independientes `N_eff = N / (1 + (N−1)·ρ̄)`. Si **`N_eff < 2`**, la estabilidad
  cross-asset **no cuenta como evidencia independiente** y así se declara en el
  informe: "validada en un activo efectivo, replicada en cuatro correlacionados".

## E1.4 · Registro de intentos obligatorio

`src/trial_registry.py`, append-only, persistido a disco **en el momento de cada
evaluación**. Sin él, C5 (DSR) es decorativo: el DSR necesita `N` y `Var(SR)`
reales, y un `N` reconstruido de memoria al final siempre sale corto.

- Cuenta **toda** configuración evaluada: exploraciones, descartes y errores.
- Las repeticiones se registran y quedan visibles, pero el `N` del DSR usa
  configuraciones únicas.
- El módulo no expone ninguna API de borrado.
- El informe publica `n_trials`, `n_unique`, `n_repeats` y el desglose por
  resultado.

## E1.5 · Reinicio de estado y calentamiento en cada bloque de test

El purgado derivado del lookback no basta para estrategias con estado: una ruptura
de Donchian de 55 días puede mantener la posición meses, mucho más allá de su
ventana. Si el bloque de test arranca con la posición heredada del entrenamiento,
sus primeros meses miden el entrenamiento.

- Cada `StrategySpec` declara `warmup(params)`, que **no** es su lookback.
- Al entrar en cada bloque de test el estado se **reinicia a plano** y se
  reconstruye usando solo los `warmup` días previos, que el purgado ya excluye del
  entrenamiento.
- Se puntúa únicamente el bloque de test (`backtest.run(..., score_from=)`).
- Si delante del bloque no hay `warmup` días, el calentamiento sale del propio
  bloque y esos días no se puntúan.
- Si el purgado más el calentamiento superan el 40 % de TRAIN
  (`validation.is_feasible`), la estrategia **no es validable con estos datos** y
  el informe lo dice así, en lugar de publicar un número.

Coste medido sobre el TRAIN de BTC (1.992 días): lookback 200 con calentamiento
200 consume el 31,4 %; con calentamiento 400 llega al 42,2 % y queda **inviable**.
Las estrategias de tendencia muy lenta pueden no ser evaluables en este proyecto,
y eso es un resultado, no un fallo.
