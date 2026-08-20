"""Fase 1 — Descarga, caché en disco, validación de integridad y splits temporales.

Contrato:
  - `load(asset)` devuelve un DataFrame diario UTC con columnas
    [open, high, low, close, volume], índice `DatetimeIndex` en UTC con frontera de
    vela a 00:00, sin duplicados y sin huecos.
  - La descarga va a `data/raw/` una sola vez. Ejecuciones posteriores leen de
    disco salvo `force_refresh=True`.
  - `split(df, "train"|"validation"|"lockbox")` corta según `config.SPLITS`.
    Nadie corta fechas a mano en otro módulo.

Fuentes (regla 6-bis):
  - Coinbase Exchange vía ccxt = **serie de ejecución**. Todo precio operado sale
    de aquí.
  - yfinance = **solo detector de anomalías**. Se comparan cierres y se registra
    toda diferencia > 2 %. Nunca alimenta un backtest.
"""

from __future__ import annotations

import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src import config

OHLCV_COLS = ["open", "high", "low", "close", "volume"]

# Umbral de retorno diario absoluto por encima del cual la vela se marca para
# revisión manual. No se borra nada automáticamente: cripto tiene días de ±40 %
# que son reales.
OUTLIER_ABS_LOG_RETURN = 0.40


# ---------------------------------------------------------------------------
# Descarga
# ---------------------------------------------------------------------------
def _raw_path(asset: str, source: str) -> Path:
    return config.DATA_RAW / f"{asset}_{source}_1d.csv"


def _processed_path(asset: str) -> Path:
    return config.DATA_PROCESSED / f"{asset}_1d.csv"


def download_coinbase(asset: str, force_refresh: bool = False) -> pd.DataFrame:
    """OHLCV diario de Coinbase Exchange, paginado hacia adelante desde 2015.

    Coinbase devuelve ~100-300 velas por petición y no admite rangos abiertos, así
    que se pagina avanzando el cursor. Se cachea en disco: la descarga completa
    tarda minutos y no se repite en cada ejecución.
    """
    import ccxt

    path = _raw_path(asset, "coinbase")
    if path.exists() and not force_refresh:
        return _read_cached(path)

    ex = ccxt.coinbaseexchange({"enableRateLimit": True})
    symbol = config.COINBASE_SYMBOLS[asset]
    day_ms = 86_400_000
    cursor = ex.parse8601("2015-01-01T00:00:00Z")
    now_ms = ex.milliseconds()

    rows: list[list] = []
    stall = 0
    while cursor < now_ms:
        try:
            batch = ex.fetch_ohlcv(symbol, config.TIMEFRAME, since=cursor, limit=300)
        except Exception as exc:  # red inestable / rate limit: reintento acotado
            stall += 1
            if stall > 5:
                raise RuntimeError(f"{asset}: fallo repetido descargando Coinbase: {exc}") from exc
            time.sleep(2 * stall)
            continue

        if not batch:
            # Hueco real o zona anterior al listado: salta 300 días y sigue.
            cursor += 300 * day_ms
            continue

        rows.extend(batch)
        last = batch[-1][0]
        cursor = max(last + day_ms, cursor + day_ms)
        stall = 0

    if not rows:
        raise RuntimeError(f"{asset}: Coinbase no devolvió ninguna vela para {symbol}")

    df = pd.DataFrame(rows, columns=["ts"] + OHLCV_COLS)
    df["date"] = pd.to_datetime(df["ts"], unit="ms", utc=True)
    df = df.drop(columns="ts").set_index("date").sort_index()
    df = df[~df.index.duplicated(keep="first")]

    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path)
    return df


