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
