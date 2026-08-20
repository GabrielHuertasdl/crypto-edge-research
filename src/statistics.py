"""Corrección por comparaciones múltiples (regla 4).

  - `log_trial()`: registra CADA configuración probada en `results/trials_log.csv`,
    incluidas las descartadas. Ese contador entra en el informe y alimenta el DSR.
  - `deflated_sharpe_ratio()`: Bailey & López de Prado (2014). Descuenta el Sharpe
    observado por el número de pruebas, el sesgo (skew) y la curtosis de los
    retornos.
  - `probability_of_backtest_overfitting()`: PBO por CSCV (Bailey et al., 2015).
    Probabilidad de que la configuración mejor en in-sample quede por debajo de la
    mediana en out-of-sample.
"""

from __future__ import annotations

raise NotImplementedError("Fase 4 — pendiente")
