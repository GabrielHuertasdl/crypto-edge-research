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

---

# Enmienda 2 — 2026-08-20

**También anterior al primer backtest de una estrategia** (`results/trials_log.csv`
sigue sin existir en el commit que la introduce). Los cuatro cambios endurecen o
declaran de antemano un fracaso previsible. Ninguno relaja nada.

## E2.1 · El PBO está centrado, pero un PBO suelto no dice nada

Simulación bajo la nula (matrices de intentos sin ninguna habilidad, 100-150
réplicas por celda, S ∈ {8, 10, 16}, N ∈ {10, 25, 50}):

| | media | desv. típica | P(PBO ≤ 0,20 \| nula) |
|---|---:|---:|---:|
| S=8, N=25 | 0,479 | 0,202 | 10,7 % |
| S=10, N=25 | 0,490 | 0,207 | 9,3 % |
| S=16, N=50 | 0,511 | 0,169 | 3,3 % |

El estimador **está centrado en 0,50**, como debe. El 36 % que se reportó antes
sobre "ruido puro" era **una sola matriz**, no un promedio: con una desviación
típica de 0,20, una realización cualquiera cae fácilmente en 0,36. Corregido
también un sesgo menor de ±0,04 en el tratamiento de los empates exactos en la
mediana (con N impar el logit vale exactamente 0 en 1 de cada N casos; ahora se
reparte a la mitad).

Lo que sí queda demostrado es que **C6 por sí solo es débil**: una familia de
estrategias sin ninguna ventaja saca PBO ≤ 0,20 entre el 3 % y el 13 % de las
veces, del mismo orden que la tasa de falso positivo de C1.

**C6 (nuevo enunciado):** PBO ≤ 0,20 **y** `statistics.pbo_pvalue` ≤ 0,10, con la
nula simulada con la misma longitud, el mismo número de configuraciones y el mismo
número de bloques. Ambas condiciones son necesarias.

## E2.2 · El DSR NO es uniforme bajo la nula: 0,95 no es el 95 %

Simulación: 1.500 réplicas, en cada una se eligen `N` estrategias sin habilidad,
se toma la mejor por Sharpe y se calcula su DSR con la varianza observada de los
Sharpes de los intentos.

| Escenario | media | KS contra U(0,1) | P(DSR ≥ 0,95 \| nula) |
|---|---:|---|---:|
| N=20, intentos independientes | 0,496 | D=0,212, p≈1,6·10⁻⁵⁹ | 0,00 % |
| N=100, independientes | 0,491 | D=0,235, p≈1,3·10⁻⁷³ | 0,07 % |
| N=500, independientes | 0,495 | D=0,253, p≈3,5·10⁻⁸⁵ | 0,07 % |
| N=100, ρ̄ = 0,6 | 0,509 | D=0,078, p≈2,3·10⁻⁸ | 2,07 % |

**La media es correcta (≈ 0,50) pero la distribución está concentrada alrededor de
0,5, no es uniforme.** El Kolmogorov-Smirnov rechaza la uniformidad con enorme
holgura en los cuatro escenarios. La causa es que `SR_0` se calcula con la varianza
*observada* de los Sharpes de los intentos, que es justo la que determina el
máximo: numerador y umbral se mueven juntos y la diferencia se comprime.

Consecuencias, escritas antes de ver ningún resultado:

1. **"DSR ≥ 0,95" no significa "95 % de confianza".** Con intentos independientes
   es mucho **más** estricto (falso positivo < 0,1 %); con intentos correlacionados
   —que es el caso real, porque las configuraciones de una misma familia se parecen
   mucho— se relaja hasta ~2 %. El umbral nominal no está calibrado.
2. **C5 (nuevo enunciado):** DSR ≥ 0,95 **y** `statistics.dsr_pvalue` ≤ 0,05, con
   la nula simulada usando `N`, la longitud real y la **correlación media observada
   entre los intentos** (`statistics.mean_pairwise_correlation` sobre la matriz de
   retornos de las configuraciones). El p-valor manda sobre el umbral nominal.
