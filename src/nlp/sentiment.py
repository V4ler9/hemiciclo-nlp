"""Validación del sentimiento ParlaSent de ParlaCAP (Fase 3a, D-26).

Flujo en dos pasos gobernado por ``main``:

1. Si no existe ``reports/tables/validacion_sentimiento_muestra.csv``, se genera
   una muestra proporcional por estratos de ``senti_3`` por ``term``, con la
   semilla de la configuración, con identificador, fecha, legislatura y texto.
   Las etiquetas de referencia se quedan fuera para no sesgar la anotación.
2. Cuando exista ``reports/tables/validacion_sentimiento_anotaciones.csv`` con
   ``utterance_id``, ``senti_3_final`` y ``senti_6_final`` (más la trazabilidad
   ``model``, ``prompt_version``, ``date`` y ``reviewed_by``), se calculan
   accuracy, F1 macro, métricas por clase y matrices de confusión contra las
   etiquetas de ParlaCAP.

Las métricas se implementan con pandas y numpy, de modo que importar el módulo
no exige los extras `nlp` (D-30).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

import numpy as np
import pandas as pd

from src.utils.config import CONFIG_DIR, PROJECT_ROOT, SEED, load_config

SAMPLE_FILENAME = "validacion_sentimiento_muestra.csv"
ANNOTATIONS_FILENAME = "validacion_sentimiento_anotaciones.csv"
METRICS_FILENAME = "validacion_sentimiento_metricas.csv"
PER_CLASS_FILENAME = "validacion_sentimiento_por_clase.csv"
CONFUSION_TEMPLATE = "validacion_sentimiento_confusion_{level}.csv"

SAMPLE_COLUMNS = ["utterance_id", "date", "term", "text"]
REFERENCE_COLUMNS = {"senti_3": "senti_3_final", "senti_6": "senti_6_final"}
SENTIMENT_LEVELS = ("senti_3", "senti_6")


@dataclass(frozen=True)
class SentimentConfig:
    """Parámetros de la muestra de validación."""

    sample_size: int
    strata: tuple[str, ...]
    seed: int


@dataclass(frozen=True)
class SentimentReport:
    """Resultado de comparar las anotaciones con las etiquetas de ParlaCAP."""

    summary: pd.DataFrame
    per_class: pd.DataFrame
    confusions: dict[str, pd.DataFrame]


def build_sentiment_config(config: Mapping[str, Any]) -> SentimentConfig:
    """Construye la configuración de validación desde la sección ``sentiment``."""
    section = config["sentiment"]
    strata = tuple(str(value) for value in section.get("strata", ("senti_3", "term")))
    if not strata:
        raise ValueError("sentiment.strata no puede estar vacío")
    sample_size = int(section.get("sample_size", 200))
    if sample_size <= 0:
        raise ValueError("sentiment.sample_size debe ser positivo")
    return SentimentConfig(
        sample_size=sample_size,
        strata=strata,
        seed=int(section.get("seed", SEED)),
    )


def _largest_remainder(sizes: pd.Series, total: int) -> dict[Any, int]:
    """Reparte ``total`` proporcionalmente con el método del mayor resto."""
    if total <= 0 or sizes.empty:
        return {key: 0 for key in sizes.index}
    exact = sizes / float(sizes.sum()) * total
    floors = np.floor(exact).astype(int)
    quotas = {key: int(value) for key, value in floors.items()}
    remainder = total - int(floors.sum())
    order = (exact - floors).sort_values(ascending=False, kind="stable").index
    for key in order[:remainder]:
        quotas[key] += 1
    return quotas


def proportional_sample(frame: pd.DataFrame, config: SentimentConfig) -> pd.DataFrame:
    """Muestra proporcional por estratos, determinista con la semilla fijada."""
    missing = [column for column in (*SAMPLE_COLUMNS, *config.strata) if column not in frame]
    if missing:
        raise ValueError(f"Faltan columnas en el corpus para muestrear: {missing}")
    sizes = frame.groupby(list(config.strata), observed=True).size()
    size_by_key: dict[Any, int] = {key: int(cast(Any, value)) for key, value in sizes.items()}
    quotas = _largest_remainder(sizes, config.sample_size)
    grouped = frame.groupby(list(config.strata), observed=True)
    rng = np.random.default_rng(config.seed)
    parts: list[pd.DataFrame] = []
    for key in sorted(quotas, key=str):
        quota = min(quotas[key], size_by_key[key])
        if quota <= 0:
            continue
        group = grouped.get_group(key)
        chosen = np.sort(rng.choice(group.index.to_numpy(), size=quota, replace=False))
        parts.append(group.loc[chosen])
    if not parts:
        raise ValueError("La muestra quedó vacía: revisa sample_size y los estratos")
    sample = pd.concat(parts, axis=0)
    return (
        sample.loc[:, SAMPLE_COLUMNS]
        .sort_values("utterance_id", kind="stable")
        .reset_index(drop=True)
    )


def confusion_frame(y_true: pd.Series, y_pred: pd.Series, labels: Sequence[str]) -> pd.DataFrame:
    """Matriz de confusión con todas las clases, indexada por etiqueta real."""
    table = pd.crosstab(y_true, y_pred).reindex(
        index=pd.Index(labels), columns=pd.Index(labels), fill_value=0
    )
    table.index.name = "real"
    table.columns.name = "anotado"
    return table


def _prf(tp: int, fp: int, fn: int) -> tuple[float, float, float]:
    precision = 0.0 if tp + fp == 0 else tp / (tp + fp)
    recall = 0.0 if tp + fn == 0 else tp / (tp + fn)
    f1 = 0.0 if precision + recall == 0.0 else 2 * precision * recall / (precision + recall)
    return precision, recall, f1


def evaluate_sentiment(annotations: pd.DataFrame, reference: pd.DataFrame) -> SentimentReport:
    """Compara las anotaciones revisadas con las etiquetas ParlaCAP (3 y 6 clases)."""
    required = {"utterance_id", *REFERENCE_COLUMNS.values()}
    missing = sorted(required - set(annotations.columns))
    if missing:
        raise ValueError(f"Faltan columnas de anotación: {missing}")
    merged = annotations.merge(
        reference.loc[:, ["utterance_id", *REFERENCE_COLUMNS.keys()]],
        on="utterance_id",
        how="left",
        validate="one_to_one",
    )
    unknown = merged["senti_3"].isna() | merged["senti_6"].isna()
    if unknown.any():
        raise ValueError(f"Hay {int(unknown.sum())} anotaciones sin referencia en el corpus")
    for column in REFERENCE_COLUMNS.values():
        if merged[column].isna().any():
            raise ValueError(f"Hay anotaciones vacías en {column}")

    rows: list[dict[str, Any]] = []
    class_rows: list[dict[str, Any]] = []
    confusions: dict[str, pd.DataFrame] = {}
    for level, annotation_column in REFERENCE_COLUMNS.items():
        y_true = merged[level].astype(str)
        y_pred = merged[annotation_column].astype(str)
        labels = sorted(set(y_true) | set(y_pred))
        table = confusion_frame(y_true, y_pred, labels)
        confusions[level] = table
        matrix = table.to_numpy(dtype=np.int64)
        macro = 0.0
        for position, label in enumerate(labels):
            tp = int(matrix[position, position])
            fp = int(matrix[:, position].sum()) - tp
            fn = int(matrix[position, :].sum()) - tp
            precision, recall, f1 = _prf(tp, fp, fn)
            macro += f1
            class_rows.append(
                {
                    "nivel": level,
                    "clase": label,
                    "precision": round(precision, 6),
                    "recall": round(recall, 6),
                    "f1": round(f1, 6),
                    "support": int(matrix[position, :].sum()),
                }
            )
        rows.append(
            {
                "nivel": level,
                "n": len(merged),
                "accuracy": round(float((y_true == y_pred).mean()), 6),
                "f1_macro": round(macro / len(labels), 6),
            }
        )
    return SentimentReport(
        summary=pd.DataFrame(rows, columns=["nivel", "n", "accuracy", "f1_macro"]),
        per_class=pd.DataFrame(
            class_rows, columns=["nivel", "clase", "precision", "recall", "f1", "support"]
        ),
        confusions=confusions,
    )


def write_reports(report: SentimentReport, reports_dir: Path) -> list[Path]:
    """Escribe métricas, métricas por clase y matrices de confusión en ``reports_dir``."""
    written: list[Path] = []
    metrics_path = reports_dir / METRICS_FILENAME
    report.summary.to_csv(metrics_path, index=False)
    written.append(metrics_path)
    per_class_path = reports_dir / PER_CLASS_FILENAME
    report.per_class.to_csv(per_class_path, index=False)
    written.append(per_class_path)
    for level, table in report.confusions.items():
        path = reports_dir / CONFUSION_TEMPLATE.format(level=level)
        table.to_csv(path)
        written.append(path)
    return written


def main() -> None:
    """CLI: exporta la muestra de validación o calcula las métricas si hay anotaciones."""
    config = build_sentiment_config(load_config(CONFIG_DIR / "experiment_01.yaml"))
    reports_dir = PROJECT_ROOT / "reports" / "tables"
    sample_path = reports_dir / SAMPLE_FILENAME
    annotations_path = reports_dir / ANNOTATIONS_FILENAME
    if not sample_path.exists():
        corpus = pd.read_parquet(
            PROJECT_ROOT / "data" / "processed" / "intervenciones_limpias.parquet"
        )
        sample = proportional_sample(corpus, config)
        reports_dir.mkdir(parents=True, exist_ok=True)
        sample.to_csv(sample_path, index=False)
        print(
            f"Muestra de {len(sample)} intervenciones -> {sample_path}\n"
            "Pre-anota con el asistente, revisa y guarda las correcciones en "
            f"{annotations_path} (columnas: utterance_id, senti_3_final, senti_6_final, "
            "model, prompt_version, date, reviewed_by)"
        )
        return
    if not annotations_path.exists():
        print(
            f"La muestra existe ({sample_path}) pero faltan las anotaciones revisadas "
            f"({annotations_path}); nada que evaluar todavía"
        )
        return
    corpus = pd.read_parquet(PROJECT_ROOT / "data" / "processed" / "intervenciones_limpias.parquet")
    annotations = pd.read_csv(annotations_path)
    report = evaluate_sentiment(annotations, corpus)
    paths = write_reports(report, reports_dir)
    print(report.summary.to_string(index=False))
    for path in paths:
        print(f"escrito: {path}")


if __name__ == "__main__":
    main()
