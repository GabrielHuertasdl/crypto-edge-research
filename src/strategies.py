"""Fase 3 — Universo de estrategias.

Contrato: una estrategia es una función pura `(df, **params) -> Series` de
exposición en [0, 1] con el mismo índice que `df`. No conoce costes, ni retardo,
ni splits: de eso se encarga `backtest.py`. Una estrategia que desplaza por su
cuenta desplaza dos veces.

**La tesis económica es requisito de entrada, no documentación posterior.** Cada
`StrategySpec` declara quién te paga y por qué. Las que no tienen mecanismo
identificable llevan `thesis=None` y salen marcadas SIN TESIS en el informe. Están
en el universo a propósito: sirven de control: si una estrategia sin mecanismo
puntúa como las demás, lo que mide el proyecto es capacidad de ajuste, no ventaja.

Campos `lookback` y `warmup`, y por qué son distintos:

  - `lookback`: la ventana más larga que consulta la señal. Alimenta el purgado
    del CPCV.
  - `warmup`: los días que la estrategia necesita para reconstruir su ESTADO al
    entrar en un bloque de test. Una ruptura de Donchian de 55 días puede
    mantener la posición seis meses; su lookback es 55 y su calentamiento tiene
    que cubrir la duración típica de la posición. Las estrategias con estado
    declaran múltiplos de su ventana; las sin estado igualan lookback.

Prioridad de familias (por D2, pocos ciclos independientes en cripto): se
prefieren las que generan muchas observaciones cuasi-independientes. Con ~3 ciclos
disponibles, una estrategia de 20 operaciones no llega ni al mínimo de C4.
"""

from __future__ import annotations

import sys
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from itertools import product
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src import config, indicators as ind


# ---------------------------------------------------------------------------
# Contrato
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class StrategySpec:
    name: str
    signal: Callable[..., pd.Series]
    param_grid: dict[str, list]
    lookback: Callable[[dict], int]
    thesis: str | None
    warmup: Callable[[dict], int] | None = None
    family: str = "sin clasificar"

    @property
    def has_thesis(self) -> bool:
        return bool(self.thesis and self.thesis.strip())

    def warmup_for(self, params: dict) -> int:
        base = int(self.lookback(params))
        return base if self.warmup is None else int(max(self.warmup(params), base))

    def needs_external_validation(self, params: dict) -> bool:
        """E2.4: con lookback o calentamiento largos, cripto no da para validar y
        el conjunto primario pasa a ser oro / S&P / divisas."""
        return (
            self.lookback(params) >= config.EXTERNAL_REQUIRED_LOOKBACK
            or self.warmup_for(params) >= config.EXTERNAL_REQUIRED_WARMUP
        )

    def grid(self) -> Iterator[dict]:
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


def _state(entrada: pd.Series, salida: pd.Series) -> pd.Series:
    """Máquina de estados entrar/salir con arrastre hacia delante.

    Si entrada y salida coinciden el mismo día gana la salida: ante la duda, fuera
    del mercado. `ffill` propaga el pasado, nunca el futuro.
    """
    s = pd.Series(np.nan, index=entrada.index)
    s[entrada.fillna(False)] = 1.0
    s[salida.fillna(False)] = 0.0
    return s.ffill().fillna(0.0)


# ---------------------------------------------------------------------------
# Familia: seguimiento de tendencia
# ---------------------------------------------------------------------------
TESIS_TENDENCIA = (
    "Quién te paga: los que tienen que vender cuando el precio baja y comprar "
    "cuando sube por razones ajenas al valor — liquidaciones de posiciones "
    "apalancadas, reembolsos de fondos, coberturas obligatorias, y los "
    "asignadores que persiguen rentabilidad reciente. El seguidor de tendencia "
    "les da la contrapartida y cobra por asumir el riesgo de que la tendencia se "
    "gire de golpe: paga muchas pérdidas pequeñas para cobrar pocas ganancias "
    "grandes. Es la prima documentada durante décadas en futuros gestionados. "
    "Riesgo declarado: en cripto el número de ciclos independientes es de un "
    "dígito (D2), así que la evidencia LOCAL es débil aunque la familia tenga "
    "buen respaldo fuera."
)


def sma_cross(df, fast, slow):
    r, l = ind.sma(df["close"], fast), ind.sma(df["close"], slow)
    return (r > l).astype(float).where(l.notna(), 0.0)


def ema_cross(df, fast, slow):
    r, l = ind.ema(df["close"], fast), ind.ema(df["close"], slow)
    return (r > l).astype(float).where(l.notna(), 0.0)


