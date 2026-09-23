"""Cambios de régimen y asociación con eventos de la Fase 3b (D-08, D-09, D-28).

- PELT (``ruptures``, coste l2, ``min_size``/``jump`` de configuración) sobre
  cada serie mensual (58 tópicos + tono). La penalización se elige por criterio
  tipo BIC (``n·log(RSS/n) + k·log(n)``) sobre una rejilla logarítmica y se
  reporta un análisis de sensibilidad de cinco factores.
- Contraste por cambio: Mann-Whitney U bilateral de los valores mensuales
  anteriores y posteriores a cada corte, con ``r`` rango-biserial (signo
  concordante con ``delta``), meses en juego y Benjamini-Hochberg sobre la
  familia completa de contrastes (``cambios_regimen_test.csv``).
- Asociación exploratoria evento↔serie con ventana de ±``window_months``,
  Spearman, corrección de Benjamini-Hochberg sobre una única familia y
  medias dentro/fuera de la ventana; lenguaje no causal (D-09).

Las dependencias del extra ``analysis`` se cargan en tiempo de ejecución con
``import_optional`` (D-30).
"""

from __future__ import annotations

import math
import shutil
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import numpy.typing as npt
import pandas as pd

from src.utils.config import CONFIG_DIR, PROJECT_ROOT, SEED, load_config
from src.utils.helpers import import_optional

FloatArray = npt.NDArray[np.float64]

REGIME_COLUMNS = [
    "serie",
    "serie_id",
    "fecha",
    "indice",
    "media_antes",
    "media_despues",
    "delta",
    "pen_seleccionada",
    "n_cambios",
    "n_puntos",
    "tamano_serie",
]
SENSITIVITY_COLUMNS = ["serie", "serie_id", "factor", "penalizacion", "n_cambios"]
CHANGE_TEST_COLUMNS = [
    "serie",
    "serie_id",
    "fecha",
    "r",
    "p",
    "q",
    "n_antes",
    "n_despues",
    "n",
    "significativo_bh",
]
RELATION_COLUMNS = [
    "evento",
    "serie",
    "serie_id",
    "rho",
    "p",
    "q",
    "n",
    "media_en_ventana",
    "media_fuera",
]
EVENT_COLUMNS = ["evento", "fecha", "tipo", "fuente", "notas"]
SERIES_WITH_REGIMES = ("topic", "tone")
EVENTS_MIRROR = "eventos.csv"
CHANGES_FILENAME = "cambios_regimen.csv"
CHANGES_TEST_FILENAME = "cambios_regimen_test.csv"
SENSITIVITY_FILENAME = "cambios_regimen_sensibilidad.csv"
RELATIONS_FILENAME = "eventos_relaciones.csv"


@dataclass(frozen=True)
class RegimeConfig:
    """Parámetros de PELT y del contraste con eventos."""

    model: str
    min_size: int
    jump: int
    penalty_start: float
    penalty_stop: float
    penalty_num: int
    sensitivity_factors: tuple[float, ...]
    window_months: int
    seed: int


@dataclass(frozen=True)
class ChangeResult:
    """Resultado de PELT para una serie: cortes, penalización y sensibilidad."""

    breaks: tuple[int, ...]
    penalty: float
    score: float
    sensitivity: tuple[tuple[float, float, int], ...]


def build_regime_config(config: Mapping[str, Any]) -> RegimeConfig:
    """Construye la configuración de regímenes y eventos."""
    section = config["regime"]
    penalty = section.get("penalty", {})
    events = config.get("events", {})
    return RegimeConfig(
        model=str(section.get("model", "l2")),
        min_size=int(section.get("min_size", 6)),
        jump=int(section.get("jump", 1)),
        penalty_start=float(penalty.get("start", 0.1)),
        penalty_stop=float(penalty.get("stop", 1000.0)),
        penalty_num=int(penalty.get("num", 40)),
        sensitivity_factors=tuple(
            float(value) for value in section.get("sensitivity_factors", (0.25, 0.5, 1.0, 2.0, 4.0))
        ),
        window_months=int(events.get("window_months", 3)),
        seed=int(config.get("seed", SEED)),
    )


def penalty_grid(config: RegimeConfig) -> FloatArray:
    """Rejilla logarítmica de penalizaciones."""
    return np.asarray(
        np.logspace(
            math.log10(config.penalty_start),
            math.log10(config.penalty_stop),
            config.penalty_num,
        ),
        dtype=np.float64,
    )


