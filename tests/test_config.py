"""Las reglas innegociables son numéricas. Si alguien las cambia, esto falla."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src import config


def test_costes_exactos():
    assert config.COMMISSION_PER_SIDE == 0.0010
    assert config.SLIPPAGE_PER_TRADE == 0.0005
    assert config.COST_PER_TURN == 0.0015


def test_sin_apalancamiento():
    assert (config.MIN_POSITION, config.MAX_POSITION) == (0.0, 1.0)


def test_ejecucion_al_cierre_de_t_mas_1():
    """En 24/7 el open de t+1 es el cierre de t: ejecutar al open no retarda nada."""
    assert config.EXECUTION_LAG_DAYS == 1
    assert config.EXECUTION_PRICE == "close"
    assert config.RETURN_LAG_TOTAL == 2


def test_splits_no_se_solapan_y_cubren_desde_2015():
    train, val, lock = (config.SPLITS[k] for k in ("train", "validation", "lockbox"))
    assert train[0] == "2015-01-01"
    assert train[1] < val[0] < val[1] < lock[0]
    assert lock[1] is None  # hasta el último dato disponible


def test_reparto_de_activos():
    assert config.OPTIMIZATION_ASSETS == ("BTC", "ETH")
    assert config.CROSS_ASSET_TEST_ASSETS == ("SOL", "LTC")
    assert set(config.OPTIMIZATION_ASSETS) & set(config.CROSS_ASSET_TEST_ASSETS) == set()
    assert config.ASSETS == config.OPTIMIZATION_ASSETS + config.CROSS_ASSET_TEST_ASSETS


def test_fuentes_de_datos():
    """Coinbase ejecuta, yfinance solo vigila. Si esto se invierte, hay que decirlo."""
    assert config.EXECUTION_SOURCE == "coinbaseexchange"
    assert config.ANOMALY_SOURCE == "yfinance"
    assert config.CROSS_CHECK_TOLERANCE == 0.02


def test_cpcv_configurado():
    assert config.CPCV_N_GROUPS > config.CPCV_N_TEST_GROUPS >= 2
    assert 0 < config.CPCV_EMBARGO_PCT < 0.1


def test_nulidad_por_block_bootstrap():
    assert config.N_SYNTHETIC_PATHS >= 1000
    assert config.BOOTSTRAP_MEAN_BLOCK_DAYS >= 5
