"""Bootstrap, intervalos de confianza, DSR y PBO."""

import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src import config, statistics as st  # noqa: E402


@pytest.fixture(scope="module")
def rng():
    return np.random.default_rng(config.SEED)


# ---------------------------------------------------------------------------
# Bootstrap por bloques
# ---------------------------------------------------------------------------
def test_bootstrap_forma_y_reproducibilidad(rng):
    x = rng.normal(0, 0.02, 500)
    a = st.stationary_block_bootstrap(x, n_paths=50, seed=1)
    b = st.stationary_block_bootstrap(x, n_paths=50, seed=1)
    assert a.shape == (50, 500)
    np.testing.assert_array_equal(a, b)


def test_bootstrap_solo_reordena_valores_existentes(rng):
    x = rng.normal(0, 0.02, 300)
    p = st.stationary_block_bootstrap(x, n_paths=20, seed=2)
    assert set(np.unique(p)).issubset(set(np.unique(x)))


def test_bootstrap_conserva_la_distribucion_marginal(rng):
    """Colas gruesas incluidas: es justo lo que un paseo aleatorio gaussiano
    destruiría."""
    x = rng.standard_t(df=3, size=2000) * 0.01
    p = st.stationary_block_bootstrap(x, n_paths=200, seed=3)
    assert abs(p.mean() - x.mean()) < 0.1 * x.std()
    assert abs(p.std() / x.std() - 1.0) < 0.15
    curt_orig = float(((x - x.mean()) ** 4).mean() / x.var() ** 2)
    curt_boot = float(((p - p.mean()) ** 4).mean() / p.var() ** 2)
    assert curt_boot > 5.0 and abs(curt_boot / curt_orig - 1.0) < 0.5


def test_bootstrap_conserva_agrupamiento_de_volatilidad():
    """Serie con volatilidad por rachas: la autocorrelación de |r| debe
    sobrevivir al remuestreo por bloques. Con bloques de 1 día se destruye."""
    rng = np.random.default_rng(11)
    vol = np.repeat(rng.choice([0.005, 0.05], size=100), 40)
    x = rng.normal(0, 1, 4000) * vol

    def autocorr_abs(s):
        a = np.abs(s) - np.abs(s).mean()
        return float((a[:-1] * a[1:]).mean() / a.var())

    orig = autocorr_abs(x)
    bloques = autocorr_abs(st.stationary_block_bootstrap(x, n_paths=1, mean_block=20, seed=4)[0])
    iid = autocorr_abs(st.stationary_block_bootstrap(x, n_paths=1, mean_block=1, seed=4)[0])
    assert orig > 0.15
    assert bloques > 0.5 * orig
    assert iid < 0.3 * orig


# ---------------------------------------------------------------------------
# Intervalos de confianza
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("T,esperado", [(1992, 0.428), (1095, 0.577), (963, 0.616), (398, 0.958)])
def test_error_estandar_coincide_con_sqrt_periodos_entre_T(T, esperado):
    """Regla de bolsillo SE ≈ sqrt(365/T), que es de donde salen los 0,43 / 0,58 /
    0,62 / 0,96 de TRAIN, VALIDATION, LOCKBOX y un bloque CPCV."""
    rng = np.random.default_rng(5)
    r = rng.normal(0.0, 0.02, T)
    assert abs(st.sharpe_standard_error(r) - esperado) < 0.12 * esperado


def test_ic_de_ruido_incluye_cero(rng):
    r = rng.normal(0.0, 0.02, 1095)
    ci = st.sharpe_confidence_interval(r, n_paths=400, seed=6)
    assert ci.includes_zero
    assert ci.lo < ci.point < ci.hi


def test_ic_de_senal_fuerte_excluye_cero():
    rng = np.random.default_rng(7)
    r = rng.normal(0.004, 0.02, 1095)   # Sharpe anualizado ~3.8
    ci = st.sharpe_confidence_interval(r, n_paths=400, seed=7)
    assert not ci.includes_zero
    assert ci.lo > 1.0


