"""Exporta holdings actuales a data/holdings.json."""
from __future__ import annotations
import json
from pathlib import Path
from datetime import datetime

import pandas as pd

HOLDINGS_PATH = Path(__file__).resolve().parent.parent / "data" / "holdings.json"


def export_holdings(ph: pd.DataFrame, fx_rate: float) -> None:
    if ph.empty:
        return
    snapshot = {
        "updated_at": datetime.now().isoformat(timespec="seconds"),
        "fx_rate_usdclp": round(fx_rate, 2),
        "total_market_value_usd": round(float(ph["market_value_usd"].sum()), 2),
        "total_cost_basis_usd": round(float(ph["cost_basis_usd"].sum()), 2),
        "total_unrealized_usd": round(float(ph["unrealized_usd"].sum()), 2),
        "positions": ph.to_dict(orient="records"),
    }
    HOLDINGS_PATH.write_text(json.dumps(snapshot, indent=2, ensure_ascii=False), encoding="utf-8")
