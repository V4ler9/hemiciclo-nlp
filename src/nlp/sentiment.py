# pyright: reportUnknownVariableType=false
"""Validación del sentimiento ParlaSent de ParlaCAP (Fase 3a, D-26/D-36/D-37).

Flujo gobernado por ``main`` (idempotente: genera todo artefacto cuyo insumo exista):

1. Si no existe ``reports/tables/validacion_sentimiento_muestra.csv``, se genera una
   muestra proporcional por estratos de ``senti_3`` por ``term`` con la semilla de la
   configuración (identificador, fecha, legislatura y texto; sin etiquetas de referencia).
2. Si existe ``reports/tables/validacion_sentimiento_anotaciones.csv`` (pre-anotación
   LLM de 200 filas), se materializa la concordancia LLM ↔ ParlaCAP
   (``validacion_sentimiento_concordancia_llm.csv``) y sus métricas secundarias.
3. Si existe ``reports/tables/validacion_sentimiento_revision.csv`` (revisión humana),
   se estima la calidad de ParlaCAP contra ese oro humano con accuracy cruda,
   balanceada y re-ponderada al corpus, F1 macro, kappa lineal y cuadrática,
   intervalos de confianza bootstrap, matrices de confusión, acuerdo a tres bandas
   y un informe HTML autocontenido.

Las etiquetas de ParlaCAP son predicciones de ParlaSent, no oro humano (D-36). Las
métricas delegan en scikit-learn (accuracy, balanced accuracy, F1, confusión, kappa) y
statsmodels (Fleiss), ambas dependencias base; el muestreo y el bootstrap usan
numpy/pandas.
"""

from __future__ import annotations

import warnings
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

import numpy as np
import pandas as pd
from sklearn.metrics import (
    accuracy_score,
    balanced_accuracy_score,
    cohen_kappa_score,
    confusion_matrix,
    f1_score,
    precision_recall_fscore_support,
)
from statsmodels.stats.inter_rater import fleiss_kappa as _statsmodels_fleiss_kappa

from src.utils.config import CONFIG_DIR, PROJECT_ROOT, SEED, load_config

FloatArray = np.ndarray[Any, np.dtype[np.float64]]
IntArray = np.ndarray[Any, np.dtype[np.int64]]

SAMPLE_FILENAME = "validacion_sentimiento_muestra.csv"
ANNOTATIONS_FILENAME = "validacion_sentimiento_anotaciones.csv"
REVISION_FILENAME = "validacion_sentimiento_revision.csv"
CONCORDANCE_FILENAME = "validacion_sentimiento_concordancia_llm.csv"
CONCORDANCE_METRICS_FILENAME = "validacion_sentimiento_concordancia_llm_metricas.csv"
REVISION_METRICS_FILENAME = "validacion_sentimiento_revision_metricas.csv"
REVISION_PER_CLASS_FILENAME = "validacion_sentimiento_revision_por_clase.csv"
REVISION_CONFUSION_TEMPLATE = "validacion_sentimiento_revision_confusion_{level}.csv"
REVISION_IC_FILENAME = "validacion_sentimiento_revision_ic.csv"
AGREEMENT_FILENAME = "validacion_sentimiento_acuerdo_3bandas.csv"
REPORT_HTML_FILENAME = "validacion_sentimiento_revision.html"

SAMPLE_COLUMNS = ["utterance_id", "date", "term", "text"]
CORPUS_COLUMNS = [*SAMPLE_COLUMNS, "senti_3", "senti_6"]
REVISION_COLUMNS = [
    "utterance_id",
    "date",
    "term",
    "text",
    "senti_3_final",
    "senti_6_final",
    "revisado_por",
    "fecha",
]
REFERENCE_COLUMNS = {"senti_3": "senti_3_final", "senti_6": "senti_6_final"}
SENTIMENT_LEVELS = ("senti_3", "senti_6")

# Taxonomías fijas y ordenadas (necesarias para kappa ponderada y confusión comparable).
SENTI3_LABELS = ("Negative", "Neutral", "Positive")
SENTI6_LABELS = (
    "Negative",
    "Mixed Negative",
    "Neutral Negative",
    "Neutral Positive",
    "Mixed Positive",
    "Positive",
)
LABELS_BY_LEVEL: dict[str, tuple[str, ...]] = {
    "senti_3": SENTI3_LABELS,
    "senti_6": SENTI6_LABELS,
}
METRIC_KEYS = (
    "accuracy",
    "balanced_accuracy",
    "reweighted_accuracy",
    "f1_macro",
    "kappa_linear",
    "kappa_quadratic",
)

SUMMARY_COLUMNS = [
    "nivel",
    "n",
    "accuracy",
    "balanced_accuracy",
    "reweighted_accuracy",
    "f1_macro",
    "kappa_linear",
    "kappa_quadratic",
]
PER_CLASS_COLUMNS = ["nivel", "clase", "precision", "recall", "f1", "support"]
IC_COLUMNS = ["nivel", "metrica", "variante", "estimador", "ic_inf", "ic_sup", "n_boot", "alpha"]
AGREEMENT_COLUMNS = [
    "par",
    "nivel",
    "n",
    "acuerdo",
    "kappa_linear",
    "kappa_quadratic",
    "fleiss_kappa",
]
PATTERN_ORDER = (
    "unanime",
    "mayoria_sin_llm",
    "mayoria_sin_parlacap",
    "mayoria_sin_humano",
    "sin_mayoria",
)
PATTERN_COLUMNS = ["nivel", "patron", "n", "proporcion"]
DISTANCE_COLUMNS = ["nivel", "comparacion", "distancia", "n", "proporcion", "distancia_media"]


