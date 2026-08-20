"""CPCV: purgado derivado del lookback, embargo, y caminos (no combinaciones)."""

import sys
from math import comb
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src import config, validation as v  # noqa: E402


def idx(n, start="2015-01-01"):
    return pd.date_range(start, periods=n, freq="D", tz="UTC")


# ---------------------------------------------------------------------------
# Caminos
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("N,k,esperado", [(6, 2, 5), (8, 2, 7), (10, 2, 9), (12, 2, 11), (6, 3, 10)])
def test_numero_de_caminos(N, k, esperado):
    assert v.n_paths(N, k) == esperado
    assert len(v.cpcv_paths(N, k)) == esperado


def test_caminos_no_son_combinaciones():
    """El error que se quiere evitar: reportar 45 cuando hay 9."""
    N, k = config.CPCV_N_GROUPS, config.CPCV_N_TEST_GROUPS
    assert comb(N, k) == 45
    assert v.n_paths() == 9
    assert v.n_paths() < comb(N, k)


def test_cada_camino_cubre_todos_los_grupos_una_vez():
    for camino in v.cpcv_paths():
        grupos = [g for _, g in camino]
        assert sorted(grupos) == list(range(config.CPCV_N_GROUPS))


def test_cada_par_combo_grupo_se_usa_una_sola_vez():
    usados = [par for camino in v.cpcv_paths() for par in camino]
    assert len(usados) == len(set(usados))


# ---------------------------------------------------------------------------
# Spans de purgado
# ---------------------------------------------------------------------------
def test_purgado_posterior_es_el_lookback_no_una_constante():
    """El punto exacto: con SMA de 200, purgar 20 días no elimina la fuga."""
    corto = v.purge_spans(max_lookback=20, n_samples=1000)
    largo = v.purge_spans(max_lookback=200, n_samples=1000)
    assert corto.after == 20
    assert largo.after == 200
    assert largo.after == 10 * corto.after


def test_purgado_anterior_es_el_horizonte_de_la_etiqueta():
    s = v.purge_spans(max_lookback=50, n_samples=1000, label_horizon=1, lag=2)
    assert s.before == 2
    s5 = v.purge_spans(max_lookback=50, n_samples=1000, label_horizon=5, lag=2)
    assert s5.before == 6


def test_embargo_es_fraccion_de_la_muestra():
    s = v.purge_spans(max_lookback=10, n_samples=2000, embargo_pct=0.01)
    assert s.embargo == 20
    assert s.total_after == 30


# ---------------------------------------------------------------------------
# Splits
# ---------------------------------------------------------------------------
def test_train_y_test_nunca_se_tocan():
    splits = v.cpcv_splits(idx(1000), max_lookback=50)
    for s in splits:
        assert len(s.train.intersection(s.test)) == 0


def test_numero_de_splits_es_el_de_combinaciones():
    splits = v.cpcv_splits(idx(1000), max_lookback=50)
    assert len(splits) == comb(config.CPCV_N_GROUPS, config.CPCV_N_TEST_GROUPS)


def test_purgado_elimina_exactamente_el_tramo_esperado():
    """Índice de 100 días, N=10 -> grupos de 10. Combo con el grupo 5 (posiciones
    50-59) entre los de test: con lookback 7, lag 2 y embargo del 1 % (1 día),
    las posiciones 48-49 y 60-66 deben desaparecer del entrenamiento."""
    index = idx(100)
    splits = v.cpcv_splits(index, max_lookback=7, n_groups=10, n_test_groups=2, embargo_pct=0.01)
    # Se elige (0, 5): el grupo 0 está lejos y no solapa su purgado con el 5.
    s = next(x for x in splits if x.test_groups == (0, 5))

    pos = {ts: i for i, ts in enumerate(index)}
    train_pos = {pos[t] for t in s.train}

    assert 47 in train_pos                       # justo antes del purgado previo
    assert not ({48, 49} & train_pos)            # purgado previo (lag + h - 1 = 2)
    assert not (set(range(50, 60)) & train_pos)  # el propio bloque de test
    assert not (set(range(60, 68)) & train_pos)  # lookback 7 + embargo 1
    assert 68 in train_pos                       # ya limpio


def test_fraccion_purgada_crece_con_el_lookback():
    index = idx(2000)
    fracs = [
        v.purged_fraction(v.cpcv_splits(index, max_lookback=L), 2000)
        for L in (10, 50, 200)
    ]
    assert fracs[0] < fracs[1] < fracs[2]


def test_lookback_desmesurado_se_marca_inviable():
    index = idx(1000)
    splits = v.cpcv_splits(index, max_lookback=400)
    assert not v.is_feasible(splits, 1000)


def test_sma200_sigue_siendo_viable_en_el_train_real():
    """Comprobación de que la elección N=10 no ahoga a las estrategias lentas."""
    index = idx(1992)  # TRAIN de BTC
    splits = v.cpcv_splits(index, max_lookback=200)
    assert v.is_feasible(splits, 1992)
    assert v.purged_fraction(splits, 1992) < 0.25


def test_grupos_contiguos_y_ordenados():
    bounds = v.group_bounds(1000, 10)
    assert bounds[0][0] == 0 and bounds[-1][1] == 1000
    for (a, b), (c, d) in zip(bounds, bounds[1:]):
        assert b == c


def test_test_es_siempre_contiguo_por_grupo():
    splits = v.cpcv_splits(idx(1000), max_lookback=20)
    for s in splits:
        assert len(s.test) == len(set(s.test))
        assert s.test.is_monotonic_increasing


def test_rechaza_configuracion_absurda():
    with pytest.raises(ValueError):
        v.cpcv_splits(idx(1000), max_lookback=10, n_groups=1, n_test_groups=1)
    with pytest.raises(ValueError):
        v.cpcv_splits(idx(5), max_lookback=10, n_groups=10, n_test_groups=2)