def download_yfinance(asset: str, force_refresh: bool = False) -> pd.DataFrame:
    """Serie de referencia para el cross-check. NO se opera con ella."""
    import yfinance as yf

    path = _raw_path(asset, "yfinance")
    if path.exists() and not force_refresh:
        return _read_cached(path)

    raw = yf.Ticker(config.YFINANCE_TICKERS[asset]).history(
        period="max", interval="1d", auto_adjust=False
    )
    if raw.empty:
        raise RuntimeError(f"{asset}: yfinance no devolvió datos")

    raw.index = pd.to_datetime(raw.index, utc=True)
    df = raw.rename(columns=str.lower)[OHLCV_COLS].sort_index()
    df = df[~df.index.duplicated(keep="first")]

    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path)
    return df


def _read_cached(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path, index_col=0, parse_dates=True)
    df.index = pd.to_datetime(df.index, utc=True)
    df.index.name = "date"
    return df[OHLCV_COLS].sort_index()


# ---------------------------------------------------------------------------
# Integridad
# ---------------------------------------------------------------------------
@dataclass
class IntegrityReport:
    asset: str
    source: str
    n_rows: int
    start: pd.Timestamp
    end: pd.Timestamp
    duplicated_dates: int = 0
    missing_days: list[str] = field(default_factory=list)
    zero_volume_days: list[str] = field(default_factory=list)
    flat_candles: list[str] = field(default_factory=list)
    ohlc_violations: list[str] = field(default_factory=list)
    nonpositive_prices: list[str] = field(default_factory=list)
    outliers: list[tuple[str, float]] = field(default_factory=list)
    not_utc_midnight: int = 0

    @property
    def is_fatal(self) -> bool:
        """Problemas que impiden usar la serie. Los outliers y el volumen cero no
        lo son: en cripto son reales y se documentan, no se borran."""
        return bool(
            self.duplicated_dates
            or self.ohlc_violations
            or self.nonpositive_prices
            or self.not_utc_midnight
        )


def validate_integrity(df: pd.DataFrame, asset: str, source: str) -> IntegrityReport:
    """Huecos, duplicados, volumen cero, velas planas, incoherencias OHLC y
    outliers. Documenta; no arregla en silencio."""
    rep = IntegrityReport(
        asset=asset, source=source, n_rows=len(df), start=df.index[0], end=df.index[-1]
    )

    rep.duplicated_dates = int(df.index.duplicated().sum())

    # Convención horaria: todo a 00:00 UTC (regla 6-bis / test_utc_convention).
    idx = df.index
    rep.not_utc_midnight = int(
        ((idx.hour != 0) | (idx.minute != 0) | (idx.second != 0)).sum()
    )

    full = pd.date_range(df.index[0], df.index[-1], freq="D", tz="UTC")
    rep.missing_days = [d.strftime("%Y-%m-%d") for d in full.difference(df.index)]

    vol = df["volume"]
    rep.zero_volume_days = [
        d.strftime("%Y-%m-%d") for d in df.index[(vol == 0) | vol.isna()]
    ]

    flat = (df["open"] == df["high"]) & (df["high"] == df["low"]) & (df["low"] == df["close"])
    rep.flat_candles = [d.strftime("%Y-%m-%d") for d in df.index[flat]]

    bad = (
        (df["high"] < df[["open", "close"]].max(axis=1))
        | (df["low"] > df[["open", "close"]].min(axis=1))
        | (df["high"] < df["low"])
    )
    rep.ohlc_violations = [d.strftime("%Y-%m-%d") for d in df.index[bad]]

    nonpos = (df[["open", "high", "low", "close"]] <= 0).any(axis=1)
    rep.nonpositive_prices = [d.strftime("%Y-%m-%d") for d in df.index[nonpos]]

    logret = np.log(df["close"]).diff()
    big = logret.abs() > OUTLIER_ABS_LOG_RETURN
    rep.outliers = [
        (d.strftime("%Y-%m-%d"), float(logret.loc[d])) for d in df.index[big.fillna(False)]
    ]
    return rep


