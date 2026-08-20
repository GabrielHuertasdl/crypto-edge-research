"""Fase 2 — Motor de backtest vectorizado, long/flat, sin apalancamiento.

Reglas que impone el motor (no quien lo llama):
  - posición ∈ [0, 1]. Fuera de rango es error, no se recorta en silencio.
  - la señal de `t` se ejecuta al **cierre de `t+1`** y el primer retorno que cobra
    es `r[t+2]`  ->  `position = signal.shift(lag)` con `lag = 2` por defecto.
  - costes de `config.COST_PER_TURN` sobre cada unidad de rotación.

Convención de índices, escrita una sola vez para no equivocarse dos:

    r[t]        = close[t] / close[t-1] - 1        retorno del día t
    position[t] = fracción mantenida DURANTE el día t, es decir la que cobra r[t]
    position    = signal.shift(lag)                lag = 2 (oficial)
    turnover[t] = |position[t] - position[t-1]|
    ret[t]      = position[t] * r[t] - turnover[t] * COST_PER_TURN

El coste se imputa el día `t` aunque la operación ocurra en el cierre de `t-1`.
Es un desplazamiento de un día de un coste, no de un precio: no crea ni destruye
información, y evita una rama especial en el vectorizado.

No se confía en ningún número de este módulo hasta que `tests/test_backtest.py`
pase entero (posiciones sintéticas con resultado calculado a mano).
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src import config

METRIC_KEYS = (
    "total_return", "cagr", "volatility", "sharpe", "sortino",
    "max_drawdown", "max_drawdown_days", "hit_rate", "profit_factor",
    "n_trades", "exposure", "avg_position", "turnover_per_year", "n_days",
)


@dataclass(frozen=True)
class BacktestResult:
    """Resultado inmutable. `metrics` es un dict plano listo para tabular."""

    returns: pd.Series      # retornos netos diarios de la estrategia
    equity: pd.Series       # curva de capital, base 1.0
    position: pd.Series     # posición que cobra r[t]
    trades: pd.DataFrame    # una fila por operación cerrada o abierta al final
    metrics: dict
    lag: int

    def __repr__(self) -> str:  # pragma: no cover - conveniencia
        m = self.metrics
        return (
            f"<Backtest lag={self.lag} sharpe={m['sharpe']:.2f} "
            f"cagr={m['cagr']:.1%} mdd={m['max_drawdown']:.1%} "
            f"trades={m['n_trades']}>"
        )


# ---------------------------------------------------------------------------
# Núcleo
# ---------------------------------------------------------------------------
def _validate(prices: pd.DataFrame, signal: pd.Series) -> None:
    if not isinstance(prices.index, pd.DatetimeIndex):
        raise TypeError("prices necesita un DatetimeIndex")
    if str(prices.index.tz) != "UTC":
        raise ValueError("prices debe estar en UTC (regla 6-bis)")
    if not prices.index.is_monotonic_increasing or prices.index.has_duplicates:
        raise ValueError("índice de prices desordenado o con duplicados")
    if not signal.index.equals(prices.index):
        raise ValueError(
            "signal y prices no comparten índice. Alinear ANTES de llamar al motor: "
            "un reindex silencioso aquí es la vía más rápida a un alpha falso."
        )
    finite = signal.dropna()
    if len(finite) and (finite.min() < config.MIN_POSITION or finite.max() > config.MAX_POSITION):
        raise ValueError(
            f"señal fuera de [{config.MIN_POSITION}, {config.MAX_POSITION}]: "
            f"min={finite.min()}, max={finite.max()}. Sin apalancamiento ni cortos "
            "(regla 7). El motor no recorta por su cuenta."
        )


def run(
    prices: pd.DataFrame,
    signal: pd.Series,
    lag: int | None = None,
    cost_per_turn: float | None = None,
) -> BacktestResult:
    """Ejecuta una señal sobre una serie de precios.

    `signal[t]` es la exposición deseada decidida con datos hasta el cierre de `t`.
    El motor se encarga del retardo; las estrategias NUNCA desplazan por su cuenta.
    """
    lag = config.OFFICIAL_LAG if lag is None else lag
    cost_per_turn = config.COST_PER_TURN if cost_per_turn is None else cost_per_turn
    if lag < 1:
        raise ValueError("lag < 1 es lookahead por definición")
    _validate(prices, signal)

    r = prices["close"].pct_change().fillna(0.0)
    position = signal.shift(lag).fillna(0.0).astype(float)

    prev = position.shift(1).fillna(0.0)
    turnover = (position - prev).abs()
    costs = turnover * cost_per_turn
    returns = position * r - costs
    equity = (1.0 + returns).cumprod()

    trades = _extract_trades(position, returns, equity)
    metrics = _metrics(returns, equity, position, turnover, trades)
    return BacktestResult(
        returns=returns, equity=equity, position=position,
        trades=trades, metrics=metrics, lag=lag,
    )


def buy_and_hold(prices: pd.DataFrame, lag: int | None = None) -> BacktestResult:
    """Benchmark obligatorio (regla 5). Mismos costes: paga una entrada.

    Se ejecuta por el mismo motor a propósito. Un benchmark calculado aparte es un
    benchmark que no comparte los bugs del motor, y entonces la comparación mide
    los bugs.
    """
    signal = pd.Series(1.0, index=prices.index)
    return run(prices, signal, lag=lag)


# ---------------------------------------------------------------------------
# Operaciones
# ---------------------------------------------------------------------------
def _extract_trades(
    position: pd.Series, returns: pd.Series, equity: pd.Series
) -> pd.DataFrame:
    """Una operación = tramo contiguo con posición > 0.

    Con posiciones fraccionarias (volatility targeting) el tramo puede cambiar de
    tamaño por dentro; sigue contando como una operación. El retorno de la
    operación es el compuesto de los retornos netos del tramo, costes incluidos,
    y se obtiene de la curva de capital: `equity[fin] / equity[inicio-1] - 1`.

    Vectorizado a propósito: con una rejilla de parámetros por 45 splits de CPCV
    esto se llama decenas de miles de veces, y un bucle por operación convertía
    una tarde de cómputo en media hora por estrategia.
    """
    active = (position > 0).to_numpy()
    if not active.any():
        return pd.DataFrame(
            columns=["entry", "exit", "days", "ret", "max_position"]
        ).astype({"days": int})

    padded = np.concatenate(([False], active, [False]))
    starts = np.flatnonzero(~padded[:-1] & padded[1:])
    ends = np.flatnonzero(padded[:-1] & ~padded[1:]) - 1

    eq = equity.to_numpy()
    base = np.where(starts > 0, eq[starts - 1], 1.0)
    pos = position.to_numpy()

    return pd.DataFrame(
        {
            "entry": position.index[starts],
            "exit": position.index[ends],
            "days": (ends - starts + 1).astype(int),
            "ret": eq[ends] / base - 1.0,
            "max_position": np.maximum.reduceat(pos, starts),
        }
    )


# ---------------------------------------------------------------------------
# Métricas
# ---------------------------------------------------------------------------
def _drawdown(equity: pd.Series) -> tuple[float, int]:
    """Máximo drawdown y su duración en días naturales.

    La duración se mide de pico a **recuperación** del pico. Si la serie termina
    sin recuperarse, se cuenta hasta el último día: un drawdown no recuperado no
    es un drawdown de duración cero.
    """
    if not len(equity):
        return 0.0, 0
    eq = equity.to_numpy()
    peak = np.maximum.accumulate(eq)
    max_dd = float((eq / peak - 1.0).min())

    en_pico = np.flatnonzero(eq >= peak)
    # Días transcurridos desde el inicio. Vía TimedeltaIndex.days porque no
    # depende de la unidad interna del índice (pandas 3 usa microsegundos, no
    # nanosegundos) ni pierde la zona horaria.
    dias = (equity.index - equity.index[0]).days.to_numpy()
    hitos = np.concatenate(([dias[0]], dias[en_pico], [dias[-1]]))
    longest = int(np.diff(hitos).max()) if len(hitos) > 1 else 0
    return max_dd, longest


def _metrics(
    returns: pd.Series,
    equity: pd.Series,
    position: pd.Series,
    turnover: pd.Series,
    trades: pd.DataFrame,
) -> dict:
    n_days = len(returns)
    ann = config.TRADING_DAYS_PER_YEAR
    years = n_days / ann if n_days else np.nan

    total_return = float(equity.iloc[-1] - 1.0) if n_days else 0.0
    cagr = float((1.0 + total_return) ** (1.0 / years) - 1.0) if years and years > 0 else np.nan

    sd = float(returns.std(ddof=1)) if n_days > 1 else 0.0
    vol = sd * np.sqrt(ann)
    mean = float(returns.mean()) if n_days else 0.0
    sharpe = mean / sd * np.sqrt(ann) if sd > 0 else 0.0

    downside = returns[returns < 0]
    dsd = float(downside.std(ddof=1)) if len(downside) > 1 else 0.0
    sortino = mean / dsd * np.sqrt(ann) if dsd > 0 else 0.0

    max_dd, dd_days = _drawdown(equity)

    if len(trades):
        wins = trades.loc[trades["ret"] > 0, "ret"]
        losses = trades.loc[trades["ret"] < 0, "ret"]
        hit_rate = float(len(wins) / len(trades))
        profit_factor = (
            float(wins.sum() / abs(losses.sum())) if len(losses) and losses.sum() != 0
            else (np.inf if len(wins) else np.nan)
        )
    else:
        hit_rate, profit_factor = np.nan, np.nan

    return {
        "total_return": total_return,
        "cagr": cagr,
        "volatility": vol,
        "sharpe": sharpe,
        "sortino": sortino,
        "max_drawdown": max_dd,
        "max_drawdown_days": dd_days,
        "hit_rate": hit_rate,
        "profit_factor": profit_factor,
        "n_trades": int(len(trades)),
        "exposure": float((position > 0).mean()) if n_days else 0.0,
        "avg_position": float(position.mean()) if n_days else 0.0,
        "turnover_per_year": float(turnover.sum() / years) if years and years > 0 else np.nan,
        "n_days": n_days,
    }


# ---------------------------------------------------------------------------
# Diagnóstico de lag (regla 2)
# ---------------------------------------------------------------------------
def run_lag_variants(
    prices: pd.DataFrame, signal: pd.Series, lags: tuple[int, ...] | None = None
) -> dict[int, BacktestResult]:
    """Corre la misma señal con varios lags. El oficial es `config.OFFICIAL_LAG`.

    Diagnóstico, no resultado: si el alpha existe con lag 1 y se evapora con lag 2,
    lo que se había encontrado era un artefacto de un día, no una ventaja.
    """
    lags = config.LAG_VARIANTS if lags is None else lags
    return {lag: run(prices, signal, lag=lag) for lag in lags}


def lag_decay(results: dict[int, BacktestResult]) -> float:
    """Sharpe(lag oficial) / Sharpe(lag 1). Criterio C10: ≥ 0,70."""
    s1 = results[1].metrics["sharpe"]
    s_off = results[config.OFFICIAL_LAG].metrics["sharpe"]
    if s1 == 0:
        return np.nan
    return s_off / s1
