"""Fase 3 — Universo de estrategias (15-25 clásicas).

Este módulo define el **contrato**. El universo llega en la fase 3.

Cada estrategia es un `StrategySpec`. Una estrategia es una función pura
`(df, **params) -> Series` de exposición en [0, 1] con el mismo índice que `df`.
No conoce costes, ni retardo, ni splits: de eso se encarga `backtest.py`. Una
estrategia que desplaza por su cuenta desplaza dos veces.

Campos obligatorios y por qué:

  - `thesis`: la razón económica por la que debería funcionar — **quién te paga y
    por qué**. Si no se sabe escribir: `thesis = None`, y aparece como SIN TESIS
    en el informe. Ese campo pesa tanto como el Sharpe.
  - `lookback(params)`: la ventana más larga que consulta la señal. Alimenta el
    purgado del CPCV. Si miente por lo bajo, hay fuga entre pliegues.
  - `warmup(params)`: los días que la estrategia necesita para reconstruir su
    ESTADO al entrar en un bloque de test, que **no** es lo mismo que su lookback.
    Una ruptura de Donchian de 55 días puede mantener una posición seis meses: su
    lookback es 55 y su calentamiento debe cubrir la duración típica de la
    posición. Declararlo corto equivale a heredar del entrenamiento la posición
    con la que arranca el test.

Prioridad de familias en la fase 3 (por D2, pocos ciclos independientes): se
prefieren las que generan muchas observaciones cuasi-independientes —horizontes
cortos, más operaciones— frente a las que dependen de un puñado de tendencias
largas. Con ~3 ciclos disponibles, una estrategia de 20 operaciones no es
evaluable: no llega ni al mínimo pre-registrado de C4.
"""

from __future__ import annotations

import sys
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from itertools import product
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src import config


@dataclass(frozen=True)
class StrategySpec:
    name: str
    signal: Callable[..., pd.Series]
    param_grid: dict[str, list]
    lookback: Callable[[dict], int]
    thesis: str | None
    warmup: Callable[[dict], int] | None = None
    family: str = "sin clasificar"
    notes: str = ""

    @property
    def has_thesis(self) -> bool:
        return bool(self.thesis and self.thesis.strip())

    def warmup_for(self, params: dict) -> int:
        """Por defecto el calentamiento iguala al lookback. Toda estrategia que
        mantenga posición más allá de su ventana DEBE declarar más."""
        if self.warmup is None:
            return int(self.lookback(params))
        return int(max(self.warmup(params), self.lookback(params)))

    def grid(self) -> Iterator[dict]:
        """Todas las combinaciones de la rejilla. Cada una es un trial y se
        registra en `trial_registry`, se conserve o se descarte."""
        claves = list(self.param_grid)
        for valores in product(*(self.param_grid[k] for k in claves)):
            yield dict(zip(claves, valores))

    def n_configs(self) -> int:
        n = 1
        for v in self.param_grid.values():
            n *= len(v)
        return n

    def build(self, df: pd.DataFrame, params: dict) -> pd.Series:
        """Genera la señal y comprueba el contrato antes de que llegue al motor."""
        s = self.signal(df, **params)
        if not isinstance(s, pd.Series) or not s.index.equals(df.index):
            raise ValueError(f"{self.name}: la señal debe compartir índice con df")
        finita = s.dropna()
        if len(finita) and (finita.min() < config.MIN_POSITION or finita.max() > config.MAX_POSITION):
            raise ValueError(
                f"{self.name}: exposición fuera de [0, 1] "
                f"(min={finita.min()}, max={finita.max()})"
            )
        return s


UNIVERSE: list[StrategySpec] = field(default_factory=list) if False else []
"""El universo de la fase 3 se registra aquí. Vacío a propósito hasta entonces."""


def total_configs() -> int:
    """Configuraciones que el universo va a generar. Cota inferior del número de
    trials del proyecto: las exploraciones descartadas suman por encima."""
    return sum(s.n_configs() for s in UNIVERSE)


def without_thesis() -> list[str]:
    """Estrategias marcadas SIN TESIS. Va tal cual al informe."""
    return [s.name for s in UNIVERSE if not s.has_thesis]
