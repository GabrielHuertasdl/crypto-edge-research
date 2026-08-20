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

## D5 · Sesgo de supervivencia en la selección de activos
*Fase 2.*

BTC, ETH, SOL y LTC están elegidos **porque siguen existiendo y cotizando en
Coinbase en 2026**. Ninguno es una muestra aleatoria del universo cripto de 2015:
son los que sobrevivieron.

El universo real de entonces incluía cientos de activos que hoy no cotizan, no
tienen liquidez o directamente desaparecieron con su exchange. Una estrategia de
seguimiento de tendencia probada solo sobre supervivientes hereda un sesgo obvio:
mantener la posición funciona muy bien cuando se sabe de antemano que el activo no
va a morir. Las estrategias de "comprar la caída" y de reversión a la media son las
más contaminadas por esto — la caída siempre se recupera... en los que
sobrevivieron.

Nota adicional: el propio listado en Coinbase es un filtro de calidad aplicado con
información posterior. SOL entra en 2021-06 **porque ya se había convertido en un
activo relevante**; en 2020 no habría estado en la lista.

No hay forma limpia de corregir esto con los datos disponibles: reconstruir el
universo delistado requiere históricos de exchanges que ya no existen. Se declara
como limitación, se evita cualquier lectura de "funciona en todo el mercado", y
refuerza la necesidad de la validación fuera de cripto (oro, S&P 500, divisas),
donde el sesgo de supervivencia del activo es mucho menor.

## D6 · Más caminos CPCV no son más regímenes
*Fase 2.*

Se ha subido a N=10 grupos (9 caminos frente a los 5 de N=6) para que el PBO se
estime sobre más caminos. Eso mejora la **estimación**, no la **evidencia**.

Los 9 caminos se construyen con los mismos 1.992 días y los mismos ~3 ciclos de
mercado. Comparten datos por construcción. Si el proyecto acaba diciendo "válido en
9 caminos CPCV", eso hay que leerlo como "válido en 3 regímenes, medido 9 veces",
no como 9 pruebas independientes.

## D7 · El purgado protege contra la fuga mecánica, no contra la memoria del que investiga
*Fase 2.*

El purgado derivado del lookback elimina el solape de ventanas entre entrenamiento
y test. No elimina que quien diseña las estrategias ya ha visto la historia de
BTC: sabe que 2018 y 2022 fueron bajistas y que 2020-21 fue alcista. Cualquier
elección de familia de estrategias está condicionada por ese conocimiento previo, y
ningún esquema de validación cruzada lo corrige.

Mitigación parcial: el contador de trials incluye las estrategias descartadas, y el
universo de la fase 3 se fija por familias clásicas documentadas en la literatura
**antes** de mirar resultados, no por lo que parezca prometedor sobre la marcha.
