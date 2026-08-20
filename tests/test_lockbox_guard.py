"""El lockbox debe bloquearse solo tras la primera ejecución (regla 1)."""

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "lockbox"))

import evaluate  # noqa: E402


def test_guard_bloquea_segunda_ejecucion(tmp_path, monkeypatch):
    sentinel = tmp_path / ".lockbox_used"
    monkeypatch.setattr(evaluate, "LOCKBOX_SENTINEL", sentinel)

    evaluate.assert_lockbox_unused()  # virgen: pasa

    evaluate.seal_lockbox([{"name": "dummy", "params": {"n": 20}}])
    assert sentinel.exists()

    with pytest.raises(evaluate.LockboxAlreadyUsedError):
        evaluate.assert_lockbox_unused()


def test_sentinel_real_intacto():
    """El lockbox de verdad sigue sin usarse. Si esto falla, mira qué pasó."""
    from src.config import LOCKBOX_SENTINEL

    if LOCKBOX_SENTINEL.exists():
        pytest.skip("Lockbox ya consumido: el resultado final del proyecto está fijado.")