3. Es previsible que C5 sea el criterio más difícil de superar, y que su dificultad
   dependa de cuán parecidas sean entre sí las configuraciones probadas. El informe
   publicará ρ̄ junto al DSR.

## E2.3 · Predicción registrada: C8c va a fallar

Con `N = 4` activos, `N_eff = 4 / (1 + 3ρ̄) ≥ 2` exige **ρ̄ ≤ 0,333**.

Las curvas de equity de una misma estrategia sobre BTC, ETH, SOL y LTC van a
correlacionar muy por encima de 0,333: los cuatro comparten factor de mercado y la
estrategia responde a él de la misma forma en todos. **Se deja escrito ahora que lo
esperable es `N_eff` entre 1 y 1,5**, es decir, que C8c falle.

Eso **no** invalida C8a ni C8b, que siguen siendo exigibles. Lo que hace es fijar
de antemano cómo se redacta el resultado: si C8c falla, el informe dirá
literalmente **"validada en ~1 activo efectivo, replicada en cuatro
correlacionados"**, y la estabilidad cross-asset no se contará como evidencia
independiente en el veredicto. Registrarlo ahora impide presentarlo después como
un matiz técnico menor.

## E2.4 · La validación fuera de cripto pasa a conjunto de datos primario

La tabla de viabilidad del CPCV (E1.5) tiene una consecuencia que no se había
extraído: con lookback 200 y calentamiento 400 el purgado se come el 42,2 % de
TRAIN y la configuración es **inviable**. Es decir, **el seguimiento de tendencia
lento —la familia con mejor evidencia documentada fuera de muestra, décadas de
ella en futuros gestionados— queda excluido por longitud de datos**.

Lo que queda viable es justo el conjunto complementario: familias de horizonte
corto, con evidencia previa más débil, más operaciones y por tanto **mucha mayor
sensibilidad a los costes**. Dejarlo así sesgaría el proyecto entero hacia las
estrategias con menos probabilidad *a priori* de tener ventaja real.

Por tanto:

- Para toda estrategia con `lookback ≥ 100` o `warmup ≥ 200`, **oro (`GC=F`),
  S&P 500 (`^GSPC`), EURUSD y USDJPY dejan de ser un test final y pasan a ser
  conjunto de datos primario**, con su propio TRAIN/VALIDATION/LOCKBOX.
- Esa infraestructura se monta en la **fase 3**, no al final.
- Los parámetros se ajustan en el TRAIN de cripto y se aplican **sin reoptimizar**
  fuera de cripto. La dirección no se invierte nunca: no se ajusta en oro para
  aplicar en BTC.
- Esos mercados aportan lo que a cripto le falta: décadas de historia y regímenes
  de verdad independientes. Un lookback de 200 días sobre el S&P desde 1990 tiene
  ~8.500 sesiones y varios ciclos completos; sobre BTC tiene 1.992 días y tres.
- Contrapartida declarada: el oro, el S&P y las divisas **no son el activo que se
  quiere operar**. Que una estrategia funcione ahí es evidencia de que la familia
  no es un artefacto, no de que vaya a funcionar en cripto. El informe mantendrá
  las dos cosas separadas.

---

# Enmienda 3 — 2026-08-20

**Última enmienda anterior al primer trial.** `results/trials_log.csv` sigue sin
existir en el commit que la introduce. A partir del commit siguiente, cualquier
cambio de criterio se considera posterior a los resultados y el informe lo tratará
como tal.

## E3.1 · Control de exposición equiparada (nuevo criterio C12)

Medición sobre el TRAIN de BTC (CAGR del 134 %), señales **aleatorias** con
exposición y rotación realistas, costes incluidos:

