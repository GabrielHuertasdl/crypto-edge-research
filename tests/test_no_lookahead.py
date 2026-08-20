"""Regla 2 — test automático de lookahead.

Idea: desplazar las series de entrada y comprobar que las señales y los resultados
se desplazan exactamente igual. Si un indicador mira al futuro, el desplazamiento
no cuadra y el test falla.
"""

import pytest

pytestmark = pytest.mark.skip(reason="Fase 2 — pendiente")


def test_placeholder():
    ...
