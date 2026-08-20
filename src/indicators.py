"""Indicadores técnicos. TODOS causales (regla 2).

Prohibido en este módulo:
  - `center=True` en cualquier rolling
  - `shift(-n)` (desplazamiento hacia el pasado desde el futuro)
  - normalizar con estadísticos de la muestra completa (media/std globales)
  - `bfill()` / `interpolate` que arrastre valores futuros hacia atrás

Cada función devuelve una serie alineada al índice de entrada donde el valor en `t`
depende únicamente de datos disponibles al cierre de `t`.
"""

from __future__ import annotations

raise NotImplementedError("Fase 2 — pendiente")
