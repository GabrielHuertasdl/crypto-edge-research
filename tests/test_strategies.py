"""Universo de estrategias: contrato, causalidad y honestidad de las declaraciones.

Ninguna estrategia se evalúa aquí. Estos tests comprueban que **generan señales
válidas y causales**; el rendimiento es la fase 4 y pasa por `trial_registry`.
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src import config, strategies as sg  # noqa: E402

TODAS = [(s, p) for s in sg.UNIVERSE for p in s.grid()]
IDS = [f"{s.name}-{'_'.join(f'{k}{v}' for k, v in p.items())}" for s, p in TODAS]


@pytest.fixture(scope="module")
def precios():
    """Serie sintética con tendencia, reversión y volatilidad cambiante, para que
    todas las familias tengan algo a lo que reaccionar."""
    rng = np.random.default_rng(config.SEED)
    n = 900
    vol = np.repeat(rng.choice([0.01, 0.04], size=n // 30), 30)[:n]
    deriva = np.concatenate([np.full(n // 2, 0.002), np.full(n - n // 2, -0.001)])
    r = rng.normal(deriva, vol)
    c = pd.Series(
        100 * np.cumprod(1 + r),
        index=pd.date_range("2016-01-01", periods=n, freq="D", tz="UTC"),
    )
    return pd.DataFrame(
        {
            "open": c.shift(1).fillna(c.iloc[0]),
            "high": c * (1 + np.abs(rng.normal(0, 0.01, n))),
            "low": c * (1 - np.abs(rng.normal(0, 0.01, n))),
            "close": c,
            "volume": rng.lognormal(10, 0.5, n),
        },
        index=c.index,
    )


# ---------------------------------------------------------------------------
# Composición del universo
# ---------------------------------------------------------------------------
def test_tamano_del_universo():
    assert 15 <= len(sg.UNIVERSE) <= 25


def test_nombres_unicos():
    nombres = [s.name for s in sg.UNIVERSE]
    assert len(nombres) == len(set(nombres))


def test_hay_varias_familias_representadas():
    fams = sg.by_family()
    assert {"tendencia", "reversion", "volatilidad"} <= set(fams)
    assert all(len(v) >= 2 for v in fams.values())


def test_la_tesis_es_requisito_de_entrada():
    """Solo se admiten estrategias sin tesis si están declaradas de antemano como
    control. Si aparece una nueva SIN TESIS sin declararla, esto falla."""
    controles_declarados = {"turn_of_month"}
    assert set(sg.without_thesis()) == controles_declarados


def test_las_tesis_dicen_quien_paga():
    """No vale un párrafo genérico: la tesis tiene que nombrar la contraparte."""
    for s in sg.UNIVERSE:
        if not s.has_thesis:
            continue
        assert "Quién te paga" in s.thesis, f"{s.name}: la tesis no dice quién paga"
        assert len(s.thesis) > 200, f"{s.name}: tesis demasiado corta para ser una tesis"


def test_las_tesis_declaran_su_riesgo():
    """Al menos las familias principales deben declarar en qué se pueden estar
    equivocando."""
    familias = {s.family for s in sg.UNIVERSE if s.has_thesis}
    for fam in familias - {"regimen"}:
        textos = [s.thesis for s in sg.UNIVERSE if s.family == fam and s.has_thesis]
        assert any("Riesgo declarado" in t or "declarada como tal" in t for t in textos), fam


def test_numero_de_configuraciones_es_manejable():
    """Cada configuración es un trial y entra en el DSR. Un universo de 10.000
    configuraciones hunde el DSR de cualquier ganadora."""
    assert 100 <= sg.total_configs() <= 400


# ---------------------------------------------------------------------------
# Contrato de la señal
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("spec,params", TODAS, ids=IDS)
def test_senal_respeta_el_contrato(spec, params, precios):
    s = spec.build(precios, params)
    assert s.index.equals(precios.index)
    assert not s.isna().any(), f"{spec.name}: la señal tiene NaN"
    assert float(s.min()) >= 0.0 and float(s.max()) <= 1.0


@pytest.mark.parametrize("spec,params", TODAS, ids=IDS)
def test_senal_es_causal(spec, params, precios):
    """Truncado: lo calculado hasta T no puede cambiar porque existan datos
    posteriores. Es el test que cazaría un `shift(-1)` escondido en una señal."""
    T = 700
    completa = spec.build(precios, params).iloc[:T]
    truncada = spec.build(precios.iloc[:T], params)
    pd.testing.assert_series_equal(completa, truncada, check_names=False, rtol=1e-12)


@pytest.mark.parametrize("spec,params", TODAS, ids=IDS)
def test_el_calentamiento_declarado_cubre_la_dependencia_real(spec, params, precios):
    """El test que sostiene E1.5.

    Se altera un precio `warmup` días antes y se comprueba que la señal de hoy no
    cambia. Si cambiara, el calentamiento declarado sería insuficiente y el bloque
    de test del CPCV arrancaría con estado heredado del entrenamiento — que es
    justo la fuga que el calentamiento existe para cortar.

    No se exige coincidencia perfecta: las medias exponenciales tienen memoria
    infinita (decae, pero nunca es cero) y una máquina de estados puede arrastrar
    una posición mucho tiempo. Se exige que el efecto sea residual.
    """
    if spec.family == "calendario":
        pytest.skip("las de calendario no dependen del precio")

    w = spec.warmup_for(params)
    base = spec.build(precios, params)

    alterado = precios.copy()
    pos = len(precios) - w - 60
    if pos <= spec.lookback(params):
        pytest.skip("serie de prueba demasiado corta para este calentamiento")
    for col in ("open", "high", "low", "close"):
        alterado.iloc[pos, alterado.columns.get_loc(col)] *= 1.25

    otra = spec.build(alterado, params)
    cola = slice(pos + w, None)
    # Con tolerancia: las medias móviles de pandas usan sumas acumuladas, así que
    # una perturbación lejana deja diferencias a nivel de bit que no son
    # dependencia real. Lo que se persigue es un cambio de exposición de verdad.
    difieren = float(
        (~np.isclose(base.iloc[cola], otra.iloc[cola], rtol=1e-6, atol=1e-9)).mean()
    )
    assert difieren <= 0.05, (
        f"{spec.name}: alterar un precio {w} días antes cambia el "
        f"{difieren:.0%} de las señales posteriores; el calentamiento declarado "
        "se queda corto"
    )


@pytest.mark.parametrize("spec", sg.UNIVERSE, ids=[s.name for s in sg.UNIVERSE])
def test_calentamiento_nunca_es_menor_que_el_lookback(spec):
    for p in spec.grid():
        assert spec.warmup_for(p) >= spec.lookback(p)


@pytest.mark.parametrize("spec", sg.UNIVERSE, ids=[s.name for s in sg.UNIVERSE])
def test_las_estrategias_con_estado_declaran_calentamiento_mayor(spec):
    """Una ruptura mantiene posición mucho más que su ventana. Si su calentamiento
    igualara al lookback, el bloque de test heredaría estado del entrenamiento."""
    con_estado = {
        "donchian_breakout", "donchian_atr_stop", "breakout_volume_confirmed",
        "rsi_oversold", "bollinger_reversion", "zscore_reversion",
        "rsi_reversion_in_uptrend", "donchian_vol_targeted", "momentum_with_dd_stop",
        "vol_expansion_breakout",
    }
    if spec.name not in con_estado:
        pytest.skip("sin estado")
    for p in spec.grid():
        assert spec.warmup_for(p) >= 2 * spec.lookback(p), spec.name


# ---------------------------------------------------------------------------
# Promoción a validación fuera de cripto (E2.4)
# ---------------------------------------------------------------------------
def test_hay_estrategias_que_exigen_datos_externos():
    marcadas = {
        s.name for s in sg.UNIVERSE for p in s.grid() if s.needs_external_validation(p)
    }
    assert marcadas, "ninguna estrategia dispara la validación externa: revisa el umbral"
    assert "trend_with_vol_filter" in marcadas


def test_el_criterio_de_promocion_usa_lookback_o_calentamiento():
    spec = sg.get("price_vs_sma")
    assert not spec.needs_external_validation({"n": 20})
    assert spec.needs_external_validation({"n": 200})


def test_las_de_calendario_no_exigen_datos_externos():
    for s in sg.UNIVERSE:
        if s.family != "calendario":
            continue
        assert not any(s.needs_external_validation(p) for p in s.grid())


# ---------------------------------------------------------------------------
# Rejilla
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("spec", sg.UNIVERSE, ids=[s.name for s in sg.UNIVERSE])
def test_la_rejilla_coincide_con_el_conteo(spec):
    assert len(list(spec.grid())) == spec.n_configs()
    assert spec.n_configs() >= 2


def test_get_y_errores():
    assert sg.get("sma_cross").name == "sma_cross"
    with pytest.raises(KeyError):
        sg.get("no_existe")


def test_build_rechaza_exposicion_invalida(precios):
    mala = sg.StrategySpec(
        "mala", lambda df: pd.Series(2.0, index=df.index), {"x": [1, 2]},
        lookback=lambda p: 1, thesis="Quién te paga: nadie. " + "x" * 200,
    )
    with pytest.raises(ValueError, match="fuera de"):
        mala.build(precios, {})
