"""Fase 4 — CPCV purgado, robustez y prueba de nulidad.

  - `cpcv_splits()`: Combinatorial Purged Cross-Validation (López de Prado).
    N=6 bloques contiguos, k=2 de test -> C(6,2)=15 combinaciones. Cada bloque de
    test se **purga** (fuera las observaciones de entrenamiento cuyo horizonte
    solape con el test) y lleva **embargo** del 1 % de la muestra después, para
    matar la fuga por autocorrelación en la frontera.
    Sustituye al walk-forward de una pasada: TRAIN es corto y un walk-forward
    simple deja demasiado pocos pliegues. Además el PBO está definido sobre este
    esquema combinatorio, no sobre una división única.
  - `parameter_sensitivity()`: una estrategia buena no puede depender de que el
    periodo sea 14 y no 13. Mide la meseta, no el pico.
  - `cross_asset_stability()`: SOL y LTC nunca entran en la optimización, así que
    para ellos esto es 100 % fuera de muestra.
  - `subperiod_breakdown()`: separa 2018 y 2022 (bajistas) de 2020-21 y 2023-24,
    según `config.SUBPERIODS`. Incluye obligatoriamente el desglose 2015-2017 vs
    resto: si el alpha se concentra en la era pre-CME, va a la conclusión.
  - `block_bootstrap_null()`: stationary block bootstrap (Politis & Romano 1994)
    sobre los retornos reales, bloque geométrico de media 20 días. Conserva colas
    gruesas y agrupamiento de volatilidad; destruye solo la dependencia serial que
    la estrategia dice explotar. Un paseo aleatorio gaussiano sería un rival de
    paja.
"""

from __future__ import annotations

raise NotImplementedError("Fase 4 — pendiente")
