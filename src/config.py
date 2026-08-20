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

# --- Posiciones (regla 7) ------------------------------------------------
MIN_POSITION = 0.0
MAX_POSITION = 1.0   # long/flat, sin apalancamiento

# --- Validación: CPCV (regla 1 / fase 4) ---------------------------------
# Combinatorial Purged Cross-Validation (López de Prado). Sustituye al
# walk-forward simple: da muchos más pliegues out-of-sample sobre un TRAIN corto,
# y es el método sobre el que está definido el PBO.
CPCV_N_GROUPS = 6          # N: bloques temporales contiguos
CPCV_N_TEST_GROUPS = 2     # k: bloques de test por combinación -> C(6,2) = 15
CPCV_EMBARGO_PCT = 0.01    # embargo: 1 % de la muestra tras cada bloque de test

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
