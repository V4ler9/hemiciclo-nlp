"""API FastAPI de hemiciclo-nlp (Fase 5).

Sirve como JSON los artefactos precalculados de las fases 1-3: tópicos y
etiquetas, series mensuales, cambios de régimen, eventos, anexo de sensibilidad
y validación de sentimiento. No ejecuta modelos: lee artefactos locales y es
apta para ejecutarse en local o en el contenedor de ``compose.yaml``.

Los directorios de datos e informes se pueden sustituir en los tests mediante
``create_app``. Si un artefacto no existe, el endpoint responde 503 con un
mensaje explícito en lugar de fallar con un error interno.
"""

# pyright: reportUnusedFunction=false
# Las funciones-ruta se registran mediante decoradores, no por referencia directa.

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import pandas as pd
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from src.utils.config import PROJECT_ROOT

DATA_DIR = PROJECT_ROOT / "data"
REPORTS_DIR = PROJECT_ROOT / "reports"

GRID_PARAMS = ("min_topic_size", "n_neighbors", "min_samples")
SENTIMENT_FILES = (
    ("revision_metricas", "validacion_sentimiento_revision_metricas.csv"),
    ("revision_ic", "validacion_sentimiento_revision_ic.csv"),
    ("acuerdo_3bandas", "validacion_sentimiento_acuerdo_3bandas.csv"),
    ("concordancia_llm", "validacion_sentimiento_concordancia_llm_metricas.csv"),
)


def _records(frame: pd.DataFrame) -> list[dict[str, Any]]:
    """Convierte un DataFrame en registros JSON (fechas ISO, NaN como null)."""
    payload: list[dict[str, Any]] = json.loads(frame.to_json(orient="records", date_format="iso"))
    return payload


def _load_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise HTTPException(status_code=503, detail=f"Artefacto no disponible: {path.name}")
    return pd.read_csv(path)


