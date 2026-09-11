"""Funciones auxiliares compartidas."""

from __future__ import annotations

import importlib
from typing import Any


def import_optional(module_name: str) -> Any:
    """Importa en tiempo de ejecución un módulo pesado y opcional.

    Mantiene las dependencias de los extras (`nlp`, `analysis`) fuera del arranque
    del paquete y de los tests unitarios (D-30).
    """
    return importlib.import_module(module_name)
