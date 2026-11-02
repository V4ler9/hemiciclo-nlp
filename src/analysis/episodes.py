"""Episodios editoriales de la v2 (D-45).

Une la tabla narrativa de episodios con los cambios de régimen, la
descomposición de actores y el event study para producir el bundle que consume
la home. El bundle es un artefacto precalculado y determinista; la API no
ejecuta cálculos estadísticos.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false, reportUnknownParameterType=false, reportUnknownLambdaType=false

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from src.utils.config import CONFIG_DIR, PROJECT_ROOT, load_config

logger = logging.getLogger(__name__)

NARRATIVE_COLUMNS = (
    "episodio_id",
    "titulo",
    "fecha",
    "resumen",
    "topicos",
    "eventos_ids",
    "actores",
    "fuente",
    "reviewed_by",
)
MAX_NEAREST_MONTHS = 12


def _parse_ids(value: Any) -> list[str]:
    """Convierte una lista separada por ``;`` en identificadores limpios."""
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return []
    return [item.strip() for item in str(value).split(";") if item.strip()]


def _to_float(value: Any) -> float | None:
    """Convierte un valor a float JSON-safe."""
    if value is None:
        return None
    number = float(value)
    return None if not np.isfinite(number) else number


def _to_int(value: Any) -> int | None:
    """Convierte un valor a int JSON-safe."""
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return None
    return int(value)


def _as_timestamp(value: Any) -> pd.Timestamp:
    """Convierte un valor a Timestamp y falla si es NaT."""
    timestamp = pd.Timestamp(value)
    if not isinstance(timestamp, pd.Timestamp):
        raise ValueError(f"Fecha inválida: {value!r}")
    return timestamp


def load_narrative_episodes(path: Path) -> pd.DataFrame:
    """Carga y valida la tabla narrativa de los episodios del MVP."""
    episodes = pd.read_csv(path)
    missing = [column for column in NARRATIVE_COLUMNS if column not in episodes.columns]
    if missing:
        raise ValueError(f"Faltan columnas en los episodios: {missing}")
    episodes = episodes.loc[:, list(NARRATIVE_COLUMNS)].copy()
    episodes["fecha"] = pd.to_datetime(episodes["fecha"], errors="raise")
    if episodes["episodio_id"].duplicated().any():
        raise ValueError("Hay identificadores de episodio narrativo duplicados")
    episodes["topicos"] = episodes["topicos"].apply(_parse_ids)
    episodes["eventos_ids"] = episodes["eventos_ids"].apply(_parse_ids)
    episodes["reviewed_by"] = episodes["reviewed_by"].fillna("").astype(str)
    return episodes


def _nearest_change(
    changes: pd.DataFrame,
    topic_id: str,
    episode_date: pd.Timestamp,
    max_months: int = MAX_NEAREST_MONTHS,
) -> pd.Series | None:
    """Cambio más cercano de un tópico, si está dentro de la ventana."""
    subset = changes.loc[
        (changes["serie"] == "topic") & (changes["serie_id"].astype(str) == str(topic_id))
    ].copy()
    if subset.empty:
        return None
    subset["distancia"] = (
        (subset["fecha"].dt.year - episode_date.year) * 12
        + (subset["fecha"].dt.month - episode_date.month)
    ).abs()
    subset = subset.loc[subset["distancia"] <= max_months].sort_values("distancia")
    if subset.empty:
        return None
    return subset.iloc[0]


def _stats_for_change(
    stats: pd.DataFrame, serie: str, serie_id: str, fecha: pd.Timestamp
) -> pd.Series | None:
    """Estadísticos exactos de un cambio."""
    subset = stats.loc[
        (stats["serie"] == serie)
        & (stats["serie_id"].astype(str) == str(serie_id))
        & (stats["fecha"] == fecha)
    ]
    return None if subset.empty else subset.iloc[0]


def _top_actors(
    actor_decomp: pd.DataFrame,
    serie_id: str,
    fecha: pd.Timestamp,
    limit: int = 5,
) -> list[dict[str, Any]]:
    """Contribuciones de actores agregadas por familia de partido."""
    subset = actor_decomp.loc[
        (actor_decomp["serie"] == "topic")
        & (actor_decomp["serie_id"].astype(str) == str(serie_id))
        & (actor_decomp["fecha"] == fecha)
        & (actor_decomp["nivel"] == "partido")
        & (actor_decomp["partido"] != "__residual__")
    ].copy()
    if subset.empty:
        return []
    subset["contribucion"] = subset["contribucion_dentro"].fillna(0.0) + subset[
        "contribucion_composicion"
    ].fillna(0.0)
    grouped = (
        subset.groupby("partido", as_index=False)
        .agg(
            contribucion=("contribucion", "sum"),
            n_antes=("n_antes", "sum"),
            n_despues=("n_despues", "sum"),
        )
        .sort_values("contribucion", key=lambda series: series.abs(), ascending=False)
        .head(limit)
    )
    return [
        {
            "partido": str(row["partido"]),
            "contribucion": _to_float(row["contribucion"]),
            "n_antes": _to_int(row["n_antes"]),
            "n_despues": _to_int(row["n_despues"]),
        }
        for _, row in grouped.iterrows()
    ]


def _tone_actors(
    actor_decomp: pd.DataFrame,
    fecha: pd.Timestamp,
    limit: int = 6,
) -> list[dict[str, Any]]:
    """Contribuciones de actores al cambio de tono (share negativo)."""
    subset = actor_decomp.loc[
        (actor_decomp["serie"] == "tone")
        & (actor_decomp["fecha"] == fecha)
        & (actor_decomp["metrica"] == "negative_share")
        & (actor_decomp["nivel"] == "partido")
        & (actor_decomp["partido"] != "__residual__")
    ].copy()
    if subset.empty:
        return []
    subset["contribucion"] = subset["contribucion_dentro"].fillna(0.0) + subset[
        "contribucion_composicion"
    ].fillna(0.0)
    grouped = (
        subset.groupby("partido", as_index=False)
        .agg(
            contribucion=("contribucion", "sum"),
            contribucion_dentro=("contribucion_dentro", "sum"),
            contribucion_composicion=("contribucion_composicion", "sum"),
            n_antes=("n_antes", "sum"),
            n_despues=("n_despues", "sum"),
        )
        .sort_values("contribucion", key=lambda series: series.abs(), ascending=False)
        .head(limit)
    )
    return [
        {
            "partido": str(row["partido"]),
            "contribucion": _to_float(row["contribucion"]),
            "contribucion_dentro": _to_float(row["contribucion_dentro"]),
            "contribucion_composicion": _to_float(row["contribucion_composicion"]),
            "n_antes": _to_int(row["n_antes"]),
            "n_despues": _to_int(row["n_despues"]),
        }
        for _, row in grouped.iterrows()
    ]


def _topic_bundle(
    topic_id: str,
    episode_date: pd.Timestamp,
    changes: pd.DataFrame,
    stats: pd.DataFrame,
    actor_decomp: pd.DataFrame,
    labels: pd.DataFrame,
) -> dict[str, Any] | None:
    """Ficha de un tópico dentro de un episodio."""
    change = _nearest_change(changes, topic_id, episode_date)
    if change is None:
        return None
    fecha = _as_timestamp(change["fecha"])
    stat = _stats_for_change(stats, "topic", str(topic_id), fecha)
    label_row = labels.loc[labels["topic"].astype(str) == str(topic_id)]
    label = str(label_row.iloc[0]["label"]) if not label_row.empty else f"Tópico {topic_id}"
    return {
        "topic": int(topic_id),
        "label": label,
        "fecha_cambio": fecha.date().isoformat(),
        "meses_distancia": int(
            abs((fecha.year - episode_date.year) * 12 + fecha.month - episode_date.month)
        ),
        "delta": _to_float(change["delta"]),
        "q": _to_float(stat["q"]) if stat is not None else None,
        "n": _to_int(stat["n"]) if stat is not None else None,
        "tamano_serie": _to_int(change["tamano_serie"]),
        "significativo_bh": _to_int(stat["significativo_bh"]) if stat is not None else 0,
        "direccion": "up" if float(change["delta"]) >= 0 else "down",
        "actores": _top_actors(actor_decomp, str(topic_id), fecha),
    }


def _tone_bundle(
    episode_date: pd.Timestamp,
    changes: pd.DataFrame,
    stats: pd.DataFrame,
    tone_ci: pd.DataFrame,
    actor_decomp: pd.DataFrame,
) -> dict[str, Any] | None:
    """Ficha del cambio de tono del episodio, si existe."""
    tone_changes = changes.loc[changes["serie"] == "tone"].copy()
    if tone_changes.empty:
        return None
    tone_changes["distancia"] = (
        (tone_changes["fecha"].dt.year - episode_date.year) * 12
        + (tone_changes["fecha"].dt.month - episode_date.month)
    ).abs()
    tone_changes = tone_changes.loc[tone_changes["distancia"] <= 1].sort_values("distancia")
    if tone_changes.empty:
        return None
    change = tone_changes.iloc[0]
    fecha = _as_timestamp(change["fecha"])
    stat = _stats_for_change(stats, "tone", "tone", fecha)
    intervals = tone_ci.loc[tone_ci["fecha"] == fecha]
    interval_records = [
        {
            "metrica": str(row["metrica"]),
            "delta": _to_float(row["delta"]),
            "ic_inf": _to_float(row["ic_inf"]),
            "ic_sup": _to_float(row["ic_sup"]),
            "n_boot": _to_int(row["n_boot"]),
        }
        for _, row in intervals.iterrows()
    ]
    delta_by_metric = {record["metrica"]: record["delta"] for record in interval_records}
    return {
        "fecha_cambio": fecha.date().isoformat(),
        "delta_serie": _to_float(change["delta"]),
        "delta_share_negativo": delta_by_metric.get("negative_share"),
        "delta_senti_n": delta_by_metric.get("senti_n"),
        "q": _to_float(stat["q"]) if stat is not None else None,
        "significativo_bh": _to_int(stat["significativo_bh"]) if stat is not None else 0,
        "intervalos": interval_records,
        "actores": _tone_actors(actor_decomp, fecha),
    }


def build_episode_bundle(
    episodes: pd.DataFrame,
    changes: pd.DataFrame,
    stats: pd.DataFrame,
    actor_decomp: pd.DataFrame,
    alignment: pd.DataFrame,
    labels: pd.DataFrame,
    event_episodes: pd.DataFrame,
    tone_ci: pd.DataFrame,
) -> list[dict[str, Any]]:
    """Construye el bundle editorial de los episodios del MVP."""
    event_lookup = event_episodes.set_index("episodio_id")
    bundle: list[dict[str, Any]] = []
    for episode in episodes.to_dict(orient="records"):
        episode_date = _as_timestamp(episode["fecha"])
        topicos = [
            topic
            for topic_id in episode["topicos"]
            if (
                topic := _topic_bundle(
                    str(topic_id), episode_date, changes, stats, actor_decomp, labels
                )
            )
            is not None
        ]
        eventos: list[dict[str, Any]] = []
        for event_id in episode["eventos_ids"]:
            if event_id in event_lookup.index:
                event_row = event_lookup.loc[event_id]
                eventos.append(
                    {
                        "episodio_evento_id": event_id,
                        "titulo": str(event_row["titulo"]),
                        "fecha_ancla": pd.Timestamp(event_row["fecha_ancla"]).date().isoformat(),
                        "eventos": str(event_row["eventos"]),
                        "resumen": str(event_row["resumen"]),
                    }
                )
            subset = alignment.loc[alignment["episodio_id"] == event_id]
            eventos.extend(
                {
                    "hipotesis_id": str(row["hipotesis_id"]),
                    "serie": str(row["serie"]),
                    "serie_id": str(row["serie_id"]),
                    "metrica": str(row["metrica"]),
                    "delta": _to_float(row["delta"]),
                    "q": _to_float(row["q"]),
                    "significativo_bh": _to_int(row["significativo_bh"]),
                    "direccion_esperada": str(row["direccion_esperada"]),
                }
                for _, row in subset.iterrows()
            )
        bundle.append(
            {
                "episodio_id": str(episode["episodio_id"]),
                "titulo": str(episode["titulo"]),
                "fecha": episode_date.date().isoformat(),
                "resumen": str(episode["resumen"]),
                "fuente": str(episode["fuente"]),
                "reviewed_by": str(episode["reviewed_by"]),
                "topicos": topicos,
                "tono": _tone_bundle(episode_date, changes, stats, tone_ci, actor_decomp),
                "eventos": eventos,
            }
        )
    return bundle


def main() -> None:
    """CLI: escribe ``reports/tables/episodios_bundle.json``."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    config = load_config(CONFIG_DIR / "experiment_04.yaml")
    tables = PROJECT_ROOT / "reports" / "tables"
    episodes = load_narrative_episodes(PROJECT_ROOT / str(config["episodes"]["narrative_path"]))
    changes = pd.read_csv(tables / "cambios_regimen.csv", parse_dates=["fecha"])
    stats = pd.read_csv(tables / "cambios_regimen_test.csv", parse_dates=["fecha"])
    actor_decomp = pd.read_csv(tables / "cambios_regimen_actores.csv", parse_dates=["fecha"])
    alignment = pd.read_csv(tables / "eventos_alineacion.csv", parse_dates=["fecha_ancla"])
    labels = pd.read_csv(tables / "topics_labels.csv")
    event_episodes = pd.read_csv(
        tables / "eventos_episodios.csv", parse_dates=["fecha_ancla", "fecha_inicio", "fecha_fin"]
    )
    tone_ci = pd.read_csv(tables / "tono_ic.csv", parse_dates=["fecha"])
    bundle = build_episode_bundle(
        episodes,
        changes,
        stats,
        actor_decomp,
        alignment,
        labels,
        event_episodes,
        tone_ci,
    )
    destination = PROJECT_ROOT / str(config["episodes"]["bundle_path"])
    destination.write_text(
        json.dumps(bundle, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    logger.info("episodios: %s fichas -> %s", len(bundle), destination)


if __name__ == "__main__":
    main()