def cross_check(exec_df: pd.DataFrame, ref_df: pd.DataFrame) -> pd.DataFrame:
    """Compara cierres Coinbase vs yfinance. Devuelve solo las fechas con
    discrepancia relativa > `config.CROSS_CHECK_TOLERANCE`."""
    joined = pd.DataFrame(
        {"coinbase": exec_df["close"], "yfinance": ref_df["close"]}
    ).dropna()
    joined["rel_diff"] = (joined["coinbase"] - joined["yfinance"]).abs() / joined["yfinance"]
    flagged = joined[joined["rel_diff"] > config.CROSS_CHECK_TOLERANCE].copy()
    return flagged.sort_values("rel_diff", ascending=False)


# ---------------------------------------------------------------------------
# Serie procesada y splits
# ---------------------------------------------------------------------------
def trim_listing_artifacts(df: pd.DataFrame) -> pd.DataFrame:
    """Recorta el arranque sucio de la serie.

    Los primeros días tras el listado de un par traen huecos de calendario y velas
    planas (O=H=L=C): el libro aún no tiene profundidad y el exchange no genera
    vela algunos días. Un hueco convierte un retorno de 1 día en uno de 3, y una
    vela plana es un precio congelado, no un precio.

    Se corta en la primera fecha a partir de la cual el calendario es contiguo y
    no quedan velas planas. Cuesta unos pocos días al principio de TRAIN y evita
    retornos falsos. No se toca nada más allá de ese punto.
    """
    flat = (df["open"] == df["high"]) & (df["high"] == df["low"]) & (df["low"] == df["close"])
    gaps = df.index.to_series().diff() > pd.Timedelta(days=1)
    bad = flat | gaps
    if not bad.any():
        return df
    last_bad = df.index[bad][-1]
    return df.loc[df.index > last_bad]


def build_processed(asset: str, force_refresh: bool = False) -> pd.DataFrame:
    """Serie final de ejecución: Coinbase, sin rellenar huecos con datos ajenos.

    Los huecos NO se imputan desde yfinance: mezclar dos fuentes de precio dentro
    de la misma serie mete saltos artificiales que el motor leería como retornos.
    Un hueco se propaga como tal y se documenta.
    """
    df = download_coinbase(asset, force_refresh=force_refresh).copy()
    df = df[~df.index.duplicated(keep="first")].sort_index()
    df = df[OHLCV_COLS].astype(float)
    df = trim_listing_artifacts(df)
    _processed_path(asset).parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(_processed_path(asset))
    return df


def load(asset: str) -> pd.DataFrame:
    """Serie de ejecución lista para el motor. Construye la caché si falta."""
    path = _processed_path(asset)
    if not path.exists():
        return build_processed(asset)
    return _read_cached(path)


def split(df: pd.DataFrame, name: str) -> pd.DataFrame:
    """Corta por `config.SPLITS`. Único sitio del proyecto donde se cortan fechas."""
    if name not in config.SPLITS:
        raise KeyError(f"Split desconocido: {name!r}. Válidos: {list(config.SPLITS)}")
    start, end = config.SPLITS[name]
    lo = pd.Timestamp(start, tz="UTC")
    hi = pd.Timestamp(end, tz="UTC") if end else df.index[-1]
    return df.loc[lo:hi]


# ---------------------------------------------------------------------------
# Fase 1 — informe de calidad de datos
# ---------------------------------------------------------------------------
def _fmt_list(items: list, limit: int = 12) -> str:
    if not items:
        return "—"
    shown = ", ".join(str(x) for x in items[:limit])
    return shown if len(items) <= limit else f"{shown} … (+{len(items) - limit} más)"


