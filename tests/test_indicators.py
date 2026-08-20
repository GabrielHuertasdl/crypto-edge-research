"""Especificación de los indicadores, con valores calculados a mano.

Existe por una razón concreta: el test de causalidad NO detecta el sesgo de
**misma vela**. `high.rolling(n).max()` sin `shift(1)` es perfectamente causal —
solo usa datos hasta `t` — pero incluye el máximo de HOY en el canal, así que
`close >= upper` compara el precio contra un techo que él mismo acaba de fijar.
Eso no es mirar al futuro, es mirarse a sí mismo, y el test de truncado lo deja
pasar. Aquí se fija por especificación.
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src import indicators as ind  # noqa: E402


def series(vals, start="2020-01-01"):
    return pd.Series(
        vals, index=pd.date_range(start, periods=len(vals), freq="D", tz="UTC"), dtype=float
    )


def ohlc(highs, lows, closes):
    idx = pd.date_range("2020-01-01", periods=len(closes), freq="D", tz="UTC")
    return pd.DataFrame(
        {"open": closes, "high": highs, "low": lows, "close": closes, "volume": 1.0}, index=idx
    )


# ---------------------------------------------------------------------------
# Canal de Donchian: el que más veces se implementa mal
# ---------------------------------------------------------------------------
def test_donchian_excluye_la_vela_actual():
    """upper[t] = max(high[t-n .. t-1]). Si incluyera high[t], una ruptura sería
    tautológica el día que se marca el máximo."""
    highs = [10, 12, 11, 20, 13]
    df = ohlc(highs, [h - 5 for h in highs], [h - 1 for h in highs])
    up = ind.donchian(df, 3)["upper"]

    assert np.isnan(up.iloc[0]) and np.isnan(up.iloc[1]) and np.isnan(up.iloc[2])
    assert up.iloc[3] == 12.0          # max(10, 12, 11), NO incluye el 20 de hoy
    assert up.iloc[4] == 20.0          # ahora sí, el 20 ya es pasado


def test_donchian_lower_excluye_la_vela_actual():
    lows = [10, 8, 9, 2, 7]
    df = ohlc([l + 5 for l in lows], lows, [l + 1 for l in lows])
    lo = ind.donchian(df, 3)["lower"]
    assert lo.iloc[3] == 8.0
    assert lo.iloc[4] == 2.0


def test_el_canal_no_incorpora_el_maximo_del_propio_dia():
    """El día en que se imprime un máximo nuevo, el canal debe seguir mostrando el
    máximo ANTERIOR. Solo así `close > upper` es una ruptura de un techo que ya
    existía y no una comparación contra un techo que el propio día acaba de fijar.
    """
    highs = [10, 10, 10, 10, 30, 10, 10]
    closes = [9, 9, 9, 9, 29, 9, 9]
    df = ohlc(highs, [h - 5 for h in highs], closes)
    up = ind.donchian(df, 3)["upper"]

    assert up.iloc[4] == 10.0          # techo previo, el 30 de hoy no entra
    assert bool(df["close"].iloc[4] > up.iloc[4])   # ruptura legítima del techo viejo
    assert up.iloc[5] == 30.0          # mañana el 30 ya es pasado

    # Versión rota (sin shift): el máximo del día entra en su propio canal y la
    # comparación high >= upper se vuelve cierta por construcción.
    roto = df["high"].rolling(3, min_periods=3).max()
    assert bool((df["high"] >= roto).iloc[4])
    assert not bool((df["high"] >= up).iloc[4]) or up.iloc[4] < df["high"].iloc[4]


# ---------------------------------------------------------------------------
# Medias y calentamiento
# ---------------------------------------------------------------------------
def test_sma_valor_exacto_y_calentamiento():
    s = series([1, 2, 3, 4, 5])
    m = ind.sma(s, 3)
    assert m.iloc[:2].isna().all()
    assert m.iloc[2] == 2.0 and m.iloc[3] == 3.0 and m.iloc[4] == 4.0


def test_ema_no_emite_valores_parciales():
    s = series(list(range(1, 11)))
    e = ind.ema(s, 5)
    assert e.iloc[:4].isna().all()
    assert e.notna().iloc[4:].all()


def test_roc_es_retorno_cerrado_en_t():
    s = series([100, 110, 121])
    np.testing.assert_allclose(ind.roc(s, 2).iloc[2], 0.21)


# ---------------------------------------------------------------------------
# Volatilidad y rango
# ---------------------------------------------------------------------------
def test_true_range_sin_cierre_previo_es_nan():
    df = ohlc([10, 12], [8, 9], [9, 11])
    tr = ind.true_range(df)
    assert np.isnan(tr.iloc[0])
    # max(12-9, |12-9|, |9-9|) = 3
    assert tr.iloc[1] == 3.0


def test_realized_vol_es_positiva_y_escala():
    rng = np.random.default_rng(0)
    s = series(100 * np.cumprod(1 + rng.normal(0, 0.02, 400)))
    v = ind.realized_vol(s, 30)
    assert (v.dropna() > 0).all()
    # 2 % diario -> ~38 % anualizado con 365 días
    assert 0.2 < v.dropna().median() < 0.6


# ---------------------------------------------------------------------------
# RSI
# ---------------------------------------------------------------------------
def test_rsi_solo_subidas_es_100():
    s = series(list(range(1, 40)))
    assert ind.rsi(s, 14).dropna().iloc[-1] == 100.0


def test_rsi_solo_bajadas_tiende_a_cero():
    s = series(list(range(40, 1, -1)))
    assert ind.rsi(s, 14).dropna().iloc[-1] < 1.0


def test_rsi_dentro_de_rango():
    rng = np.random.default_rng(1)
    s = series(100 * np.cumprod(1 + rng.normal(0, 0.02, 500)))
    v = ind.rsi(s, 14).dropna()
    assert v.min() >= 0.0 and v.max() <= 100.0


# ---------------------------------------------------------------------------
# Z-score y Bollinger
# ---------------------------------------------------------------------------
def test_zscore_usa_ventana_rolling_no_la_muestra_completa():
    """Si usara la media global, el z-score del primer tramo cambiaría al añadir
    datos al final. Se comprueba directamente."""
    rng = np.random.default_rng(2)
    largo = series(100 * np.cumprod(1 + rng.normal(0, 0.02, 600)))
    corto = largo.iloc[:300]
    pd.testing.assert_series_equal(
        ind.zscore(largo, 20).iloc[:300], ind.zscore(corto, 20), rtol=1e-12
    )


def test_bollinger_bandas_ordenadas():
    rng = np.random.default_rng(3)
    s = series(100 * np.cumprod(1 + rng.normal(0, 0.02, 300)))
    b = ind.bollinger(s, 20, 2.0).dropna()
    assert (b["upper"] > b["mid"]).all()
    assert (b["mid"] > b["lower"]).all()


@pytest.mark.parametrize("name,fn,lookback", ind.CAUSALITY_SUITE, ids=lambda x: x if isinstance(x, str) else "")
def test_lookback_declarado_coincide_con_los_nan_iniciales(name, fn, lookback):
    """El lookback declarado alimenta el purgado del CPCV. Si miente, el purgado
    es insuficiente y hay fuga entre pliegues."""
    rng = np.random.default_rng(4)
    c = series(100 * np.cumprod(1 + rng.normal(0, 0.02, 500)))
    df = pd.DataFrame(
        {"open": c, "high": c * 1.01, "low": c * 0.99, "close": c, "volume": 1.0}, index=c.index
    )
    n_nan = int(fn(df).isna().sum())
    assert n_nan <= lookback, f"{name}: {n_nan} NaN iniciales > lookback declarado {lookback}"
