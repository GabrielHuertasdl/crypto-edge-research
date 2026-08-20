# Fase 1 — Calidad de datos

Serie de **ejecución**: Coinbase Exchange (ccxt). yfinance solo como
detector de anomalías (umbral 2% sobre cierres).
Los huecos no se imputan entre fuentes: mezclar precios mete retornos falsos.

## Resumen

| activo | rol | inicio | fin | velas | TRAIN | VAL | LOCK | huecos | dif>2% |
|---|---|---|---|---:|---:|---:|---:|---:|---:|
| BTC | optimización | 2015-07-20 | 2026-08-20 | 4050 | 1992 | 1095 | 963 | 0 | 65 |
| ETH | optimización | 2016-05-18 | 2026-08-20 | 3745 | 1683 | 1095 | 963 | 2 | 40 |
| SOL | test cross-asset | 2021-06-17 | 2026-08-20 | 1891 | 0 | 928 | 963 | 0 | 3 |
| LTC | test cross-asset | 2016-08-17 | 2026-08-20 | 3655 | 1592 | 1095 | 963 | 1 | 171 |


## BTC  (optimización)

- Coinbase: 4050 velas, 2015-07-20 → 2026-08-20
- yfinance: 4356 velas, 2014-09-17 → 2026-08-20
- Serie procesada: 4050 velas, 2015-07-20 → 2026-08-20  (sin recorte)
- Splits: TRAIN 1992 · VALIDATION 1095 · LOCKBOX 963
- Duplicados: 0 · fuera de 00:00 UTC: 0
- Incoherencias OHLC: —
- Precios <= 0: —
- Huecos (0): —
- Volumen cero (0): —
- Velas planas O=H=L=C (0): —
- Outliers |log-ret| > 40% (1): 2020-03-12 (-49.1%)
- Discrepancias vs yfinance > 2%: **65**

| fecha | Coinbase | yfinance | dif. rel. |
|---|---:|---:|---:|
| 2017-09-04 | 4,498.25 | 4,236.31 | 6.18% |
| 2015-08-18 | 221.99 | 211.08 | 5.17% |
| 2016-06-20 | 703.12 | 737.23 | 4.63% |
| 2017-09-17 | 3,719.97 | 3,582.88 | 3.83% |
| 2021-12-14 | 48,367.43 | 46,612.63 | 3.76% |
| 2017-04-23 | 1,251.98 | 1,207.21 | 3.71% |
| 2017-05-28 | 2,232.78 | 2,155.80 | 3.57% |
| 2020-03-18 | 5,413.64 | 5,238.44 | 3.34% |
| 2017-04-29 | 1,365.43 | 1,321.79 | 3.30% |
| 2017-06-25 | 2,505.61 | 2,589.41 | 3.24% |
| 2017-11-30 | 9,903.00 | 10,233.60 | 3.23% |
| 2017-05-26 | 2,272.70 | 2,202.42 | 3.19% |
| 2017-09-10 | 4,251.36 | 4,122.94 | 3.11% |
| 2017-09-14 | 3,250.40 | 3,154.95 | 3.03% |
| 2017-05-27 | 2,099.99 | 2,038.87 | 3.00% |
| … | | | (+50 más) |

## ETH  (optimización)

- Coinbase: 3745 velas, 2016-05-18 → 2026-08-20
- yfinance: 3207 velas, 2017-11-09 → 2026-08-20
- Serie procesada: 3741 velas, 2016-05-24 → 2026-08-20  (recortadas 4 velas de arranque: huecos/velas planas tras el listado)
- Splits: TRAIN 1683 · VALIDATION 1095 · LOCKBOX 963
- Duplicados: 0 · fuera de 00:00 UTC: 0
- Incoherencias OHLC: —
- Precios <= 0: —
- Huecos (2): 2016-05-21, 2016-05-22
- Volumen cero (0): —
- Velas planas O=H=L=C (0): —
- Outliers |log-ret| > 40% (1): 2020-03-12 (-56.8%)
- Discrepancias vs yfinance > 2%: **40**