def _pelt(values: Sequence[float] | FloatArray, config: RegimeConfig, penalty: float) -> list[int]:
    ruptures_module = import_optional("ruptures")
    algorithm = ruptures_module.Pelt(model=config.model, min_size=config.min_size, jump=config.jump)
    algorithm.fit(np.asarray(values, dtype=np.float64))
    return [int(index) for index in algorithm.predict(pen=penalty)]


def segment_boundaries(breaks: Sequence[int], n_points: int) -> list[tuple[int, int]]:
    """Convierte los cortes de PELT (fin inclusive) en rangos ``[inicio, fin)``."""
    boundaries: list[tuple[int, int]] = []
    start = 0
    for end in breaks:
        clipped = min(int(end), n_points)
        boundaries.append((start, clipped))
        start = clipped
    return boundaries


def rss_of_breaks(values: Sequence[float] | FloatArray, breaks: Sequence[int]) -> float:
    """Suma de residuos al cuadrado de la segmentación dada."""
    array = np.asarray(values, dtype=np.float64)
    total = 0.0
    for start, end in segment_boundaries(breaks, array.size):
        segment = array[start:end]
        if segment.size:
            total += float(np.sum((segment - segment.mean()) ** 2))
    return total


def bic_like(values: Sequence[float] | FloatArray, breaks: Sequence[int]) -> float:
    """Criterio tipo BIC: ``n·log(RSS/n) + k·log(n)`` con k cortes."""
    array = np.asarray(values, dtype=np.float64)
    n = array.size
    rss = rss_of_breaks(array, breaks)
    k = max(len(breaks) - 1, 0)
    tiny = np.finfo(np.float64).tiny
    return float(n * np.log(max(rss / n, tiny)) + k * np.log(n))


def detect_changes(values: Sequence[float] | FloatArray, config: RegimeConfig) -> ChangeResult:
    """PELT con selección de penalización por BIC y sensibilidad de cinco factores.

    Entre penalizaciones con el mismo BIC se prefiere la mayor (segmentación
    más simple); la rejilla arranca en el valor de configuración para no dejar
    fuera series de varianza pequeña.
    """
    array = np.asarray(values, dtype=np.float64)
    if array.size < 2 * config.min_size:
        raise ValueError("Serie demasiado corta para PELT")
    best_score = float("inf")
    best_penalty = float("nan")
    best_breaks: list[int] = [array.size]
    for penalty in penalty_grid(config):
        breaks = _pelt(array, config, float(penalty))
        score = bic_like(array, breaks)
        if score <= best_score:
            best_score = score
            best_penalty = float(penalty)
            best_breaks = breaks
    sensitivity = tuple(
        (
            float(factor),
            best_penalty * float(factor),
            max(len(_pelt(array, config, best_penalty * factor)) - 1, 0),
        )
        for factor in config.sensitivity_factors
    )
    return ChangeResult(
        breaks=tuple(best_breaks),
        penalty=best_penalty,
        score=best_score,
        sensitivity=sensitivity,
    )


