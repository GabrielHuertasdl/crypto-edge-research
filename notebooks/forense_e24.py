"""Forense de la cartera conjunta de E2.4 (informe §6.1-§6.3).

Recalcula, sobre los backtests externos ya ejecutados:
  - curtosis bruta, recortada al 1 % y concentración del cuarto momento;
  - mercados vivos por sesión;
  - SE del Sharpe por bootstrap frente al ingenuo, con y sin octubre de 1987;
  - reparto de la varianza por mercado, equiponderado y ponderado por riesgo;
  - N_eff de las 19 configuraciones y N_eff transversal de los mercados.

No reoptimiza nada ni toca el lockbox: es diagnóstico sobre resultados existentes.
Escribe `results/e24_forense.csv`.
"""
from __future__ import annotations

import json
import pickle
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats as sps

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src import config  # noqa: E402

config.TRADING_DAYS_PER_YEAR = config.EXTERNAL_TRADING_DAYS_PER_YEAR  # 252, como en E2.4
from src.statistics import effective_number_of_trials, sharpe_confidence_interval  # noqa: E402

CACHE = Path(sys.argv[1] if len(sys.argv) > 1 else "ext.pkl")  # dict {mercado: {clave: BacktestResult}}


def conjunta(ext, keys, k, idx):
    return pd.DataFrame({m: ext[m][k].returns.reindex(idx) for m in ext}).mean(axis=1)


def main() -> None:
    ext = pickle.load(open(CACHE, "rb"))
    keys = [(n, json.dumps(p, sort_keys=True)) for n, p, _ in json.load(open(CACHE.with_name("frozen.json")))]
    idx = None
    for m in ext:
        i = ext[m][keys[0]].returns.index
        idx = i if idx is None else idx.union(i)

    vivos = pd.DataFrame({m: ext[m][keys[0]].returns.reindex(idx).notna() for m in ext}).sum(axis=1)
    print("mercados vivos por sesión:\n", vivos.value_counts().sort_index(), "\nmedia:", vivos.mean())

    oct87 = (idx >= pd.Timestamp("1987-10-01", tz="UTC")) & (idx <= pd.Timestamp("1987-10-31", tz="UTC"))
    ingenuo = np.sqrt(config.TRADING_DAYS_PER_YEAR / len(idx))
    sd = {m: ext[m]["r"].reindex(idx).rolling(252, min_periods=60).std().shift(1) for m in ext}
    inv = (1.0 / pd.DataFrame(sd)).where(pd.DataFrame(sd) > 0)

    filas = []
    for k in keys:
        panel = pd.DataFrame({m: ext[m][k].returns.reindex(idx) for m in ext})
        v = panel.mean(axis=1).dropna()
        x = v.values
        lo, hi = np.quantile(x, [0.01, 0.99])
        z = ((x - x.mean()) / x.std(ddof=1)) ** 4
        z = z / z.sum()
        orden = np.argsort(-z)
        ci = sharpe_confidence_interval(x, seed=config.SEED)
        v87 = panel[~oct87].mean(axis=1).dropna().values
        ci87 = sharpe_confidence_interval(v87, seed=config.SEED)
        w = inv.where(panel.notna())
        w = w.div(w.sum(axis=1), axis=0)
        rp = (panel.fillna(0.0) * w.fillna(0.0)).sum(axis=1).where(panel.notna().any(axis=1)).dropna()
        cuota = {m: np.cov(panel[m].fillna(0.0).reindex(v.index), v)[0, 1] for m in ext}
        tot = sum(cuota.values())
        filas.append(
            {
                "estrategia": k[0],
                "params": k[1],
                "sharpe": ci.point,
                "se_boot": (ci.hi - ci.lo) / (2 * 1.959964),
                "se_boot_sobre_ingenuo": (ci.hi - ci.lo) / (2 * 1.959964) / ingenuo,
                "se_boot_sin_oct87_sobre_ingenuo": (ci87.hi - ci87.lo) / (2 * 1.959964) / ingenuo,
                "curtosis": sps.kurtosis(x, fisher=False, bias=False),
                "curtosis_recortada_1pct": sps.kurtosis(x[(x >= lo) & (x <= hi)], fisher=False, bias=False),
                "curtosis_sin_oct87": sps.kurtosis(v87, fisher=False, bias=False),
                "dias_para_50pct_m4": int(np.searchsorted(np.cumsum(z[orden]), 0.5) + 1),
                "cuota_3_peores_dias": z[orden][:3].sum(),
                "frac_dias_no_nulos": float((v != 0).mean()),
                "sharpe_riesgo_ex_ante": rp.mean() / rp.std(ddof=1) * np.sqrt(config.TRADING_DAYS_PER_YEAR),
                **{f"var_{m}": cuota[m] / tot for m in ext},
            }
        )
    tabla = pd.DataFrame(filas)
    salida = Path(__file__).resolve().parents[1] / "results" / "e24_forense.csv"
    tabla.to_csv(salida, index=False)

    M = pd.DataFrame({k: conjunta(ext, keys, k, idx) for k in keys}).fillna(0.0).values
    print("N_eff de las 19 configuraciones:", round(effective_number_of_trials(M), 3))
    bh = pd.DataFrame({m: ext[m]["r"].reindex(idx) for m in ext}).dropna()
    print("N_eff transversal de los 4 mercados:", round(effective_number_of_trials(bh.values), 3))
    print(tabla.to_string(index=False))


if __name__ == "__main__":
    main()
