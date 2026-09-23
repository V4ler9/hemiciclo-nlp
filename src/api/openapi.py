"""Exporta el esquema OpenAPI de la API a JSON para el frontend TypeScript.

``reports/openapi.json`` es el contrato intermedio del que ``frontend/`` genera
sus tipos con ``openapi-typescript`` mediante ``npm run gen:api``. El esquema se
deriva de FastAPI, de modo que la regeneración siempre refleja el estado real de
los endpoints.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from src.api.main import app
from src.utils.config import PROJECT_ROOT

logger = logging.getLogger(__name__)

OPENAPI_PATH = PROJECT_ROOT / "reports" / "openapi.json"


def export_openapi(path: Path = OPENAPI_PATH) -> Path:
    """Vuelca el esquema OpenAPI de la app en ``path`` (UTF-8) y devuelve la ruta."""
    schema = app.openapi()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(schema, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def main() -> None:
    """CLI: genera ``reports/openapi.json`` desde los esquemas de FastAPI."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    destination = export_openapi()
    logger.info("esquema OpenAPI -> %s", destination)


if __name__ == "__main__":
    main()