def build_changes_table(
    series: pd.DataFrame, config: RegimeConfig
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """PELT por serie (tópicos y tono); devuelve cambios y tabla de sensibilidad."""
    frame = series.loc[series["has_session"] & series["series_type"].isin(SERIES_WITH_REGIMES)]
    rows: list[dict[str, Any]] = []
    sensitivity_rows: list[dict[str, Any]] = []
    for (series_type, series_id), group in frame.groupby(["series_type", "series_id"], sort=True):
        ordered = group.sort_values("month")
        values = ordered["value"].to_numpy(dtype=np.float64)
        months = ordered["month"].to_numpy()
        mask = np.isfinite(values)
        values = values[mask]
        months = months[mask]
        result = detect_changes(values, config)
        for factor, penalty, n_changes in result.sensitivity:
            sensitivity_rows.append(
                {
                    "serie": series_type,
                    "serie_id": series_id,
                    "factor": factor,
                    "penalizacion": penalty,
                    "n_cambios": n_changes,
                }
            )
        boundaries = segment_boundaries(result.breaks, values.size)
        means = [float(values[start:end].mean()) for start, end in boundaries]
        for order in range(len(boundaries) - 1):
            change_index = boundaries[order][1]
            rows.append(
                {
                    "serie": series_type,
                    "serie_id": series_id,
                    "fecha": pd.Timestamp(months[change_index]),
                    "indice": change_index,
                    "media_antes": round(means[order], 6),
                    "media_despues": round(means[order + 1], 6),
                    "delta": round(means[order + 1] - means[order], 6),
                    "pen_seleccionada": result.penalty,
                    "n_cambios": max(len(result.breaks) - 1, 0),
                    "n_puntos": int(values.size),
                    "tamano_serie": int(ordered["n_interventions"].sum()),
                }
            )
    changes = pd.DataFrame(rows, columns=REGIME_COLUMNS)
    sensitivity = pd.DataFrame(sensitivity_rows, columns=SENSITIVITY_COLUMNS)
    return changes, sensitivity


def build_changes_stats(series: pd.DataFrame, changes: pd.DataFrame) -> pd.DataFrame:
    """Mann-Whitney U antes/después de cada cambio con corrección de BH.

    Para cada fila de ``changes`` se contrastan (bilateral) los valores
    mensuales anteriores y posteriores al corte. ``r`` es la correlación
    rango-biserial ``2·U/(n_antes·n_despues) - 1``, calculada con el segmento
    posterior como primer argumento, de modo que su signo es concordante con
    ``delta`` (positivo si el valor posterior supera al anterior). ``p`` y ``q``
    se guardan sin redondear: el formateo para mostrar es responsabilidad de la
    capa de presentación. ``q`` corresponde a Benjamini-Hochberg sobre todos los
    contrastes y ``significativo_bh`` marca ``q < 0.05``.
    """
    scipy_stats = import_optional("scipy.stats")
    frame = series.loc[series["has_session"] & series["series_type"].isin(SERIES_WITH_REGIMES)]
    ordered_values: dict[tuple[str, str], FloatArray] = {}
    for (series_type, series_id), group in frame.groupby(["series_type", "series_id"], sort=True):
        values = group.sort_values("month")["value"].to_numpy(dtype=np.float64)
        ordered_values[(str(series_type), str(series_id))] = values[np.isfinite(values)]
    rows: list[dict[str, Any]] = []
    for record in changes.to_dict(orient="records"):
        key = (str(record["serie"]), str(record["serie_id"]))
        values = ordered_values.get(key)
        if values is None:
            raise ValueError(f"Sin serie mensual para el cambio: {key}")
        index = int(record["indice"])
        if not 0 < index < values.size:
            raise ValueError(f"Índice de cambio fuera de rango en {key}: {index}")
        before = values[:index]
        after = values[index:]
        n_antes = int(before.size)
        n_despues = int(after.size)
        if np.unique(values).size < 2:
            statistic = n_antes * n_despues / 2
            p_value = 1.0
        else:
            result = scipy_stats.mannwhitneyu(after, before, alternative="two-sided")
            statistic = float(result.statistic)
            p_value = float(result.pvalue)
        rows.append(
            {
                "serie": key[0],
                "serie_id": key[1],
                "fecha": pd.Timestamp(record["fecha"]),
                "r": round(2.0 * statistic / (n_antes * n_despues) - 1.0, 6),
                "p": p_value,
                "n_antes": n_antes,
                "n_despues": n_despues,
                "n": n_antes + n_despues,
            }
        )
    table = pd.DataFrame(rows)
    if table.empty:
        return table.reindex(columns=CHANGE_TEST_COLUMNS)
    p_array = table["p"].to_numpy(dtype=np.float64)
    table["q"] = scipy_stats.false_discovery_control(p_array)
    table["significativo_bh"] = (table["q"] < 0.05).astype(int)
    return table.reindex(columns=CHANGE_TEST_COLUMNS)


def load_events(path: Path) -> pd.DataFrame:
    """Carga y valida el CSV de eventos editado a mano (D-09)."""
    events = pd.read_csv(path)
    missing = sorted(set(EVENT_COLUMNS) - set(events.columns))
    if missing:
        raise ValueError(f"Faltan columnas en el CSV de eventos: {missing}")
    events = events.loc[:, EVENT_COLUMNS].copy()
    events["fecha"] = pd.to_datetime(events["fecha"], errors="raise")
    if events["fecha"].isna().any():
        raise ValueError("Hay fechas de evento vacías o inválidas")
    return events


def event_indicator(
    months: pd.Index | pd.Series | npt.NDArray[Any], event_date: pd.Timestamp, window: int
) -> npt.NDArray[np.bool_]:
    """Indicador binario de los meses dentro de ``event_date ± window``."""
    periods = pd.PeriodIndex(months, freq="M")
    event_period = pd.Period(event_date, freq="M")
    distance = np.abs(
        (periods.year - event_period.year) * 12 + (periods.month - event_period.month)
    )
    return distance <= window


def build_event_relations(
    series: pd.DataFrame, events: pd.DataFrame, config: RegimeConfig
) -> pd.DataFrame:
    """Spearman evento↔serie con ventana, corrección BH y medias dentro/fuera."""
    scipy_stats = import_optional("scipy.stats")
    frame = series.loc[series["has_session"] & series["series_type"].isin(SERIES_WITH_REGIMES)]
    rows: list[dict[str, Any]] = []
    p_values: list[float] = []
    for (series_type, series_id), group in frame.groupby(["series_type", "series_id"], sort=True):
        ordered = group.sort_values("month")
        values = ordered["value"].to_numpy(dtype=np.float64)
        months = ordered["month"].to_numpy()
        mask = np.isfinite(values)
        values = values[mask]
        months = months[mask]
        for _, event in events.iterrows():
            indicator = event_indicator(months, event["fecha"], config.window_months)
            n_inside = int(indicator.sum())
            if n_inside == 0 or n_inside == indicator.size or np.unique(values).size < 2:
                rho = float("nan")
                p_value = float("nan")
            else:
                result = scipy_stats.spearmanr(values, indicator.astype(np.float64))
                rho = float(result.statistic)
                p_value = float(result.pvalue)
            p_values.append(p_value)
            rows.append(
                {
                    "evento": str(event["evento"]),
                    "serie": series_type,
                    "serie_id": series_id,
                    "rho": None if np.isnan(rho) else round(rho, 6),
                    "p": None if np.isnan(p_value) else round(p_value, 6),
                    "q": None,
                    "n": int(values.size),
                    "media_en_ventana": (
                        round(float(values[indicator].mean()), 6) if n_inside else None
                    ),
                    "media_fuera": (
                        round(float(values[~indicator].mean()), 6)
                        if n_inside < indicator.size
                        else None
                    ),
                }
            )
    table = pd.DataFrame(rows, columns=RELATION_COLUMNS)
    p_array = np.asarray(p_values, dtype=np.float64)
    q_array: FloatArray = np.full(p_array.shape, np.nan)
    finite = np.isfinite(p_array)
    if finite.any():
        q_array[finite] = scipy_stats.false_discovery_control(p_array[finite])
    table["q"] = [None if np.isnan(value) else round(float(value), 6) for value in q_array]
    return table


def mirror_events(events_path: Path, destination: Path) -> Path:
    """Espejo byte a byte del CSV de eventos para versionar la tabla usada (D-13)."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(events_path, destination)
    return destination


def main() -> None:
    """CLI: cambios de régimen por serie y asociación exploratoria con eventos."""
    config = build_regime_config(load_config(CONFIG_DIR / "experiment_03.yaml"))
    series_path = PROJECT_ROOT / "data" / "intermediate" / "series_mensuales.parquet"
    series = pd.read_parquet(series_path)
    changes, sensitivity = build_changes_table(series, config)
    reports_dir = PROJECT_ROOT / "reports" / "tables"
    reports_dir.mkdir(parents=True, exist_ok=True)
    changes_path = reports_dir / CHANGES_FILENAME
    changes.to_csv(changes_path, index=False)
    sensitivity_path = reports_dir / SENSITIVITY_FILENAME
    sensitivity.to_csv(sensitivity_path, index=False)
    changes_stats = build_changes_stats(series, changes)
    changes_stats_path = reports_dir / CHANGES_TEST_FILENAME
    changes_stats.to_csv(changes_stats_path, index=False)
    print(f"{len(changes)} cambios en {changes['serie_id'].nunique()} series -> {changes_path}")
    print(f"contraste Mann-Whitney + BH -> {changes_stats_path}")
    print(f"sensibilidad de penalizaciones -> {sensitivity_path}")
    print(f"series con cambios: {changes.groupby(['serie', 'serie_id']).size().shape[0]}")

    events_path = PROJECT_ROOT / str(
        load_config(CONFIG_DIR / "experiment_03.yaml")["events"]["path"]
    )
    events = load_events(events_path)
    mirror = mirror_events(events_path, reports_dir / EVENTS_MIRROR)
    relations = build_event_relations(series, events, config)
    relations_path = reports_dir / RELATIONS_FILENAME
    relations.to_csv(relations_path, index=False)
    significant = (relations["q"].astype(float) < 0.05).sum()
    print(f"{len(relations)} contrastes ({int(significant)} con q<0,05) -> {relations_path}")
    print(f"espejo de eventos -> {mirror}")


if __name__ == "__main__":
    main()
