"""Configuración central del proyecto: semilla, rutas y carga de YAML."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

SEED: int = 42

PROJECT_ROOT: Path = Path(__file__).resolve().parents[2]
CONFIG_DIR: Path = PROJECT_ROOT / "configs"
DATA_DIR: Path = PROJECT_ROOT / "data"
REPORTS_DIR: Path = PROJECT_ROOT / "reports"
DEFAULT_CONFIG_PATH: Path = CONFIG_DIR / "default.yaml"


def load_config(path: Path | None = None) -> dict[str, Any]:
    """Carga la configuración YAML indicada.

    Por defecto carga ``configs/default.yaml``.
    """
    config_path = path if path is not None else DEFAULT_CONFIG_PATH
    with config_path.open(encoding="utf-8") as handle:
        config: dict[str, Any] = yaml.safe_load(handle)
    return config
