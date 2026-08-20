"""Corrección por comparaciones múltiples e intervalos de confianza (regla 4).

Contenido:
  - `stationary_block_bootstrap`: remuestreo por bloques geométricos (Politis &
    Romano 1994). Base tanto de los intervalos de confianza como de la prueba de
    nulidad (C9).
  - `sharpe_confidence_interval`: IC del Sharpe por bootstrap de bloques, más el
    error estándar analítico de Lo (2002) como contraste.
  - `deflated_sharpe_ratio`: Bailey & López de Prado (2014).
  - `probability_of_backtest_overfitting`: PBO por CSCV (Bailey et al. 2015).

Motivo de que el IC sea obligatorio y no opcional: con las muestras de este
proyecto el error estándar del Sharpe anualizado es ≈ sqrt(365/T), es decir 0,43
en TRAIN, 0,58 en VALIDATION, 0,62 en LOCKBOX y 0,96 en un bloque CPCV de 398
días. Un Sharpe puntual de 0,50 en el lockbox trae un IC del 95 % de
[−0,71, +1,71]: informar el punto sin el intervalo es informar ruido con tres
cifras significativas.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from itertools import combinations
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src import config

EULER_MASCHERONI = 0.5772156649015329


# ---------------------------------------------------------------------------
# Bootstrap por bloques
# ---------------------------------------------------------------------------
def stationary_block_bootstrap(
    x: np.ndarray,
    n_paths: int | None = None,
    mean_block: int | None = None,
    seed: int | None = None,
) -> np.ndarray:
    """Stationary block bootstrap (Politis & Romano 1994).

    Bloques de longitud geométrica con media `mean_block`, arranque uniforme y
    envoltura circular. Conserva colas gruesas y agrupamiento de volatilidad;
    destruye la dependencia serial de largo alcance.

    Devuelve una matriz `(n_paths, len(x))`.
    """
    x = np.asarray(x, dtype=float)
    T = len(x)
    if T < 2:
        raise ValueError("serie demasiado corta para remuestrear")
    n_paths = config.N_SYNTHETIC_PATHS if n_paths is None else n_paths
    mean_block = config.BOOTSTRAP_MEAN_BLOCK_DAYS if mean_block is None else mean_block
    if mean_block < 1:
        raise ValueError("mean_block >= 1")

    rng = np.random.default_rng(config.SEED if seed is None else seed)
    p = 1.0 / mean_block

    # Cada posición o continúa el bloque anterior (prob 1-p) o abre uno nuevo.
    nuevo = rng.random((n_paths, T)) < p
    nuevo[:, 0] = True
    arranques = rng.integers(0, T, size=(n_paths, T))

    idx = np.empty((n_paths, T), dtype=np.int64)
    idx[:, 0] = arranques[:, 0]
    for t in range(1, T):
        idx[:, t] = np.where(nuevo[:, t], arranques[:, t], (idx[:, t - 1] + 1) % T)
    return x[idx]


# ---------------------------------------------------------------------------
# Sharpe: punto, error estándar e intervalo
# ---------------------------------------------------------------------------
def annualized_sharpe(returns: np.ndarray, periods: int | None = None) -> float:
    periods = config.TRADING_DAYS_PER_YEAR if periods is None else periods
    r = np.asarray(returns, dtype=float)
    sd = r.std(ddof=1)
    return float(r.mean() / sd * np.sqrt(periods)) if sd > 0 else 0.0


def sharpe_standard_error(returns: np.ndarray, periods: int | None = None) -> float:
    """Error estándar analítico del Sharpe anualizado (Lo 2002).

        SE(SR) ≈ sqrt( (1 + SR_d²/2 − γ3·SR_d + (γ4−3)/4·SR_d²) / T ) · sqrt(A)

    Para Sharpes pequeños se reduce a `sqrt(A/T)`, que es la regla de bolsillo:
    0,43 con 1.992 días, 0,58 con 1.095, 0,96 con 398.
    """
    periods = config.TRADING_DAYS_PER_YEAR if periods is None else periods
    r = np.asarray(returns, dtype=float)
    T = len(r)
    if T < 3 or r.std(ddof=1) == 0:
        return float("nan")
    sr_d = r.mean() / r.std(ddof=1)
    g3 = float(stats.skew(r, bias=False))
    g4 = float(stats.kurtosis(r, fisher=False, bias=False))
    var = (1 + 0.5 * sr_d**2 - g3 * sr_d + 0.25 * (g4 - 3) * sr_d**2) / T
    return float(np.sqrt(max(var, 0.0) * periods))


@dataclass(frozen=True)
class SharpeInterval:
    point: float
    lo: float
    hi: float
    se_analytic: float
    n_obs: int
    level: float

    @property
    def includes_zero(self) -> bool:
        return self.lo <= 0.0 <= self.hi

    def __str__(self) -> str:
        marca = "  [IC incluye 0 -> NO CONCLUYENTE]" if self.includes_zero else ""
        return f"{self.point:.2f} [{self.lo:.2f}, {self.hi:.2f}]{marca}"


def sharpe_confidence_interval(
    returns: np.ndarray,
    level: float = 0.95,
    n_paths: int | None = None,
    mean_block: int | None = None,
    seed: int | None = None,
) -> SharpeInterval:
    """IC del Sharpe anualizado por bootstrap de bloques.

    Se remuestrea la propia serie de retornos de la estrategia, así que el
    intervalo hereda su autocorrelación y su curtosis en vez de suponer
    normalidad.
    """
    r = np.asarray(returns, dtype=float)
    paths = stationary_block_bootstrap(r, n_paths=n_paths, mean_block=mean_block, seed=seed)
    sd = paths.std(axis=1, ddof=1)
    with np.errstate(invalid="ignore", divide="ignore"):
        srs = np.where(sd > 0, paths.mean(axis=1) / sd * np.sqrt(config.TRADING_DAYS_PER_YEAR), 0.0)
    alpha = (1.0 - level) / 2.0
    lo, hi = np.quantile(srs, [alpha, 1.0 - alpha])
    return SharpeInterval(
        point=annualized_sharpe(r),
        lo=float(lo), hi=float(hi),
        se_analytic=sharpe_standard_error(r),
        n_obs=len(r), level=level,
    )


# ---------------------------------------------------------------------------
# Deflated Sharpe Ratio
# ---------------------------------------------------------------------------
def expected_max_sharpe(sr_variance: float, n_trials: int) -> float:
    """`SR_0`: Sharpe que cabe esperar del MEJOR de N intentos sin ninguna ventaja.

    Es el umbral contra el que hay que comparar. Con 200 configuraciones y una
    dispersión de Sharpes diarios normal, el mejor backtest sale claramente
    positivo aunque ninguna estrategia sirva: ese es todo el problema.
    """
    if n_trials < 1:
        raise ValueError("n_trials >= 1")
    if n_trials == 1 or sr_variance <= 0:
        return 0.0
    g = EULER_MASCHERONI
    z1 = stats.norm.ppf(1.0 - 1.0 / n_trials)
    z2 = stats.norm.ppf(1.0 - 1.0 / (n_trials * np.e))
    return float(np.sqrt(sr_variance) * ((1.0 - g) * z1 + g * z2))


def deflated_sharpe_ratio(
    returns: np.ndarray,
    n_trials: int,
    sr_variance: float,
    periods: int | None = None,
) -> float:
    """DSR de Bailey & López de Prado (2014).

    Probabilidad de que el Sharpe verdadero supere `SR_0`, descontando el número
    de intentos, la asimetría y la curtosis de los retornos.

    `sr_variance` es la varianza de los Sharpes **diarios** entre configuraciones
    probadas (`trial_registry.sharpe_variance()` devuelve la anualizada; hay que
    dividir por `periods`). `annualized_sr_variance_to_periodic` hace la cuenta.
    """
    periods = config.TRADING_DAYS_PER_YEAR if periods is None else periods
    r = np.asarray(returns, dtype=float)
    T = len(r)
    if T < 3:
        return float("nan")
    sd = r.std(ddof=1)
    if sd == 0:
        return 0.0

    sr = r.mean() / sd                      # Sharpe por periodo, no anualizado
    sr0 = expected_max_sharpe(sr_variance, n_trials)
    g3 = float(stats.skew(r, bias=False))
    g4 = float(stats.kurtosis(r, fisher=False, bias=False))

    denom = 1.0 - g3 * sr + 0.25 * (g4 - 1.0) * sr**2
    if denom <= 0:
        return float("nan")
    z = (sr - sr0) * np.sqrt(T - 1) / np.sqrt(denom)
    return float(stats.norm.cdf(z))


def annualized_sr_variance_to_periodic(var_ann: float, periods: int | None = None) -> float:
    periods = config.TRADING_DAYS_PER_YEAR if periods is None else periods
    return float(var_ann / periods)


# ---------------------------------------------------------------------------
# Probability of Backtest Overfitting (CSCV)
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class PBOResult:
    pbo: float
    n_combinations: int
    n_configs: int
    logits: np.ndarray
    median_oos_of_is_best: float

    def __str__(self) -> str:
        return f"PBO={self.pbo:.1%} ({self.n_combinations} particiones, {self.n_configs} configs)"


def probability_of_backtest_overfitting(
    returns_matrix: np.ndarray, n_blocks: int = 16
) -> PBOResult:
    """PBO por Combinatorially Symmetric Cross-Validation (Bailey et al. 2015).

    `returns_matrix` es `(T, n_configs)`: los retornos diarios de cada
    configuración sobre el MISMO periodo. Se parte en `n_blocks` bloques, se toman
    todas las mitades posibles como in-sample, se elige la mejor configuración
    in-sample y se mira en qué percentil queda out-of-sample.

    PBO = fracción de particiones en las que la ganadora in-sample cae por debajo
    de la mediana out-of-sample. Un PBO alto significa que el proceso de selección
    no distingue señal de ruido, con independencia de lo bien que puntúe la
    ganadora.
    """
    M = np.asarray(returns_matrix, dtype=float)
    if M.ndim != 2 or M.shape[1] < 2:
        raise ValueError("hacen falta al menos 2 configuraciones en columnas")
    T, N = M.shape
    if n_blocks % 2 or n_blocks < 4:
        raise ValueError("n_blocks debe ser par y >= 4")
    if T < n_blocks * 2:
        raise ValueError(f"{T} observaciones no dan para {n_blocks} bloques")

    edges = np.linspace(0, T, n_blocks + 1).astype(int)
    # Sumas por bloque: permiten reconstruir media y desviación de cualquier unión
    # de bloques sin recorrer los datos otra vez.
    s1 = np.stack([M[a:b].sum(axis=0) for a, b in zip(edges, edges[1:])])
    s2 = np.stack([(M[a:b] ** 2).sum(axis=0) for a, b in zip(edges, edges[1:])])
    cnt = np.array([b - a for a, b in zip(edges, edges[1:])], dtype=float)

    def sharpe(mask: np.ndarray) -> np.ndarray:
        n = cnt[mask].sum()
        m = s1[mask].sum(axis=0) / n
        var = s2[mask].sum(axis=0) / n - m**2
        var = np.maximum(var * n / (n - 1), 0.0)
        sd = np.sqrt(var)
        return np.where(sd > 0, m / np.where(sd > 0, sd, 1.0), 0.0)

    logits, oos_of_best = [], []
    todos = np.arange(n_blocks)
    for combo in combinations(range(n_blocks), n_blocks // 2):
        is_mask = np.zeros(n_blocks, dtype=bool)
        is_mask[list(combo)] = True
        sr_is = sharpe(is_mask)
        sr_oos = sharpe(~is_mask)

        mejor = int(np.argmax(sr_is))
        # Rango relativo de la ganadora in-sample dentro del ranking out-of-sample.
        rango = float(stats.rankdata(sr_oos)[mejor])
        omega = rango / (N + 1.0)
        omega = min(max(omega, 1e-12), 1 - 1e-12)
        logits.append(np.log(omega / (1.0 - omega)))
        oos_of_best.append(sr_oos[mejor] - np.median(sr_oos))

    logits = np.asarray(logits)
    return PBOResult(
        pbo=float((logits <= 0).mean()),
        n_combinations=len(logits),
        n_configs=N,
        logits=logits,
        median_oos_of_is_best=float(np.median(oos_of_best)),
    )
