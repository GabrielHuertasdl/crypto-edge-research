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
    # de bloques con un producto de matrices, sin recorrer los datos otra vez.
    s1 = np.stack([M[a:b].sum(axis=0) for a, b in zip(edges, edges[1:])])
    s2 = np.stack([(M[a:b] ** 2).sum(axis=0) for a, b in zip(edges, edges[1:])])
    cnt = np.array([b - a for a, b in zip(edges, edges[1:])], dtype=float)

    combos = np.array(list(combinations(range(n_blocks), n_blocks // 2)))
    masks = np.zeros((len(combos), n_blocks), dtype=float)
    np.put_along_axis(masks, combos, 1.0, axis=1)

    def sharpes(w: np.ndarray) -> np.ndarray:
        n = w @ cnt                              # (C,)
        m = (w @ s1) / n[:, None]                # (C, N)
        var = (w @ s2) / n[:, None] - m**2
        var = np.maximum(var * (n / (n - 1.0))[:, None], 0.0)
        sd = np.sqrt(var)
        return np.divide(m, sd, out=np.zeros_like(m), where=sd > 0)

    sr_is = sharpes(masks)
    sr_oos = sharpes(1.0 - masks)

    mejor = np.argmax(sr_is, axis=1)
    valor = np.take_along_axis(sr_oos, mejor[:, None], axis=1)
    # Rango medio (empates repartidos), igual que scipy.stats.rankdata.
    menores = (sr_oos < valor).sum(axis=1)
    iguales = (sr_oos == valor).sum(axis=1)
    rango = menores + (iguales + 1.0) / 2.0

    omega = np.clip(rango / (N + 1.0), 1e-12, 1 - 1e-12)
    logits = np.log(omega / (1.0 - omega))
    oos_of_best = valor.ravel() - np.median(sr_oos, axis=1)

    # El logit vale EXACTAMENTE 0 cuando la ganadora in-sample cae justo en la
    # mediana out-of-sample, cosa que con N impar ocurre en 1 de cada N casos.
    # Contar ese átomo entero como sobreajuste sesga el PBO al alza (+0,04 con
    # N=25); ignorarlo lo sesga a la baja en lo mismo. Se reparte a la mitad, que
    # es lo único que deja el estimador centrado en 0,50 bajo la nula.
    empate = np.isclose(logits, 0.0)

    return PBOResult(
        pbo=float(((logits < 0) & ~empate).mean() + 0.5 * empate.mean()),
        n_combinations=len(logits),
        n_configs=N,
        logits=logits,
        median_oos_of_is_best=float(np.median(oos_of_best)),
    )


def pbo_null_distribution(
    n_obs: int,
    n_configs: int,
    n_blocks: int = 16,
    n_sims: int = 300,
    seed: int | None = None,
) -> np.ndarray:
    """PBO de `n_sims` conjuntos de configuraciones SIN ninguna habilidad.

    Existe porque el PBO calculado sobre una sola matriz de resultados es muy
    ruidoso: bajo la nula su media es 0,50 pero su desviación típica ronda 0,20.
    Un PBO observado de 0,20 no demuestra que no haya sobreajuste; puede ser una
    fluctuación de un conjunto sin ninguna señal.
    """
    rng = np.random.default_rng(config.SEED if seed is None else seed)
    return np.array(
        [
            probability_of_backtest_overfitting(
                rng.normal(0.0, 0.02, (n_obs, n_configs)), n_blocks=n_blocks
            ).pbo
            for _ in range(n_sims)
        ]
    )


def pbo_pvalue(
    observed_pbo: float,
    n_obs: int,
    n_configs: int,
    n_blocks: int = 16,
    n_sims: int = 300,
    seed: int | None = None,
) -> float:
    """Probabilidad de obtener un PBO tan bajo como el observado sin habilidad.

    Es el complemento honesto de C6: un PBO bajo con p-valor alto no es evidencia
    de nada.
    """
    nula = pbo_null_distribution(n_obs, n_configs, n_blocks, n_sims, seed)
    return float((nula <= observed_pbo).mean())


# ---------------------------------------------------------------------------
# Calibración: qué significan de verdad un DSR y un PBO
# ---------------------------------------------------------------------------
def mean_pairwise_correlation(matrix: np.ndarray) -> float:
    """Correlación media entre columnas. Los intentos de una misma familia de
    estrategias están muy correlacionados entre sí, y eso cambia la distribución
    nula tanto del DSR como del PBO."""
    M = np.asarray(matrix, dtype=float)
    if M.shape[1] < 2:
        return 0.0
    c = np.corrcoef(M, rowvar=False)
    iu = np.triu_indices_from(c, k=1)
    return float(np.nanmean(c[iu]))


def _null_trial_matrix(rng, n_obs: int, n_configs: int, rho: float) -> np.ndarray:
    """Intentos SIN habilidad con correlación media `rho` entre ellos."""
    rho = float(np.clip(rho, 0.0, 0.999))
    comun = rng.normal(0.0, 0.02, (n_obs, 1))
    propio = rng.normal(0.0, 0.02, (n_obs, n_configs))
    return np.sqrt(rho) * comun + np.sqrt(1.0 - rho) * propio


def dsr_null_distribution(
    n_obs: int,
    n_configs: int,
    rho: float = 0.0,
    n_sims: int = 500,
    seed: int | None = None,
) -> np.ndarray:
    """DSR de la MEJOR de `n_configs` estrategias sin habilidad.

    Existe porque el DSR **no** es uniforme en [0, 1] bajo la nula: está
    concentrado alrededor de 0,5 (ver `tests/test_statistics.py`). Por tanto
    "DSR ≥ 0,95" NO significa "95 % de confianza"; hay que traducirlo a un
    p-valor empírico con la misma `n_configs`, la misma longitud y la misma
    correlación entre intentos que el experimento real.
    """
    rng = np.random.default_rng(config.SEED if seed is None else seed)
    out = np.empty(n_sims)
    for i in range(n_sims):
        M = _null_trial_matrix(rng, n_obs, n_configs, rho)
        sd = M.std(axis=0, ddof=1)
        sr = np.divide(M.mean(axis=0), sd, out=np.zeros(n_configs), where=sd > 0)
        mejor = int(np.argmax(sr))
        out[i] = deflated_sharpe_ratio(M[:, mejor], n_configs, float(np.var(sr, ddof=1)))
    return out


def dsr_pvalue(
    observed_dsr: float,
    n_obs: int,
    n_configs: int,
    rho: float = 0.0,
    n_sims: int = 500,
    seed: int | None = None,
) -> float:
    """Probabilidad de alcanzar un DSR así de alto sin ninguna habilidad.

    Es lo que hay que reportar junto al DSR. El umbral nominal de 0,95 no está
    calibrado; este p-valor sí.
    """
    nula = dsr_null_distribution(n_obs, n_configs, rho, n_sims, seed)
    return float((nula >= observed_dsr).mean())


# ---------------------------------------------------------------------------
# Nulo de exposición equiparada
# ---------------------------------------------------------------------------
def _strategy_returns_matrix(
    r: np.ndarray, positions: np.ndarray, cost_per_turn: float
) -> np.ndarray:
    """Réplica vectorizada de `backtest.run` para muchas posiciones a la vez.

    `positions` es (n_paths, T). Misma aritmética que el motor, verificada contra
    él en `tests/test_matched_null.py`: si divergen, el nulo mediría otra cosa.
    """
    prev = np.concatenate([np.zeros((positions.shape[0], 1)), positions[:, :-1]], axis=1)
    turnover = np.abs(positions - prev)
    return positions * r[None, :] - turnover * cost_per_turn


def _rotated_positions(position: np.ndarray, n_paths: int, rng) -> np.ndarray:
    """Rotaciones circulares de la MISMA senda de posiciones.

    Conserva exactamente la exposición, la rotación y hasta la distribución de la
    duración de las operaciones; lo único que destruye es la alineación con los
    retornos. Es el nulo más ajustado posible: cualquier diferencia de Sharpe solo
    puede venir de saber CUÁNDO estar dentro.
    """
    T = len(position)
    desfases = rng.choice(np.arange(1, T), size=n_paths, replace=T <= n_paths)
    idx = (np.arange(T)[None, :] + desfases[:, None]) % T
    return position[idx]


def _markov_positions(
    exposure: float, turnover_per_day: float, T: int, n_paths: int, rng
) -> np.ndarray:
    """Cadena de Markov de dos estados con exposición y rotación equiparadas.

    Estacionaria en `exposure`; `p10 = rot / (2·e)` y `p01 = rot / (2·(1−e))`
    reproducen la rotación media. Complementa a las rotaciones: no reutiliza la
    senda real, así que no arrastra su forma.
    """
    e = float(np.clip(exposure, 1e-6, 1 - 1e-6))
    p10 = float(np.clip(turnover_per_day / (2 * e), 0.0, 1.0))
    p01 = float(np.clip(turnover_per_day / (2 * (1 - e)), 0.0, 1.0))

    out = np.empty((n_paths, T))
    cur = (rng.random(n_paths) < e).astype(float)
    for t in range(T):
        u = rng.random(n_paths)
        cur = np.where(cur > 0, np.where(u < p10, 0.0, 1.0), np.where(u < p01, 1.0, 0.0))
        out[:, t] = cur
    return out


@dataclass(frozen=True)
class MatchedNullResult:
    observed_sharpe: float
    null_sharpes: np.ndarray
    percentile: float
    p95: float
    exposure: float
    turnover_per_day: float
    method: str

    @property
    def passes(self) -> bool:
        """Criterio: superar el percentil 95 del nulo equiparado."""
        return self.observed_sharpe > self.p95

    def __str__(self) -> str:
        return (
            f"SR={self.observed_sharpe:.2f} vs nulo equiparado p95={self.p95:.2f} "
            f"(percentil {self.percentile:.1%}, exp={self.exposure:.0%}, "
            f"rot/día={self.turnover_per_day:.3f}, {self.method})"
        )


def matched_exposure_null(
    returns: np.ndarray,
    position: np.ndarray,
    observed_sharpe: float | None = None,
    n_paths: int | None = None,
    method: str = "rotation",
    cost_per_turn: float | None = None,
    periods_per_year: int | None = None,
    seed: int | None = None,
) -> MatchedNullResult:
    """Nulo con exposición y rotación equiparadas sobre el activo REAL.

    Motivo, medido sobre el TRAIN de BTC (CAGR del 134 %): señales **aleatorias**
    con 55 % de exposición y rotación realista alcanzan Sharpe ≥ 0,70 el **90 %**
    de las veces. Sobre la misma serie con la deriva quitada, el 0,8 %.

    Es decir: la tasa de falso positivo de un umbral absoluto de Sharpe la fija la
    deriva del activo, no la estrategia. Comparar contra buy & hold al 100 % de
    exposición tampoco lo arregla, porque una estrategia expuesta el 55 % del
    tiempo asume menos riesgo y no tiene por qué batirlo en Sharpe.

    Este nulo no sustituye a C9 (block bootstrap de los retornos, que pregunta si
    la SERIE tiene estructura explotable). Pregunta otra cosa: dado que estás
    dentro del mercado tanto tiempo y rotas tanto, ¿aporta algo saber CUÁNDO?
    """
    r = np.asarray(returns, dtype=float)
    pos = np.asarray(position, dtype=float)
    if len(r) != len(pos):
        raise ValueError("retornos y posiciones deben tener la misma longitud")
    if method not in {"rotation", "markov"}:
        raise ValueError("method debe ser 'rotation' o 'markov'")

    n_paths = config.N_SYNTHETIC_PATHS if n_paths is None else n_paths
    cost_per_turn = config.COST_PER_TURN if cost_per_turn is None else cost_per_turn
    periods = config.TRADING_DAYS_PER_YEAR if periods_per_year is None else periods_per_year
    rng = np.random.default_rng(config.SEED if seed is None else seed)

    exposure = float((pos > 0).mean())
    turnover = float(np.abs(np.diff(np.concatenate([[0.0], pos]))).sum() / len(pos))

    if method == "rotation":
        paths = _rotated_positions(pos, n_paths, rng)
    else:
        paths = _markov_positions(exposure, turnover, len(pos), n_paths, rng)
        # Escala a la exposición media real para que valgan también las
        # estrategias de posición fraccionaria.
        media = pos[pos > 0].mean() if (pos > 0).any() else 0.0
        paths = paths * media

    rets = _strategy_returns_matrix(r, paths, cost_per_turn)
    sd = rets.std(axis=1, ddof=1)
    srs = np.divide(
        rets.mean(axis=1) * np.sqrt(periods), sd, out=np.zeros(len(rets)), where=sd > 0
    )

    if observed_sharpe is None:
        obs_rets = _strategy_returns_matrix(r, pos[None, :], cost_per_turn)[0]
        observed_sharpe = annualized_sharpe(obs_rets, periods)

    return MatchedNullResult(
        observed_sharpe=float(observed_sharpe),
        null_sharpes=srs,
        percentile=float((srs < observed_sharpe).mean()),
        p95=float(np.quantile(srs, 0.95)),
        exposure=exposure,
        turnover_per_day=turnover,
        method=method,
    )


# ---------------------------------------------------------------------------
# Intentos efectivamente independientes
# ---------------------------------------------------------------------------
def effective_number_of_trials(returns_matrix: np.ndarray) -> float:
    """`N_eff` por participación de autovalores: `(Σλ)² / Σλ²`.

    Un `ρ̄` único no describe la estructura real: dentro de una familia las
    parametrizaciones correlacionan ~0,95 y entre familias mucho menos. La
    participación de autovalores sobre la matriz de correlación de los retornos de
    los intentos resume esa estructura en un solo número, y es la misma idea que
    `N_eff` en C8c.

    Usar `N` en bruto en el DSR **sobrepenaliza**: 149 configuraciones que en
    realidad son 8 apuestas distintas no equivalen a 149 intentos independientes.
    Usar `N_eff` es la corrección estándar. Se reportan ambos.
    """
    M = np.asarray(returns_matrix, dtype=float)
    if M.ndim != 2 or M.shape[1] < 2:
        return float(max(M.shape[1] if M.ndim == 2 else 1, 1))
    sd = M.std(axis=0, ddof=1)
    vivas = sd > 0
    if vivas.sum() < 2:
        return float(max(int(vivas.sum()), 1))
    C = np.corrcoef(M[:, vivas], rowvar=False)
    C = np.nan_to_num(C, nan=0.0)
    lam = np.linalg.eigvalsh(C)
    lam = np.clip(lam, 0.0, None)
    if lam.sum() <= 0:
        return 1.0
    return float(lam.sum() ** 2 / (lam**2).sum())


@dataclass(frozen=True)
class DeflatedSharpeReport:
    dsr: float
    p_value: float
    n_trials_raw: int
    n_trials_effective: float
    sr_variance_periodic: float
    sr0_periodic: float

    @property
    def passes(self) -> bool:
        """C5 tras la Enmienda 2: umbral nominal Y p-valor calibrado."""
        return self.dsr >= 0.95 and self.p_value <= 0.05

    def __str__(self) -> str:
        return (
            f"DSR={self.dsr:.3f} (p={self.p_value:.3f}) con N={self.n_trials_raw} "
            f"intentos, N_eff={self.n_trials_effective:.1f}"
        )


def deflated_sharpe_report(
    returns_best: np.ndarray,
    trials_matrix: np.ndarray,
    n_sims: int = 400,
    periods_per_year: int | None = None,
    seed: int | None = None,
) -> DeflatedSharpeReport:
    """DSR usando el número EFECTIVO de intentos independientes.

    `trials_matrix` es (T, N): los retornos diarios de todas las configuraciones
    evaluadas, sobre el mismo periodo. De ahí salen las tres cosas que el DSR
    necesita y que no se pueden inventar: la varianza de los Sharpes, el número
    efectivo de intentos y la estructura de correlación con la que simular la nula.
    """
    periods = config.TRADING_DAYS_PER_YEAR if periods_per_year is None else periods_per_year
    M = np.asarray(trials_matrix, dtype=float)
    n_raw = int(M.shape[1])
    n_eff = effective_number_of_trials(M)

    sd = M.std(axis=0, ddof=1)
    sr = np.divide(M.mean(axis=0), sd, out=np.zeros(n_raw), where=sd > 0)
    var_sr = float(np.var(sr, ddof=1)) if n_raw > 1 else 0.0

    n_para_dsr = max(int(round(n_eff)), 1)
    dsr = deflated_sharpe_ratio(returns_best, n_para_dsr, var_sr, periods)
    # La nula se simula con N_eff intentos INDEPENDIENTES: N_eff ya absorbe la
    # correlación, así que volver a meterla como rho la contaría dos veces.
    p = dsr_pvalue(dsr, len(returns_best), n_para_dsr, rho=0.0, n_sims=n_sims, seed=seed)
    return DeflatedSharpeReport(
        dsr=dsr, p_value=p, n_trials_raw=n_raw, n_trials_effective=n_eff,
        sr_variance_periodic=var_sr,
        sr0_periodic=expected_max_sharpe(var_sr, n_para_dsr),
    )
