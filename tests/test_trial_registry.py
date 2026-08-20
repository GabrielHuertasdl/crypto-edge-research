"""El registro de intentos alimenta el DSR. Si miente, C5 es decorativo."""

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.trial_registry import TrialRegistry  # noqa: E402


@pytest.fixture
def reg(tmp_path):
    return TrialRegistry(tmp_path / "trials.csv")


def test_registra_y_persiste_al_instante(reg):
    """Un proceso que muere a mitad debe dejar en disco lo que ya había probado."""
    reg.log("sma", {"n": 20}, "BTC", "train", {"sharpe": 1.1})
    otro = TrialRegistry(reg.path)          # relee desde cero, sin estado en memoria
    assert otro.n_trials() == 1


def test_cuenta_descartes_y_exploraciones(reg):
    reg.log("sma", {"n": 10}, "BTC", "train", {"sharpe": 0.2}, outcome="discarded")
    reg.log("sma", {"n": 20}, "BTC", "train", {"sharpe": 1.4}, outcome="kept")
    reg.log("rsi", {"n": 14}, "BTC", "train", {"sharpe": 0.1}, outcome="exploration")
    reg.log("bb", {"n": 20}, "BTC", "train", None, outcome="error", notes="crash")
    assert reg.n_trials() == 4
    assert reg.summary()["by_outcome"] == {
        "discarded": 1, "kept": 1, "exploration": 1, "error": 1
    }


def test_repeticiones_se_registran_pero_no_inflan_N(reg):
    for _ in range(3):
        reg.log("sma", {"n": 20}, "BTC", "train", {"sharpe": 1.1})
    assert reg.n_trials() == 3           # cuenta honesta de evaluaciones
    assert reg.n_unique_trials() == 1    # N que entra en el DSR
    assert reg.summary()["n_repeats"] == 2


def test_configuraciones_distintas_son_trials_distintos(reg):
    reg.log("sma", {"n": 20}, "BTC", "train", {"sharpe": 1.0})
    reg.log("sma", {"n": 21}, "BTC", "train", {"sharpe": 1.0})   # parámetro
    reg.log("sma", {"n": 20}, "ETH", "train", {"sharpe": 1.0})   # activo
    reg.log("sma", {"n": 20}, "BTC", "validation", {"sharpe": 1.0})  # split
    reg.log("sma", {"n": 20}, "BTC", "train", {"sharpe": 1.0}, lag=1)  # lag
    assert reg.n_unique_trials() == 5


def test_hash_estable_frente_al_orden_de_los_parametros(reg):
    a = reg.config_hash("sma", {"a": 1, "b": 2}, "BTC", "train", 2)
    b = reg.config_hash("sma", {"b": 2, "a": 1}, "BTC", "train", 2)
    assert a == b


def test_varianza_de_sharpes_para_el_dsr(reg):
    for i, s in enumerate([0.0, 1.0, 2.0]):
        reg.log("s", {"n": i}, "BTC", "train", {"sharpe": s})
    assert reg.n_unique_trials() == 3
    assert abs(reg.sharpe_variance() - 1.0) < 1e-9


def test_varianza_ignora_repeticiones(reg):
    reg.log("s", {"n": 1}, "BTC", "train", {"sharpe": 0.0})
    reg.log("s", {"n": 2}, "BTC", "train", {"sharpe": 2.0})
    for _ in range(20):
        reg.log("s", {"n": 1}, "BTC", "train", {"sharpe": 0.0})
    assert abs(reg.sharpe_variance() - 2.0) < 1e-9


def test_filtra_por_split(reg):
    reg.log("s", {"n": 1}, "BTC", "train", {"sharpe": 1.0})
    reg.log("s", {"n": 1}, "BTC", "validation", {"sharpe": 0.5})
    assert reg.n_unique_trials("train") == 1
    assert reg.n_unique_trials("validation") == 1
    assert len(reg.sharpes("train")) == 1


def test_entradas_sin_sharpe_no_rompen_la_varianza(reg):
    reg.log("s", {"n": 1}, "BTC", "train", None, outcome="error")
    reg.log("s", {"n": 2}, "BTC", "train", {"sharpe": 1.0})
    reg.log("s", {"n": 3}, "BTC", "train", {"sharpe": 3.0})
    assert reg.n_trials() == 3
    assert len(reg.sharpes()) == 2
    assert abs(reg.sharpe_variance() - 2.0) < 1e-9


def test_outcome_invalido_se_rechaza(reg):
    with pytest.raises(ValueError):
        reg.log("s", {"n": 1}, "BTC", "train", {"sharpe": 1.0}, outcome="genial")


def test_no_hay_api_para_borrar():
    """Append-only por diseño: si aparece un método de borrado, alguien podrá
    'limpiar' los intentos fallidos y el DSR dejará de significar nada."""
    prohibidos = {"delete", "remove", "clear", "drop", "reset", "truncate", "purge"}
    assert not prohibidos & {m for m in dir(TrialRegistry) if not m.startswith("_")}
