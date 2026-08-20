"""Fase 2 — tests del motor. Escritos ANTES de confiar en ningún resultado.

Todos los valores esperados están calculados a mano en el propio test. No se
recalcula con el motor lo que el motor debe demostrar: eso solo comprueba que el
código es consistente consigo mismo, incluidos sus bugs.
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src import backtest as bt, config  # noqa: E402

COST = config.COST_PER_TURN  # 0.0015


def mk(closes, start="2020-01-01"):
    """OHLCV mínimo y coherente a partir de una lista de cierres."""
    idx = pd.date_range(start, periods=len(closes), freq="D", tz="UTC")
    c = pd.Series(closes, index=idx, dtype=float)
    return pd.DataFrame(
        {"open": c, "high": c, "low": c, "close": c, "volume": 1.0}, index=idx
    )


def sig(values, prices):
    return pd.Series(values, index=prices.index, dtype=float)


# ---------------------------------------------------------------------------
# Aritmética básica
# ---------------------------------------------------------------------------
def test_senal_plana_no_opera_ni_gasta():
    p = mk([100, 110, 121, 133.1])
    res = bt.run(p, sig([0, 0, 0, 0], p), lag=2)
    assert (res.returns == 0).all()
    assert res.equity.iloc[-1] == 1.0
    assert res.metrics["n_trades"] == 0
    assert res.metrics["exposure"] == 0.0
    assert np.isnan(res.metrics["hit_rate"])


def test_largo_constante_valores_exactos():
    """closes +10 % diario; lag 2 -> se entra el día 2 y se paga UNA rotación.

    returns esperados: [0, 0, 0.10 - 0.0015, 0.10]
    equity  esperada: [1, 1, 1.0985, 1.0985 * 1.1 = 1.20835]
    """
    p = mk([100, 110, 121, 133.1])
    res = bt.run(p, sig([1, 1, 1, 1], p), lag=2)

    assert res.position.tolist() == [0.0, 0.0, 1.0, 1.0]
    np.testing.assert_allclose(res.returns.values, [0.0, 0.0, 0.10 - COST, 0.10])
    np.testing.assert_allclose(res.equity.values, [1.0, 1.0, 1.0985, 1.0985 * 1.1])
    np.testing.assert_allclose(res.metrics["total_return"], 0.20835)
    assert res.metrics["n_trades"] == 1
    np.testing.assert_allclose(res.trades.loc[0, "ret"], 0.20835)


def test_lag_coloca_la_posicion_exactamente_donde_toca():
    """Un pulso de señal en el día 1 debe producir posición SOLO en el día 1+lag."""
    p = mk([100] * 6)
    for lag in (1, 2, 3):
        res = bt.run(p, sig([0, 1, 0, 0, 0, 0], p), lag=lag)
        expected = [0.0] * 6
        expected[1 + lag] = 1.0
        assert res.position.tolist() == expected, f"lag={lag}"


def test_lag_cero_o_negativo_se_rechaza():
    p = mk([100, 101, 102])
    with pytest.raises(ValueError, match="lookahead"):
        bt.run(p, sig([1, 1, 1], p), lag=0)


def test_costes_exactos_por_rotacion():
    """Precio plano: el único efecto es el coste. 6 rotaciones -> (1-0.0015)^6."""
    p = mk([100] * 8)
    res = bt.run(p, sig([1, 0, 1, 0, 1, 0, 1, 0], p), lag=2)
    assert res.position.tolist() == [0, 0, 1, 0, 1, 0, 1, 0]
    turnover = np.abs(np.diff([0.0] + res.position.tolist()))
    assert turnover.sum() == 6.0
    np.testing.assert_allclose(res.equity.iloc[-1], (1 - COST) ** 6)


def test_coste_proporcional_en_posicion_fraccionaria():
    """Pasar de 0 a 0.5 cuesta la mitad que pasar de 0 a 1 (volatility targeting)."""
    p = mk([100] * 5)
    res = bt.run(p, sig([0.5, 0.5, 0.5, 0.5, 0.5], p), lag=2)
    np.testing.assert_allclose(res.returns.iloc[2], -0.5 * COST)
    assert res.returns.iloc[3] == 0.0


def test_drawdown_valor_y_duracion():
    """r = [0, 0, +20 %, -50 %, +100 %, +100 %], posición 1 desde el día 2.

    equity = [1, 1, 1.1985, 0.59925, 1.1985, 2.397]
    MDD = 0.59925 / 1.1985 - 1 = -0.50
    duración pico->recuperación = 2 días (día 2 -> día 4)
    """
    p = mk([100, 100, 120, 60, 120, 240])
    res = bt.run(p, sig([1] * 6, p), lag=2)
    np.testing.assert_allclose(res.metrics["max_drawdown"], -0.5)
    assert res.metrics["max_drawdown_days"] == 2


def test_drawdown_sin_recuperar_no_dura_cero():
    p = mk([100, 100, 100, 50, 50, 50])
    res = bt.run(p, sig([1] * 6, p), lag=2)
    assert res.metrics["max_drawdown"] < -0.4
    assert res.metrics["max_drawdown_days"] >= 2


def test_operaciones_tramos_contiguos():
    p = mk([100] * 10)
    res = bt.run(p, sig([1, 1, 0, 0, 1, 1, 1, 0, 0, 0], p), lag=2)
    # position = [0,0,1,1,0,0,1,1,1,0] -> dos tramos
    assert res.metrics["n_trades"] == 2
    assert res.trades["days"].tolist() == [2, 3]


def test_operacion_abierta_al_final_se_cuenta():
    p = mk([100] * 5)
    res = bt.run(p, sig([0, 0, 1, 1, 1], p), lag=2)
    assert res.metrics["n_trades"] == 1
    assert res.trades.loc[0, "exit"] == p.index[-1]


def test_hit_rate_y_profit_factor():
    """Dos operaciones: una gana ~+10 %, otra pierde ~-10 %."""
    p = mk([100, 100, 100, 110, 110, 110, 110, 99, 99])
    res = bt.run(p, sig([1, 1, 0, 0, 1, 1, 0, 0, 0], p), lag=2)
    assert res.metrics["n_trades"] == 2
    assert res.metrics["hit_rate"] == 0.5
    assert 0 < res.metrics["profit_factor"] < np.inf


def test_sharpe_de_serie_sin_varianza_es_cero_no_nan():
    p = mk([100] * 6)
    res = bt.run(p, sig([0] * 6, p), lag=2)
    assert res.metrics["sharpe"] == 0.0
    assert res.metrics["sortino"] == 0.0


def test_sharpe_signo_correcto():
    rng = np.random.default_rng(config.SEED)
    up = 100 * np.cumprod(1 + rng.normal(0.004, 0.02, 500))
    p = mk(up)
    res = bt.run(p, sig([1] * 500, p), lag=2)
    assert res.metrics["sharpe"] > 0
    inv = bt.run(p, sig([0] * 500, p), lag=2)
    assert inv.metrics["sharpe"] == 0.0


def test_exposicion_y_rotacion_anual():
    p = mk([100] * 366)
    s = [0.0] * 366
    for i in range(0, 366, 2):
        s[i] = 1.0
    res = bt.run(p, sig(s, p), lag=2)
    assert 0.45 < res.metrics["exposure"] < 0.55
    assert res.metrics["turnover_per_year"] > 300


# ---------------------------------------------------------------------------
# Validaciones defensivas
# ---------------------------------------------------------------------------
def test_rechaza_apalancamiento():
    p = mk([100, 101, 102])
    with pytest.raises(ValueError, match="fuera de"):
        bt.run(p, sig([1.5, 1.5, 1.5], p), lag=2)


def test_rechaza_cortos():
    p = mk([100, 101, 102])
    with pytest.raises(ValueError, match="fuera de"):
        bt.run(p, sig([-1, 0, 0], p), lag=2)


def test_rechaza_indice_desalineado():
    p = mk([100, 101, 102])
    otra = pd.Series([1.0, 1.0, 1.0], index=pd.date_range("2021-01-01", periods=3, tz="UTC"))
    with pytest.raises(ValueError, match="no comparten índice"):
        bt.run(p, otra, lag=2)


def test_rechaza_indice_sin_utc():
    p = mk([100, 101, 102])
    p.index = p.index.tz_localize(None)
    with pytest.raises(ValueError, match="UTC"):
        bt.run(p, pd.Series([1.0] * 3, index=p.index), lag=2)


# ---------------------------------------------------------------------------
# Benchmark y variantes de lag
# ---------------------------------------------------------------------------
def test_buy_and_hold_paga_una_entrada():
    p = mk([100, 110, 121, 133.1])
    bh = bt.buy_and_hold(p, lag=2)
    np.testing.assert_allclose(bh.metrics["total_return"], 0.20835)
    assert bh.metrics["n_trades"] == 1


def test_buy_and_hold_es_peor_que_sin_costes():
    """Comprobación de que el benchmark NO se calcula sin comisiones (regla 3)."""
    p = mk([100, 110, 121, 133.1])
    bh = bt.buy_and_hold(p, lag=2)
    bruto = (1 + 0.10) ** 2 - 1
    assert bh.metrics["total_return"] < bruto


def test_run_lag_variants_y_decay():
    rng = np.random.default_rng(7)
    p = mk(100 * np.cumprod(1 + rng.normal(0.001, 0.02, 400)))
    s = sig((np.arange(400) % 7 < 4).astype(float), p)
    res = bt.run_lag_variants(p, s)
    assert set(res) == set(config.LAG_VARIANTS)
    assert res[2].lag == 2
    assert not np.isnan(bt.lag_decay(res))
