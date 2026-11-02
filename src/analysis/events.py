"""Event study de la v2 (D-45).

Sustituye el contraste exploratorio de ventana simétrica de la Fase 3b por un
event study local pre/post alrededor de episodios:

- La unidad es el **episodio**, no el evento suelto, para no atribuir cambios a
  eventos que se solapan en el tiempo.
- La ventana es de 6 meses antes y después del mes ancla.
- La inferencia es una permutación de la fecha ancla (placebo) y una corrección
  de Benjamini-Hochberg dentro de cada subfamilia (tono y tópicos).
- La familia de hipótesis está pre-especificada en
  ``reports/tables/eventos_hipotesis.csv``; el contraste es a dos colas y la
  dirección esperada se documenta pero no se usa para ganar potencia.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false, reportUnknownParameterType=false, reportUnknownLambdaType=false

from __future__ import annotations

import logging
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from src.utils.config import CONFIG_DIR, PROJECT_ROOT, SEED, load_config
from src.utils.helpers import import_optional

logger = logging.getLogger(__name__)

CATALOG_COLUMNS = ("evento", "fecha", "capa", "tipo", "subtipo", "episodio", "fuente", "notas")
EPISODE_COLUMNS = (
    "episodio_id",
    "titulo",
    "fecha_ancla",
    "fecha_inicio",
    "fecha_fin",
    "eventos",
    "resumen",
    "fuente",
)
HYPOTHESIS_COLUMNS = (
    "hipotesis_id",
    "episodio_id",
    "serie",
    "serie_id",
    "metrica",
    "direccion_esperada",
    "subfamilia",
    "justificacion",
)
ALIGNMENT_COLUMNS = [
    "hipotesis_id",
    "episodio_id",
    "serie",
    "serie_id",
    "metrica",
    "fecha_ancla",
    "ventana_meses",
    "n_antes",
    "n_despues",
    "valor_antes",
    "valor_despues",
    "delta",
    "p",
    "q",
    "significativo_bh",
    "direccion_esperada",
    "subfamilia",
    "justificacion",
]
VALID_CAPAS = {"covariable", "contexto"}


@dataclass(frozen=True)
class EventStudyConfig:
    """Rutas y parámetros del event study."""

    catalog_path: Path
    episodes_path: Path
    hypotheses_path: Path
    alignment_path: Path
    window_months: int
    min_months_side: int
    n_permutations: int
    alpha: float
    seed: int


def build_event_study_config(
    config: Mapping[str, Any], root: Path | None = None
) -> EventStudyConfig:
    """Construye la configuración del event study desde ``events_v2``."""
    base = root or PROJECT_ROOT
    section = config["events_v2"]
    return EventStudyConfig(
        catalog_path=base / str(section["catalog_path"]),
        episodes_path=base / str(section["episodes_path"]),
        hypotheses_path=base / str(section["hypotheses_path"]),
        alignment_path=base / str(section["alignment_path"]),
        window_months=int(section.get("window_months", 6)),
        min_months_side=int(section.get("min_months_side", 4)),
        n_permutations=int(section.get("n_permutations", 10000)),
        alpha=float(section.get("alpha", 0.05)),
        seed=int(config.get("seed", SEED)),
    )


def _validate_columns(frame: pd.DataFrame, columns: tuple[str, ...], name: str) -> None:
    missing = [column for column in columns if column not in frame.columns]
    if missing:
        raise ValueError(f"Faltan columnas en {name}: {missing}")


def load_catalog(path: Path) -> pd.DataFrame:
    """Carga el catálogo de eventos de dos capas."""
    catalog = pd.read_csv(path)
    _validate_columns(catalog, CATALOG_COLUMNS, "el catálogo de eventos")
    catalog = catalog.loc[:, list(CATALOG_COLUMNS)].copy()
    catalog["fecha"] = pd.to_datetime(catalog["fecha"], errors="raise")
    catalog["capa"] = catalog["capa"].astype(str).str.strip()
    invalid = sorted(set(catalog["capa"]) - VALID_CAPAS)
    if invalid:
        raise ValueError(f"Capas de evento no válidas: {invalid}")
    catalog["episodio"] = catalog["episodio"].fillna("").astype(str).str.strip()
    return catalog


def load_episodes(path: Path) -> pd.DataFrame:
    """Carga y valida los episodios de eventos."""
    episodes = pd.read_csv(path)
    _validate_columns(episodes, EPISODE_COLUMNS, "los episodios")
    episodes = episodes.loc[:, list(EPISODE_COLUMNS)].copy()
    for column in ("fecha_ancla", "fecha_inicio", "fecha_fin"):
        episodes[column] = pd.to_datetime(episodes[column], errors="raise")
    if episodes["episodio_id"].duplicated().any():
        raise ValueError("Hay identificadores de episodio duplicados")
    return episodes


def load_hypotheses(path: Path) -> pd.DataFrame:
    """Carga y valida la familia pre-especificada de pares episodio-serie."""
    hypotheses = pd.read_csv(path)
    _validate_columns(hypotheses, HYPOTHESIS_COLUMNS, "las hipótesis")
    hypotheses = hypotheses.loc[:, list(HYPOTHESIS_COLUMNS)].copy()
    if hypotheses["hipotesis_id"].duplicated().any():
        raise ValueError("Hay identificadores de hipótesis duplicados")
    invalid = sorted(set(hypotheses["subfamilia"]) - {"tone", "topicos"})
    if invalid:
        raise ValueError(f"Subfamilias no válidas: {invalid}")
    return hypotheses


def _series_values(
    series: pd.DataFrame, series_type: str, series_id: str
) -> tuple[pd.Series, np.ndarray]:
    """Meses con sesión y valores finitos de una serie mensual."""
    subset = series.loc[
        (series["series_type"] == series_type)
        & (series["series_id"].astype(str) == str(series_id))
        & series["has_session"].astype(bool)
    ].sort_values("month")
    values = subset["value"].to_numpy(dtype=np.float64)
    months = pd.to_datetime(subset["month"])
    mask = np.isfinite(values)
    return months.loc[mask].reset_index(drop=True), values[mask]


def local_window_delta(
    values: np.ndarray,
    anchor_index: int,
    window: int,
    min_side: int,
) -> tuple[float, int, int, float, float]:
    """Diferencia de medias después-antes en una ventana local."""
    start = max(0, anchor_index - window)
    end = min(len(values), anchor_index + window + 1)
    before = values[start:anchor_index]
    after = values[anchor_index:end]
    if before.size < min_side or after.size < min_side:
        raise ValueError(f"Ventana insuficiente: {before.size} meses antes y {after.size} después")
    mean_before = float(before.mean())
    mean_after = float(after.mean())
    return mean_after - mean_before, int(before.size), int(after.size), mean_before, mean_after


def permutation_p_value(
    values: np.ndarray,
    anchor_index: int,
    window: int,
    min_side: int,
    n_permutations: int,
    rng: np.random.Generator,
) -> float:
    """p bilateral por permutación de la fecha ancla (placebo)."""
    valid = np.arange(min_side, len(values) - min_side + 1)
    valid = valid[valid != anchor_index]
    if valid.size == 0:
        return 1.0
    observed, _, _, _, _ = local_window_delta(values, anchor_index, window, min_side)
    exceed = 0
    for _ in range(n_permutations):
        placebo = int(rng.choice(valid))
        delta, _, _, _, _ = local_window_delta(values, placebo, window, min_side)
        if abs(delta) >= abs(observed):
            exceed += 1
    return (1.0 + exceed) / (1.0 + n_permutations)


def bh_within_families(table: pd.DataFrame, alpha: float) -> pd.DataFrame:
    """Añade ``q`` y ``significativo_bh`` con BH dentro de cada subfamilia."""
    scipy_stats = import_optional("scipy.stats")
    result = table.copy()
    result["q"] = np.nan
    for _, group in result.groupby("subfamilia", sort=True):
        p_values = group["p"].to_numpy(dtype=np.float64)
        result.loc[group.index, "q"] = scipy_stats.false_discovery_control(p_values)
    result["significativo_bh"] = (result["q"] < alpha).astype(int)
    return result


def build_alignment(
    series: pd.DataFrame,
    hypotheses: pd.DataFrame,
    episodes: pd.DataFrame,
    config: EventStudyConfig,
) -> pd.DataFrame:
    """Construye la tabla de alineación episodio-serie."""
    rng = np.random.default_rng(config.seed)
    episode_lookup = episodes.set_index("episodio_id")
    rows: list[dict[str, Any]] = []
    for hypothesis in hypotheses.to_dict(orient="records"):
        episode_id = str(hypothesis["episodio_id"])
        if episode_id not in episode_lookup.index:
            raise ValueError(f"Episodio desconocido en las hipótesis: {episode_id}")
        anchor = pd.Timestamp(episode_lookup.loc[episode_id, "fecha_ancla"])
        if not isinstance(anchor, pd.Timestamp):
            raise ValueError(f"Fecha ancla inválida en el episodio {episode_id}")
        months, values = _series_values(
            series, str(hypothesis["serie"]), str(hypothesis["serie_id"])
        )
        if values.size == 0:
            raise ValueError(
                f"Serie vacía para la hipótesis {hypothesis['hipotesis_id']}: "
                f"{hypothesis['serie']}/{hypothesis['serie_id']}"
            )
        anchor_index = int(
            np.searchsorted(months.to_numpy(), np.datetime64(anchor.to_pydatetime()), side="left")
        )
        if anchor_index <= 0 or anchor_index >= values.size:
            raise ValueError(
                f"El ancla {anchor.date()} queda fuera de la serie "
                f"{hypothesis['serie']}/{hypothesis['serie_id']}"
            )
        delta, n_before, n_after, mean_before, mean_after = local_window_delta(
            values, anchor_index, config.window_months, config.min_months_side
        )
        p_value = permutation_p_value(
            values,
            anchor_index,
            config.window_months,
            config.min_months_side,
            config.n_permutations,
            rng,
        )
        rows.append(
            {
                "hipotesis_id": str(hypothesis["hipotesis_id"]),
                "episodio_id": episode_id,
                "serie": str(hypothesis["serie"]),
                "serie_id": str(hypothesis["serie_id"]),
                "metrica": str(hypothesis["metrica"]),
                "fecha_ancla": anchor,
                "ventana_meses": config.window_months,
                "n_antes": n_before,
                "n_despues": n_after,
                "valor_antes": mean_before,
                "valor_despues": mean_after,
                "delta": delta,
                "p": p_value,
                "q": float("nan"),
                "significativo_bh": 0,
                "direccion_esperada": str(hypothesis["direccion_esperada"]),
                "subfamilia": str(hypothesis["subfamilia"]),
                "justificacion": str(hypothesis["justificacion"]),
            }
        )
    table = pd.DataFrame(rows, columns=ALIGNMENT_COLUMNS)
    return bh_within_families(table, config.alpha)


def main() -> None:
    """CLI: construye ``reports/tables/eventos_alineacion.csv``."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    config = load_config(CONFIG_DIR / "experiment_04.yaml")
    event_config = build_event_study_config(config)

    topics = pd.read_parquet(
        PROJECT_ROOT / "data" / "intermediate" / "series_mensuales.parquet",
        columns=["month", "series_type", "series_id", "value", "has_session"],
    )
    actors = pd.read_csv(
        PROJECT_ROOT / "reports" / "tables" / "series_actores.csv", parse_dates=["month"]
    )
    global_actors = actors.loc[
        (actors["party_family"] == "Todos") & (actors["party_status"] == "Todos")
    ].copy()
    negative = global_actors.loc[:, ["month", "negative_share", "has_session"]].rename(
        columns={"negative_share": "value"}
    )
    negative["series_type"] = "tone"
    negative["series_id"] = "negative_share"
    negative["series_id"] = negative["series_id"].astype(str)
    combined = pd.concat([topics, negative.loc[:, topics.columns]], ignore_index=True)

    catalog = load_catalog(event_config.catalog_path)
    episodes = load_episodes(event_config.episodes_path)
    hypotheses = load_hypotheses(event_config.hypotheses_path)
    alignment = build_alignment(combined, hypotheses, episodes, event_config)
    alignment.to_csv(event_config.alignment_path, index=False, encoding="utf-8")
    significant = alignment.loc[alignment["significativo_bh"] == 1]
    logger.info(
        "event study: %s hipótesis, %s significativas tras BH; covariables=%s, contexto=%s",
        len(alignment),
        len(significant),
        int((catalog["capa"] == "covariable").sum()),
        int((catalog["capa"] == "contexto").sum()),
    )
    logger.info("resultados -> %s", event_config.alignment_path)


if __name__ == "__main__":
    main()
