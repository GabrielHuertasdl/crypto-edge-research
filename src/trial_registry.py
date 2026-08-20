"""Registro persistente de configuraciones evaluadas (regla 4).

Sin esto, el Deflated Sharpe es decorativo: el DSR necesita `N` (cuántas
configuraciones se probaron) y `Var(SR)` (cuánto varía el Sharpe entre ellas). Si
`N` se estima "de memoria" al final del proyecto, siempre sale más bajo de lo que
fue, y el DSR sale más alto de lo que debe.

Reglas de este módulo:

  - Se escribe **en el momento de evaluar**, no al final. Un proceso que muere a
    mitad deja igualmente registradas las configuraciones que ya había probado.
  - Es **append-only**. No hay API para borrar ni editar. Una exploración
    abandonada, un experimento fallido y un barrido que no llevó a nada cuentan
    exactamente igual que la ganadora.
  - Una misma configuración evaluada dos veces se registra dos veces, marcada como
    repetición. Para el DSR cuenta una sola (`n_unique_trials`), pero la
    repetición queda visible: reevaluar es una forma de buscar sin declararlo.
"""

from __future__ import annotations

import csv
import json
import os
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src import config

FIELDS = [
    "ts_utc", "trial_id", "config_hash", "repeat_of",
    "strategy", "params_json", "asset", "split", "lag",
    "sharpe", "total_return", "max_drawdown", "n_trades", "n_days",
    "outcome", "notes",
]

OUTCOMES = {"kept", "discarded", "error", "exploration"}


@dataclass
class TrialRegistry:
    """Diario append-only de configuraciones evaluadas."""

    path: Path = field(default_factory=lambda: config.TRIALS_LOG)

    def __post_init__(self) -> None:
        self.path = Path(self.path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            with self.path.open("w", newline="", encoding="utf-8") as fh:
                csv.DictWriter(fh, fieldnames=FIELDS).writeheader()
        self._seen: dict[str, str] = {}
        for row in self.read().itertuples():
            self._seen.setdefault(row.config_hash, row.trial_id)

    # -- escritura --------------------------------------------------------
    @staticmethod
    def config_hash(strategy: str, params: dict, asset: str, split: str, lag: int) -> str:
        payload = json.dumps(
            {"s": strategy, "p": params, "a": asset, "sp": split, "l": lag},
            sort_keys=True, default=str,
        )
        return sha256(payload.encode()).hexdigest()[:16]

    def log(
        self,
        strategy: str,
        params: dict,
        asset: str,
        split: str,
        metrics: dict | None = None,
        lag: int | None = None,
        outcome: str = "exploration",
        notes: str = "",
    ) -> str:
        """Registra una evaluación y devuelve su `trial_id`. Escribe y cierra."""
        if outcome not in OUTCOMES:
            raise ValueError(f"outcome debe ser uno de {sorted(OUTCOMES)}")
        lag = config.OFFICIAL_LAG if lag is None else lag
        m = metrics or {}
        h = self.config_hash(strategy, params, asset, split, lag)
        trial_id = f"{h}-{os.getpid():d}-{datetime.now(timezone.utc).timestamp():.6f}"

        row = {
            "ts_utc": datetime.now(timezone.utc).isoformat(),
            "trial_id": trial_id,
            "config_hash": h,
            "repeat_of": self._seen.get(h, ""),
            "strategy": strategy,
            "params_json": json.dumps(params, sort_keys=True, default=str),
            "asset": asset,
            "split": split,
            "lag": lag,
            "sharpe": m.get("sharpe", ""),
            "total_return": m.get("total_return", ""),
            "max_drawdown": m.get("max_drawdown", ""),
            "n_trades": m.get("n_trades", ""),
            "n_days": m.get("n_days", ""),
            "outcome": outcome,
            "notes": notes,
        }
        with self.path.open("a", newline="", encoding="utf-8") as fh:
            csv.DictWriter(fh, fieldnames=FIELDS).writerow(row)
            fh.flush()
            os.fsync(fh.fileno())
        self._seen.setdefault(h, trial_id)
        return trial_id

    # -- lectura ----------------------------------------------------------
    def read(self) -> pd.DataFrame:
        df = pd.read_csv(self.path, dtype={"repeat_of": str, "notes": str})
        return df.fillna({"repeat_of": "", "notes": ""})

    def n_trials(self, split: str | None = None) -> int:
        """Total de evaluaciones, repeticiones incluidas. Es el número honesto."""
        df = self.read()
        if split is not None:
            df = df[df["split"] == split]
        return int(len(df))

    def n_unique_trials(self, split: str | None = None) -> int:
        """Configuraciones distintas. Es el `N` que entra en el DSR."""
        df = self.read()
        if split is not None:
            df = df[df["split"] == split]
        return int(df["config_hash"].nunique())

    def sharpes(self, split: str | None = None, unique: bool = True) -> np.ndarray:
        """Sharpes anualizados registrados, para `Var(SR)` del DSR."""
        df = self.read()
        if split is not None:
            df = df[df["split"] == split]
        df = df[pd.to_numeric(df["sharpe"], errors="coerce").notna()]
        if unique:
            df = df.drop_duplicates(subset="config_hash", keep="first")
        return pd.to_numeric(df["sharpe"]).to_numpy(dtype=float)

    def sharpe_variance(self, split: str | None = None) -> float:
        s = self.sharpes(split)
        return float(np.var(s, ddof=1)) if len(s) > 1 else 0.0

    def summary(self) -> dict:
        df = self.read()
        return {
            "n_trials": len(df),
            "n_unique": int(df["config_hash"].nunique()) if len(df) else 0,
            "n_repeats": int((df["repeat_of"] != "").sum()) if len(df) else 0,
            "by_outcome": df["outcome"].value_counts().to_dict() if len(df) else {},
            "by_split": df["split"].value_counts().to_dict() if len(df) else {},
        }