def _load_parquet(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise HTTPException(status_code=503, detail=f"Artefacto no disponible: {path.name}")
    return pd.read_parquet(path)


def _optional_csv(path: Path) -> pd.DataFrame | None:
    return pd.read_csv(path) if path.exists() else None


def create_app(reports_dir: Path | None = None, data_dir: Path | None = None) -> FastAPI:
    """Crea la aplicación FastAPI apuntando a los artefactos indicados."""
    reports = reports_dir or REPORTS_DIR
    data = data_dir or DATA_DIR
    tables = reports / "tables"

    app = FastAPI(
        title="hemiciclo-nlp API",
        version="0.1.0",
        description="Evolución temática y tonal del Congreso de los Diputados (2015-2023).",
    )

    allowed_origins = [
        origin.strip()
        for origin in os.environ.get("HEMICICLO_ALLOWED_ORIGINS", "http://localhost:3000").split(
            ","
        )
        if origin.strip()
    ]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_methods=["GET"],
        allow_headers=["*"],
    )

    @app.get("/health")
    def health() -> dict[str, str]:
        """Comprobación de disponibilidad."""
        return {"status": "ok"}

    @app.get("/meta")
    def meta() -> dict[str, Any]:
        """Resumen del corpus, la rejilla y el modelo de tópicos final."""
        assignments = _load_parquet(data / "processed" / "intervenciones_topicos.parquet")
        selection = _load_csv(tables / "topics_selection.csv")
        selected = selection.loc[selection["selected"].astype(bool)]
        if selected.empty:
            raise HTTPException(
                status_code=503, detail="La rejilla no tiene combinación seleccionada"
            )
        best = selected.iloc[0]
        is_outlier = assignments["is_outlier"].astype(bool)
        return {
            "intervenciones": len(assignments),
            "topicos": int(assignments.loc[~is_outlier, "bertopic_topic"].nunique()),
            "tasa_outliers": round(float(is_outlier.mean()), 6),
            "rejilla_seleccionada": {key: int(best[key]) for key in GRID_PARAMS},
            "coherencia_cv": float(best["coherence"]),
            "diversidad": float(best["diversity"]),
        }

    @app.get("/topics")
    def topics() -> list[dict[str, Any]]:
        """Tópicos con etiqueta, tamaño y términos principales."""
        evidence = _load_csv(tables / "topics_evidence.csv")
        labels = _optional_csv(tables / "topics_labels.csv")
        frame = evidence.copy()
        if labels is not None:
            frame = frame.merge(
                labels.loc[:, ["topic", "label", "description", "reviewed_by"]],
                on="topic",
                how="left",
            )
        columns = ["topic", "size", "share", "top_terms", "label", "description", "reviewed_by"]
        return _records(frame.reindex(columns=columns))

    @app.get("/topics/selection")
    def topics_selection() -> list[dict[str, Any]]:
        """Rejilla completa de combinaciones probadas y regla de selección (D-32)."""
        return _records(_load_csv(tables / "topics_selection.csv"))

    @app.get("/topics/{topic_id}")
    def topic_detail(topic_id: int) -> dict[str, Any]:
        """Detalle de un tópico: términos y documentos representativos."""
        evidence = _load_csv(tables / "topics_evidence.csv")
        row = evidence.loc[evidence["topic"] == topic_id]
        if row.empty:
            raise HTTPException(status_code=404, detail=f"Tópico {topic_id} no encontrado")
        record = _records(row)[0]
        record["representative_utterance_ids"] = str(
            record.get("representative_utterance_ids", "")
        ).split("; ")
        record["representative_texts"] = str(record.get("representative_texts", "")).split(" || ")
        labels = _optional_csv(tables / "topics_labels.csv")
        if labels is not None:
            match = labels.loc[labels["topic"] == topic_id]
            if not match.empty:
                record["label"] = str(match.iloc[0]["label"])
                record["description"] = str(match.iloc[0]["description"])
        return record

    @app.get("/series")
    def series(
        series_type: str = Query(..., description="topic, tone, tone_weighted, outliers o volume"),
        series_id: str | None = Query(default=None),
    ) -> list[dict[str, Any]]:
        """Serie mensual en formato largo, filtrada por tipo e identificador."""
        frame = _load_parquet(data / "intermediate" / "series_mensuales.parquet")
        subset = frame.loc[frame["series_type"] == series_type]
        if series_id is not None:
            subset = subset.loc[subset["series_id"].astype(str) == series_id]
        if subset.empty:
            raise HTTPException(status_code=404, detail="Serie no encontrada")
        return _records(subset.sort_values("month"))

    @app.get("/changes")
    def changes(
        serie: str = Query(..., description="'topic' o 'tone'"),
        serie_id: str | None = Query(default=None),
    ) -> list[dict[str, Any]]:
        """Puntos de cambio de una serie (PELT; D-28 y D-38)."""
        frame = _load_csv(tables / "cambios_regimen.csv")
        subset = frame.loc[frame["serie"] == serie]
        if serie_id is not None:
            subset = subset.loc[subset["serie_id"].astype(str) == serie_id]
        return _records(subset.sort_values("fecha"))

    @app.get("/changes/sensitivity")
    def changes_sensitivity(
        serie: str | None = Query(default=None),
        serie_id: str | None = Query(default=None),
    ) -> list[dict[str, Any]]:
        """Sensibilidad de la penalización de PELT por serie."""
        frame = _load_csv(tables / "cambios_regimen_sensibilidad.csv")
        if serie is not None:
            frame = frame.loc[frame["serie"] == serie]
        if serie_id is not None:
            frame = frame.loc[frame["serie_id"].astype(str) == serie_id]
        return _records(frame)

    @app.get("/changes/stats")
    def changes_stats(
        serie: str | None = Query(default=None),
        serie_id: str | None = Query(default=None),
        max_q: float | None = Query(default=None),
    ) -> list[dict[str, Any]]:
        """Estadísticos por cambio (Mann-Whitney antes/después con BH)."""
        frame = _load_csv(tables / "cambios_regimen_test.csv")
        if serie is not None:
            frame = frame.loc[frame["serie"] == serie]
        if serie_id is not None:
            frame = frame.loc[frame["serie_id"].astype(str) == serie_id]
        if max_q is not None:
            frame = frame.loc[frame["q"].astype(float) <= max_q]
        return _records(frame.sort_values("fecha"))

    @app.get("/events")
    def events() -> list[dict[str, Any]]:
        """Tabla de eventos usada en el contraste (espejo versionado, D-13)."""
        return _records(_load_csv(tables / "eventos.csv"))

    @app.get("/events/relations")
    def event_relations(
        serie: str | None = Query(default=None),
        serie_id: str | None = Query(default=None),
        max_q: float | None = Query(default=None),
    ) -> list[dict[str, Any]]:
        """Asociaciones exploratorias evento-serie (Spearman + BH; D-09)."""
        frame = _load_csv(tables / "eventos_relaciones.csv")
        if serie is not None:
            frame = frame.loc[frame["serie"] == serie]
        if serie_id is not None:
            frame = frame.loc[frame["serie_id"].astype(str) == serie_id]
        if max_q is not None:
            frame = frame.loc[frame["q"].astype(float) <= max_q]
        return _records(frame)

    @app.get("/sensitivity")
    def sensitivity() -> list[dict[str, Any]]:
        """Anexo de robustez de embeddings e5 frente a bge-m3 (D-39)."""
        return _records(_load_csv(tables / "sensibilidad_embeddings.csv"))

    @app.get("/sentiment")
    def sentiment() -> dict[str, list[dict[str, Any]]]:
        """Métricas de la validación humana de sentimiento (D-36 y D-37)."""
        payload: dict[str, list[dict[str, Any]]] = {}
        for name, filename in SENTIMENT_FILES:
            frame = _optional_csv(tables / filename)
            payload[name] = [] if frame is None else _records(frame)
        return payload

    @app.get("/sentiment/confusion/{level}")
    def sentiment_confusion(level: str) -> dict[str, Any]:
        """Matriz de confusión por nivel (``senti_3`` o ``senti_6``)."""
        if level not in {"senti_3", "senti_6"}:
            raise HTTPException(status_code=404, detail="Nivel no soportado")
        path = tables / f"validacion_sentimiento_revision_confusion_{level}.csv"
        if not path.exists():
            raise HTTPException(status_code=503, detail=f"Artefacto no disponible: {path.name}")
        frame = pd.read_csv(path, index_col=0)
        return {
            "nivel": level,
            "index": [str(value) for value in frame.index],
            "columns": [str(value) for value in frame.columns],
            "values": [[int(value) for value in row] for row in frame.to_numpy().tolist()],
        }

    return app


app = create_app()
