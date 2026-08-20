"""Fase 2 — Motor de backtest vectorizado, long/flat, sin apalancamiento.

Reglas que impone el motor (no el usuario del motor):
  - posición ∈ {0, 1}; cualquier señal fuera de rango es un error, no se recorta
    en silencio
  - la señal de `t` se ejecuta al open de `t+1` (`config.EXECUTION_LAG_DAYS`)
  - costes de `config.COST_PER_TURN` aplicados sobre cada cambio de posición

Métricas devueltas: retorno total y anualizado, Sharpe, Sortino, máximo drawdown
y su duración, tasa de acierto, profit factor, número de operaciones y exposición
temporal.

No se confía en un solo número de este módulo hasta que `tests/test_backtest.py`
pase entero (posiciones sintéticas de resultado conocido a mano).
"""

from __future__ import annotations

raise NotImplementedError("Fase 2 — pendiente")
