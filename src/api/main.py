"""API FastAPI de hemiciclo-nlp (Fase 5).

Sirve como JSON los artefactos precalculados de las fases 1-3: tópicos y
etiquetas, series mensuales, cambios de régimen, eventos, anexo de sensibilidad
y validación de sentimiento. No ejecuta modelos: lee artefactos locales y es
apta para ejecutarse en local o en el contenedor de ``compose.yaml``.

Los directorios de datos e informes se pueden sustituir en los tests mediante
``create_app``. Si un artefacto no existe, el endpoint responde 503 con un
mensaje explícito en lugar de fallar con un error interno.
"""

# pyright: reportUnusedFunction=false, reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false, reportUnknownParameterType=false, reportUnknownLambdaType=false
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
    payload: list[dict[str, Any]] = json.loads(
        frame.to_json(orient="records", date_format="iso") or "[]"
    )
    return payload


def _load_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise HTTPException(status_code=503, detail=f"Artefacto no disponible: {path.name}")
    return pd.read_csv(path)


def _load_parquet(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise HTTPException(status_code=503, detail=f"Artefacto no disponible: {path.name}")
    return pd.read_parquet(path)


def _load_json(path: Path) -> Any:
    if not path.exists():
        raise HTTPException(status_code=503, detail=f"Artefacto no disponible: {path.name}")
    return json.loads(path.read_text(encoding="utf-8"))


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

    @app.get("/home")
    def home() -> dict[str, Any]:
        """Bundle curado de la home editorial (D-45)."""
        meta_payload = meta()
        counterfactual = _load_csv(tables / "tono_contrafactual.csv")
        episodes = _load_json(tables / "episodios_bundle.json")
        actors = _load_csv(tables / "series_actores.csv")
        alignment = _load_csv(tables / "eventos_alineacion.csv")
        changes = _load_csv(tables / "cambios_regimen.csv")
        stats = _load_csv(tables / "cambios_regimen_test.csv")
        labels = _optional_csv(tables / "topics_labels.csv")
        frame = changes.merge(stats, on=["serie", "serie_id", "fecha"], how="left")
        frame = frame.loc[frame["significativo_bh"] == 1].copy()
        frame["topic_num"] = pd.to_numeric(frame["serie_id"], errors="coerce")
        if labels is not None:
            frame = frame.merge(
                labels.loc[:, ["topic", "label"]],
                left_on="topic_num",
                right_on="topic",
                how="left",
            )
        else:
            frame["label"] = None
        frame["label"] = frame["label"].fillna("Tono global")
        frame["impacto"] = (frame["delta"].abs() * frame["tamano_serie"] / frame["n_puntos"]).where(
            frame["serie"] == "topic"
        )
        actors_home = actors.loc[
            (actors["party_status"] == "Todos") & (actors["party_family"] != "Todos")
        ]
        actor_changes = _load_csv(tables / "cambios_regimen_actores.csv")
        actor_changes = actor_changes.loc[
            (actor_changes["nivel"] == "partido")
            & (actor_changes["partido"] != "__residual__")
            & (actor_changes["significativo_bh"].astype(int) == 1)
            & (
                ((actor_changes["serie"] == "topic") & (actor_changes["metrica"] == "cuota_topico"))
                | (
                    (actor_changes["serie"] == "tone")
                    & (actor_changes["metrica"] == "negative_share")
                )
            )
        ]
        tone_dates = frame.loc[frame["serie"] == "tone", "fecha"]
        return {
            "tesis": {
                "titular": "El Congreso cambia a saltos",
                "subtitulo": (
                    "La agenda se mueve por shocks y cambios de legislatura; "
                    "el tono, por quién habla."
                ),
            },
            "kpis": {
                "intervenciones": meta_payload["intervenciones"],
                "topicos": meta_payload["topicos"],
                "cambios_significativos": len(frame),
                "fechas": int(frame["fecha"].nunique()),
                "cambio_tono": str(tone_dates.iloc[0]) if not tone_dates.empty else None,
            },
            "tono": _records(counterfactual.sort_values("month")),
            "episodios": episodes,
            "actores": _records(actors_home.sort_values(["month", "party_family"])),
            "actores_cambio": _records(actor_changes.sort_values(["fecha", "partido"])),
            "eventos": _records(alignment.sort_values(["q", "hipotesis_id"])),
            "cambios": _records(frame.sort_values("fecha")),
            "caveats": [
                "La asociación no es causal: los episodios agrupan eventos que se solapan.",
                "El 32 % de intervenciones queda fuera de los tópicos (outliers de BERTopic).",
                "El tono de 6 clases es poco fiable; la home usa el share negativo.",
            ],
        }

    @app.get("/episodes")
    def episodes() -> list[dict[str, Any]]:
        """Episodios editoriales del MVP con sus fichas y estadísticos."""
        return _load_json(tables / "episodios_bundle.json")

    @app.get("/episodes/{episode_id}")
    def episode_detail(episode_id: str) -> dict[str, Any]:
        """Ficha de un episodio editorial."""
        payload = _load_json(tables / "episodios_bundle.json")
        for episode in payload:
            if episode.get("episodio_id") == episode_id:
                return episode
        raise HTTPException(status_code=404, detail=f"Episodio {episode_id} no encontrado")

    @app.get("/actors")
    def actors(
        party_family: str | None = Query(default=None),
        party_status: str | None = Query(default=None),
    ) -> list[dict[str, Any]]:
        """Series mensuales por familia de partido y estatus."""
        frame = _load_csv(tables / "series_actores.csv")
        if party_family is not None:
            frame = frame.loc[frame["party_family"] == party_family]
        if party_status is not None:
            frame = frame.loc[frame["party_status"] == party_status]
        return _records(frame.sort_values(["month", "party_family", "party_status"]))

    @app.get("/actors/changes")
    def actor_changes(
        serie: str | None = Query(default=None),
        serie_id: str | None = Query(default=None),
        metrica: str | None = Query(default=None),
        nivel: str | None = Query(default=None),
        significativo_bh: int | None = Query(default=None),
    ) -> list[dict[str, Any]]:
        """Descomposición intra-partido/composición por cambio."""
        frame = _load_csv(tables / "cambios_regimen_actores.csv")
        if serie is not None:
            frame = frame.loc[frame["serie"] == serie]
        if serie_id is not None:
            frame = frame.loc[frame["serie_id"].astype(str) == serie_id]
        if metrica is not None:
            frame = frame.loc[frame["metrica"] == metrica]
        if nivel is not None:
            frame = frame.loc[frame["nivel"] == nivel]
        if significativo_bh is not None:
            frame = frame.loc[frame["significativo_bh"].astype(int) == significativo_bh]
        return _records(frame.sort_values(["fecha", "partido"]))

    @app.get("/events/catalog")
    def events_catalog(capa: str | None = Query(default=None)) -> list[dict[str, Any]]:
        """Catálogo de eventos de dos capas (covariable/contexto)."""
        frame = _load_csv(tables / "eventos_catalogo.csv")
        if capa is not None:
            frame = frame.loc[frame["capa"] == capa]
        return _records(frame.sort_values("fecha"))

    @app.get("/events/episodes")
    def event_episodes() -> list[dict[str, Any]]:
        """Episodios de eventos usados en el event study."""
        return _records(_load_csv(tables / "eventos_episodios.csv").sort_values("fecha_ancla"))

    @app.get("/events/alignment")
    def event_alignment(
        subfamilia: str | None = Query(default=None),
        significativo_bh: int | None = Query(default=None),
        max_q: float | None = Query(default=None),
    ) -> list[dict[str, Any]]:
        """Resultados del event study local con permutación y BH."""
        frame = _load_csv(tables / "eventos_alineacion.csv")
        if subfamilia is not None:
            frame = frame.loc[frame["subfamilia"] == subfamilia]
        if significativo_bh is not None:
            frame = frame.loc[frame["significativo_bh"].astype(int) == significativo_bh]
        if max_q is not None:
            frame = frame.loc[frame["q"].astype(float) <= max_q]
        return _records(frame.sort_values(["subfamilia", "q", "hipotesis_id"]))

    @app.get("/tone/counterfactual")
    def tone_counterfactual() -> list[dict[str, Any]]:
        """Tono real y contrafactual con cuotas de partido fijas."""
        return _records(_load_csv(tables / "tono_contrafactual.csv").sort_values("month"))

    @app.get("/tone/ci")
    def tone_ci() -> list[dict[str, Any]]:
        """IC bootstrap del cambio de tono de 2020-06."""
        return _records(_load_csv(tables / "tono_ic.csv"))

    return app


app = create_app()
