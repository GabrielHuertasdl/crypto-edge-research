"""Constantes del proyecto. Única fuente de verdad para las reglas innegociables.

Nada de números mágicos repartidos por el código: si un coste o una fecha de corte
aparece en otro sitio, es un bug.
"""

from __future__ import annotations

from pathlib import Path

# --- Rutas ---------------------------------------------------------------
ROOT = Path(__file__).resolve().parent.parent
DATA_RAW = ROOT / "data" / "raw"
DATA_PROCESSED = ROOT / "data" / "processed"
RESULTS = ROOT / "results"
FIGURES = RESULTS / "figures"
LOCKBOX_DIR = ROOT / "lockbox"

# Registro global de configuraciones probadas (regla 4: comparaciones múltiples).
TRIALS_LOG = RESULTS / "trials_log.csv"

# Centinela: existe <=> el lockbox ya se ha ejecutado. Ver lockbox/.
LOCKBOX_SENTINEL = LOCKBOX_DIR / ".lockbox_used"

# --- Universo ------------------------------------------------------------
# La optimización de parámetros solo ve BTC y ETH. SOL y LTC quedan reservados
# como test de estabilidad cross-asset: para ellos, todo es fuera de muestra.
OPTIMIZATION_ASSETS = ("BTC", "ETH")
CROSS_ASSET_TEST_ASSETS = ("SOL", "LTC")
ASSETS = OPTIMIZATION_ASSETS + CROSS_ASSET_TEST_ASSETS

QUOTE = "USD"
TIMEFRAME = "1d"

# --- Fuentes de datos ----------------------------------------------------
# Coinbase Exchange = serie de EJECUCIÓN. Todo precio con el que se opera sale
# de aquí. yfinance = detector de anomalías; nunca alimenta un backtest.
EXECUTION_SOURCE = "coinbaseexchange"
ANOMALY_SOURCE = "yfinance"
CROSS_CHECK_TOLERANCE = 0.02   # se loguea toda diferencia de cierre > 2 %

COINBASE_SYMBOLS = {a: f"{a}/{QUOTE}" for a in ASSETS}
YFINANCE_TICKERS = {a: f"{a}-{QUOTE}" for a in ASSETS}

# Frontera de vela: 00:00 UTC. Verificado por tests/test_utc_convention.py.
CANDLE_BOUNDARY_UTC = "00:00"

# --- Splits temporales (regla 1) -----------------------------------------
# Cerrados por ambos extremos. LOCKBOX_END = None significa "hasta el último dato".
SPLITS = {
    "train": ("2015-01-01", "2020-12-31"),
    "validation": ("2021-01-01", "2023-12-31"),
    "lockbox": ("2024-01-01", None),
}

# Subperiodos para el análisis de régimen (fase 4).
SUBPERIODS = {
    "bear_2018": ("2018-01-01", "2018-12-31"),
    "bull_2020_21": ("2020-04-01", "2021-11-30"),
    "bear_2022": ("2022-01-01", "2022-12-31"),
    "bull_2023_24": ("2023-01-01", "2024-12-31"),
}

# --- Costes (regla 3) ----------------------------------------------------
COMMISSION_PER_SIDE = 0.0010   # 0,10 % por lado
SLIPPAGE_PER_TRADE = 0.0005    # 0,05 % por operación
# Coste total de un cambio de posición completo (entrar o salir):
COST_PER_TURN = COMMISSION_PER_SIDE + SLIPPAGE_PER_TRADE

# --- Ejecución (regla 2) -------------------------------------------------
# Mercado 24/7: el open de t+1 ES el cierre de t, así que ejecutar "al open de
# t+1" no impone ningún retardo real. Se ejecuta al CIERRE de t+1.
#
# Cadena exacta:
#   señal s[t]      calculada con datos hasta el cierre de t
#   posición p[t+1] establecida al cierre de t+1        -> p = s.shift(1)
#   retorno   r[t+2] es el primero que cobra esa posición -> ret = p.shift(1) * r
#   efectivo: strategy_return = s.shift(2) * r
EXECUTION_LAG_DAYS = 1
EXECUTION_PRICE = "close"
RETURN_LAG_TOTAL = 2   # desplazamiento total señal -> retorno cobrado

# Lag oficial = 2. El lag 1 se corre EN PARALELO como diagnóstico, nunca como
# resultado: si el alpha existe con lag 1 y desaparece con lag 2, era un artefacto
# de un día (microestructura, cierre mal alineado, señal que ya conocía el dato).
OFFICIAL_LAG = RETURN_LAG_TOTAL
LAG_VARIANTS = (1, 2)

# --- Posiciones (regla 7) ------------------------------------------------
MIN_POSITION = 0.0
MAX_POSITION = 1.0   # long/flat, sin apalancamiento