@dataclass(frozen=True)
class SentimentConfig:
    """Parámetros de la muestra y del bootstrap de validación."""

    sample_size: int
    strata: tuple[str, ...]
    seed: int
    bootstrap_n: int
    alpha: float


@dataclass(frozen=True)
class SentimentReport:
    """Resultado de comparar unas anotaciones con las etiquetas de ParlaCAP."""

    summary: pd.DataFrame
    per_class: pd.DataFrame
    confusions: dict[str, pd.DataFrame]
    ic: pd.DataFrame


def build_sentiment_config(config: Mapping[str, Any]) -> SentimentConfig:
    """Construye la configuración de validación desde la sección ``sentiment``."""
    section = config["sentiment"]
    strata = tuple(str(value) for value in section.get("strata", ("senti_3", "term")))
    if not strata:
        raise ValueError("sentiment.strata no puede estar vacío")
    sample_size = int(section.get("sample_size", 200))
    if sample_size <= 0:
        raise ValueError("sentiment.sample_size debe ser positivo")
    bootstrap = section.get("bootstrap", {})
    bootstrap_n = int(bootstrap.get("n", 10000))
    if bootstrap_n < 0:
        raise ValueError("sentiment.bootstrap.n no puede ser negativo")
    alpha = float(bootstrap.get("alpha", 0.05))
    if not 0.0 < alpha < 1.0:
        raise ValueError("sentiment.bootstrap.alpha debe estar en (0, 1)")
    return SentimentConfig(
        sample_size=sample_size,
        strata=strata,
        seed=int(section.get("seed", SEED)),
        bootstrap_n=bootstrap_n,
        alpha=alpha,
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


def build_revision_subsample(
    sample: pd.DataFrame,
    reference: pd.DataFrame,
    per_class: Mapping[str, int],
    seed: int,
) -> pd.DataFrame:
    """Submuestra de revisión equilibrada por clase, barajada y sin etiquetas.

    La selección usa la clase real (``senti_3``) para balancear, pero el CSV
    resultante queda ciego: identificador, fecha, legislatura, texto y las
    columnas vacías que rellenará el revisor.
    """
    merged = sample.merge(
        reference.loc[:, ["utterance_id", "senti_3"]],
        on="utterance_id",
        how="left",
        validate="one_to_one",
    )
    if merged["senti_3"].isna().any():
        raise ValueError("Hay intervenciones de la muestra sin clase de referencia")
    missing = sorted(set(per_class) - set(merged["senti_3"]))
    if missing:
        raise ValueError(f"Clases solicitadas sin datos en la muestra: {missing}")
    rng = np.random.default_rng(seed)
    parts: list[pd.DataFrame] = []
    for label in sorted(per_class):
        group = merged.loc[merged["senti_3"] == label]
        quota = min(int(per_class[label]), len(group))
        if quota <= 0:
            continue
        chosen = np.sort(rng.choice(group.index.to_numpy(), size=quota, replace=False))
        parts.append(group.loc[chosen])
    if not parts:
        raise ValueError("La submuestra de revisión quedó vacía")
    subsample = pd.concat(parts, axis=0)
    subsample = subsample.iloc[rng.permutation(len(subsample))]
    revision = subsample.loc[:, SAMPLE_COLUMNS].copy()
    revision["senti_3_final"] = ""
    revision["senti_6_final"] = ""
    revision["revisado_por"] = ""
    revision["fecha"] = ""
    return revision.loc[:, REVISION_COLUMNS].reset_index(drop=True)


def reweighted_accuracy(
    y_true: Sequence[str], y_pred: Sequence[str], prevalence: Mapping[str, float]
) -> float:
    """Accuracy re-ponderada a la prevalencia del corpus por probabilidad inversa.

    Cada fila pesa ``prevalencia_corpus(clase) / frecuencia_submuestra(clase)``.
    """
    truth = [str(value) for value in y_true]
    preds = [str(value) for value in y_pred]
    if not truth:
        return float("nan")
    frequencies = pd.Series(truth).value_counts(normalize=True).to_dict()
    weights = np.asarray(
        [float(prevalence.get(value, 0.0)) / frequencies[value] for value in truth], dtype=float
    )
    if float(weights.sum()) == 0.0:
        return float("nan")
    return float(accuracy_score(truth, preds, sample_weight=weights))


def _safe_kappa(
    y_true: Sequence[str], y_pred: Sequence[str], labels: Sequence[str], weights: str
) -> float:
    """Kappa de Cohen de scikit-learn silenciando avisos de casos degenerados."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        value = cohen_kappa_score(y_true, y_pred, labels=list(labels), weights=weights)
    return float(value)


def fleiss_kappa(raters: Sequence[Sequence[str]], labels: Sequence[str]) -> float:
    """Kappa de Fleiss (nominal) para varios anotadores sobre la misma rejilla."""
    if not raters or not raters[0]:
        return float("nan")
    index = {label: position for position, label in enumerate(labels)}
    table = np.zeros((len(raters[0]), len(labels)), dtype=float)
    for rater in raters:
        for position, value in enumerate(rater):
            table[position, index[str(value)]] += 1.0
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        value = _statsmodels_fleiss_kappa(table, method="fleiss")
    return float(value)


def corpus_prevalence(reference: pd.DataFrame) -> dict[str, dict[str, float]]:
    """Prevalencia por nivel de las etiquetas de referencia del corpus."""
    return {
        level: {
            str(label): float(value)
            for label, value in reference[level].astype(str).value_counts(normalize=True).items()
        }
        for level in SENTIMENT_LEVELS
    }


def _metrics(
    y_true: Sequence[str],
    y_pred: Sequence[str],
    labels: Sequence[str],
    prevalence: Mapping[str, float],
) -> dict[str, float]:
    """Métricas de un nivel (scikit-learn + re-ponderación propia)."""
    truth = [str(value) for value in y_true]
    preds = [str(value) for value in y_pred]
    if not truth:
        return {key: float("nan") for key in METRIC_KEYS}
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return {
            "accuracy": float(accuracy_score(truth, preds)),
            "balanced_accuracy": float(balanced_accuracy_score(truth, preds)),
            "reweighted_accuracy": float(reweighted_accuracy(truth, preds, prevalence)),
            "f1_macro": float(f1_score(truth, preds, average="macro", zero_division=cast(Any, 0))),
            "kappa_linear": _safe_kappa(truth, preds, labels, "linear"),
            "kappa_quadratic": _safe_kappa(truth, preds, labels, "quadratic"),
        }


def _evaluate_arrays(
    y_true: Sequence[str],
    y_pred: Sequence[str],
    level: str,
    prevalence: Mapping[str, float],
) -> tuple[dict[str, float], pd.DataFrame, list[tuple[str, float, float, float, int]]]:
    """Métricas, confusión y desglose por clase de un nivel."""
    labels = LABELS_BY_LEVEL[level]
    truth = [str(value) for value in y_true]
    preds = [str(value) for value in y_pred]
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        matrix = cast(Any, confusion_matrix(truth, preds, labels=list(labels)))
        precision, recall, f1, support = cast(
            tuple[Any, Any, Any, Any],
            precision_recall_fscore_support(
                truth, preds, labels=list(labels), zero_division=cast(Any, 0)
            ),
        )
    table = pd.DataFrame(
        matrix,
        index=pd.Index(labels, name="real"),
        columns=pd.Index(labels, name="anotado"),
    )
    per_class = [
        (
            label,
            float(precision[index]),
            float(recall[index]),
            float(f1[index]),
            int(support[index]),
        )
        for index, label in enumerate(labels)
    ]
    return _metrics(truth, preds, labels, prevalence), table, per_class


def _label_codes(values: Sequence[str], labels: Sequence[str]) -> IntArray:
    """Codifica etiquetas a enteros según la rejilla fija (falla si hay una ajena)."""
    index = {label: position for position, label in enumerate(labels)}
    codes = np.empty(len(values), dtype=np.int64)
    for position, value in enumerate(values):
        label = str(value)
        if label not in index:
            raise ValueError(f"Etiqueta fuera de la taxonomía: {label!r}")
        codes[position] = index[label]
    return codes


def _confusion_counts(true_codes: IntArray, pred_codes: IntArray, size: int) -> FloatArray:
    """Matriz de confusión vectorizada (``bincount``) a partir de códigos enteros."""
    if true_codes.size == 0:
        return np.zeros((size, size), dtype=float)
    combined = true_codes * size + pred_codes
    counts = np.bincount(combined, minlength=size * size).reshape(size, size).astype(float)
    return cast(FloatArray, counts)


def _kappa_from_counts(counts: FloatArray, weights: str | None) -> float:
    """Kappa de Cohen desde una matriz de confusión (mismo cálculo que scikit-learn)."""
    size = int(counts.shape[0])
    total = float(counts.sum())
    if total == 0.0 or size <= 1:
        return float("nan")
    rows = cast(FloatArray, np.sum(counts, axis=1))
    columns = cast(FloatArray, np.sum(counts, axis=0))
    expected = np.outer(rows, columns) / total
    grid = np.subtract.outer(np.arange(size), np.arange(size))
    if weights is None:
        weight_matrix = 1.0 - np.eye(size)
    elif weights == "linear":
        weight_matrix = np.abs(grid) / (size - 1)
    elif weights == "quadratic":
        weight_matrix = (grid**2) / ((size - 1) ** 2)
    else:
        raise ValueError(f"Pesos de kappa no soportados: {weights!r}")
    denominator = float((weight_matrix * expected).sum())
    if np.isclose(denominator, 0.0):
        return float("nan")
    return float(1.0 - float((weight_matrix * counts).sum()) / denominator)


def _metrics_from_counts(counts: FloatArray, prevalence: FloatArray) -> dict[str, float]:
    """Métricas desde la matriz de confusión (equivalente vectorizado de ``_metrics``)."""
    size = int(counts.shape[0])
    total = float(counts.sum())
    if total == 0.0:
        return {key: float("nan") for key in METRIC_KEYS}
    rows = cast(FloatArray, np.sum(counts, axis=1))
    columns = cast(FloatArray, np.sum(counts, axis=0))
    diagonal = cast(FloatArray, np.diag(counts))
    precision = np.divide(diagonal, columns, out=np.zeros(size), where=columns > 0)
    recall = np.divide(diagonal, rows, out=np.zeros(size), where=rows > 0)
    f1 = np.divide(
        2 * precision * recall,
        precision + recall,
        out=np.zeros(size),
        where=(precision + recall) > 0,
    )
    active = (rows > 0) | (columns > 0)
    present = rows > 0
    prevalence_total = float(prevalence[present].sum())
    reweighted = (
        float((prevalence[present] * recall[present]).sum() / prevalence_total)
        if prevalence_total > 0
        else float("nan")
    )
    return {
        "accuracy": float(diagonal.sum() / total),
        "balanced_accuracy": float(recall[active].mean()) if active.any() else float("nan"),
        "reweighted_accuracy": reweighted,
        "f1_macro": float(f1[active].mean()) if active.any() else float("nan"),
        "kappa_linear": _kappa_from_counts(counts, "linear"),
        "kappa_quadratic": _kappa_from_counts(counts, "quadratic"),
    }


def _bootstrap_ic(
    merged: pd.DataFrame,
    level: str,
    prevalence: Mapping[str, float],
    metrics: Mapping[str, float],
    n_boot: int,
    seed: int,
    alpha: float,
) -> list[dict[str, Any]]:
    """IC bootstrap percentil: i.i.d. por fila, salvo la balanceada (estrato ``senti_3``).

    El remuestreo usa conteos vectorizados (``bincount``) para que 10 000 réplicas no
    dominen el tiempo; las métricas coinciden con ``_metrics`` (scikit-learn).
    """
    labels = LABELS_BY_LEVEL[level]
    annotation_column = REFERENCE_COLUMNS[level]
    truth = _label_codes(merged[level].astype(str).tolist(), labels)
    preds = _label_codes(merged[annotation_column].astype(str).tolist(), labels)
    strata = _label_codes(merged["senti_3"].astype(str).tolist(), SENTI3_LABELS)
    size = len(truth)
    if size == 0 or n_boot <= 0:
        return []
    prevalence_vector = cast(
        FloatArray,
        np.asarray([float(prevalence.get(label, 0.0)) for label in labels], dtype=float),
    )
    groups = [np.flatnonzero(strata == code) for code in range(len(SENTI3_LABELS))]
    groups = [group for group in groups if group.size > 0]
    label_count = len(labels)
    rng = np.random.default_rng(seed)
    iid_keys = ("accuracy", "reweighted_accuracy", "f1_macro", "kappa_linear", "kappa_quadratic")
    iid_samples: dict[str, np.ndarray] = {key: np.empty(n_boot) for key in iid_keys}
    balanced_samples = np.empty(n_boot)
    for iteration in range(n_boot):
        positions = rng.integers(0, size, size)
        resampled = _metrics_from_counts(
            _confusion_counts(
                cast(IntArray, truth[positions]), cast(IntArray, preds[positions]), label_count
            ),
            prevalence_vector,
        )
        for key in iid_keys:
            iid_samples[key][iteration] = resampled[key]
        balanced_positions = cast(
            IntArray,
            np.concatenate([group[rng.integers(0, group.size, group.size)] for group in groups]),
        )
        balanced = _metrics_from_counts(
            _confusion_counts(
                cast(IntArray, truth[balanced_positions]),
                cast(IntArray, preds[balanced_positions]),
                label_count,
            ),
            prevalence_vector,
        )
        balanced_samples[iteration] = balanced["balanced_accuracy"]

    def interval(values: np.ndarray) -> tuple[float, float]:
        low, high = np.nanpercentile(values, [100 * alpha / 2, 100 * (1 - alpha / 2)])
        return float(low), float(high)

    rows: list[dict[str, Any]] = []

    def add(metrica: str, variante: str, estimate: float, values: np.ndarray) -> None:
        low, high = interval(values)
        rows.append(
            {
                "nivel": level,
                "metrica": metrica,
                "variante": variante,
                "estimador": round(float(estimate), 6),
                "ic_inf": round(low, 6),
                "ic_sup": round(high, 6),
                "n_boot": n_boot,
                "alpha": alpha,
            }
        )

    add("accuracy", "cruda", metrics["accuracy"], iid_samples["accuracy"])
    add("accuracy", "balanceada", metrics["balanced_accuracy"], balanced_samples)
    add(
        "accuracy",
        "re-ponderada",
        metrics["reweighted_accuracy"],
        iid_samples["reweighted_accuracy"],
    )
    add("f1_macro", "", metrics["f1_macro"], iid_samples["f1_macro"])
    add("kappa", "lineal", metrics["kappa_linear"], iid_samples["kappa_linear"])
    add("kappa", "cuadratica", metrics["kappa_quadratic"], iid_samples["kappa_quadratic"])
    return rows


def evaluate_sentiment(
    annotations: pd.DataFrame,
    reference: pd.DataFrame,
    *,
    prevalence: Mapping[str, Mapping[str, float]] | None = None,
    n_boot: int = 0,
    seed: int = SEED,
    alpha: float = 0.05,
) -> SentimentReport:
    """Compara anotaciones con las etiquetas ParlaCAP (3 y 6 clases).

    ``prevalence`` permite re-ponderar a la prevalencia del corpus; si es ``None`` se
    calcula sobre ``reference``. ``n_boot > 0`` añade intervalos bootstrap percentil.
    """
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
    if prevalence is None:
        prevalence = corpus_prevalence(reference)

    for level in SENTIMENT_LEVELS:
        allowed = set(LABELS_BY_LEVEL[level])
        seen = set(merged[level].astype(str)) | set(merged[REFERENCE_COLUMNS[level]].astype(str))
        unexpected = sorted(seen - allowed)
        if unexpected:
            raise ValueError(f"Etiquetas fuera de la taxonomía en {level}: {unexpected}")

    summary_rows: list[dict[str, Any]] = []
    class_rows: list[dict[str, Any]] = []
    confusions: dict[str, pd.DataFrame] = {}
    ic_rows: list[dict[str, Any]] = []
    for level in SENTIMENT_LEVELS:
        annotation_column = REFERENCE_COLUMNS[level]
        metrics, table, per_class = _evaluate_arrays(
            merged[level].astype(str).tolist(),
            merged[annotation_column].astype(str).tolist(),
            level,
            prevalence[level],
        )
        confusions[level] = table
        summary_rows.append(
            {
                "nivel": level,
                "n": len(merged),
                **{key: round(value, 6) for key, value in metrics.items()},
            }
        )
        for label, precision, recall, f1, support in per_class:
            class_rows.append(
                {
                    "nivel": level,
                    "clase": label,
                    "precision": round(precision, 6),
                    "recall": round(recall, 6),
                    "f1": round(f1, 6),
                    "support": support,
                }
            )
        if n_boot > 0:
            ic_rows.extend(
                _bootstrap_ic(merged, level, prevalence[level], metrics, n_boot, seed, alpha)
            )
    return SentimentReport(
        summary=pd.DataFrame(summary_rows, columns=SUMMARY_COLUMNS),
        per_class=pd.DataFrame(class_rows, columns=PER_CLASS_COLUMNS),
        confusions=confusions,
        ic=pd.DataFrame(ic_rows, columns=IC_COLUMNS),
    )


def build_concordance(annotations: pd.DataFrame, reference: pd.DataFrame) -> pd.DataFrame:
    """Tabla pareada ParlaCAP ↔ pre-anotación LLM con marcas de coincidencia."""
    required = {"utterance_id", "senti_3_final", "senti_6_final"}
    missing = sorted(required - set(annotations.columns))
    if missing:
        raise ValueError(f"Faltan columnas de anotación: {missing}")
    merged = annotations.loc[:, ["utterance_id", "senti_3_final", "senti_6_final"]].merge(
        reference.loc[:, ["utterance_id", "senti_3", "senti_6"]],
        on="utterance_id",
        how="left",
        validate="one_to_one",
    )
    if merged["senti_3"].isna().any() or merged["senti_6"].isna().any():
        raise ValueError("Hay anotaciones sin referencia en el corpus")
    table = merged.loc[
        :, ["utterance_id", "senti_3", "senti_3_final", "senti_6", "senti_6_final"]
    ].copy()
    table["match_senti_3"] = table["senti_3"] == table["senti_3_final"]
    table["match_senti_6"] = table["senti_6"] == table["senti_6_final"]
    return table.reset_index(drop=True)


def _three_way_frame(
    revision: pd.DataFrame, annotations: pd.DataFrame, reference: pd.DataFrame
) -> pd.DataFrame:
    """Terna alineada por ítem: ParlaCAP, pre-anotación LLM y revisión humana."""
    human = revision.loc[:, ["utterance_id", "senti_3_final", "senti_6_final"]].rename(
        columns={"senti_3_final": "human_3", "senti_6_final": "human_6"}
    )
    llm = annotations.loc[:, ["utterance_id", "senti_3_final", "senti_6_final"]].rename(
        columns={"senti_3_final": "llm_3", "senti_6_final": "llm_6"}
    )
    merged = human.merge(llm, on="utterance_id", how="inner", validate="one_to_one").merge(
        reference.loc[:, ["utterance_id", "senti_3", "senti_6"]],
        on="utterance_id",
        how="inner",
        validate="one_to_one",
    )
    return merged.reset_index(drop=True)


def build_agreement(
    revision: pd.DataFrame, annotations: pd.DataFrame, reference: pd.DataFrame
) -> pd.DataFrame:
    """Acuerdo pareado a tres bandas (ParlaCAP, pre-anotación LLM y revisión humana)."""
    merged = _three_way_frame(revision, annotations, reference)
    pair_defs = (
        ("parlacap_humano", "senti_{suffix}", "human_{suffix}"),
        ("llm_humano", "llm_{suffix}", "human_{suffix}"),
        ("parlacap_llm", "senti_{suffix}", "llm_{suffix}"),
    )
    rows: list[dict[str, Any]] = []
    for level, suffix in (("senti_3", "3"), ("senti_6", "6")):
        labels = LABELS_BY_LEVEL[level]
        for pair, left_template, right_template in pair_defs:
            left = merged[left_template.format(suffix=suffix)].astype(str).tolist()
            right = merged[right_template.format(suffix=suffix)].astype(str).tolist()
            rows.append(
                {
                    "par": pair,
                    "nivel": level,
                    "n": len(merged),
                    "acuerdo": round(float(accuracy_score(left, right)), 6),
                    "kappa_linear": round(_safe_kappa(left, right, labels, "linear"), 6),
                    "kappa_quadratic": round(_safe_kappa(left, right, labels, "quadratic"), 6),
                    "fleiss_kappa": float("nan"),
                }
            )
        raters = [
            merged[f"senti_{suffix}"].astype(str).tolist(),
            merged[f"human_{suffix}"].astype(str).tolist(),
            merged[f"llm_{suffix}"].astype(str).tolist(),
        ]
        rows.append(
            {
                "par": "fleiss_3anotadores",
                "nivel": level,
                "n": len(merged),
                "acuerdo": float("nan"),
                "kappa_linear": float("nan"),
                "kappa_quadratic": float("nan"),
                "fleiss_kappa": round(fleiss_kappa(raters, labels), 6),
            }
        )
    return pd.DataFrame(rows, columns=AGREEMENT_COLUMNS)


def _pattern_name(parlacap: str, llm: str, human: str) -> str:
    if parlacap == llm == human:
        return "unanime"
    if parlacap == human:
        return "mayoria_sin_llm"
    if llm == human:
        return "mayoria_sin_parlacap"
    if parlacap == llm:
        return "mayoria_sin_humano"
    return "sin_mayoria"


def build_pattern_table(
    revision: pd.DataFrame, annotations: pd.DataFrame, reference: pd.DataFrame
) -> pd.DataFrame:
    """Patrones de mayoría por ítem en la terna ParlaCAP · LLM · humano."""
    merged = _three_way_frame(revision, annotations, reference)
    rows: list[dict[str, Any]] = []
    for level, suffix in (("senti_3", "3"), ("senti_6", "6")):
        patterns = [
            _pattern_name(str(parlacap), str(llm), str(human))
            for parlacap, llm, human in zip(
                merged[f"senti_{suffix}"],
                merged[f"llm_{suffix}"],
                merged[f"human_{suffix}"],
                strict=True,
            )
        ]
        counts = pd.Series(patterns).value_counts()
        for name in PATTERN_ORDER:
            n = int(counts.get(name, 0))
            rows.append(
                {
                    "nivel": level,
                    "patron": name,
                    "n": n,
                    "proporcion": round(n / len(merged), 6) if len(merged) else 0.0,
                }
            )
    return pd.DataFrame(rows, columns=PATTERN_COLUMNS)


def build_distance_table(
    revision: pd.DataFrame, annotations: pd.DataFrame, reference: pd.DataFrame
) -> pd.DataFrame:
    """Distribución de distancias ordinales en ``senti_6`` frente al humano."""
    merged = _three_way_frame(revision, annotations, reference)
    rank = {label: position for position, label in enumerate(SENTI6_LABELS)}
    rows: list[dict[str, Any]] = []
    for name, column in (("parlacap", "senti_6"), ("llm", "llm_6")):
        distances = (merged[column].map(rank) - merged["human_6"].map(rank)).abs()
        if distances.isna().any():
            raise ValueError("Hay etiquetas de senti_6 fuera de la taxonomía")
        mean = round(float(distances.mean()), 6)
        counts = distances.value_counts().sort_index()
        for distance, n in counts.items():
            rows.append(
                {
                    "nivel": "senti_6",
                    "comparacion": f"{name}_humano",
                    "distancia": int(cast(int, distance)),
                    "n": int(n),
                    "proporcion": round(int(n) / len(merged), 6),
                    "distancia_media": mean,
                }
            )
    return pd.DataFrame(rows, columns=DISTANCE_COLUMNS)


def write_revision_tables(report: SentimentReport, reports_dir: Path) -> list[Path]:
    """Escribe las tablas de la revisión humana (métricas, clase, IC y confusión)."""
    written: list[Path] = []
    targets = (
        (REVISION_METRICS_FILENAME, report.summary),
        (REVISION_PER_CLASS_FILENAME, report.per_class),
        (REVISION_IC_FILENAME, report.ic),
    )
    for filename, frame in targets:
        path = reports_dir / filename
        frame.to_csv(path, index=False)
        written.append(path)
    for level, table in report.confusions.items():
        path = reports_dir / REVISION_CONFUSION_TEMPLATE.format(level=level)
        table.to_csv(path)
        written.append(path)
    return written


def write_concordance_tables(
    concordance: pd.DataFrame, metrics: pd.DataFrame, reports_dir: Path
) -> list[Path]:
    """Escribe la concordancia LLM ↔ ParlaCAP y sus métricas secundarias."""
    written: list[Path] = []
    for filename, frame in (
        (CONCORDANCE_FILENAME, concordance),
        (CONCORDANCE_METRICS_FILENAME, metrics),
    ):
        path = reports_dir / filename
        frame.to_csv(path, index=False)
        written.append(path)
    return written


def write_agreement_table(agreement: pd.DataFrame, reports_dir: Path) -> list[Path]:
    """Escribe el acuerdo pareado a tres bandas."""
    path = reports_dir / AGREEMENT_FILENAME
    agreement.to_csv(path, index=False)
    return [path]


def _format_float(value: float) -> str:
    return f"{value:.6f}"


def _plain_table_html(frame: pd.DataFrame) -> str:
    if frame.empty:
        return '<p class="vacio">sin datos</p>'
    return frame.to_html(index=False, border=0, classes="tabla", float_format=_format_float)


def _confusion_table_html(table: pd.DataFrame) -> str:
    labels = [str(label) for label in table.index]
    counts = table.to_numpy(dtype=float)
    parts = ['<table class="confusion"><thead><tr><th></th>']
    parts.extend(f"<th>{label}</th>" for label in labels)
    parts.append("</tr></thead><tbody>")
    for row_position, row_label in enumerate(labels):
        row_total = float(counts[row_position].sum())
        parts.append(f"<tr><th>{row_label}</th>")
        for column_position in range(len(labels)):
            count = float(counts[row_position, column_position])
            proportion = 0.0 if row_total == 0 else count / row_total
            alpha = 0.06 + 0.74 * proportion
            text_color = "color:#ffffff;" if proportion > 0.55 else ""
            parts.append(
                f'<td style="background-color:rgba(31,119,180,{alpha:.3f});{text_color}">'
                f"{int(count)}</td>"
            )
        parts.append("</tr>")
    parts.append("</tbody></table>")
    return "".join(parts)


def render_revision_html(
    report: SentimentReport,
    agreement: pd.DataFrame | None,
    concordance_metrics: pd.DataFrame | None,
    patterns: pd.DataFrame | None,
    distances: pd.DataFrame | None,
    meta: Mapping[str, Any],
) -> str:
    """Informe HTML autocontenido (sin dependencias ni marcas de tiempo de reloj)."""
    author = str(meta.get("revisado_por", ""))
    date = str(meta.get("fecha", ""))
    seed = meta.get("seed")
    n_boot = meta.get("n_boot")
    alpha = meta.get("alpha")
    style = """
    body { font-family: system-ui, Segoe UI, Helvetica, Arial, sans-serif;
           margin: 2rem auto; max-width: 1080px; color: #1c1c1c;
           line-height: 1.45; padding: 0 1rem; }
    h1 { font-size: 1.6rem; margin-bottom: 0.2rem; }
    h2 { font-size: 1.15rem; margin-top: 2rem; border-bottom: 1px solid #ddd;
         padding-bottom: 0.2rem; }
    table.tabla { border-collapse: collapse; font-size: 0.86rem; margin: 0.6rem 0; }
    table.tabla th, table.tabla td { border: 1px solid #ddd;
         padding: 0.25rem 0.5rem; text-align: right; }
    table.tabla th { background: #f4f6f8; }
    table.confusion { border-collapse: collapse; font-size: 0.86rem;
         margin: 0.6rem 1.5rem 0.6rem 0; }
    table.confusion th, table.confusion td { border: 1px solid #ccc;
         padding: 0.3rem 0.55rem; text-align: center; }
    table.confusion thead th, table.confusion tbody th { background: #f4f6f8; }
    .meta { color: #555; font-size: 0.85rem; }
    .nota { background: #fff8e1; border-left: 3px solid #f0ad4e;
         padding: 0.5rem 0.8rem; font-size: 0.88rem; }
    .vacio { color: #777; font-style: italic; }
    footer { margin-top: 2.5rem; color: #666; font-size: 0.8rem;
         border-top: 1px solid #ddd; padding-top: 0.6rem; }
    """
    parts: list[str] = [
        "<!DOCTYPE html>",
        '<html lang="es"><head><meta charset="utf-8">',
        "<title>Validación de sentimiento (revisión humana)</title>",
        f"<style>{style}</style></head><body>",
        "<h1>Validación de sentimiento ParlaCAP/ParlaSent contra revisión humana</h1>",
        (
            '<p class="meta">Revisión humana de la submuestra equilibrada '
            f"(n={meta.get('n')}) por <strong>{author}</strong>, fecha {date}. "
            "Referencia: ParlaCAP 1.0 (predicciones de ParlaSent 1.0). ParlaMint aporta "
            "texto y metadatos, no sentimiento.</p>"
        ),
        "<h2>Métricas principales (por nivel)</h2>",
        _plain_table_html(report.summary),
        "<h2>Intervalos de confianza (bootstrap percentil)</h2>",
        _plain_table_html(report.ic),
        "<h2>Métricas por clase</h2>",
        _plain_table_html(report.per_class),
        "<h2>Matrices de confusión (real x anotado)</h2>",
    ]
    for level in SENTIMENT_LEVELS:
        table = report.confusions.get(level)
        parts.append(f"<h3>{level}</h3>")
        parts.append(
            _confusion_table_html(table) if table is not None else '<p class="vacio">sin datos</p>'
        )
    parts.append("<h2>Acuerdo a tres bandas (ParlaCAP · LLM · humano)</h2>")
    if agreement is None:
        parts.append('<p class="vacio">sin pre-anotaciones: no disponible</p>')
    else:
        parts.append(_plain_table_html(agreement))
    parts.append("<h2>Patrones de mayoría por ítem (ParlaCAP · LLM · humano)</h2>")
    if patterns is None:
        parts.append('<p class="vacio">sin pre-anotaciones: no disponible</p>')
    else:
        parts.append(
            '<p class="nota">Quién queda fuera de la mayoría cuando los tres no coinciden; '
            "el reparto mide calibraciones compartidas entre modelos.</p>"
        )
        parts.append(_plain_table_html(patterns))
    parts.append("<h2>Distancias ordinales en senti_6 frente al humano</h2>")
    if distances is None:
        parts.append('<p class="vacio">sin pre-anotaciones: no disponible</p>')
    else:
        parts.append(
            '<p class="nota">Escala ordinal de seis niveles: distancia 0 = coincidencia, '
            "1 = categoría contigua.</p>"
        )
        parts.append(_plain_table_html(distances))
    parts.append("<h2>Concordancia LLM vs ParlaCAP (secundaria, modelo-modelo)</h2>")
    parts.append(
        '<p class="nota">No es calidad contra un oro humano: mide acuerdo entre modelos '
        "(D-36). Se incluye solo como referencia.</p>"
    )
    if concordance_metrics is None:
        parts.append('<p class="vacio">sin pre-anotaciones: no disponible</p>')
    else:
        parts.append(_plain_table_html(concordance_metrics))
    parts.extend(
        [
            "<h2>Limitaciones</h2>",
            "<ul>",
            "<li>n = "
            f"{meta.get('n')} con diseño equilibrado 30/30/20; la accuracy cruda no estima la "
            "prevalencia del corpus: usa la re-ponderada.</li>",
            "<li>Bootstrap i.i.d. por fila (la balanceada se remuestrea por estrato "
            "<code>senti_3</code>); no modela la dependencia entre intervenciones "
            "de una misma sesión.</li>",
            "<li>Las etiquetas de referencia son predicciones de ParlaSent, "
            "no anotación humana.</li>",
            "</ul>",
            "<h2>Reproducir</h2>",
            "<pre>uv run --extra corpus python -m src.nlp.sentiment</pre>",
            (
                f"<footer>pandas {pd.__version__} · SEED={seed} · n_boot={n_boot} · "
                f"alpha={alpha} · generado por <code>src/nlp/sentiment.py</code></footer>"
            ),
            "</body></html>",
        ]
    )
    return "\n".join(parts) + "\n"


def _join_distinct(frame: pd.DataFrame, column: str) -> str:
    if column not in frame.columns:
        return ""
    values = sorted({str(value) for value in frame[column].dropna().tolist()})
    return ", ".join(values)


def _load_corpus(path: Path) -> pd.DataFrame:
    return pd.read_parquet(path, columns=CORPUS_COLUMNS)


def main() -> None:
    """CLI: genera la muestra, la concordancia LLM y las métricas de la revisión humana."""
    config = build_sentiment_config(load_config(CONFIG_DIR / "experiment_01.yaml"))
    reports_dir = PROJECT_ROOT / "reports" / "tables"
    reports_dir.mkdir(parents=True, exist_ok=True)
    sample_path = reports_dir / SAMPLE_FILENAME
    annotations_path = reports_dir / ANNOTATIONS_FILENAME
    revision_path = reports_dir / REVISION_FILENAME

    corpus: pd.DataFrame | None = None

    def get_corpus() -> pd.DataFrame:
        nonlocal corpus
        if corpus is None:
            corpus = _load_corpus(
                PROJECT_ROOT / "data" / "processed" / "intervenciones_limpias.parquet"
            )
        return corpus

    if not sample_path.exists():
        sample = proportional_sample(get_corpus(), config)
        sample.to_csv(sample_path, index=False)
        print(f"muestra de {len(sample)} intervenciones -> {sample_path}")
    else:
        print(f"muestra existente -> {sample_path}")

    annotations: pd.DataFrame | None = None
    concordance_metrics: pd.DataFrame | None = None
    if annotations_path.exists():
        annotations = pd.read_csv(annotations_path)
        reference = get_corpus()
        concordance = build_concordance(annotations, reference)
        concordance_metrics = evaluate_sentiment(
            annotations, reference, prevalence=corpus_prevalence(reference), seed=config.seed
        ).summary
        for path in write_concordance_tables(concordance, concordance_metrics, reports_dir):
            print(f"escrito: {path}")
    else:
        print(f"sin pre-anotaciones ({annotations_path}); se omite la concordancia LLM")

    if not revision_path.exists():
        print(f"sin revisión ({revision_path}); se omiten las métricas humanas")
        return

    revision = pd.read_csv(revision_path)
    reference = get_corpus()
    prevalence = corpus_prevalence(reference)
    report = evaluate_sentiment(
        revision,
        reference,
        prevalence=prevalence,
        n_boot=config.bootstrap_n,
        seed=config.seed,
        alpha=config.alpha,
    )
    for path in write_revision_tables(report, reports_dir):
        print(f"escrito: {path}")

    agreement: pd.DataFrame | None = None
    patterns: pd.DataFrame | None = None
    distances: pd.DataFrame | None = None
    if annotations is not None:
        agreement = build_agreement(revision, annotations, reference)
        patterns = build_pattern_table(revision, annotations, reference)
        distances = build_distance_table(revision, annotations, reference)
        for path in write_agreement_table(agreement, reports_dir):
            print(f"escrito: {path}")
    else:
        print("sin pre-anotaciones: se omite el acuerdo a 3 bandas")

    meta: dict[str, Any] = {
        "n": len(revision),
        "revisado_por": _join_distinct(revision, "revisado_por"),
        "fecha": _join_distinct(revision, "fecha"),
        "seed": config.seed,
        "n_boot": config.bootstrap_n,
        "alpha": config.alpha,
    }
    html_path = PROJECT_ROOT / "reports" / REPORT_HTML_FILENAME
    html_path.write_text(
        render_revision_html(report, agreement, concordance_metrics, patterns, distances, meta),
        encoding="utf-8",
    )
    print(f"escrito: {html_path}")
    print(report.summary.to_string(index=False))


if __name__ == "__main__":
    main()
