"""Fase 4 — Optimización en TRAIN por CPCV, con registro de TODOS los intentos.

Estructura, y por qué es así:

**Nivel 1 — rendimiento fuera de bloque de cada configuración.**
TRAIN se parte en `CPCV_N_GROUPS` bloques contiguos. Cada bloque se evalúa con el
estado reiniciado y su propio calentamiento (E1.5), así que ningún bloque hereda
posición de lo anterior. Se concatenan los retornos de los 10 bloques: eso es la
curva fuera de bloque de esa configuración sobre TRAIN.

Aquí no hay ajuste dentro del pliegue: los parámetros vienen de una rejilla fija,
no se estiman. Por eso los retornos de un bloque **no dependen de qué combinación
lo dejó fuera**, y basta con evaluar cada bloque una vez en lugar de 45.

**Nivel 2 — CPCV sobre el PROCEDIMIENTO DE SELECCIÓN.**
Lo que hay que validar no es una configuración concreta: es "coger la rejilla y
quedarse con la mejor". Para cada una de las 45 combinaciones se elige la mejor
configuración mirando **solo** los bloques de entrenamiento y se anota cómo le fue
en los bloques de test. De ahí salen los 9 caminos.

Consecuencia que conviene tener clara: **si no hubiera selección dentro del
pliegue, los 9 caminos serían idénticos**. La multiplicidad de caminos solo aporta
información porque el procedimiento elige algo en cada pliegue.

Todo intento se registra en `trial_registry` en el momento de evaluarlo.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from itertools import combinations
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src import backtest as bt, config, data_loader as dl, statistics as st
from src import strategies as sg, validation as v
from src.trial_registry import TrialRegistry

N_MATCHED_NULL_PATHS = 500


# ---------------------------------------------------------------------------
# Nivel 1
# ---------------------------------------------------------------------------
def group_blocks(index: pd.DatetimeIndex, warmup: int, n_groups: int | None = None):
    """Un bloque por grupo, cada uno con su calentamiento delante.

    Si delante no hay `warmup` días (grupo pegado al inicio), el calentamiento
    sale del propio grupo y esos días no se puntúan.
    """
    n_groups = config.CPCV_N_GROUPS if n_groups is None else n_groups
    n = len(index)
    bloques = []
    for lo, hi in v.group_bounds(n, n_groups):
        w_lo = max(0, lo - warmup)
        falta = warmup - (lo - w_lo)
        t_lo = min(lo + falta, hi)
        bloques.append(v.TestBlock(warmup=index[w_lo:t_lo], test=index[t_lo:hi]))
    return bloques


def evaluate_out_of_block(
    prices: pd.DataFrame,
    spec: sg.StrategySpec,
    params: dict,
    lag: int | None = None,
    periods_per_year: int | None = None,
    cost_per_turn: float | None = None,
) -> tuple[bt.BacktestResult, list[pd.Series]]:
    """Retornos fuera de bloque sobre todo el índice de `prices`.

    Devuelve el resultado agregado y la lista de series de retornos por grupo (que
    es lo que necesita el nivel 2 para armar los caminos).
    """
    warmup = spec.warmup_for(params)
    trozos: list[bt.BacktestResult] = []
    for bloque in group_blocks(prices.index, warmup):
        if len(bloque.test) == 0:
            trozos.append(None)
            continue
        ventana = prices.loc[bloque.full[0] : bloque.test[-1]]
        señal = spec.build(ventana, params)          # estado reiniciado aquí
        trozos.append(
            bt.run(
                ventana, señal, lag=lag, score_from=bloque.test[0],
                periods_per_year=periods_per_year, cost_per_turn=cost_per_turn,
            )
        )
    vivos = [t for t in trozos if t is not None]
    return bt.combine(vivos, periods_per_year=periods_per_year), [
        (t.returns if t is not None else pd.Series(dtype=float)) for t in trozos
    ]


@dataclass
class TrialOutcome:
    asset: str
    strategy: str
    params: dict
    metrics: dict
    returns: pd.Series
    group_returns: list[pd.Series]
    matched_rotation: st.MatchedNullResult
    matched_markov: st.MatchedNullResult

    @property
    def passes_c12(self) -> bool:
        return self.matched_rotation.passes and self.matched_markov.passes


def run_grid(
    assets: tuple[str, ...] | None = None,
    registry: TrialRegistry | None = None,
    split: str = "train",
    verbose: bool = True,
) -> list[TrialOutcome]:
    """Evalúa la rejilla entera y registra cada configuración según se evalúa."""
    assets = config.OPTIMIZATION_ASSETS if assets is None else assets
    registry = TrialRegistry() if registry is None else registry
    salida: list[TrialOutcome] = []

    for asset in assets:
        precios = dl.split(dl.load(asset), split)
        if len(precios) < 2 * config.CPCV_N_GROUPS:
            continue
        r = precios["close"].pct_change().fillna(0.0)

        for spec in sg.UNIVERSE:
            for params in spec.grid():
                try:
                    res, por_grupo = evaluate_out_of_block(precios, spec, params)
                except Exception as exc:                      # pragma: no cover
                    registry.log(
                        spec.name, params, asset, split, None,
                        outcome="error", notes=repr(exc)[:200],
                    )
                    continue

                pos = res.position.reindex(precios.index).fillna(0.0).to_numpy()
                rr = r.to_numpy()
                nulo_rot = st.matched_exposure_null(
                    rr, pos, res.metrics["sharpe"],
                    n_paths=N_MATCHED_NULL_PATHS, method="rotation", seed=config.SEED,
                )
                nulo_mkv = st.matched_exposure_null(
                    rr, pos, res.metrics["sharpe"],
                    n_paths=N_MATCHED_NULL_PATHS, method="markov", seed=config.SEED,
                )

                registry.log(
                    spec.name, params, asset, split, res.metrics,
                    outcome="exploration",
                    notes=(
                        f"oob; c12_rot_pct={nulo_rot.percentile:.3f}; "
                        f"c12_mkv_pct={nulo_mkv.percentile:.3f}; "
                        f"exp={nulo_rot.exposure:.3f}"
                    ),
                )
                salida.append(
                    TrialOutcome(
                        asset, spec.name, params, res.metrics, res.returns,
                        por_grupo, nulo_rot, nulo_mkv,
                    )
                )
        if verbose:
            print(f"  {asset}: {sum(1 for o in salida if o.asset == asset)} configuraciones")
    return salida


# ---------------------------------------------------------------------------
# Nivel 2 — CPCV sobre el procedimiento de selección
# ---------------------------------------------------------------------------
@dataclass
class CPCVSelection:
    paths: list[float]
    chosen: list[str]
    median_path_sharpe: float
    n_paths: int

    def __str__(self) -> str:
        return (
            f"mediana de los {self.n_paths} caminos = {self.median_path_sharpe:.2f}; "
            f"{len(set(self.chosen))} configuraciones distintas elegidas en "
            f"{len(self.chosen)} pliegues"
        )


def _sharpe_of(chunks: list[pd.Series], periods: int) -> float:
    if not chunks:
        return 0.0
    s = pd.concat(chunks)
    sd = s.std(ddof=1)
    return float(s.mean() / sd * np.sqrt(periods)) if sd > 0 else 0.0


def cpcv_selection(
    outcomes: list[TrialOutcome], periods_per_year: int | None = None
) -> CPCVSelection:
    """CPCV sobre "quédate con la mejor de la rejilla".

    Para cada combinación se elige mirando solo los bloques de entrenamiento y se
    anota el resultado en los de test. Los caminos se arman como en `cpcv_paths`.
    """
    periods = config.TRADING_DAYS_PER_YEAR if periods_per_year is None else periods_per_year
    N, k = config.CPCV_N_GROUPS, config.CPCV_N_TEST_GROUPS
    combos = list(combinations(range(N), k))

    elegidas: dict[int, int] = {}
    por_combo_grupo: dict[tuple[int, int], pd.Series] = {}
    for ci, combo in enumerate(combos):
        entreno = [g for g in range(N) if g not in combo]
        puntos = [
            _sharpe_of([o.group_returns[g] for g in entreno if len(o.group_returns[g])], periods)
            for o in outcomes
        ]
        mejor = int(np.argmax(puntos))
        elegidas[ci] = mejor
        for g in combo:
            por_combo_grupo[(ci, g)] = outcomes[mejor].group_returns[g]

    caminos, nombres = [], []
    for camino in v.cpcv_paths(N, k):
        trozos = [por_combo_grupo[(ci, g)] for ci, g in camino]
        trozos = [t for t in trozos if len(t)]
        caminos.append(_sharpe_of(trozos, periods))
        nombres.extend(
            f"{outcomes[elegidas[ci]].strategy}{outcomes[elegidas[ci]].params}"
            for ci, _ in camino
        )
    return CPCVSelection(
        paths=caminos,
        chosen=nombres,
        median_path_sharpe=float(np.median(caminos)),
        n_paths=len(caminos),
    )


# ---------------------------------------------------------------------------
# Matriz de intentos para PBO / DSR
# ---------------------------------------------------------------------------
def trials_matrix(outcomes: list[TrialOutcome]) -> tuple[np.ndarray, list[str]]:
    """(T, N) con los retornos fuera de bloque de cada configuración, alineados."""
    marco = pd.concat(
        {f"{o.strategy}|{o.params}": o.returns for o in outcomes}, axis=1
    ).fillna(0.0)
    return marco.to_numpy(), list(marco.columns)
