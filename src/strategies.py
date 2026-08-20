"""Fase 3 — Universo de estrategias (15-25 clásicas).

Cada estrategia declara:
  - `name`
  - `params` (rejilla a optimizar SOLO en TRAIN)
  - `thesis`: la razón económica por la que debería funcionar — quién te paga y
    por qué. Si no se sabe escribir: `thesis = None` y aparece como SIN TESIS en
    el informe.

Una estrategia es una función pura `(df, **params) -> Series` de señales en {0,1}
con la misma longitud e índice que `df`. No conoce costes ni ejecución: de eso se
encarga `backtest.py`.
"""

from __future__ import annotations

raise NotImplementedError("Fase 3 — pendiente")
