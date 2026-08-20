"""
================================================================================
  ⚠  LOCKBOX — EVALUACIÓN FINAL. SE EJECUTA UNA SOLA VEZ EN TODO EL PROYECTO.  ⚠
================================================================================

Este módulo evalúa las finalistas sobre 2024 → hoy: datos que NO se han mirado en
ninguna fase anterior.

NO IMPORTES NADA DE AQUÍ desde `src/`. La dependencia va en un solo sentido:
lockbox → src, nunca al revés.

Reglas:
  1. Solo se ejecuta cuando hay entre 1 y 3 finalistas ya cerradas, con sus
     parámetros congelados por escrito.
  2. Se ejecuta UNA VEZ. El resultado que salga es el resultado final del proyecto.
  3. Si después de verlo se reajusta la estrategia y se vuelve a ejecutar, la
     prueba queda contaminada y el proyecto entero deja de valer. No hay forma de
     "descontaminarlo" salvo esperar a que exista un tramo nuevo de datos.
  4. Nada de este módulo se usa para seleccionar, filtrar ni ordenar estrategias.
     El lockbox mide, no elige.

El fichero centinela `lockbox/.lockbox_used` registra la ejecución (fecha,
finalistas y hash de sus parámetros). Si existe, `run_final_evaluation()` aborta.
Borrarlo a mano para "volver a probar" es exactamente la trampa que la regla 3
prohíbe: si alguien lo hace, tiene que constar en el informe.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.config import LOCKBOX_SENTINEL  # noqa: E402


class LockboxAlreadyUsedError(RuntimeError):
    """El lockbox ya se consumió. Ese resultado es final; no hay segunda tirada."""


def assert_lockbox_unused() -> None:
    """Aborta si el lockbox ya se ha ejecutado alguna vez."""
    if LOCKBOX_SENTINEL.exists():
        record = LOCKBOX_SENTINEL.read_text(encoding="utf-8")
        raise LockboxAlreadyUsedError(
            "El lockbox ya fue consumido. Registro de la única ejecución válida:\n"
            f"{record}\n"
            "Volver a ejecutarlo contamina la prueba fuera de muestra. "
            "El resultado final del proyecto es el de arriba."
        )


def seal_lockbox(finalists: list[dict]) -> None:
    """Escribe el centinela. Se llama justo ANTES de mirar ningún resultado,
    para que un fallo a mitad de la evaluación no permita una segunda pasada
    "porque la primera no llegó a terminar"."""
    record = {
        "sealed_at_utc": datetime.now(timezone.utc).isoformat(),
        "finalists": finalists,
    }
    LOCKBOX_SENTINEL.write_text(json.dumps(record, indent=2, ensure_ascii=False), encoding="utf-8")


def run_final_evaluation(finalists: list[dict]) -> None:
    """Fase 5 — pendiente. Al implementarla: `assert_lockbox_unused()` y
    `seal_lockbox()` van al principio, antes de cargar ningún precio de 2024+."""
    assert_lockbox_unused()
    raise NotImplementedError("Fase 5 — pendiente. No ejecutar hasta tener finalistas.")


if __name__ == "__main__":
    raise SystemExit(
        "El lockbox no se ejecuta a mano por accidente. "
        "Importa run_final_evaluation() desde el script de la fase 5."
    )
