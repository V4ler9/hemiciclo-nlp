"""Figuras de la Fase 3b: series mensuales, regímenes y eventos.

Genera las cinco figuras del entregable (``reports/figures``):

1. Mapa de calor mes x top-tópicos (cuota relativa).
2. Tono mensual con eventos y cambios de régimen del tono.
3. Series de los tópicos mayores con sus puntos de cambio.
4. Mapa de calor de asociaciones evento x tópico (rho, con * si q < 0,05).
5. Volumen mensual y tasa de outliers.

``matplotlib`` y ``seaborn`` (extra ``analysis``) se cargan en tiempo de
ejecución con ``import_optional`` y el backend es ``Agg`` (sin display).
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from src.analysis.regime_change import load_events
from src.utils.config import CONFIG_DIR, PROJECT_ROOT, load_config
from src.utils.helpers import import_optional

HEATMAP_FILENAME = "fig_heatmap_topicos.png"
TONE_FILENAME = "fig_tono_eventos.png"
CHANGES_FILENAME = "fig_cambios_top.png"
ASSOCIATIONS_FILENAME = "fig_eventos_correlaciones.png"
VOLUME_FILENAME = "fig_volumen_outliers.png"
LABEL_MAX_LENGTH = 42


@dataclass(frozen=True)
class FigureConfig:
    """Parámetros de las figuras."""

    dpi: int
    heatmap_topics: int
    change_topics: int
    association_topics: int


def build_figure_config(config: Mapping[str, Any]) -> FigureConfig:
    """Construye la configuración de figuras desde la sección ``figures``."""
    section = config["figures"]
    return FigureConfig(
        dpi=int(section.get("dpi", 150)),
        heatmap_topics=int(section.get("heatmap_topics", 20)),
        change_topics=int(section.get("change_topics", 12)),
        association_topics=int(section.get("association_topics", 20)),
    )


def _pyplot() -> Any:
    matplotlib = import_optional("matplotlib")
    matplotlib.use("Agg")
    seaborn = import_optional("seaborn")
    seaborn.set_theme(style="whitegrid")
    return import_optional("matplotlib.pyplot")


def load_topic_labels(path: Path | None = None) -> dict[str, str]:
    """Etiquetas legibles por tópico (o vacío si no existe el CSV)."""
    labels_path = (
        path if path is not None else PROJECT_ROOT / "reports" / "tables" / "topics_labels.csv"
    )
    if not labels_path.exists():
        return {}
    labels = pd.read_csv(labels_path)
    return {str(int(row["topic"])): str(row["label"]) for _, row in labels.iterrows()}


def _short_label(topic_id: str, labels: Mapping[str, str]) -> str:
    label = labels.get(topic_id, f"tópico {topic_id}")
    if len(label) > LABEL_MAX_LENGTH:
        label = label[: LABEL_MAX_LENGTH - 1] + "…"
    return label


def top_topic_ids(series: pd.DataFrame, top_n: int) -> list[str]:
    """Tópicos ordenados por intervenciones totales (descendente)."""
    topics = series.loc[series["series_type"] == "topic"]
    totals = topics.groupby("series_id")["n_interventions"].sum().sort_values(ascending=False)
    return [str(topic) for topic in totals.index[:top_n]]


def _pivot(series: pd.DataFrame, series_type: str) -> pd.DataFrame:
    rows = series.loc[series["series_type"] == series_type]
    return rows.pivot(index="month", columns="series_id", values="value").sort_index()


def topic_heatmap(
    series: pd.DataFrame, labels: Mapping[str, str], config: FigureConfig, output_path: Path
) -> Path:
    """Mapa de calor mes x top-tópicos con la cuota relativa."""
    plt = _pyplot()
    heatmap = _pivot(series, "topic").reindex(columns=top_topic_ids(series, config.heatmap_topics))
    heatmap = heatmap.transpose()
    figure, axes = plt.subplots(figsize=(16, 7))
    axes.imshow(
        heatmap.to_numpy(dtype=np.float64), aspect="auto", cmap="viridis", interpolation="nearest"
    )
    axes.set_yticks(range(len(heatmap.index)))
    axes.set_yticklabels([_short_label(topic, labels) for topic in heatmap.index], fontsize=8)
    positions = range(0, len(heatmap.columns), 12)
    axes.set_xticks(list(positions))
    axes.set_xticklabels(
        [pd.Timestamp(month).strftime("%Y-%m") for month in heatmap.columns[list(positions)]],
        rotation=45,
        ha="right",
        fontsize=8,
    )
    axes.set_title("Cuota relativa por tópico y mes (top tópicos)")
    axes.grid(False)
    figure.colorbar(axes.images[0], ax=axes, label="cuota")
    figure.tight_layout()
    figure.savefig(output_path, dpi=config.dpi)
    plt.close(figure)
    return output_path


def tone_figure(
    series: pd.DataFrame,
    events: pd.DataFrame,
    changes: pd.DataFrame,
    config: FigureConfig,
    output_path: Path,
) -> Path:
    """Serie de tono mensual con eventos y cambios de régimen del tono."""
    plt = _pyplot()
    tone = _pivot(series, "tone")["tone"].sort_index()
    figure, axes = plt.subplots(figsize=(14, 6))
    axes.plot(
        tone.index,
        tone.to_numpy(dtype=np.float64),
        color="#1f77b4",
        linewidth=1.4,
        label="tono medio",
    )
    for _, event in events.iterrows():
        event_date = pd.Timestamp(event["fecha"])
        axes.axvline(event_date, color="#d62728", alpha=0.35, linewidth=1.0)
        axes.annotate(
            str(event["evento"]),
            xy=(event_date, 0.01),
            xycoords=("data", "axes fraction"),
            rotation=90,
            fontsize=7,
            va="bottom",
            ha="right",
            color="#a33",
        )
    tone_changes = changes.loc[changes["serie"] == "tone"]
    for _, change in tone_changes.iterrows():
        axes.axvline(pd.Timestamp(change["fecha"]), color="black", linestyle="--", linewidth=1.1)
    axes.set_title("Tono mensual del Pleno, eventos y cambios de régimen del tono")
    axes.set_ylabel("senti_n medio (0-6)")
    axes.set_xlabel("mes")
    axes.legend(loc="lower left")
    figure.tight_layout()
    figure.savefig(output_path, dpi=config.dpi)
    plt.close(figure)
    return output_path


def changes_figure(
    series: pd.DataFrame,
    changes: pd.DataFrame,
    labels: Mapping[str, str],
    config: FigureConfig,
    output_path: Path,
) -> Path:
    """Small multiples de los tópicos mayores con sus puntos de cambio."""
    plt = _pyplot()
    topics = top_topic_ids(series, config.change_topics)
    quotations = _pivot(series, "topic")
    columns = 3
    rows = int(np.ceil(len(topics) / columns))
    figure, axes = plt.subplots(rows, columns, figsize=(15, 3.2 * rows), sharex=True)
    flat = np.atleast_1d(axes).ravel()
    for position, topic in enumerate(topics):
        axis = flat[position]
        values = quotations[topic].sort_index()
        axis.plot(values.index, values.to_numpy(dtype=np.float64), color="#2ca02c", linewidth=1.1)
        topic_changes = changes.loc[(changes["serie"] == "topic") & (changes["serie_id"] == topic)]
        for _, change in topic_changes.iterrows():
            axis.axvline(
                pd.Timestamp(change["fecha"]), color="black", linestyle="--", linewidth=0.8
            )
        axis.set_title(_short_label(topic, labels), fontsize=8)
        axis.tick_params(axis="x", labelrotation=45, labelsize=7)
        axis.tick_params(axis="y", labelsize=7)
    for axis in flat[len(topics) :]:
        axis.axis("off")
    figure.suptitle("Cuota mensual de los tópicos mayores con cambios de régimen detectados")
    figure.tight_layout()
    figure.savefig(output_path, dpi=config.dpi)
    plt.close(figure)
    return output_path


def associations_figure(
    relations: pd.DataFrame,
    labels: Mapping[str, str],
    config: FigureConfig,
    output_path: Path,
) -> Path:
    """Mapa de calor de asociaciones evento x tópico (rho; * si q < 0,05)."""
    plt = _pyplot()
    frame = relations.loc[relations["serie"] == "topic"].copy()
    totals = (
        frame.assign(abs_rho=frame["rho"].abs())
        .groupby("serie_id")["abs_rho"]
        .max()
        .sort_values(ascending=False)
    )
    topics = [str(topic) for topic in totals.index[: config.association_topics]]
    frame = frame.loc[frame["serie_id"].isin(topics)]
    rho_matrix = frame.pivot_table(index="serie_id", columns="evento", values="rho").reindex(
        index=topics
    )
    q_matrix = frame.pivot_table(index="serie_id", columns="evento", values="q").reindex(
        index=topics
    )
    rho_values = rho_matrix.to_numpy(dtype=np.float64)
    q_values = q_matrix.to_numpy(dtype=np.float64)
    figure, axes = plt.subplots(figsize=(10, max(6, 0.28 * len(topics))))
    image = axes.imshow(rho_values, cmap="RdBu_r", vmin=-0.6, vmax=0.6, aspect="auto")
    axes.set_xticks(range(len(rho_matrix.columns)))
    axes.set_xticklabels(list(rho_matrix.columns), rotation=45, ha="right", fontsize=8)
    axes.set_yticks(range(len(rho_matrix.index)))
    axes.set_yticklabels([_short_label(topic, labels) for topic in rho_matrix.index], fontsize=8)
    for row_position in range(q_values.shape[0]):
        for column_position in range(q_values.shape[1]):
            q_value = q_values[row_position, column_position]
            if np.isfinite(q_value) and q_value < 0.05:
                axes.text(column_position, row_position, "*", ha="center", va="center", fontsize=10)
    axes.set_title("Asociación exploratoria (Spearman rho) evento x tópico; * q < 0,05")
    axes.grid(False)
    figure.colorbar(image, ax=axes, label="rho")
    figure.tight_layout()
    figure.savefig(output_path, dpi=config.dpi)
    plt.close(figure)
    return output_path


def volume_figure(series: pd.DataFrame, config: FigureConfig, output_path: Path) -> Path:
    """Volumen mensual de intervenciones y tasa de outliers."""
    plt = _pyplot()
    volume = _pivot(series, "volume")["volume"].sort_index()
    outliers = _pivot(series, "outliers")["outliers"].sort_index()
    figure, axes = plt.subplots(figsize=(14, 6))
    axes.bar(
        volume.index,
        volume.to_numpy(dtype=np.float64),
        width=20,
        color="#8c8c8c",
        label="intervenciones",
    )
    axes.set_ylabel("intervenciones por mes")
    twin = axes.twinx()
    twin.plot(
        outliers.index,
        outliers.to_numpy(dtype=np.float64),
        color="#d62728",
        linewidth=1.3,
        label="tasa de outliers",
    )
    twin.set_ylabel("tasa de outliers")
    axes.set_title("Volumen mensual y tasa de outliers de BERTopic")
    axes.set_xlabel("mes")
    handles_left, labels_left = axes.get_legend_handles_labels()
    handles_right, labels_right = twin.get_legend_handles_labels()
    axes.legend(handles_left + handles_right, labels_left + labels_right, loc="upper left")
    figure.tight_layout()
    figure.savefig(output_path, dpi=config.dpi)
    plt.close(figure)
    return output_path


def main() -> None:
    """CLI: genera las cinco figuras de la fase 3b en ``reports/figures``."""
    config = build_figure_config(load_config(CONFIG_DIR / "experiment_03.yaml"))
    reports_tables = PROJECT_ROOT / "reports" / "tables"
    series = pd.read_parquet(PROJECT_ROOT / "data" / "intermediate" / "series_mensuales.parquet")
    changes = pd.read_csv(reports_tables / "cambios_regimen.csv")
    relations = pd.read_csv(reports_tables / "eventos_relaciones.csv")
    events = load_events(PROJECT_ROOT / "data" / "external" / "eventos.csv")
    labels = load_topic_labels()
    figures_dir = PROJECT_ROOT / "reports" / "figures"
    figures_dir.mkdir(parents=True, exist_ok=True)
    outputs = [
        topic_heatmap(series, labels, config, figures_dir / HEATMAP_FILENAME),
        tone_figure(series, events, changes, config, figures_dir / TONE_FILENAME),
        changes_figure(series, changes, labels, config, figures_dir / CHANGES_FILENAME),
        associations_figure(relations, labels, config, figures_dir / ASSOCIATIONS_FILENAME),
        volume_figure(series, config, figures_dir / VOLUME_FILENAME),
    ]
    for path in outputs:
        print(f"escrito: {path}")


if __name__ == "__main__":
    main()
