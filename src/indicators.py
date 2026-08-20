"""Indicadores técnicos. TODOS causales (regla 2).

Prohibido en este módulo:
  - `center=True` en cualquier rolling
  - `shift(-n)` (traer el futuro hacia el presente)
  - normalizar con estadísticos de la muestra completa (media/std globales)
  - `bfill()` / `interpolate` que arrastre valores futuros hacia atrás

Contrato: el valor en `t` depende **únicamente** de datos disponibles al cierre de
`t`. Verificado por `tests/test_no_lookahead.py::test_indicadores_son_causales`,
que recalcula cada indicador sobre la serie truncada en `t` y exige el mismo valor.

Todas las funciones devuelven NaN durante su periodo de calentamiento en lugar de
un valor parcial: un valor calculado con 3 datos cuando la ventana es 200 no es el
indicador, es otra cosa con el mismo nombre.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


# ---------------------------------------------------------------------------
# Medias y tendencia
# ---------------------------------------------------------------------------
def sma(s: pd.Series, n: int) -> pd.Series:
    return s.rolling(n, min_periods=n).mean()


def ema(s: pd.Series, n: int) -> pd.Series:
    """EMA causal. `adjust=False` = recursión estándar; `min_periods=n` evita
    emitir valores durante el calentamiento."""
    return s.ewm(span=n, adjust=False, min_periods=n).mean()


def roc(s: pd.Series, n: int) -> pd.Series:
    """Momentum: retorno acumulado de los últimos n días, cerrado en t."""
    return s.pct_change(n)


def slope(s: pd.Series, n: int) -> pd.Series:
    """Pendiente normalizada de la media móvil: (SMA_t / SMA_{t-n}) - 1."""
    m = sma(s, n)
    return m / m.shift(n) - 1.0


# ---------------------------------------------------------------------------
# Volatilidad
# ---------------------------------------------------------------------------
def log_returns(s: pd.Series) -> pd.Series:
    return np.log(s).diff()


def realized_vol(s: pd.Series, n: int, annualize: int = 365) -> pd.Series:
    """Volatilidad realizada anualizada sobre los últimos n días."""
    return log_returns(s).rolling(n, min_periods=n).std() * np.sqrt(annualize)


def true_range(df: pd.DataFrame) -> pd.Series:
    prev_close = df["close"].shift(1)
    tr = pd.concat(
        [
            df["high"] - df["low"],
            (df["high"] - prev_close).abs(),
            (df["low"] - prev_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    # Sin cierre previo el rango verdadero no está definido: NaN, no high-low.
    return tr.where(prev_close.notna())


def atr(df: pd.DataFrame, n: int) -> pd.Series:
    """ATR de Wilder. `ewm(alpha=1/n)` reproduce el suavizado original."""
    return true_range(df).ewm(alpha=1.0 / n, adjust=False, min_periods=n).mean()


# ---------------------------------------------------------------------------
# Reversión a la media
# ---------------------------------------------------------------------------
def rsi(s: pd.Series, n: int = 14) -> pd.Series:
    """RSI de Wilder. Suavizado exponencial recursivo, causal por construcción."""
    delta = s.diff()
    gain = delta.clip(lower=0.0)
    loss = (-delta).clip(lower=0.0)
    avg_gain = gain.ewm(alpha=1.0 / n, adjust=False, min_periods=n).mean()
    avg_loss = loss.ewm(alpha=1.0 / n, adjust=False, min_periods=n).mean()
    rs = avg_gain / avg_loss.replace(0.0, np.nan)
    out = 100.0 - 100.0 / (1.0 + rs)
    # avg_loss == 0 con avg_gain > 0 => RSI 100 (solo subidas en la ventana).
    return out.where(avg_loss != 0.0, 100.0).where(avg_gain.notna())


def zscore(s: pd.Series, n: int) -> pd.Series:
    """Z-score con media y desviación ROLLING, nunca de la muestra completa.

    Usar media/std globales aquí sería lookahead puro y silencioso: el z-score de
    2016 conocería la volatilidad de 2024.
    """
    m = s.rolling(n, min_periods=n).mean()
    sd = s.rolling(n, min_periods=n).std()
    return (s - m) / sd.replace(0.0, np.nan)


def bollinger(s: pd.Series, n: int = 20, k: float = 2.0) -> pd.DataFrame:
    m = s.rolling(n, min_periods=n).mean()
    sd = s.rolling(n, min_periods=n).std()
    return pd.DataFrame({"mid": m, "upper": m + k * sd, "lower": m - k * sd})


# ---------------------------------------------------------------------------
# Rupturas
# ---------------------------------------------------------------------------
def donchian(df: pd.DataFrame, n: int) -> pd.DataFrame:
    """Canal de Donchian **excluyendo la vela actual** (`shift(1)`).

    Sin el shift, el máximo de n días incluye el máximo de hoy, así que
    `close >= upper` se dispararía justo el día del máximo: la señal conocería su
    propio resultado. Es el lookahead clásico de los sistemas de ruptura y es
    exactamente por eso que va aquí y no en cada estrategia.
    """
    upper = df["high"].rolling(n, min_periods=n).max().shift(1)
    lower = df["low"].rolling(n, min_periods=n).min().shift(1)
    return pd.DataFrame({"upper": upper, "lower": lower})


# ---------------------------------------------------------------------------
# Registro para el test de causalidad
# ---------------------------------------------------------------------------
# (nombre, función df -> Series, lookback en días)
CAUSALITY_SUITE: list[tuple[str, object, int]] = [
    ("sma_50", lambda d: sma(d["close"], 50), 50),
    ("ema_20", lambda d: ema(d["close"], 20), 20),
    ("roc_30", lambda d: roc(d["close"], 30), 30),
    ("slope_20", lambda d: slope(d["close"], 20), 40),
    ("realized_vol_30", lambda d: realized_vol(d["close"], 30), 31),
    ("true_range", lambda d: true_range(d), 2),
    ("atr_14", lambda d: atr(d, 14), 14),
    ("rsi_14", lambda d: rsi(d["close"], 14), 15),
    ("zscore_20", lambda d: zscore(d["close"], 20), 20),
    ("bollinger_upper_20", lambda d: bollinger(d["close"], 20)["upper"], 20),
    ("bollinger_lower_20", lambda d: bollinger(d["close"], 20)["lower"], 20),
    ("donchian_upper_55", lambda d: donchian(d, 55)["upper"], 56),
    ("donchian_lower_20", lambda d: donchian(d, 20)["lower"], 21),
]
