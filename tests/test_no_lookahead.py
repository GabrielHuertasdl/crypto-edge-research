"""Regla 2 — lookahead bias. El test más importante del proyecto.

Cuatro ángulos distintos, porque el lookahead se cuela por cuatro sitios:
  1. el motor coloca la posición un día antes de lo que dice        -> oráculos
  2. un indicador mira al futuro                                    -> truncado
  3. la señal se construye con datos que aún no existían            -> truncado
  4. alguien escribe `center=True` o `shift(-n)` sin darse cuenta   -> grep
"""

import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src import backtest as bt, config, indicators as ind  # noqa: E402

N = 3000


@pytest.fixture(scope="module")
def ruido():
    """Retornos i.i.d. sin ninguna estructura explotable. Cualquier Sharpe alto
    sobre esto solo puede venir de conocer el futuro."""
    rng = np.random.default_rng(config.SEED)
    r = rng.normal(0.0, 0.03, N)
    close = 100 * np.cumprod(1 + r)
    idx = pd.date_range("2010-01-01", periods=N, freq="D", tz="UTC")
    c = pd.Series(close, index=idx)
    return pd.DataFrame(
        {"open": c, "high": c * 1.01, "low": c * 0.99, "close": c, "volume": 1.0}, index=idx
    )


def _oracle(prices: pd.DataFrame, horizon: int) -> pd.Series:
    """Señal en t que conoce el retorno de t+horizon. Trampa deliberada."""
    fwd = prices["close"].pct_change().shift(-horizon)
    return (fwd > 0).astype(float)


# ---------------------------------------------------------------------------
# 1. Control positivo: el motor SÍ detecta el lookahead cuando lo hay
# ---------------------------------------------------------------------------
def test_oraculo_alineado_con_el_lag_gana_muchisimo(ruido):
    """Un oráculo que conoce r[t+2] y se ejecuta con lag 2 cobra todos los días
    verdes. Si esto NO diera un Sharpe enorme, el motor estaría desplazando la
    posición de otra forma y todos los demás tests dirían poco."""
    res = bt.run(ruido, _oracle(ruido, config.OFFICIAL_LAG), lag=config.OFFICIAL_LAG)
    assert res.metrics["sharpe"] > 8, res.metrics["sharpe"]


# ---------------------------------------------------------------------------
# 2. El test que pide la regla 2: oráculo de UN día no vale con lag 2
# ---------------------------------------------------------------------------
def test_oraculo_de_un_dia_no_gana_nada_con_lag_2(ruido):
    """Señal en t que conoce r[t+1], ejecutada con el lag oficial de 2.

    La posición que resulta cobra r[t+2], así que el oráculo predice el día
    equivocado: sobre ruido i.i.d. su Sharpe debe ser indistinguible de cero.
    Si ganara, el motor estaría ejecutando antes de lo que declara.
    """
    res = bt.run(ruido, _oracle(ruido, 1), lag=config.OFFICIAL_LAG)
    assert abs(res.metrics["sharpe"]) < 1.0, res.metrics["sharpe"]


def test_el_mismo_oraculo_con_lag_1_sí_gana(ruido):
    """Contraste que justifica el cambio de regla: con lag 1 ese mismo oráculo
    de un día es imbatible. La diferencia entre 'ventaja' y 'artefacto de un día'
    es exactamente este test."""
    res1 = bt.run(ruido, _oracle(ruido, 1), lag=1)
    res2 = bt.run(ruido, _oracle(ruido, 1), lag=2)
    assert res1.metrics["sharpe"] > 8
    assert res1.metrics["sharpe"] > 8 * abs(res2.metrics["sharpe"])


def test_lag_decay_delata_el_artefacto_de_un_dia(ruido):
    """C10 en acción: `lag_decay` debe hundirse para una señal que solo vive con
    lag 1."""
    variantes = bt.run_lag_variants(ruido, _oracle(ruido, 1))
    assert bt.lag_decay(variantes) < 0.70


# ---------------------------------------------------------------------------
# 3. Truncado: nada de lo calculado en t puede cambiar al añadir datos futuros
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("name,fn,lookback", ind.CAUSALITY_SUITE, ids=lambda x: x if isinstance(x, str) else "")
def test_indicadores_son_causales(ruido, name, fn, lookback):
    """Se recalcula el indicador sobre la serie truncada en T y se exige que
    coincida con el valor de la serie completa. Un `center=True`, un `shift(-n)`
    o una normalización global rompen esto de inmediato."""
    T = 2000
    completo = fn(ruido).iloc[:T]
    truncado = fn(ruido.iloc[:T])
    pd.testing.assert_series_equal(completo, truncado, check_names=False, rtol=1e-12)


def test_pipeline_completo_es_causal(ruido):
    """Indicador + señal + motor. El resultado de los primeros T días no puede
    depender de que existan los días T+1 en adelante."""
    T = 2000

    def señal(df):
        rapida, lenta = ind.sma(df["close"], 20), ind.sma(df["close"], 100)
        return (rapida > lenta).astype(float)

    full = bt.run(ruido, señal(ruido), lag=2)
    trunc = bt.run(ruido.iloc[:T], señal(ruido.iloc[:T]), lag=2)

    pd.testing.assert_series_equal(
        full.returns.iloc[:T], trunc.returns, check_names=False, rtol=1e-12
    )
    pd.testing.assert_series_equal(
        full.equity.iloc[:T], trunc.equity, check_names=False, rtol=1e-12
    )


def test_desplazar_la_serie_desplaza_el_resultado_igual(ruido):
    """Desplazar los precios k días debe desplazar los retornos exactamente k
    días. Si el motor mirara una ventana absoluta en vez de relativa, no."""
    k = 5
    señal = pd.Series((np.arange(N) % 11 < 5).astype(float), index=ruido.index)
    base = bt.run(ruido, señal, lag=2)

    movido = ruido.copy()
    movido.index = movido.index + pd.Timedelta(days=k)
    señal_mov = pd.Series(señal.values, index=movido.index)
    otro = bt.run(movido, señal_mov, lag=2)

    np.testing.assert_allclose(base.returns.values, otro.returns.values, rtol=1e-12)


# ---------------------------------------------------------------------------
# 4. Grep: patrones prohibidos en el código de señales
# ---------------------------------------------------------------------------
PROHIBIDOS = [
    (r"center\s*=\s*True", "rolling centrado: usa datos futuros"),
    (r"\.shift\(\s*-\d+", "shift negativo: trae el futuro al presente"),
    (r"\.bfill\(", "bfill: propaga valores futuros hacia atrás"),
    (r"fillna\(\s*method\s*=\s*['\"]bfill", "bfill: propaga valores futuros"),
    (r"\.interpolate\(", "interpolate: mezcla pasado y futuro"),
]


@pytest.mark.parametrize("modulo", ["indicators.py", "strategies.py"])
def test_sin_patrones_de_lookahead_en_el_codigo(modulo):
    """`backtest.py` queda fuera a propósito: ahí el `shift` hacia atrás sobre la
    señal es justo el mecanismo del retardo. Los tests de oráculo lo cubren."""
    texto = (ROOT / "src" / modulo).read_text(encoding="utf-8")
    # Fuera comentarios y docstrings, que citan estos patrones para prohibirlos.
    codigo = re.sub(r'"""[\s\S]*?"""', "", texto)
    codigo = "\n".join(l.split("#")[0] for l in codigo.splitlines())
    for patron, motivo in PROHIBIDOS:
        assert not re.search(patron, codigo), f"{modulo}: {motivo}"
