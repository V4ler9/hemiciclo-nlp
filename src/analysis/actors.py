"""Capa de actores de la v2 (D-45).

Construye series mensuales por partido y estatus, descompone los cambios de
cuota y de tono en componente intra-partido y componente de composición, y
genera el contrafactual de tono que sostiene la tesis editorial:

    el tono agregado no cae porque todos hablen peor, sino porque cambia
    quién habla y cómo habla el PP.

Las series de tópicos se excluyen de outliers (regla D-28); las series de tono
usan todas las intervenciones. La descomposición es descriptiva, no causal.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false, reportUnknownParameterType=false, reportUnknownLambdaType=false

from __future__ import annotations

import logging
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import numpy.typing as npt
import pandas as pd

from src.utils.config import CONFIG_DIR, PROJECT_ROOT, SEED, load_config

logger = logging.getLogger(__name__)

PARTY_MAPPING_COLUMNS = ("raw_label", "family", "notes")
ACTOR_SERIES_COLUMNS = [
    "month",
    "party_family",
    "party_status",
    "n",
    "n_assigned",
    "share_all",
    "share_assigned",
    "tone_mean",
    "negative_share",
    "outlier_rate",
    "has_session",
]
DECOMPOSITION_COLUMNS = [
    "serie",
    "serie_id",
    "fecha",
    "metrica",
    "nivel",
    "partido",
    "estatus",
    "n_antes",
    "n_despues",
    "peso_antes",
    "peso_despues",
    "valor_antes",
    "valor_despues",
    "delta_total_serie",
    "contribucion_dentro",
    "contribucion_composicion",
    "residual",
    "significativo_bh",
    "tamano_serie",
]
COUNTERFACTUAL_COLUMNS = [
    "month",
    "n",
    "neg_share_real",
    "neg_share_ajustado",
    "senti_n_real",
    "senti_n_ajustado",
    "brecha_neg",
    "brecha_senti",
    "base_start",
    "base_end",
]
TONE_CI_COLUMNS = [
    "metrica",
    "fecha",
    "delta",
    "ic_inf",
    "ic_sup",
    "n_boot",
    "n_antes",
    "n_despues",
]
METRIC_TOPIC = "cuota_topico"
METRIC_NEGATIVE = "negative_share"
METRIC_TONE = "senti_n"
GLOBAL_FAMILY = "Todos"
GLOBAL_STATUS = "Todos"
RESIDUAL_LABEL = "__residual__"

FloatArray = npt.NDArray[np.float64]


@dataclass(frozen=True)
class ActorConfig:
    """Rutas y parámetros de la capa de actores."""

    mapping_path: Path
    interventions_path: Path
    assignments_path: Path
    monthly_series_path: Path
    series_parquet_path: Path
    series_csv_path: Path
    decomposition_path: Path
    counterfactual_path: Path
    tone_ci_path: Path
    min_cell: int
    bootstrap_n: int
    baseline_start: str
    baseline_end: str
    seed: int


def build_actor_config(config: Mapping[str, Any], root: Path | None = None) -> ActorConfig:
    """Construye la configuración de actores desde la sección ``actors``."""
    base = root or PROJECT_ROOT
    section = config["actors"]
    return ActorConfig(
        mapping_path=base / str(section["mapping_path"]),
        interventions_path=base / str(section["interventions_path"]),
        assignments_path=base / str(section["assignments_path"]),
        monthly_series_path=base / str(section["monthly_series_path"]),
        series_parquet_path=base / str(section["series_parquet_path"]),
        series_csv_path=base / str(section["series_csv_path"]),
        decomposition_path=base / str(section["decomposition_path"]),
        counterfactual_path=base / str(section["counterfactual_path"]),
        tone_ci_path=base / str(section["tone_ci_path"]),
        min_cell=int(section.get("min_cell", 10)),
        bootstrap_n=int(section.get("bootstrap_n", 2000)),
        baseline_start=str(section.get("baseline_start", "2015-01")),
        baseline_end=str(section.get("baseline_end", "2019-11")),
        seed=int(config.get("seed", SEED)),
    )


def load_party_mapping(path: Path) -> pd.DataFrame:
    """Carga y valida el mapeo etiqueta cruda → familia de partido."""
    mapping = pd.read_csv(path, dtype=str)
    missing = [column for column in PARTY_MAPPING_COLUMNS if column not in mapping.columns]
    if missing:
        raise ValueError(f"Faltan columnas en el mapeo de partidos: {missing}")
    mapping = mapping.loc[:, list(PARTY_MAPPING_COLUMNS)].copy()
    mapping["raw_label"] = mapping["raw_label"].fillna("").str.strip()
    mapping["family"] = mapping["family"].fillna("").str.strip()
    mapping["notes"] = mapping["notes"].fillna("").str.strip()
    if (mapping["raw_label"] == "").any() or (mapping["family"] == "").any():
        raise ValueError("El mapeo de partidos tiene etiquetas o familias vacías")
    duplicated = mapping["raw_label"].duplicated(keep=False)
    if duplicated.any():
        labels = sorted(mapping.loc[duplicated, "raw_label"].unique())
        raise ValueError(f"Etiquetas duplicadas en el mapeo de partidos: {labels}")
    return mapping


def assign_party_families(interventions: pd.DataFrame, mapping: pd.DataFrame) -> pd.DataFrame:
    """Añade ``party_family`` y normaliza ``party_status``."""
    required = {"speaker_party", "party_status"}
    missing = sorted(required - set(interventions.columns))
    if missing:
        raise ValueError(f"Faltan columnas de partido: {missing}")
    frame = interventions.copy()
    raw = frame["speaker_party"].fillna("SIN_PARTIDO").astype(str).str.strip()
    lookup = mapping.set_index("raw_label")["family"]
    family = raw.map(lookup)
    unknown = sorted(raw.loc[family.isna()].unique())
    if unknown:
        raise ValueError(f"Etiquetas de partido sin mapear: {unknown}")
    frame["party_family"] = family.astype(str)
    frame["party_status"] = frame["party_status"].fillna("Desconocido").astype(str).str.strip()
    return frame


def load_interventions(config: ActorConfig) -> pd.DataFrame:
    """Carga intervenciones, asignaciones de tópico y las une."""
    corpus = pd.read_parquet(
        config.interventions_path,
        columns=[
            "utterance_id",
            "date",
            "speaker_party",
            "party_status",
            "senti_n",
            "senti_3",
            "n_words",
        ],
    )
    assignments = pd.read_parquet(
        config.assignments_path,
        columns=["utterance_id", "bertopic_topic", "is_outlier"],
    )
    frame = corpus.merge(assignments, on="utterance_id", how="left", validate="one_to_one")
    if frame["bertopic_topic"].isna().any():
        raise ValueError("Hay intervenciones sin asignación de tópico")
    frame["date"] = pd.to_datetime(frame["date"], errors="raise")
    frame["month"] = frame["date"].dt.to_period("M").dt.to_timestamp()
    frame["negative"] = (frame["senti_3"] == "Negative").astype(float)
    frame["is_outlier"] = frame["is_outlier"].astype(bool)
    mapping = load_party_mapping(config.mapping_path)
    return assign_party_families(frame, mapping)


def _monthly_grid(frame: pd.DataFrame) -> pd.DatetimeIndex:
    """Rejilla mensual completa entre el primer y el último mes observados."""
    return pd.date_range(frame["month"].min(), frame["month"].max(), freq="MS")


def build_actor_series(interventions: pd.DataFrame, config: ActorConfig) -> pd.DataFrame:
    """Series mensuales por partido x estatus y fila global ``Todos``.

    ``share_all`` usa todas las intervenciones; ``share_assigned`` usa solo las
    asignadas a un tópico (sin outliers), que es el denominador de las cuotas.
    """
    required = {"utterance_id", "month", "party_family", "party_status", "senti_n", "negative"}
    missing = sorted(required - set(interventions.columns))
    if missing:
        raise ValueError(f"Faltan columnas para las series de actores: {missing}")
    frame = interventions.copy()
    frame["is_assigned"] = ~frame["is_outlier"].astype(bool)

    total = frame.groupby("month")["utterance_id"].size()
    total_assigned = frame.loc[frame["is_assigned"]].groupby("month")["utterance_id"].size()
    global_metrics = frame.groupby("month").agg(
        tone_mean=("senti_n", "mean"),
        negative_share=("negative", "mean"),
        outlier_rate=("is_outlier", "mean"),
    )
    groups = frame.groupby(["month", "party_family", "party_status"], observed=True).agg(
        n=("utterance_id", "size"),
        n_assigned=("is_assigned", "sum"),
        tone_mean=("senti_n", "mean"),
        negative_share=("negative", "mean"),
        outlier_rate=("is_outlier", "mean"),
    )
    family_metrics = frame.groupby(["month", "party_family"], observed=True).agg(
        n=("utterance_id", "size"),
        n_assigned=("is_assigned", "sum"),
        tone_mean=("senti_n", "mean"),
        negative_share=("negative", "mean"),
        outlier_rate=("is_outlier", "mean"),
    )
    combinations = sorted(
        {
            (str(family), str(status))
            for family, status in zip(frame["party_family"], frame["party_status"], strict=False)
        }
    )
    families = sorted(str(family) for family in frame["party_family"].unique())
    rows: list[dict[str, Any]] = []
    for month in _monthly_grid(frame):
        n_total = int(total.get(month, 0))
        n_assigned_total = int(total_assigned.get(month, 0))
        has_session = n_total > 0
        global_row = global_metrics.loc[month] if has_session else None
        rows.append(
            {
                "month": month,
                "party_family": GLOBAL_FAMILY,
                "party_status": GLOBAL_STATUS,
                "n": n_total,
                "n_assigned": n_assigned_total,
                "share_all": 1.0 if has_session else float("nan"),
                "share_assigned": 1.0 if n_assigned_total else float("nan"),
                "tone_mean": float(global_row["tone_mean"])
                if global_row is not None
                else float("nan"),
                "negative_share": (
                    float(global_row["negative_share"]) if global_row is not None else float("nan")
                ),
                "outlier_rate": (
                    float(global_row["outlier_rate"]) if global_row is not None else float("nan")
                ),
                "has_session": has_session,
            }
        )
        for family, status in combinations:
            key = (month, family, status)
            if key in groups.index:
                record = groups.loc[key]
                n = int(record["n"])
                n_assigned = int(record["n_assigned"])
                tone_mean = float(record["tone_mean"]) if n else float("nan")
                negative_share = float(record["negative_share"]) if n else float("nan")
                outlier_rate = float(record["outlier_rate"]) if n else float("nan")
            else:
                n = 0
                n_assigned = 0
                tone_mean = float("nan")
                negative_share = float("nan")
                outlier_rate = float("nan")
            rows.append(
                {
                    "month": month,
                    "party_family": family,
                    "party_status": status,
                    "n": n,
                    "n_assigned": n_assigned,
                    "share_all": n / n_total if n_total else float("nan"),
                    "share_assigned": (
                        n_assigned / n_assigned_total if n_assigned_total else float("nan")
                    ),
                    "tone_mean": tone_mean,
                    "negative_share": negative_share,
                    "outlier_rate": outlier_rate,
                    "has_session": has_session,
                }
            )
        for family in families:
            key = (month, family)
            if key in family_metrics.index:
                record = family_metrics.loc[key]
                n = int(record["n"])
                n_assigned = int(record["n_assigned"])
                tone_mean = float(record["tone_mean"]) if n else float("nan")
                negative_share = float(record["negative_share"]) if n else float("nan")
                outlier_rate = float(record["outlier_rate"]) if n else float("nan")
            else:
                n = 0
                n_assigned = 0
                tone_mean = float("nan")
                negative_share = float("nan")
                outlier_rate = float("nan")
            rows.append(
                {
                    "month": month,
                    "party_family": family,
                    "party_status": GLOBAL_STATUS,
                    "n": n,
                    "n_assigned": n_assigned,
                    "share_all": n / n_total if n_total else float("nan"),
                    "share_assigned": (
                        n_assigned / n_assigned_total if n_assigned_total else float("nan")
                    ),
                    "tone_mean": tone_mean,
                    "negative_share": negative_share,
                    "outlier_rate": outlier_rate,
                    "has_session": has_session,
                }
            )
    return pd.DataFrame(rows, columns=ACTOR_SERIES_COLUMNS)


def _series_months(
    monthly_series: pd.DataFrame, series_type: str, series_id: str
) -> tuple[pd.Series, FloatArray]:
    """Meses y valores finitos de una serie mensual, en orden temporal."""
    subset = monthly_series.loc[
        (monthly_series["series_type"] == series_type)
        & (monthly_series["series_id"].astype(str) == str(series_id))
    ].sort_values("month")
    values = subset["value"].to_numpy(dtype=np.float64)
    months = pd.to_datetime(subset["month"])
    mask = np.isfinite(values)
    return months.loc[mask].reset_index(drop=True), values[mask]


def _decompose_topic_change(
    topic_id: int,
    change: Mapping[str, Any],
    monthly_series: pd.DataFrame,
    party_month: pd.Series,
    topic_month: pd.Series,
    level: str,
) -> list[dict[str, Any]]:
    """Descompone un cambio de cuota de tópico sobre los segmentos PELT."""
    keys = ["party_family"] if level == "partido" else ["party_family", "party_status"]
    months, values = _series_months(monthly_series, "topic", str(topic_id))
    index = int(change["indice"])
    if not 0 < index < len(values):
        raise ValueError(f"Índice fuera de rango para el tópico {topic_id}: {index}")
    before_months = set(months.iloc[:index].tolist())
    after_months = set(months.iloc[index:].tolist())

    mask_before = party_month.index.get_level_values("month").isin(before_months)
    mask_after = party_month.index.get_level_values("month").isin(after_months)
    before = party_month.loc[mask_before].groupby(level=keys).sum()
    after = party_month.loc[mask_after].groupby(level=keys).sum()
    key_index = before.index.union(after.index)
    before = before.reindex(key_index, fill_value=0.0)
    after = after.reindex(key_index, fill_value=0.0)

    topic_mask_before = topic_month.index.get_level_values("month").isin(before_months) & (
        topic_month.index.get_level_values("bertopic_topic") == int(topic_id)
    )
    topic_mask_after = topic_month.index.get_level_values("month").isin(after_months) & (
        topic_month.index.get_level_values("bertopic_topic") == int(topic_id)
    )
    topic_before = topic_month.loc[topic_mask_before].groupby(level=keys).sum()
    topic_after = topic_month.loc[topic_mask_after].groupby(level=keys).sum()
    topic_before = topic_before.reindex(key_index, fill_value=0.0)
    topic_after = topic_after.reindex(key_index, fill_value=0.0)
    value_before = (topic_before / before).replace([np.inf, -np.inf], np.nan)
    value_after = (topic_after / after).replace([np.inf, -np.inf], np.nan)
    delta_total = float(values[index:].mean() - values[:index].mean())

    rows: list[dict[str, Any]] = []
    total_within = 0.0
    total_composition = 0.0
    for key in key_index:
        n_before = float(before.loc[key])
        n_after = float(after.loc[key])
        weight_before = n_before / float(before.sum()) if float(before.sum()) else float("nan")
        weight_after = n_after / float(after.sum()) if float(after.sum()) else float("nan")
        val_before = float(value_before.loc[key])
        val_after = float(value_after.loc[key])
        within = (
            weight_after * (val_after - val_before)
            if np.isfinite(weight_after) and np.isfinite(val_before) and np.isfinite(val_after)
            else float("nan")
        )
        composition = (
            (weight_after - weight_before) * val_before
            if np.isfinite(weight_before) and np.isfinite(weight_after) and np.isfinite(val_before)
            else float("nan")
        )
        if np.isfinite(within):
            total_within += within
        if np.isfinite(composition):
            total_composition += composition
        if level == "partido":
            family = str(key)
            status = GLOBAL_STATUS
        else:
            family, status = key
        rows.append(
            {
                "serie": "topic",
                "serie_id": str(topic_id),
                "fecha": pd.Timestamp(change["fecha"]),
                "metrica": METRIC_TOPIC,
                "nivel": level,
                "partido": str(family),
                "estatus": str(status),
                "n_antes": n_before,
                "n_despues": n_after,
                "peso_antes": weight_before,
                "peso_despues": weight_after,
                "valor_antes": val_before,
                "valor_despues": val_after,
                "delta_total_serie": delta_total,
                "contribucion_dentro": within,
                "contribucion_composicion": composition,
                "residual": float("nan"),
                "significativo_bh": int(change.get("significativo_bh", 0)),
                "tamano_serie": int(change.get("tamano_serie", 0)),
            }
        )
    residual = delta_total - (total_within + total_composition)
    for row in rows:
        row["residual"] = residual
    rows.append(
        {
            "serie": "topic",
            "serie_id": str(topic_id),
            "fecha": pd.Timestamp(change["fecha"]),
            "metrica": METRIC_TOPIC,
            "nivel": level,
            "partido": RESIDUAL_LABEL,
            "estatus": RESIDUAL_LABEL,
            "n_antes": 0.0,
            "n_despues": 0.0,
            "peso_antes": float("nan"),
            "peso_despues": float("nan"),
            "valor_antes": float("nan"),
            "valor_despues": float("nan"),
            "delta_total_serie": delta_total,
            "contribucion_dentro": residual,
            "contribucion_composicion": 0.0,
            "residual": residual,
            "significativo_bh": int(change.get("significativo_bh", 0)),
            "tamano_serie": int(change.get("tamano_serie", 0)),
        }
    )
    return rows


def _decompose_tone_change(
    change: Mapping[str, Any],
    monthly_series: pd.DataFrame,
    tone_month: pd.DataFrame,
    level: str,
) -> list[dict[str, Any]]:
    """Descompone un cambio de tono en intra-partido y composición."""
    keys = ["party_family"] if level == "partido" else ["party_family", "party_status"]
    months, values = _series_months(monthly_series, "tone", "tone")
    index = int(change["indice"])
    if not 0 < index < len(values):
        raise ValueError(f"Índice fuera de rango para el tono: {index}")
    before_months = set(months.iloc[:index].tolist())
    after_months = set(months.iloc[index:].tolist())
    mask_before = tone_month.index.get_level_values("month").isin(before_months)
    mask_after = tone_month.index.get_level_values("month").isin(after_months)
    before = (
        tone_month.loc[mask_before].groupby(level=keys)[["n", "sum_tone", "sum_negative"]].sum()
    )
    after = tone_month.loc[mask_after].groupby(level=keys)[["n", "sum_tone", "sum_negative"]].sum()
    key_index = before.index.union(after.index)
    before = before.reindex(key_index, fill_value=0.0)
    after = after.reindex(key_index, fill_value=0.0)

    rows: list[dict[str, Any]] = []
    for metric, sum_column in (
        (METRIC_NEGATIVE, "sum_negative"),
        (METRIC_TONE, "sum_tone"),
    ):
        total_before = float(before["n"].sum())
        total_after = float(after["n"].sum())
        overall_before = (
            float(before[sum_column].sum()) / total_before if total_before else float("nan")
        )
        overall_after = (
            float(after[sum_column].sum()) / total_after if total_after else float("nan")
        )
        delta_total = overall_after - overall_before
        total_within = 0.0
        total_composition = 0.0
        for key in key_index:
            n_before = float(before.loc[key, "n"])
            n_after = float(after.loc[key, "n"])
            weight_before = n_before / total_before if total_before else float("nan")
            weight_after = n_after / total_after if total_after else float("nan")
            val_before = float(before.loc[key, sum_column]) / n_before if n_before else float("nan")
            val_after = float(after.loc[key, sum_column]) / n_after if n_after else float("nan")
            within = (
                weight_after * (val_after - val_before)
                if np.isfinite(weight_after) and np.isfinite(val_before) and np.isfinite(val_after)
                else float("nan")
            )
            composition = (
                (weight_after - weight_before) * val_before
                if np.isfinite(weight_before)
                and np.isfinite(weight_after)
                and np.isfinite(val_before)
                else float("nan")
            )
            if np.isfinite(within):
                total_within += within
            if np.isfinite(composition):
                total_composition += composition
            if level == "partido":
                family = str(key)
                status = GLOBAL_STATUS
            else:
                family, status = key
            rows.append(
                {
                    "serie": "tone",
                    "serie_id": "tone",
                    "fecha": pd.Timestamp(change["fecha"]),
                    "metrica": metric,
                    "nivel": level,
                    "partido": str(family),
                    "estatus": str(status),
                    "n_antes": n_before,
                    "n_despues": n_after,
                    "peso_antes": weight_before,
                    "peso_despues": weight_after,
                    "valor_antes": val_before,
                    "valor_despues": val_after,
                    "delta_total_serie": delta_total,
                    "contribucion_dentro": within,
                    "contribucion_composicion": composition,
                    "residual": float("nan"),
                    "significativo_bh": int(change.get("significativo_bh", 0)),
                    "tamano_serie": int(change.get("tamano_serie", 0)),
                }
            )
        residual = delta_total - (total_within + total_composition)
        for row in rows:
            if row["metrica"] == metric:
                row["residual"] = residual
        rows.append(
            {
                "serie": "tone",
                "serie_id": "tone",
                "fecha": pd.Timestamp(change["fecha"]),
                "metrica": metric,
                "nivel": level,
                "partido": RESIDUAL_LABEL,
                "estatus": RESIDUAL_LABEL,
                "n_antes": 0.0,
                "n_despues": 0.0,
                "peso_antes": float("nan"),
                "peso_despues": float("nan"),
                "valor_antes": float("nan"),
                "valor_despues": float("nan"),
                "delta_total_serie": delta_total,
                "contribucion_dentro": residual,
                "contribucion_composicion": 0.0,
                "residual": residual,
                "significativo_bh": int(change.get("significativo_bh", 0)),
                "tamano_serie": int(change.get("tamano_serie", 0)),
            }
        )
    return rows


def build_actor_decomposition(
    interventions: pd.DataFrame,
    changes: pd.DataFrame,
    changes_stats: pd.DataFrame,
    monthly_series: pd.DataFrame,
) -> pd.DataFrame:
    """Descompone todos los cambios en intra-partido y composición."""
    required = {"serie", "serie_id", "fecha", "indice", "tamano_serie"}
    missing = sorted(required - set(changes.columns))
    if missing:
        raise ValueError(f"Faltan columnas en los cambios: {missing}")
    assigned = interventions.loc[~interventions["is_outlier"].astype(bool)]
    party_month = assigned.groupby(["month", "party_family", "party_status"], observed=True).size()
    topic_month = assigned.groupby(
        ["month", "party_family", "party_status", "bertopic_topic"], observed=True
    ).size()
    tone_month = interventions.groupby(
        ["month", "party_family", "party_status"], observed=True
    ).agg(
        n=("utterance_id", "size"),
        sum_tone=("senti_n", "sum"),
        sum_negative=("negative", "sum"),
    )
    party_month_family = assigned.groupby(["month", "party_family"], observed=True).size()
    topic_month_family = assigned.groupby(
        ["month", "party_family", "bertopic_topic"], observed=True
    ).size()
    tone_month_family = interventions.groupby(["month", "party_family"], observed=True).agg(
        n=("utterance_id", "size"),
        sum_tone=("senti_n", "sum"),
        sum_negative=("negative", "sum"),
    )
    merged = changes.copy()
    merged["fecha"] = pd.to_datetime(merged["fecha"], errors="raise")
    stats = changes_stats.copy()
    stats["fecha"] = pd.to_datetime(stats["fecha"], errors="raise")
    merged = merged.merge(
        stats.loc[:, ["serie", "serie_id", "fecha", "significativo_bh"]],
        on=["serie", "serie_id", "fecha"],
        how="left",
        validate="one_to_one",
    )
    merged["significativo_bh"] = merged["significativo_bh"].fillna(0).astype(int)
    rows: list[dict[str, Any]] = []
    for change in merged.to_dict(orient="records"):
        if change["serie"] == "topic":
            topic_id = int(str(change["serie_id"]))
            rows.extend(
                _decompose_topic_change(
                    topic_id,
                    change,
                    monthly_series,
                    party_month_family,
                    topic_month_family,
                    "partido",
                )
            )
            rows.extend(
                _decompose_topic_change(
                    topic_id,
                    change,
                    monthly_series,
                    party_month,
                    topic_month,
                    "partido_estatus",
                )
            )
        elif change["serie"] == "tone":
            rows.extend(
                _decompose_tone_change(change, monthly_series, tone_month_family, "partido")
            )
            rows.extend(
                _decompose_tone_change(change, monthly_series, tone_month, "partido_estatus")
            )
    return pd.DataFrame(rows, columns=DECOMPOSITION_COLUMNS)


def _party_month_metrics(interventions: pd.DataFrame) -> pd.DataFrame:
    """Métricas mensuales por familia de partido (sin separar estatus)."""
    return interventions.groupby(["month", "party_family"], observed=True).agg(
        n=("utterance_id", "size"),
        sum_tone=("senti_n", "sum"),
        sum_negative=("negative", "sum"),
    )


def build_tone_counterfactual(interventions: pd.DataFrame, config: ActorConfig) -> pd.DataFrame:
    """Tono real y contrafactual con las cuotas de partido de la base fija.

    El contrafactual fija las cuotas de la base (por defecto, legislaturas
    X-XIII) y deja variar el comportamiento intra-partido de cada mes. La
    diferencia entre real y ajustado es el efecto de composición.
    """
    party_month = _party_month_metrics(interventions)
    baseline_mask = (
        party_month.index.get_level_values("month") >= pd.Timestamp(config.baseline_start)
    ) & (party_month.index.get_level_values("month") <= pd.Timestamp(config.baseline_end))
    baseline = party_month.loc[baseline_mask].groupby(level="party_family")["n"].sum()
    base_weights = baseline / baseline.sum() if float(baseline.sum()) else baseline * 0.0
    global_metrics = interventions.groupby("month").agg(
        n=("utterance_id", "size"),
        neg_share_real=("negative", "mean"),
        senti_n_real=("senti_n", "mean"),
    )
    rows: list[dict[str, Any]] = []
    for month in _monthly_grid(interventions):
        if month not in global_metrics.index:
            continue
        present = party_month.xs(month, level="month")
        present = present.loc[present["n"] > 0]
        weights = base_weights.reindex(present.index).fillna(0.0)
        if not float(weights.sum()):
            continue
        weights = weights / weights.sum()
        neg_party = present["sum_negative"] / present["n"]
        tone_party = present["sum_tone"] / present["n"]
        neg_adjusted = float((weights * neg_party).sum())
        tone_adjusted = float((weights * tone_party).sum())
        global_row = global_metrics.loc[month]
        rows.append(
            {
                "month": month,
                "n": int(global_row["n"]),
                "neg_share_real": float(global_row["neg_share_real"]),
                "neg_share_ajustado": neg_adjusted,
                "senti_n_real": float(global_row["senti_n_real"]),
                "senti_n_ajustado": tone_adjusted,
                "brecha_neg": float(global_row["neg_share_real"]) - neg_adjusted,
                "brecha_senti": float(global_row["senti_n_real"]) - tone_adjusted,
                "base_start": config.baseline_start,
                "base_end": config.baseline_end,
            }
        )
    return pd.DataFrame(rows, columns=COUNTERFACTUAL_COLUMNS)


def bootstrap_delta_ci(
    before: npt.ArrayLike,
    after: npt.ArrayLike,
    n_boot: int,
    seed: int,
) -> tuple[float, float, float]:
    """IC percentil bootstrap para la diferencia de medias ``after - before``."""
    before_array = np.asarray(before, dtype=np.float64)
    after_array = np.asarray(after, dtype=np.float64)
    if before_array.size == 0 or after_array.size == 0:
        raise ValueError("No se puede bootstrappear un grupo vacío")
    rng = np.random.default_rng(seed)
    observed = float(after_array.mean() - before_array.mean())
    deltas = np.empty(n_boot, dtype=np.float64)
    for index in range(n_boot):
        sample_before = rng.choice(before_array, size=before_array.size, replace=True)
        sample_after = rng.choice(after_array, size=after_array.size, replace=True)
        deltas[index] = sample_after.mean() - sample_before.mean()
    lower, upper = np.percentile(deltas, [2.5, 97.5])
    return observed, float(lower), float(upper)


def build_tone_ci(
    interventions: pd.DataFrame,
    changes: pd.DataFrame,
    changes_stats: pd.DataFrame,
    config: ActorConfig,
) -> pd.DataFrame:
    """IC bootstrap del cambio de tono de 2020-06 (share negativo y ``senti_n``)."""
    merged = changes.merge(
        changes_stats.loc[:, ["serie", "serie_id", "fecha", "significativo_bh"]],
        on=["serie", "serie_id", "fecha"],
        how="left",
        validate="one_to_one",
    )
    tone_changes = merged.loc[
        (merged["serie"] == "tone") & (merged["significativo_bh"].fillna(0).astype(int) == 1)
    ].sort_values("fecha")
    if tone_changes.empty:
        raise ValueError("No hay cambio de tono significativo para el IC")
    change = tone_changes.iloc[0]
    fecha = pd.Timestamp(change["fecha"])
    before = interventions.loc[interventions["date"] < fecha]
    after = interventions.loc[interventions["date"] >= fecha]
    rows: list[dict[str, Any]] = []
    for metric, column in ((METRIC_NEGATIVE, "negative"), (METRIC_TONE, "senti_n")):
        observed, lower, upper = bootstrap_delta_ci(
            before[column].to_numpy(),
            after[column].to_numpy(),
            config.bootstrap_n,
            config.seed,
        )
        rows.append(
            {
                "metrica": metric,
                "fecha": fecha,
                "delta": observed,
                "ic_inf": lower,
                "ic_sup": upper,
                "n_boot": config.bootstrap_n,
                "n_antes": len(before),
                "n_despues": len(after),
            }
        )
    return pd.DataFrame(rows, columns=TONE_CI_COLUMNS)


def main() -> None:
    """CLI: genera series de actores, descomposición, contrafactual e IC."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    config = load_config(CONFIG_DIR / "experiment_04.yaml")
    actor_config = build_actor_config(config)
    interventions = load_interventions(actor_config)
    series = build_actor_series(interventions, actor_config)
    actor_config.series_parquet_path.parent.mkdir(parents=True, exist_ok=True)
    series.to_parquet(actor_config.series_parquet_path, index=False)
    actor_config.series_csv_path.parent.mkdir(parents=True, exist_ok=True)
    series.to_csv(actor_config.series_csv_path, index=False, encoding="utf-8")

    changes = pd.read_csv(
        PROJECT_ROOT / "reports" / "tables" / "cambios_regimen.csv", parse_dates=["fecha"]
    )
    changes_stats = pd.read_csv(
        PROJECT_ROOT / "reports" / "tables" / "cambios_regimen_test.csv", parse_dates=["fecha"]
    )
    monthly_series = pd.read_parquet(actor_config.monthly_series_path)
    decomposition = build_actor_decomposition(interventions, changes, changes_stats, monthly_series)
    decomposition.to_csv(actor_config.decomposition_path, index=False, encoding="utf-8")

    counterfactual = build_tone_counterfactual(interventions, actor_config)
    counterfactual.to_csv(actor_config.counterfactual_path, index=False, encoding="utf-8")

    tone_ci = build_tone_ci(interventions, changes, changes_stats, actor_config)
    tone_ci.to_csv(actor_config.tone_ci_path, index=False, encoding="utf-8")

    logger.info(
        "actores: %s filas de series, %s filas de descomposición, %s meses de contrafactual",
        len(series),
        len(decomposition),
        len(counterfactual),
    )
    logger.info("IC del tono: %s", tone_ci.to_dict(orient="records"))


if __name__ == "__main__":
    main()