def run_phase1(force_refresh: bool = False) -> str:
    """Descarga, valida, cross-checkea y escribe `results/data_quality.md`."""
    lines: list[str] = [
        "# Fase 1 — Calidad de datos",
        "",
        "Serie de **ejecución**: Coinbase Exchange (ccxt). yfinance solo como",
        f"detector de anomalías (umbral {config.CROSS_CHECK_TOLERANCE:.0%} sobre cierres).",
        "Los huecos no se imputan entre fuentes: mezclar precios mete retornos falsos.",
        "",
    ]
    summary_rows = []

    for asset in config.ASSETS:
        cb = download_coinbase(asset, force_refresh=force_refresh)
        yfd = download_yfinance(asset, force_refresh=force_refresh)
        rep_cb = validate_integrity(cb, asset, "coinbase")
        rep_yf = validate_integrity(yfd, asset, "yfinance")
        flagged = cross_check(cb, yfd)
        proc = build_processed(asset, force_refresh=False)
        trimmed = rep_cb.n_rows - len(proc)

        role = "optimización" if asset in config.OPTIMIZATION_ASSETS else "test cross-asset"
        n_train = len(split(proc, "train"))
        n_val = len(split(proc, "validation"))
        n_lock = len(split(proc, "lockbox"))
        summary_rows.append(
            f"| {asset} | {role} | {rep_cb.start:%Y-%m-%d} | {rep_cb.end:%Y-%m-%d} | "
            f"{rep_cb.n_rows} | {n_train} | {n_val} | {n_lock} | "
            f"{len(rep_cb.missing_days)} | {len(flagged)} |"
        )

        lines += [
            f"## {asset}  ({role})",
            "",
            f"- Coinbase: {rep_cb.n_rows} velas, {rep_cb.start:%Y-%m-%d} → {rep_cb.end:%Y-%m-%d}",
            f"- yfinance: {rep_yf.n_rows} velas, {rep_yf.start:%Y-%m-%d} → {rep_yf.end:%Y-%m-%d}",
            f"- Serie procesada: {len(proc)} velas, {proc.index[0]:%Y-%m-%d} → {proc.index[-1]:%Y-%m-%d}"
            + (f"  (recortadas {trimmed} velas de arranque: huecos/velas planas tras el listado)"
               if trimmed else "  (sin recorte)"),
            f"- Splits: TRAIN {n_train} · VALIDATION {n_val} · LOCKBOX {n_lock}",
            f"- Duplicados: {rep_cb.duplicated_dates} · fuera de 00:00 UTC: {rep_cb.not_utc_midnight}",
            f"- Incoherencias OHLC: {_fmt_list(rep_cb.ohlc_violations)}",
            f"- Precios <= 0: {_fmt_list(rep_cb.nonpositive_prices)}",
            f"- Huecos ({len(rep_cb.missing_days)}): {_fmt_list(rep_cb.missing_days)}",
            f"- Volumen cero ({len(rep_cb.zero_volume_days)}): {_fmt_list(rep_cb.zero_volume_days)}",
            f"- Velas planas O=H=L=C ({len(rep_cb.flat_candles)}): {_fmt_list(rep_cb.flat_candles)}",
            f"- Outliers |log-ret| > {OUTLIER_ABS_LOG_RETURN:.0%} ({len(rep_cb.outliers)}): "
            + _fmt_list([f"{d} ({r:+.1%})" for d, r in rep_cb.outliers], limit=10),
            f"- Discrepancias vs yfinance > {config.CROSS_CHECK_TOLERANCE:.0%}: **{len(flagged)}**",
            "",
        ]
        if len(flagged):
            lines.append("| fecha | Coinbase | yfinance | dif. rel. |")
            lines.append("|---|---:|---:|---:|")
            for d, row in flagged.head(15).iterrows():
                lines.append(
                    f"| {d:%Y-%m-%d} | {row['coinbase']:,.2f} | {row['yfinance']:,.2f} "
                    f"| {row['rel_diff']:.2%} |"
                )
            if len(flagged) > 15:
                lines.append(f"| … | | | (+{len(flagged) - 15} más) |")
            lines.append("")

    header = [
        "| activo | rol | inicio | fin | velas | TRAIN | VAL | LOCK | huecos | dif>2% |",
        "|---|---|---|---|---:|---:|---:|---:|---:|---:|",
    ]
    lines = lines[:5] + ["", "## Resumen", ""] + header + summary_rows + [""] + lines[5:]

    out = config.RESULTS / "data_quality.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines), encoding="utf-8")
    return "\n".join(summary_rows)


if __name__ == "__main__":
    print(run_phase1(force_refresh="--refresh" in sys.argv))
