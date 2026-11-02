"""Tests del event study de la v2 (D-45)."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from src.analysis.events import (
    ALIGNMENT_COLUMNS,
    EventStudyConfig,
    bh_within_families,
    build_alignment,
    build_event_study_config,
    load_catalog,
    load_episodes,
    load_hypotheses,
    local_window_delta,
    permutation_p_value,
)


def _config(tmp_path: Path) -> EventStudyConfig:
    return EventStudyConfig(
        catalog_path=tmp_path / "catalogo.csv",
        episodes_path=tmp_path / "episodios.csv",
        hypotheses_path=tmp_path / "hipotesis.csv",
        alignment_path=tmp_path / "alineacion.csv",
        window_months=6,
        min_months_side=4,
        n_permutations=300,
        alpha=0.05,
        seed=42,
    )


def _series() -> pd.DataFrame:
    months = pd.date_range("2019-01-01", periods=24, freq="MS")
    rows: list[dict[str, object]] = []
    for index, month in enumerate(months):
        rows.append(
            {
                "month": month,
                "series_type": "topic",
                "series_id": "0",
                "value": 0.1 if index < 18 else 0.4,
                "has_session": True,
            }
        )
        rows.append(
            {
                "month": month,
                "series_type": "tone",
                "series_id": "negative_share",
                "value": 0.3 if index < 18 else 0.5,
                "has_session": True,
            }
        )
    return pd.DataFrame(rows)


def _episodes() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "episodio_id": ["E1"],
            "titulo": ["Episodio"],
            "fecha_ancla": pd.to_datetime(["2020-07-01"]),
            "fecha_inicio": pd.to_datetime(["2020-07-01"]),
            "fecha_fin": pd.to_datetime(["2020-07-01"]),
            "eventos": ["Evento"],
            "resumen": ["Resumen"],
            "fuente": ["sintética"],
        }
    )


def _hypotheses() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "hipotesis_id": ["H01", "H02"],
            "episodio_id": ["E1", "E1"],
            "serie": ["topic", "tone"],
            "serie_id": ["0", "negative_share"],
            "metrica": ["cuota_topico", "negative_share"],
            "direccion_esperada": ["up", "up"],
            "subfamilia": ["topicos", "tone"],
            "justificacion": ["Prueba", "Prueba"],
        }
    )


def test_local_window_delta() -> None:
    values = np.array([0.0] * 10 + [1.0] * 10)
    delta, n_before, n_after, mean_before, mean_after = local_window_delta(values, 10, 4, 4)
    assert delta == pytest.approx(1.0)
    assert (n_before, n_after) == (4, 5)
    assert mean_before == pytest.approx(0.0)
    assert mean_after == pytest.approx(1.0)
    with pytest.raises(ValueError, match="insuficiente"):
        local_window_delta(values, 1, 4, 4)


def test_permutation_detecta_escalon() -> None:
    values = np.array([0.0] * 10 + [1.0] * 10)
    rng = np.random.default_rng(42)
    p_value = permutation_p_value(values, 10, 4, 4, 300, rng)
    assert p_value < 0.05


def test_bh_within_families() -> None:
    table = pd.DataFrame(
        {
            "subfamilia": ["a", "a", "b"],
            "p": [0.01, 0.04, 0.2],
        }
    )
    result = bh_within_families(table, 0.05)
    assert result["q"].notna().all()
    assert result["significativo_bh"].tolist()[0] == 1
    assert result["significativo_bh"].tolist()[2] == 0


def test_build_alignment_detecta_episodio() -> None:
    table = build_alignment(_series(), _hypotheses(), _episodes(), _config(Path(".")))
    assert list(table.columns) == ALIGNMENT_COLUMNS
    assert len(table) == 2
    assert table["delta"].abs().min() > 0.1
    assert table["p"].max() < 0.05
    assert table["significativo_bh"].tolist() == [1, 1]


def test_build_alignment_falla_sin_serie() -> None:
    empty = _series().loc[_series()["series_type"] == "tone"]
    with pytest.raises(ValueError, match="Serie vacía"):
        build_alignment(empty, _hypotheses(), _episodes(), _config(Path(".")))


def test_loaders_validan(tmp_path: Path) -> None:
    catalog_path = tmp_path / "catalogo.csv"
    pd.DataFrame(
        {
            "evento": ["Evento"],
            "fecha": ["2020-01-01"],
            "capa": ["covariable"],
            "tipo": ["prueba"],
            "subtipo": ["x"],
            "episodio": ["E1"],
            "fuente": ["sintética"],
            "notas": [""],
        }
    ).to_csv(catalog_path, index=False)
    assert len(load_catalog(catalog_path)) == 1
    broken = tmp_path / "roto.csv"
    pd.DataFrame({"evento": ["Evento"]}).to_csv(broken, index=False)
    with pytest.raises(ValueError, match="Faltan columnas"):
        load_catalog(broken)
    assert len(load_episodes_from_path(tmp_path)) == 1
    assert len(load_hypotheses_from_path(tmp_path)) == 2


def load_episodes_from_path(tmp_path: Path) -> pd.DataFrame:
    path = tmp_path / "episodios.csv"
    _episodes().to_csv(path, index=False)
    return load_episodes(path)


def load_hypotheses_from_path(tmp_path: Path) -> pd.DataFrame:
    path = tmp_path / "hipotesis.csv"
    _hypotheses().to_csv(path, index=False)
    return load_hypotheses(path)


def test_build_event_study_config() -> None:
    from src.utils.config import CONFIG_DIR, load_config

    config = build_event_study_config(load_config(CONFIG_DIR / "experiment_04.yaml"))
    assert config.window_months == 6
    assert config.min_months_side == 4
    assert config.n_permutations == 10000
    assert config.alpha == 0.05