def test_ic_se_estrecha_con_mas_datos():
    rng = np.random.default_rng(8)
    r = rng.normal(0.001, 0.02, 4000)
    corto = st.sharpe_confidence_interval(r[:500], n_paths=300, seed=8)
    largo = st.sharpe_confidence_interval(r, n_paths=300, seed=8)
    assert (largo.hi - largo.lo) < (corto.hi - corto.lo)


def test_sharpe_de_050_en_lockbox_no_es_concluyente():
    """El caso concreto del pre-registro: con 963 días, un Sharpe de 0,50 trae un
    IC que incluye el cero. El veredicto correcto es 'no concluyente'."""
    rng = np.random.default_rng(9)
    r = rng.normal(0.0, 0.02, 963)
    r = r - r.mean() + 0.50 * r.std(ddof=1) / np.sqrt(365)   # forzar SR anual = 0,50
    ci = st.sharpe_confidence_interval(r, n_paths=600, seed=9)
    assert abs(ci.point - 0.50) < 0.02
    assert ci.includes_zero, f"IC = [{ci.lo:.2f}, {ci.hi:.2f}]"


# ---------------------------------------------------------------------------
# Deflated Sharpe
# ---------------------------------------------------------------------------
def test_umbral_del_mejor_de_n_crece_con_n():
    v = st.annualized_sr_variance_to_periodic(0.4)
    valores = [st.expected_max_sharpe(v, n) for n in (1, 10, 100, 1000)]
    assert valores[0] == 0.0
    assert valores[1] < valores[2] < valores[3]


def test_dsr_castiga_probar_muchas_configuraciones():
    """Los MISMOS retornos dan un DSR alto si se probó una configuración y bajo si
    se probaron mil. Ese es todo el punto del ajuste."""
    rng = np.random.default_rng(10)
    r = rng.normal(0.0015, 0.02, 1095)
    v = st.annualized_sr_variance_to_periodic(0.5)
    pocos = st.deflated_sharpe_ratio(r, n_trials=1, sr_variance=v)
    muchos = st.deflated_sharpe_ratio(r, n_trials=5000, sr_variance=v)
    assert pocos > muchos
    assert 0.0 <= muchos <= pocos <= 1.0


def test_dsr_de_ruido_es_bajo():
    rng = np.random.default_rng(12)
    r = rng.normal(0.0, 0.02, 1095)
    v = st.annualized_sr_variance_to_periodic(0.4)
    assert st.deflated_sharpe_ratio(r, n_trials=200, sr_variance=v) < 0.60


def test_dsr_en_rango_probabilidad():
    rng = np.random.default_rng(13)
    for mu in (-0.002, 0.0, 0.003):
        r = rng.normal(mu, 0.02, 1000)
        d = st.deflated_sharpe_ratio(r, 100, st.annualized_sr_variance_to_periodic(0.3))
        assert 0.0 <= d <= 1.0


# ---------------------------------------------------------------------------
# PBO
# ---------------------------------------------------------------------------
def test_pbo_baja_cuando_hay_una_configuracion_genuinamente_buena():
    rng = np.random.default_rng(14)
    M = rng.normal(0, 0.02, (1200, 40))
    ruido = st.probability_of_backtest_overfitting(M, n_blocks=10)
    M[:, 0] += 0.005
    con_senal = st.probability_of_backtest_overfitting(M, n_blocks=10)
    assert con_senal.pbo < ruido.pbo
    assert con_senal.pbo < 0.20


def test_pbo_en_rango_y_cuenta_particiones():
    from math import comb

    rng = np.random.default_rng(15)
    M = rng.normal(0, 0.02, (800, 20))
    res = st.probability_of_backtest_overfitting(M, n_blocks=8)
    assert 0.0 <= res.pbo <= 1.0
    assert res.n_combinations == comb(8, 4)
    assert res.n_configs == 20


def test_pbo_rechaza_configuraciones_absurdas():
    rng = np.random.default_rng(16)
    with pytest.raises(ValueError):
        st.probability_of_backtest_overfitting(rng.normal(0, 1, (100, 1)), n_blocks=8)
    with pytest.raises(ValueError):
        st.probability_of_backtest_overfitting(rng.normal(0, 1, (100, 5)), n_blocks=7)
    with pytest.raises(ValueError):
        st.probability_of_backtest_overfitting(rng.normal(0, 1, (10, 5)), n_blocks=8)