def price_vs_sma(df, n):
    m = ind.sma(df["close"], n)
    return (df["close"] > m).astype(float).where(m.notna(), 0.0)


def ts_momentum(df, n):
    m = ind.roc(df["close"], n)
    return (m > 0).astype(float).where(m.notna(), 0.0)


def ma_slope(df, n):
    p = ind.slope(df["close"], n)
    return (p > 0).astype(float).where(p.notna(), 0.0)


def macd_cross(df, fast, slow, signal_n):
    macd = ind.ema(df["close"], fast) - ind.ema(df["close"], slow)
    linea = ind.ema(macd.dropna(), signal_n).reindex(df.index)
    return (macd > linea).astype(float).where(linea.notna(), 0.0)


def donchian_breakout(df, n_in, n_out):
    canal_alto = ind.donchian(df, n_in)["upper"]
    canal_bajo = ind.donchian(df, n_out)["lower"]
    return _state(df["close"] > canal_alto, df["close"] < canal_bajo)


def donchian_atr_stop(df, n_in, atr_n, atr_mult):
    canal = ind.donchian(df, n_in)["upper"]
    a = ind.atr(df, atr_n)
    entrada = df["close"] > canal
    # Salida por volatilidad: el precio cae más de `atr_mult` ATR desde el máximo
    # de cierre reciente. Todo con datos hasta t.
    techo = df["close"].rolling(n_in, min_periods=n_in).max()
    salida = df["close"] < techo - atr_mult * a
    return _state(entrada, salida)


def breakout_volume_confirmed(df, n, vol_n, vol_mult):
    canal = ind.donchian(df, n)["upper"]
    media_vol = df["volume"].rolling(vol_n, min_periods=vol_n).mean()
    entrada = (df["close"] > canal) & (df["volume"] > vol_mult * media_vol)
    salida = df["close"] < ind.donchian(df, n)["lower"]
    return _state(entrada, salida)


# ---------------------------------------------------------------------------
# Familia: reversión a la media
# ---------------------------------------------------------------------------
TESIS_REVERSION = (
    "Quién te paga: el vendedor impaciente. Tras una caída brusca hay "
    "liquidaciones forzosas de posiciones apalancadas que tienen que ejecutarse "
    "ya, al precio que sea, contra un libro que se ha vaciado. Quien compra ahí "
    "está proveyendo liquidez y cobra por ello, igual que un creador de mercado. "
    "El riesgo que asume es real y es el motivo del pago: a veces la caída no es "
    "ruido sino información, y comprarla sale carísimo. Riesgo declarado: es la "
    "familia más contaminada por el sesgo de supervivencia (D5) — la caída "
    "siempre se recupera en los activos que sobrevivieron."
)


def rsi_oversold(df, n, umbral_entrada, umbral_salida):
    r = ind.rsi(df["close"], n)
    return _state(r < umbral_entrada, r > umbral_salida)


def bollinger_reversion(df, n, k):
    b = ind.bollinger(df["close"], n, k)
    return _state(df["close"] < b["lower"], df["close"] > b["mid"])


def zscore_reversion(df, n, umbral):
    z = ind.zscore(df["close"], n)
    return _state(z < -umbral, z > 0)


def n_down_days(df, n, salida_dias):
    bajadas = (df["close"].diff() < 0).rolling(n, min_periods=n).sum()
    entrada = bajadas >= n
    subidas = (df["close"].diff() > 0).rolling(salida_dias, min_periods=salida_dias).sum()
    return _state(entrada, subidas >= salida_dias)


# ---------------------------------------------------------------------------
# Familia: volatilidad
# ---------------------------------------------------------------------------
TESIS_VOLATILIDAD = (
    "Quién te paga: el inversor que no puede apalancarse. Al no poder pedir "
    "prestado, compra el activo más volátil para alcanzar la rentabilidad que "
    "necesita, y eso encarece sistemáticamente lo volátil y abarata lo tranquilo "
    "(betting against beta, Frazzini y Pedersen). Además la volatilidad se agrupa "
    "y es predecible a un día vista, mientras que el signo del retorno no lo es: "
    "escalar la exposición con la volatilidad reciente mejora el retorno ajustado "
    "al riesgo sin necesidad de predecir la dirección. Riesgo declarado: escalar "
    "por volatilidad mejora el Sharpe pero no crea retorno donde no lo hay, y en "
    "cripto obliga a rotar mucho, así que es de las familias más expuestas a que "
    "los costes se coman la mejora."
)


def vol_target(df, n, objetivo, maximo):
    v = ind.realized_vol(df["close"], n)
    exposicion = (objetivo / v).clip(0.0, maximo)
    return exposicion.fillna(0.0).clip(0.0, 1.0)


