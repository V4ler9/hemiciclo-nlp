"""Series mensuales de la Fase 3b (D-08, D-28).

Agrega las intervenciones a nivel de mes en una tabla larga:

- ``topic``: cuota relativa del tópico entre las intervenciones asignadas
  (los outliers de BERTopic se excluyen; su tasa se reporta aparte).
- ``tone``: media mensual de ``senti_n`` y ``tone_weighted``: la misma media
  ponderada por ``n_words`` (sensibilidad).
- ``outliers``: tasa mensual de outliers y ``volume``: intervenciones del mes.

Los meses sin sesiones se conservan en la rejilla con ``has_session: false``
y quedan fuera del modelado (D-28). La lógica usa solo pandas y numpy; los
tests unitarios trabajan con dobles.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd

from src.utils.config import CONFIG_DIR, PROJECT_ROOT, load_config

SERIES_COLUMNS = ["month", "series_type", "series_id", "value", "n_interventions", "has_session"]
SERIES_TYPES = ("topic", "tone", "tone_weighted", "outliers", "volume")
OUTLIER_TOPIC = -1


@dataclass(frozen=True)
class TemporalConfig:
    """Parámetros de la rejilla mensual."""

    start: str
    end: str
    outlier_strategy: str


def build_temporal_config(config: Mapping[str, Any]) -> TemporalConfig:
    """Construye la configuración de series desde la sección ``temporal``."""
    section = config["temporal"]
    temporal = TemporalConfig(
        start=str(section.get("start", "2015-01")),
        end=str(section.get("end", "2023-02")),
        outlier_strategy=str(section.get("outlier_strategy", "exclude")),
    )
    if temporal.outlier_strategy != "exclude":
        raise ValueError("Solo se implementa la estrategia de outliers 'exclude' (D-28)")
    return temporal


def monthly_grid(start: str, end: str) -> pd.DatetimeIndex:
    """Rejilla de primeros de mes entre ``start`` y ``end`` (inclusive)."""
    return pd.date_range(start=start, end=end, freq="MS")


def build_series(interventions: pd.DataFrame, config: TemporalConfig) -> pd.DataFrame:
    """Construye la tabla larga de series mensuales.

    ``interventions`` debe traer ``utterance_id``, ``date``, ``bertopic_topic``,
    ``is_outlier``, ``senti_n`` y ``n_words`` (una fila por intervención).
    """
    required = {"utterance_id", "date", "bertopic_topic", "is_outlier", "senti_n", "n_words"}
    missing = sorted(required - set(interventions.columns))
    if missing:
        raise ValueError(f"Faltan columnas para las series: {missing}")

    frame = interventions.copy()
    frame["month"] = frame["date"].dt.to_period("M").dt.to_timestamp()
    assigned = frame.loc[~frame["is_outlier"]]
    all_topics = sorted(
        int(topic) for topic in assigned["bertopic_topic"].unique() if int(topic) != OUTLIER_TOPIC
    )

    total = frame.groupby("month")["utterance_id"].size()
    topic_counts = assigned.groupby(["month", "bertopic_topic"]).size()
    outlier_counts = frame.groupby("month")["is_outlier"].sum()
    tone = frame.groupby("month")["senti_n"].mean()
    weighted_totals = (
        frame.assign(weight=frame["senti_n"] * frame["n_words"])
        .groupby("month")[["weight", "n_words"]]
        .sum()
    )
    tone_weighted = weighted_totals["weight"] / weighted_totals["n_words"]

    rows: list[dict[str, Any]] = []
    for month in monthly_grid(config.start, config.end):
        n_total = int(total.get(month, 0))
        has_session = n_total > 0
        try:
            counts_for_month = topic_counts.xs(month, level="month")
        except KeyError:
            counts_for_month = pd.Series(dtype=np.int64)
        n_assigned = int(counts_for_month.sum())
        for topic in all_topics:
            count = int(counts_for_month.get(topic, 0))
            quota = count / n_assigned if has_session and n_assigned else float("nan")
            rows.append(
                {
                    "month": month,
                    "series_type": "topic",
                    "series_id": str(topic),
                    "value": quota,
                    "n_interventions": count,
                    "has_session": has_session,
                }
            )
        outliers_count = int(outlier_counts.get(month, 0))
        rows.extend(
            [
                {
                    "month": month,
                    "series_type": "tone",
                    "series_id": "tone",
                    "value": float(tone.get(month, np.nan)),
                    "n_interventions": n_total,
                    "has_session": has_session,
                },
                {
                    "month": month,
                    "series_type": "tone_weighted",
                    "series_id": "tone_weighted",
                    "value": float(tone_weighted.get(month, np.nan)),
                    "n_interventions": n_total,
                    "has_session": has_session,
                },
                {
                    "month": month,
                    "series_type": "outliers",
                    "series_id": "outliers",
                    "value": outliers_count / n_total if n_total else float("nan"),
                    "n_interventions": outliers_count,
                    "has_session": has_session,
                },
                {
                    "month": month,
                    "series_type": "volume",
                    "series_id": "volume",
                    "value": float(n_total),
                    "n_interventions": n_total,
                    "has_session": has_session,
                },
            ]
        )
    return pd.DataFrame(rows, columns=SERIES_COLUMNS)


def main() -> None:
    """CLI: construye ``data/intermediate/series_mensuales.parquet``."""
    config = build_temporal_config(load_config(CONFIG_DIR / "experiment_03.yaml"))
    assignments = pd.read_parquet(
        PROJECT_ROOT / "data" / "processed" / "intervenciones_topicos.parquet"
    )
    corpus = pd.read_parquet(
        PROJECT_ROOT / "data" / "processed" / "intervenciones_limpias.parquet",
        columns=["utterance_id", "date", "senti_n", "n_words"],
    )
    merged = assignments.merge(corpus, on="utterance_id", how="left", validate="one_to_one")
    if merged["date"].isna().any():
        raise ValueError("Hay asignaciones sin fecha: revisa las fases previas")
    series = build_series(merged, config)
    output_path = PROJECT_ROOT / "data" / "intermediate" / "series_mensuales.parquet"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    series.to_parquet(output_path, index=False)
    active = int(series.loc[series["has_session"], "month"].nunique())
    topics = series.loc[series["series_type"] == "topic", "series_id"].nunique()
    print(f"{len(series)} filas ({topics} tópicos, {active} meses con sesión) -> {output_path}")


if __name__ == "__main__":
    main()
