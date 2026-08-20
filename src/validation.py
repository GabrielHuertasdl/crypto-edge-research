"""Fase 4 — CPCV purgado, robustez y prueba de nulidad.

Implementado en fase 2 (adelantado): `cpcv_splits` y el cálculo de spans de
purgado, porque son aritmética de índices, se testean sin necesidad de
estrategias, y de ellos depende que la fase 4 no tenga fuga.

Pendiente de fase 4: sensibilidad paramétrica, estabilidad cross-asset, desglose
por subperiodos y `block_bootstrap_null`.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from itertools import combinations
from math import comb
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src import config


# ---------------------------------------------------------------------------
# Purgado: los spans se DERIVAN, no se fijan
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class PurgeSpans:
    """Días a eliminar del entrenamiento alrededor de cada bloque de test.

    Asimétrico, y el motivo importa:

    - **Después** del bloque de test se purgan `max_lookback` días. Una
      observación de entrenamiento en `t` construye sus features con la ventana
      `[t - L, t]`; si `t` está a menos de `L` días del final del bloque de test,
      esa ventana **contiene precios del test**. Con una SMA de 200 son 200 días
      de solape: purgar una constante de 20 no elimina nada.
    - **Antes** del bloque se purgan `lag + horizonte - 1` días, que es lo que
      tarda la etiqueta en materializarse: la observación en `t` cobra el retorno
      de `t + lag`, así que las últimas observaciones previas al test ya apuntan
      dentro de él.
    - El **embargo** se añade después del purgado posterior y cubre la
      autocorrelación residual que el solape mecánico no explica.
    """

    before: int
    after: int
    embargo: int

    @property
    def total_after(self) -> int:
        return self.after + self.embargo


def purge_spans(
    max_lookback: int,
    n_samples: int,
    label_horizon: int = 1,
    lag: int | None = None,
    embargo_pct: float | None = None,
) -> PurgeSpans:
    lag = config.OFFICIAL_LAG if lag is None else lag
    embargo_pct = config.CPCV_EMBARGO_PCT if embargo_pct is None else embargo_pct
    if max_lookback < 0 or label_horizon < 1:
        raise ValueError("max_lookback >= 0 y label_horizon >= 1")
    return PurgeSpans(
        before=lag + label_horizon - 1,
        after=int(max_lookback),
        embargo=int(np.ceil(embargo_pct * n_samples)),
    )


# ---------------------------------------------------------------------------
# Caminos: lo que se reporta
# ---------------------------------------------------------------------------
def n_paths(n_groups: int | None = None, n_test_groups: int | None = None) -> int:
    """Caminos de backtest completos = k·C(N,k)/N.

    NO es el número de combinaciones. Con N=10, k=2 hay 45 combinaciones pero
    9 caminos, y el PBO se estima sobre caminos. Reportar 45 triplica la sensación
    de evidencia.
    """
    N = config.CPCV_N_GROUPS if n_groups is None else n_groups
    k = config.CPCV_N_TEST_GROUPS if n_test_groups is None else n_test_groups
    return k * comb(N, k) // N


def cpcv_paths(
    n_groups: int | None = None, n_test_groups: int | None = None
) -> list[list[tuple[int, int]]]:
    """Reparte las combinaciones en caminos.

    Devuelve una lista de caminos; cada camino es una lista de `(combo, grupo)`
    que cubre **todos** los grupos exactamente una vez, así que concatenar sus
    predicciones reconstruye una curva de equity out-of-sample completa.
    """
    N = config.CPCV_N_GROUPS if n_groups is None else n_groups
    k = config.CPCV_N_TEST_GROUPS if n_test_groups is None else n_test_groups
    combos = list(combinations(range(N), k))

    apariciones: dict[int, list[int]] = {g: [] for g in range(N)}
    for ci, combo in enumerate(combos):
        for g in combo:
            apariciones[g].append(ci)

    n = n_paths(N, k)
    return [[(apariciones[g][j], g) for g in range(N)] for j in range(n)]


# ---------------------------------------------------------------------------
# Splits
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class TestBlock:
    """Un tramo contiguo de test con su calentamiento delante.

    El calentamiento existe porque el purgado por lookback NO basta para las
    estrategias con estado. Una ruptura de Donchian abre posición y la mantiene
    meses: mucho más que su ventana de 55 días. Si el bloque de test empieza con
    la posición heredada de lo que pasó en el entrenamiento, los primeros meses de
    ese bloque no miden la estrategia, miden el entrenamiento.

    Solución: al entrar en cada bloque el estado se reinicia a plano y se
    reconstruye usando **solo** los `warmup` días previos, que están purgados del
    entrenamiento precisamente para poder usarlos aquí. Se puntúa `test`, nunca
    `warmup`.
    """

    warmup: pd.DatetimeIndex
    test: pd.DatetimeIndex

    @property
    def full(self) -> pd.DatetimeIndex:
        return self.warmup.append(self.test)


@dataclass(frozen=True)
class CPCVSplit:
    combo: int
    test_groups: tuple[int, ...]
    train: pd.DatetimeIndex
    test: pd.DatetimeIndex
    n_purged: int
    blocks: tuple[TestBlock, ...] = ()


def group_bounds(n_samples: int, n_groups: int) -> list[tuple[int, int]]:
    """Bloques contiguos y casi iguales. Contiguos porque el orden temporal es la
    única estructura que aquí no se puede barajar."""
    edges = np.linspace(0, n_samples, n_groups + 1).astype(int)
    return [(int(edges[i]), int(edges[i + 1])) for i in range(n_groups)]


def cpcv_splits(
    index: pd.DatetimeIndex,
    max_lookback: int,
    n_groups: int | None = None,
    n_test_groups: int | None = None,
    label_horizon: int = 1,
    lag: int | None = None,
    embargo_pct: float | None = None,
    warmup: int | None = None,
) -> list[CPCVSplit]:
    """Combinatorial Purged Cross-Validation sobre un índice temporal.

    `max_lookback` es la ventana más larga que usa la estrategia. Se pasa por
    estrategia; no hay un valor por defecto a propósito.

    `warmup` es el estado que la estrategia necesita reconstruir al entrar en un
    bloque de test. Por defecto `max_lookback`, pero una estrategia con posiciones
    largas debe declarar más (ver `strategies.StrategySpec.warmup`). El purgado
    previo se amplía hasta cubrirlo: esos días alimentan el calentamiento del test
    y por tanto no pueden estar además en el entrenamiento.
    """
    N = config.CPCV_N_GROUPS if n_groups is None else n_groups
    k = config.CPCV_N_TEST_GROUPS if n_test_groups is None else n_test_groups
    n = len(index)
    if N < 2 or not (1 <= k < N):
        raise ValueError("hacen falta N >= 2 grupos y 1 <= k < N de test")
    if n < N:
        raise ValueError(f"{n} observaciones no dan para {N} grupos")

    warmup = int(max_lookback if warmup is None else warmup)
    spans = purge_spans(max_lookback, n, label_horizon, lag, embargo_pct)
    # El purgado previo cubre lo que sea mayor: el horizonte de la etiqueta o el
    # calentamiento que el bloque de test va a consumir.
    span_before = max(spans.before, warmup)
    bounds = group_bounds(n, N)
    positions = np.arange(n)

    splits: list[CPCVSplit] = []
    for ci, combo in enumerate(combinations(range(N), k)):
        test_mask = np.zeros(n, dtype=bool)
        for g in combo:
            lo, hi = bounds[g]
            test_mask[lo:hi] = True

        # Tramos contiguos de test: dos grupos adyacentes forman un solo bloque.
        padded = np.concatenate(([False], test_mask, [False]))
        inicios = np.flatnonzero(~padded[:-1] & padded[1:])
        finales = np.flatnonzero(padded[:-1] & ~padded[1:])

        excluded = test_mask.copy()
        blocks = []
        for lo, hi in zip(inicios, finales):
            w_lo = max(0, lo - warmup)
            # Si delante del bloque no hay `warmup` días (bloque pegado al inicio
            # de la muestra), el calentamiento se toma del propio bloque y esos
            # días NO se puntúan. Puntuarlos sería medir la estrategia mientras
            # sus indicadores todavía son NaN.
            falta = warmup - (lo - w_lo)
            t_lo = min(lo + falta, hi)
            excluded[max(0, lo - span_before):lo] = True
            excluded[hi:min(n, hi + spans.total_after)] = True
            blocks.append(TestBlock(warmup=index[w_lo:t_lo], test=index[t_lo:hi]))

        train = positions[~excluded]
        test = positions[test_mask]
        splits.append(
            CPCVSplit(
                combo=ci,
                test_groups=combo,
                train=index[train],
                test=index[test],
                n_purged=int(excluded.sum() - test_mask.sum()),
                blocks=tuple(blocks),
            )
        )
    return splits


def scored_fraction(splits: list[CPCVSplit], n_samples: int) -> float:
    """Fracción de la muestra que llega a puntuarse, ya descontado el
    calentamiento consumido dentro de los bloques pegados al inicio."""
    puntuados = [sum(len(b.test) for b in s.blocks) for s in splits]
    return float(np.mean(puntuados) / n_samples)


def purged_fraction(splits: list[CPCVSplit], n_samples: int) -> float:
    """Fracción media de la muestra que se pierde por purgado + embargo.

    Si supera `config.CPCV_MAX_PURGED_FRACTION`, la combinación
    (lookback, N grupos) es inviable: no queda entrenamiento suficiente y el
    resultado hay que marcarlo en el informe en vez de publicarlo.
    """
    return float(np.mean([s.n_purged for s in splits]) / n_samples)


def is_feasible(splits: list[CPCVSplit], n_samples: int) -> bool:
    return purged_fraction(splits, n_samples) <= config.CPCV_MAX_PURGED_FRACTION


# ---------------------------------------------------------------------------
# Pendiente — fase 4
# ---------------------------------------------------------------------------
def parameter_sensitivity(*args, **kwargs):
    """Meseta, no pico: mediana del Sharpe en el vecindario ±25 % (criterio C7)."""
    raise NotImplementedError("Fase 4 — pendiente")


def cross_asset_stability(*args, **kwargs):
    """SOL y LTC nunca se optimizan: para ellos esto es 100 % fuera de muestra (C8)."""
    raise NotImplementedError("Fase 4 — pendiente")


def subperiod_breakdown(*args, **kwargs):
    """Incluye obligatoriamente 2015-2017 frente al resto (D1, criterio C11)."""
    raise NotImplementedError("Fase 4 — pendiente")


def block_bootstrap_null(*args, **kwargs):
    """Stationary block bootstrap (Politis & Romano 1994), bloque geométrico de
    media 20 días. Conserva colas gruesas y agrupamiento de volatilidad (C9)."""
    raise NotImplementedError("Fase 4 — pendiente")