# --- Validación: CPCV (regla 1 / fase 4) ---------------------------------
# Combinatorial Purged Cross-Validation (López de Prado).
#
# Lo que se reporta son CAMINOS, no combinaciones. Con N grupos y k de test hay
# C(N,k) combinaciones pero solo `k*C(N,k)/N` caminos de backtest completos, y el
# PBO se estima sobre caminos. Decir "15 pliegues" cuando hay 5 caminos infla la
# sensación de evidencia por un factor de 3.
#
#   N=6  -> C(6,2)=15  combinaciones,  5 caminos, bloque BTC ~332 d
#   N=10 -> C(10,2)=45 combinaciones,  9 caminos, bloque BTC ~199 d   <- elegido
#   N=12 -> C(12,2)=66 combinaciones, 11 caminos, bloque BTC ~166 d
#
# Elegido N=10: casi dobla los caminos frente a N=6 (5 -> 9) manteniendo bloques
# de test de ~400 días (2 grupos), suficientes para contener algo más que un solo
# tramo direccional.
#
# TENSIÓN CON D2, explícita: subir N sube el número de caminos, NO el número de
# regímenes independientes. Los 9 caminos comparten los mismos datos y los mismos
# ~3 ciclos de mercado. La independencia efectiva sigue acotada por el número de
# regímenes (un dígito), no por el número de caminos. Los caminos mejoran la
# ESTIMACIÓN del PBO; no crean evidencia nueva. Va al informe.
CPCV_N_GROUPS = 10
CPCV_N_TEST_GROUPS = 2
CPCV_EMBARGO_PCT = 0.01    # embargo tras cada bloque de test, en fracción de muestra

# Fracción máxima de TRAIN que el purgado puede comerse antes de que la
# configuración se considere inviable y se marque en el informe.
CPCV_MAX_PURGED_FRACTION = 0.40

# El span de purgado NO es una constante: se deriva del lookback máximo de cada
# estrategia (una SMA de 200 arrastra 200 días de solape; purgar 20 no elimina
# nada). Ver `validation.purge_spans()`.

# --- Estadística ---------------------------------------------------------
TRADING_DAYS_PER_YEAR = 365   # cripto cotiza 24/7
SEED = 42

# --- Prueba de nulidad (regla 6) -----------------------------------------
# Stationary block bootstrap (Politis & Romano 1994) sobre los retornos REALES,
# no paseo aleatorio gaussiano: conserva colas gruesas y agrupamiento de
# volatilidad, y destruye solo la estructura de dependencia que la estrategia
# dice explotar. Un RW gaussiano es un rival de paja.
N_SYNTHETIC_PATHS = 1000
BOOTSTRAP_MEAN_BLOCK_DAYS = 20   # longitud media del bloque geométrico

# --- Validación fuera de cripto (preparado para fase 5) ------------------
# Si la finalista es de seguimiento de tendencia, se prueba SIN REOPTIMIZAR sobre
# activos con regímenes de verdad independientes. Es lo único que compensa la
# escasez de ciclos de D2. Estos mercados NO cotizan 24/7: su calendario tiene
# huecos legítimos (fines de semana, festivos) y el validador de integridad los
# trata aparte.
EXTERNAL_VALIDATION_TICKERS = {
    "GOLD": "GC=F",       # futuro continuo del oro
    "SP500": "^GSPC",
    "EURUSD": "EURUSD=X",
    "USDJPY": "USDJPY=X",
}

# Umbrales que promueven una estrategia a "necesita validación fuera de cripto"
# como conjunto PRIMARIO, no como test final (Enmienda 2, E2.4).
EXTERNAL_REQUIRED_LOOKBACK = 100
EXTERNAL_REQUIRED_WARMUP = 200

# Estos mercados no cotizan 24/7: ~252 sesiones al año y huecos legítimos de
# calendario (fines de semana, festivos). La anualización y el validador de
# integridad los tratan aparte.
EXTERNAL_TRADING_DAYS_PER_YEAR = 252

# Splits para los activos externos. `deep_oos` es todo lo anterior al TRAIN de
# cripto: décadas que NINGÚN parámetro de este proyecto ha visto, porque los
# parámetros se ajustan en el TRAIN de cripto y aquí se aplican sin reoptimizar.
#
# AVISO: `deep_oos` NO es un segundo lockbox. En cuanto se use para elegir entre
# finalistas deja de ser virgen y pasa a ser un conjunto de selección. Se declara
# como tal desde el principio en lugar de fingir después que era una prueba
# independiente.
EXTERNAL_SPLITS = {
    "deep_oos": (None, "2014-12-31"),
    "train": ("2015-01-01", "2020-12-31"),
    "validation": ("2021-01-01", "2023-12-31"),
    "lockbox": ("2024-01-01", None),
}