| fecha | Coinbase | yfinance | dif. rel. |
|---|---:|---:|---:|
| 2021-11-25 | 4,525.87 | 4,274.74 | 5.87% |
| 2017-12-12 | 686.82 | 651.43 | 5.43% |
| 2018-01-06 | 1,006.68 | 1,041.68 | 3.36% |
| 2017-12-25 | 740.50 | 765.83 | 3.31% |
| 2020-03-18 | 118.60 | 114.84 | 3.27% |
| 2018-01-04 | 949.00 | 980.92 | 3.25% |
| 2021-12-14 | 3,860.74 | 3,745.44 | 3.08% |
| 2018-01-07 | 1,118.30 | 1,153.17 | 3.02% |
| 2019-02-24 | 131.76 | 135.85 | 3.01% |
| 2017-12-27 | 739.99 | 762.84 | 3.00% |
| 2018-11-24 | 110.16 | 113.49 | 2.94% |
| 2017-12-21 | 796.98 | 821.06 | 2.93% |
| 2017-11-30 | 434.00 | 447.11 | 2.93% |
| 2018-12-06 | 89.09 | 91.76 | 2.91% |
| 2018-01-05 | 969.27 | 997.72 | 2.85% |
| … | | | (+25 más) |

## SOL  (test cross-asset)

- Coinbase: 1891 velas, 2021-06-17 → 2026-08-20
- yfinance: 2324 velas, 2020-04-10 → 2026-08-20
- Serie procesada: 1891 velas, 2021-06-17 → 2026-08-20  (sin recorte)
- Splits: TRAIN 0 · VALIDATION 928 · LOCKBOX 963
- Duplicados: 0 · fuera de 00:00 UTC: 0
- Incoherencias OHLC: —
- Precios <= 0: —
- Huecos (0): —
- Volumen cero (0): —
- Velas planas O=H=L=C (0): —
- Outliers |log-ret| > 40% (1): 2022-11-09 (-55.5%)
- Discrepancias vs yfinance > 2%: **3**

| fecha | Coinbase | yfinance | dif. rel. |
|---|---:|---:|---:|
| 2021-12-14 | 161.38 | 153.34 | 5.24% |
| 2021-11-24 | 205.69 | 214.92 | 4.30% |
| 2021-06-23 | 30.84 | 30.05 | 2.63% |

## LTC  (test cross-asset)

- Coinbase: 3655 velas, 2016-08-17 → 2026-08-20
- yfinance: 4356 velas, 2014-09-17 → 2026-08-20
- Serie procesada: 3650 velas, 2016-08-23 → 2026-08-20  (recortadas 5 velas de arranque: huecos/velas planas tras el listado)
- Splits: TRAIN 1592 · VALIDATION 1095 · LOCKBOX 963
- Duplicados: 0 · fuera de 00:00 UTC: 0
- Incoherencias OHLC: —
- Precios <= 0: —
- Huecos (1): 2016-08-20
- Volumen cero (0): —
- Velas planas O=H=L=C (2): 2016-08-21, 2016-08-22
- Outliers |log-ret| > 40% (4): 2017-03-30 (+60.7%), 2017-12-12 (+47.7%), 2020-03-12 (-47.8%), 2021-05-19 (-45.5%)
- Discrepancias vs yfinance > 2%: **171**

| fecha | Coinbase | yfinance | dif. rel. |
|---|---:|---:|---:|
| 2017-04-05 | 13.00 | 11.09 | 17.18% |
| 2017-03-30 | 7.89 | 6.98 | 13.03% |
| 2017-04-14 | 11.61 | 10.39 | 11.74% |
| 2017-12-12 | 352.08 | 316.16 | 11.36% |
| 2016-08-19 | 4.00 | 3.60 | 10.99% |
| 2017-04-10 | 9.87 | 8.92 | 10.69% |
| 2016-08-21 | 4.00 | 3.62 | 10.65% |
| 2017-04-01 | 7.61 | 6.88 | 10.55% |
| 2017-04-04 | 9.15 | 8.29 | 10.38% |
| 2017-04-23 | 15.38 | 13.94 | 10.34% |
| 2017-04-22 | 14.35 | 13.06 | 9.84% |
| 2017-04-11 | 9.71 | 8.85 | 9.67% |
| 2017-09-10 | 67.44 | 61.61 | 9.46% |
| 2017-09-04 | 71.29 | 65.21 | 9.33% |
| 2017-09-14 | 45.42 | 41.58 | 9.22% |
| … | | | (+156 más) |
