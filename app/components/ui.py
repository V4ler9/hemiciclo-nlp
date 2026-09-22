"""Cliente HTTP y utilidades compartidas del dashboard Streamlit (Fase 5)."""

from __future__ import annotations

from typing import Any

import pandas as pd
import requests

DEFAULT_TIMEOUT = 30


def api_get(base_url: str, path: str, params: dict[str, Any] | None = None) -> Any:
    """GET contra la API con error legible si el servicio no responde."""
    response = requests.get(f"{base_url.rstrip('/')}{path}", params=params, timeout=DEFAULT_TIMEOUT)
    response.raise_for_status()
    return response.json()


def records_to_frame(records: Any) -> pd.DataFrame:
    """Convierte una lista de registros JSON en DataFrame (vacío si no hay)."""
    if not records:
        return pd.DataFrame()
    return pd.DataFrame.from_records(records)