| Serie | Exposición | Rotación/día | Sharpe medio | P(Sharpe ≥ 0,70) | p95 |
|---|---:|---:|---:|---:|---:|
| BTC real | 55 % | 0,05 | 1,09 | **90,5 %** | 1,54 |
| BTC real | 55 % | 0,20 | 0,94 | **80,8 %** | 1,44 |
| BTC sin deriva | 55 % | 0,05 | −0,04 | 0,8 % | 0,49 |
| BTC sin deriva | 55 % | 0,20 | −0,20 | 0,2 % | 0,24 |

**Nueve de cada diez señales aleatorias superan C1 en el TRAIN de BTC.** Quitada
la deriva, menos de una de cada cien. La tasa de falso positivo de un umbral
absoluto de Sharpe la fija la deriva del activo, no la estrategia.

El benchmark de buy & hold no lo arregla: está al 100 % de exposición, mientras
que las estrategias del universo andan entre el 10 % y el 70 %. Comparar Sharpes
entre exposiciones distintas compara dos cosas diferentes.

**C12 (nuevo):** toda configuración debe superar el **percentil 95** de un nulo
con **exposición y rotación equiparadas** sobre el activo real
(`statistics.matched_exposure_null`). Dos métodos, ambos reportados:

- `rotation`: rotaciones circulares de la propia senda de posiciones. Conserva
  exactamente exposición, rotación y duración de las operaciones; solo destruye la
  alineación con los retornos. Es el nulo más ajustado posible.
- `markov`: cadena de dos estados con exposición y rotación equiparadas, sin
  reutilizar la senda real.

C12 **se suma** a C9, no lo sustituye. Preguntan cosas distintas: C9 pregunta si la
serie de precios tiene estructura explotable; C12 pregunta si, dado que estás
dentro del mercado tanto tiempo, aporta algo saber *cuándo*.

Primera aplicación, antes de la fase 4: `sma_cross(20, 100)` sobre el TRAIN de BTC
da Sharpe 1,55 contra un p95 del nulo equiparado de 1,71 — **percentil 90,6 %, no
supera C12**. Registrado como trial de exploración.

## E3.2 · El DSR usa el número EFECTIVO de intentos

Un `ρ̄` único no describe la estructura: dentro de una familia las
parametrizaciones correlacionan ~0,95, entre familias mucho menos.

`statistics.effective_number_of_trials` calcula `N_eff = (Σλ)² / Σλ²` por
participación de autovalores sobre la matriz de correlación de los retornos de los
intentos — la misma construcción que `N_eff` en C8c.

- El DSR se calcula con `N_eff`, no con `N` en bruto. Usar `N` sobrepenaliza:
  149 configuraciones que en el fondo son 8 apuestas no son 149 intentos
  independientes.
- La nula del p-valor se simula con `N_eff` intentos **independientes**: `N_eff`
  ya absorbe la correlación, y volver a meterla como `ρ` la contaría dos veces.
- El informe publica **`N`, `N_eff` y su cociente**. Un cociente muy alto significa
  que el universo explora mucho menos de lo que aparenta.

## E3.3 · Tolerancia del test de perturbación, derivada y con control positivo

La tolerancia de 1e-6 era arbitraria y dejaba nueve órdenes de magnitud para
esconder una dependencia real. Ahora:

- **Cota derivada**: `64 · eps · T`, del error de T sumas encadenadas de las
  ventanas móviles de pandas. Con T=900 son **1,3e-11**.
- **Dos clases de estrategia**: las de *memoria acotada* (ventanas finitas, sin
  estado: 8 de las 23) exigen **tolerancia cero** — alterar un precio más allá del
  calentamiento no puede cambiar nada. Las de memoria no acotada (medias
  exponenciales, o máquina de estados con `ffill`) admiten un residuo del 5 %,
  porque una posición abierta puede sobrevivir al calentamiento.
- **Control positivo del control**: un test inyecta una dependencia a 200 días con
  peso apenas superior a la cota y exige que el test de perturbación la detecte. Si
  alguien afloja la tolerancia, ese test falla.
