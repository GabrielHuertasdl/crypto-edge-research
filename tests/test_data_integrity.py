"""Integridad de la serie de ejecución y corrección de los splits (regla 1)."""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src import config, data_loader as dl  # noqa: E402


def _proc(asset: str) -> pd.DataFrame:
    path = dl._processed_path(asset)
    if not path.exists():
        pytest.skip(f"Falta {path.name}: ejecuta `python -m src.data_loader`")
    return dl._read_cached(path)


@pytest.mark.parametrize("asset", config.ASSETS)
def test_serie_procesada_sin_huecos_ni_velas_planas(asset):
    df = _proc(asset)
    full = pd.date_range(df.index[0], df.index[-1], freq="D", tz="UTC")
    assert len(full.difference(df.index)) == 0, f"{asset}: huecos de calendario"
    flat = (df["open"] == df["high"]) & (df["high"] == df["low"]) & (df["low"] == df["close"])
    assert not flat.any(), f"{asset}: velas planas O=H=L=C"


@pytest.mark.parametrize("asset", config.ASSETS)
def test_coherencia_ohlc(asset):
    df = _proc(asset)
    assert (df[["open", "high", "low", "close"]] > 0).all().all()
    assert (df["high"] >= df[["open", "close"]].max(axis=1)).all()
    assert (df["low"] <= df[["open", "close"]].min(axis=1)).all()
    assert (df["high"] >= df["low"]).all()
    assert (df["volume"] >= 0).all()


@pytest.mark.parametrize("asset", config.ASSETS)
def test_splits_disjuntos_y_ordenados(asset):
    df = _proc(asset)
    tr, va, lo = (dl.split(df, k) for k in ("train", "validation", "lockbox"))
    assert len(tr.index.intersection(va.index)) == 0
    assert len(va.index.intersection(lo.index)) == 0
    assert len(tr.index.intersection(lo.index)) == 0
    for part in (tr, va, lo):
        if len(part):
            assert part.index.isin(df.index).all()
    # Ninguna fecha de VALIDATION o LOCKBOX puede colarse antes de su frontera.
    if len(va):
        assert va.index[0] >= pd.Timestamp(config.SPLITS["validation"][0], tz="UTC")
    if len(lo):
        assert lo.index[0] >= pd.Timestamp(config.SPLITS["lockbox"][0], tz="UTC")


def test_split_rechaza_nombre_invalido():
    df = _proc("BTC")
    with pytest.raises(KeyError):
        dl.split(df, "todo")


@pytest.mark.parametrize("asset", config.OPTIMIZATION_ASSETS)
def test_activos_de_optimizacion_tienen_train_suficiente(asset):
    """Si un activo de optimización no llega a 3 años de TRAIN, no se puede
    ajustar nada con él y hay que degradarlo a test cross-asset."""
    assert len(dl.split(_proc(asset), "train")) > 3 * 365


def test_sol_no_tiene_train_y_por_eso_no_se_optimiza():
    """Coinbase lista SOL en 2021-06: TRAIN está vacío. Es exactamente el motivo
    por el que SOL vive en CROSS_ASSET_TEST_ASSETS."""
    assert "SOL" in config.CROSS_ASSET_TEST_ASSETS
    assert len(dl.split(_proc("SOL"), "train")) == 0


@pytest.mark.parametrize("asset", config.ASSETS)
def test_sin_retornos_absurdos(asset):
    """Un retorno diario > 100 % o < -90 % en cripto existe, pero uno > 1000 %
    es un error de datos, no un mercado."""
    r = _proc(asset)["close"].pct_change().dropna()
    assert r.max() < 10.0, f"{asset}: retorno diario de {r.max():.0%}"
    assert r.min() > -0.95, f"{asset}: retorno diario de {r.min():.0%}"