def low_vol_filter(df, n, ventana_mediana):
    v = ind.realized_vol(df["close"], n)
    mediana = v.rolling(ventana_mediana, min_periods=ventana_mediana).median()
    return (v < mediana).astype(float).where(mediana.notna(), 0.0)


def vol_expansion_breakout(df, n_vol, n_trend, mult):
    v = ind.realized_vol(df["close"], n_vol)
    base = v.rolling(n_trend, min_periods=n_trend).median()
    tendencia = df["close"] > ind.sma(df["close"], n_trend)
    entrada = (v > mult * base) & tendencia
    return _state(entrada, ~tendencia)


# ---------------------------------------------------------------------------
# Familia: filtros de régimen y combinaciones
# ---------------------------------------------------------------------------
TESIS_REGIMEN = (
    "Quién te paga: los mismos que en tendencia o en reversión. No es una prima "
    "nueva: es la misma, con un "
    "filtro que apaga la estrategia en el régimen donde su mecanismo no aplica. "
    "Riesgo declarado: "
    "La reversión a la media cobra por dar liquidez, pero en un mercado bajista "
    "estructural el que vende no es un impaciente sino alguien informado, y el "
    "pago desaparece. El filtro de régimen no añade ventaja: intenta no operar "
    "cuando no la hay. Riesgo declarado: cada filtro es un parámetro más y una "
    "vía más de sobreajuste, y por eso el número de intentos se registra entero."
)


def trend_with_vol_filter(df, n_trend, n_vol, percentil):
    tendencia = df["close"] > ind.sma(df["close"], n_trend)
    v = ind.realized_vol(df["close"], n_vol)
    techo = v.rolling(252, min_periods=252).quantile(percentil)
    return (tendencia & (v < techo)).astype(float).where(techo.notna(), 0.0)


def rsi_reversion_in_uptrend(df, n_rsi, umbral, n_trend):
    r = ind.rsi(df["close"], n_rsi)
    alcista = df["close"] > ind.sma(df["close"], n_trend)
    return _state((r < umbral) & alcista, (r > 50) | ~alcista)


def donchian_vol_targeted(df, n_in, n_out, n_vol, objetivo):
    estado = donchian_breakout(df, n_in, n_out)
    v = ind.realized_vol(df["close"], n_vol)
    escala = (objetivo / v).clip(0.0, 1.0).fillna(0.0)
    return (estado * escala).clip(0.0, 1.0)


def momentum_with_dd_stop(df, n, max_dd):
    señal = ts_momentum(df, n)
    equity = (1 + df["close"].pct_change().fillna(0.0) * señal.shift(1).fillna(0.0)).cumprod()
    dd = equity / equity.cummax() - 1.0
    return _state(señal.astype(bool) & (dd > -max_dd), dd <= -max_dd)


def trend_above_sma200(df, n_fast, n_regime):
    rapida = df["close"] > ind.sma(df["close"], n_fast)
    regimen = df["close"] > ind.sma(df["close"], n_regime)
    m = ind.sma(df["close"], n_regime)
    return (rapida & regimen).astype(float).where(m.notna(), 0.0)


# ---------------------------------------------------------------------------
# Familia: calendario
# ---------------------------------------------------------------------------
TESIS_FIN_DE_SEMANA = (
    "Quién te paga: el flujo institucional se concentra de lunes a viernes, "
    "mientras que cripto cotiza los siete días con libros mucho más finos el fin "
    "de semana. Quien mantiene posición en ese tramo asume riesgo de hueco sin "
    "poder cubrirse en los mercados tradicionales, que están cerrados, y ese "
    "riesgo debería tener precio. Tesis débil y declarada como tal: el efecto se "
    "ha estrechado desde que existen futuros regulados 24/5 y creadores de "
    "mercado profesionales."
)


def weekend_effect(df, dia_entrada, dias_dentro):
    dow = pd.Series(df.index.dayofweek, index=df.index)
    dentro = pd.Series(0.0, index=df.index)
    for d in range(dias_dentro):
        dentro = dentro.mask(dow == (dia_entrada + d) % 7, 1.0)
    return dentro


def turn_of_month(df, dias_antes, dias_despues):
    dom = pd.Series(df.index.day, index=df.index)
    fin_de_mes = pd.Series(df.index.days_in_month, index=df.index)
    return ((dom > fin_de_mes - dias_antes) | (dom <= dias_despues)).astype(float)


