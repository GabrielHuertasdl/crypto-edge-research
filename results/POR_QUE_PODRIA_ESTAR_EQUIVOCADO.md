# Por qué esto podría estar equivocado

Registro vivo. Se le añaden entradas según avanzan las fases, **incluidas las que
debilitan las conclusiones**. Va entero a la sección homónima de `INFORME.md`.

---

## D1 · El mercado de 2015-2017 no es el mercado de hoy
*Añadido en fase 0 (a priori) · confirmado con datos en fase 1.*

Sin futuros regulados (CME entra en dic-2017), sin ETF al contado, sin creadores de
mercado profesionales, exchanges quebrando y base de participantes casi
íntegramente minorista. Cualquier tendencia explotable entonces puede llevar años
arbitrada.

**Evidencia empírica de fase 1**: Coinbase y yfinance discrepan más de un 2 % en el
cierre en 118 días de 2017 solo para LTC (37 en BTC, 9 en ETH). En 2022-2026 esas
discrepancias prácticamente desaparecen. Si dos fuentes no se ponen de acuerdo en
cuál era el precio, un backtest de ese periodo depende de qué fuente elijas, y el
alpha medido ahí no es alpha: es fragmentación de mercado.

**Obligatorio**: desglosar rendimiento por régimen. Si el alpha se concentra en
2015-2017, decirlo en la conclusión y tratar la estrategia como no validada para
hoy.

## D2 · TRAIN es corto y hay un solo ciclo completo dentro
*Fase 1.*

TRAIN útil: BTC 1.992 velas (5,5 años), ETH 1.683 (4,6 años). Dentro caben un ciclo
alcista (2017), uno bajista (2018) y medio alcista (2020). Eso son ~3 regímenes
independientes, no 1.992 observaciones independientes. El tamaño muestral efectivo
para juzgar una estrategia de seguimiento de tendencia es de un solo dígito.

CPCV con purging mitiga la fuga entre pliegues, pero no fabrica ciclos que no
existen.

## D3 · SOL no tiene TRAIN en absoluto
*Fase 1.*

Coinbase lista SOL el 2021-06-17. Su TRAIN tiene 0 velas. Es un test cross-asset
fuerte (todo fuera de muestra) pero también significa que SOL solo cubre 2021-2026:
un bajista (2022) y dos alcistas. No aporta un régimen pre-2018.

## D4 · Los cuatro activos no son observaciones independientes
*Fase 1.*

BTC, ETH, SOL y LTC comparten factor de mercado con correlaciones diarias altas.
"Funciona en cuatro activos" pesa mucho menos de lo que parece: está más cerca de
"funciona en uno" que de "funciona en cuatro". Habrá que reportar la correlación
entre curvas de equity de la misma estrategia en distintos activos antes de contar
la estabilidad cross-asset como evidencia.
