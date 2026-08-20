"""Convención horaria (regla 6-bis).

Todo en UTC, frontera de vela a 00:00, y **ambas fuentes comparten convención**.
Si Coinbase y yfinance estuvieran desfasadas un día, un backtest construido con
una y validado con la otra tendría lookahead de 24 h sin que nada fallara.
"""

import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src import config, data_loader as dl  # noqa: E402

ASSETS = config.ASSETS


def _cached(asset: str, source: str) -> pd.DataFrame:
    path = dl._raw_path(asset, source)
    if not path.exists():
        pytest.skip(f"Falta caché {path.name}: ejecuta `python -m src.data_loader`")
    return dl._read_cached(path)


@pytest.mark.parametrize("asset", ASSETS)
@pytest.mark.parametrize("source", ["coinbase", "yfinance"])
def test_indice_utc_medianoche(asset, source):
    idx = _cached(asset, source).index
    assert str(idx.tz) == "UTC", f"{asset}/{source}: índice no está en UTC"
    assert (idx.hour == 0).all() and (idx.minute == 0).all() and (idx.second == 0).all(), (
        f"{asset}/{source}: hay velas fuera de la frontera 00:00 UTC"
    )


@pytest.mark.parametrize("asset", ASSETS)
@pytest.mark.parametrize("source", ["coinbase", "yfinance"])
def test_indice_unico_y_ordenado(asset, source):
    idx = _cached(asset, source).index
    assert idx.is_monotonic_increasing
    assert not idx.has_duplicates


@pytest.mark.parametrize("asset", ASSETS)
def test_ambas_fuentes_misma_convencion(asset):
    """La alineación sin desplazar debe ser claramente mejor que ±1 día.

    Si las dos fuentes usaran fronteras de vela distintas, el cierre de Coinbase
    del día t se parecería más al de yfinance de t-1 o t+1 que al de t. Se compara
    la mediana de la discrepancia relativa en los tres desplazamientos.
    """
    cb = _cached(asset, "coinbase")["close"]
    yf = _cached(asset, "yfinance")["close"]

    def median_rel_diff(shift: int) -> float:
        j = pd.DataFrame({"c": cb, "y": yf.shift(shift)}).dropna()
        return float(((j["c"] - j["y"]).abs() / j["y"]).median())

    aligned, back, fwd = median_rel_diff(0), median_rel_diff(-1), median_rel_diff(1)
    assert aligned < 0.005, f"{asset}: fuentes alineadas difieren {aligned:.2%} en mediana"
    assert aligned * 3 < min(back, fwd), (
        f"{asset}: la alineación a 0 días ({aligned:.3%}) no es claramente mejor que "
        f"-1d ({back:.3%}) / +1d ({fwd:.3%}). Sospecha de desfase de convención."
    )