# ---------------------------------------------------------------------------
# Universo
# ---------------------------------------------------------------------------
UNIVERSE: list[StrategySpec] = [
    # --- tendencia ---------------------------------------------------------
    StrategySpec(
        "sma_cross", sma_cross,
        {"fast": [10, 20, 50], "slow": [50, 100, 200]},
        lookback=lambda p: p["slow"], warmup=lambda p: 2 * p["slow"],
        thesis=TESIS_TENDENCIA, family="tendencia",
    ),
    StrategySpec(
        "ema_cross", ema_cross,
        {"fast": [12, 20], "slow": [50, 100, 200]},
        lookback=lambda p: p["slow"], warmup=lambda p: 2 * p["slow"],
        thesis=TESIS_TENDENCIA, family="tendencia",
    ),
    StrategySpec(
        "price_vs_sma", price_vs_sma,
        {"n": [20, 50, 100, 200]},
        lookback=lambda p: p["n"], warmup=lambda p: 2 * p["n"],
        thesis=TESIS_TENDENCIA, family="tendencia",
    ),
    StrategySpec(
        "ts_momentum", ts_momentum,
        {"n": [20, 60, 120, 250]},
        lookback=lambda p: p["n"], warmup=lambda p: 2 * p["n"],
        thesis=TESIS_TENDENCIA, family="tendencia",
    ),
    StrategySpec(
        "ma_slope", ma_slope,
        {"n": [20, 50, 100]},
        lookback=lambda p: 2 * p["n"], warmup=lambda p: 3 * p["n"],
        thesis=TESIS_TENDENCIA, family="tendencia",
    ),
    StrategySpec(
        "macd_cross", macd_cross,
        {"fast": [12], "slow": [26, 50], "signal_n": [9, 18]},
        lookback=lambda p: p["slow"] + p["signal_n"],
        warmup=lambda p: 3 * (p["slow"] + p["signal_n"]),
        thesis=TESIS_TENDENCIA, family="tendencia",
    ),
    StrategySpec(
        "donchian_breakout", donchian_breakout,
        {"n_in": [20, 55, 100], "n_out": [10, 20, 55]},
        lookback=lambda p: max(p["n_in"], p["n_out"]) + 1,
        warmup=lambda p: 6 * max(p["n_in"], p["n_out"]),
        thesis=TESIS_TENDENCIA, family="tendencia",
    ),
    StrategySpec(
        "donchian_atr_stop", donchian_atr_stop,
        {"n_in": [20, 55], "atr_n": [14, 20], "atr_mult": [2.0, 3.0]},
        lookback=lambda p: max(p["n_in"], p["atr_n"]) + 1,
        warmup=lambda p: 6 * p["n_in"],
        thesis=TESIS_TENDENCIA, family="tendencia",
    ),
    StrategySpec(
        "breakout_volume_confirmed", breakout_volume_confirmed,
        {"n": [20, 55], "vol_n": [20, 50], "vol_mult": [1.5, 2.0]},
        lookback=lambda p: max(p["n"], p["vol_n"]) + 1,
        warmup=lambda p: 6 * p["n"],
        thesis=(
            TESIS_TENDENCIA
            + " El filtro de volumen intenta separar la ruptura con participación "
            "real de la que solo refleja un libro vacío."
        ),
        family="tendencia",
    ),
    # --- reversión ---------------------------------------------------------
    StrategySpec(
        "rsi_oversold", rsi_oversold,
        {"n": [7, 14, 21], "umbral_entrada": [20, 30], "umbral_salida": [50, 60]},
        lookback=lambda p: p["n"] + 1, warmup=lambda p: 8 * p["n"],
        thesis=TESIS_REVERSION, family="reversion",
    ),
    StrategySpec(
        "bollinger_reversion", bollinger_reversion,
        {"n": [10, 20, 50], "k": [1.5, 2.0, 2.5]},
        lookback=lambda p: p["n"], warmup=lambda p: 5 * p["n"],
        thesis=TESIS_REVERSION, family="reversion",
    ),
    StrategySpec(
        "zscore_reversion", zscore_reversion,
        {"n": [10, 20, 50], "umbral": [1.0, 1.5, 2.0]},
        lookback=lambda p: p["n"], warmup=lambda p: 5 * p["n"],
        thesis=TESIS_REVERSION, family="reversion",
    ),
    StrategySpec(
        "n_down_days", n_down_days,
        {"n": [2, 3, 4], "salida_dias": [1, 2]},
        lookback=lambda p: p["n"] + 1, warmup=lambda p: 30,
        thesis=TESIS_REVERSION, family="reversion",
    ),
    # --- volatilidad -------------------------------------------------------
    StrategySpec(
        "vol_target", vol_target,
        {"n": [20, 60], "objetivo": [0.30, 0.50, 0.70], "maximo": [1.0]},
        lookback=lambda p: p["n"] + 1, warmup=lambda p: 3 * p["n"],
        thesis=TESIS_VOLATILIDAD, family="volatilidad",
    ),
    StrategySpec(
        "low_vol_filter", low_vol_filter,
        {"n": [20, 60], "ventana_mediana": [120, 250]},
        lookback=lambda p: p["ventana_mediana"] + p["n"],
        warmup=lambda p: 2 * (p["ventana_mediana"] + p["n"]),
        thesis=TESIS_VOLATILIDAD, family="volatilidad",
    ),
    StrategySpec(
        "vol_expansion_breakout", vol_expansion_breakout,
        {"n_vol": [10, 20], "n_trend": [50, 100], "mult": [1.3, 1.8]},
        lookback=lambda p: p["n_trend"] + p["n_vol"],
        warmup=lambda p: 4 * p["n_trend"],
        thesis=TESIS_VOLATILIDAD, family="volatilidad",
    ),
    # --- régimen y combinaciones ------------------------------------------
    StrategySpec(
        "trend_with_vol_filter", trend_with_vol_filter,
        {"n_trend": [50, 100], "n_vol": [20, 60], "percentil": [0.7, 0.9]},
        lookback=lambda p: 252 + p["n_vol"], warmup=lambda p: 400,
        thesis=TESIS_REGIMEN, family="regimen",
    ),
    StrategySpec(
        "rsi_reversion_in_uptrend", rsi_reversion_in_uptrend,
        {"n_rsi": [7, 14], "umbral": [25, 35], "n_trend": [100, 200]},
        lookback=lambda p: p["n_trend"], warmup=lambda p: 3 * p["n_trend"],
        thesis=TESIS_REGIMEN, family="regimen",
    ),
    StrategySpec(
        "donchian_vol_targeted", donchian_vol_targeted,
        {"n_in": [20, 55], "n_out": [10, 20], "n_vol": [20], "objetivo": [0.40, 0.60]},
        lookback=lambda p: max(p["n_in"], p["n_out"], p["n_vol"]) + 1,
        warmup=lambda p: 6 * p["n_in"],
        thesis=TESIS_REGIMEN + " " + TESIS_VOLATILIDAD, family="regimen",
    ),
    StrategySpec(
        "momentum_with_dd_stop", momentum_with_dd_stop,
        {"n": [60, 120], "max_dd": [0.20, 0.35]},
        lookback=lambda p: p["n"], warmup=lambda p: 5 * p["n"],
        thesis=TESIS_REGIMEN, family="regimen",
    ),
    StrategySpec(
        "trend_above_sma200", trend_above_sma200,
        {"n_fast": [20, 50], "n_regime": [150, 200]},
        lookback=lambda p: p["n_regime"], warmup=lambda p: 2 * p["n_regime"],
        thesis=TESIS_REGIMEN, family="regimen",
    ),
    # --- calendario --------------------------------------------------------
    StrategySpec(
        "weekend_effect", weekend_effect,
        {"dia_entrada": [4, 5], "dias_dentro": [2, 3]},
        lookback=lambda p: 1, warmup=lambda p: 10,
        thesis=TESIS_FIN_DE_SEMANA, family="calendario",
    ),
    StrategySpec(
        "turn_of_month", turn_of_month,
        {"dias_antes": [1, 3], "dias_despues": [2, 3]},
        lookback=lambda p: 1, warmup=lambda p: 10,
        thesis=None,   # SIN TESIS, a propósito. Ver nota abajo.
        family="calendario",
    ),
]

# Nota sobre `turn_of_month`: en renta variable el mecanismo son las aportaciones
# periódicas a planes de pensiones y el reequilibrio de fin de mes. Cripto no
# tiene ese calendario institucional, así que no sé escribir quién pagaría el
# efecto. Se queda en el universo como CONTROL: si puntúa igual que las demás,
# lo que el proyecto está midiendo es capacidad de ajuste, no ventaja.


def total_configs() -> int:
    """Cota inferior del número de trials: las exploraciones descartadas suman
    por encima. El valor real sale de `trial_registry`."""
    return sum(s.n_configs() for s in UNIVERSE)


def without_thesis() -> list[str]:
    return [s.name for s in UNIVERSE if not s.has_thesis]


def by_family() -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for s in UNIVERSE:
        out.setdefault(s.family, []).append(s.name)
    return out


def get(name: str) -> StrategySpec:
    for s in UNIVERSE:
        if s.name == name:
            return s
    raise KeyError(f"Estrategia desconocida: {name!r}")
