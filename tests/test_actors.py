"""Tests de la capa de actores (D-45)."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from src.analysis.actors import (
    ACTOR_SERIES_COLUMNS,
    DECOMPOSITION_COLUMNS,
    ActorConfig,
    assign_party_families,
    bootstrap_delta_ci,
    build_actor_decomposition,
    build_actor_series,
    build_tone_counterfactual,
    load_party_mapping,
)


def _mapping(tmp_path: Path) -> Path:
    path = tmp_path / "partidos.csv"
    pd.DataFrame(
        {
            "raw_label": ["PP", "PP-Foro", "PSOE", "SIN_PARTIDO"],
            "family": ["PP", "PP", "PSOE", "Otros"],
            "notes": ["", "", "", ""],
        }
    ).to_csv(path, index=False)
    return path


def _interventions() -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    months_before = pd.date_range("2020-01-01", periods=6, freq="MS")
    months_after = pd.date_range("2020-07-01", periods=6, freq="MS")
    for month in months_before:
        for party, n, topic in (("PP", 10, 2), ("PSOE", 10, 2)):
            for index in range(n):
                rows.append(
                    {
                        "utterance_id": f"{month:%Y%m}-{party}-{index}",
                        "date": month + pd.Timedelta(days=1),
                        "month": month,
                        "speaker_party": party,
                        "party_status": "Coalition" if party == "PP" else "Opposition",
                        "party_family": party,
                        "senti_n": 2.0 if party == "PP" else 1.0,
                        "negative": 0.0 if party == "PP" else 1.0,
                        "n_words": 100,
                        "bertopic_topic": 0 if index < topic else 1,
                        "is_outlier": False,
                    }
                )
    for month in months_after:
        for party, n, topic in (("PP", 2, 1), ("PSOE", 18, 6)):
            for index in range(n):
                rows.append(
                    {
                        "utterance_id": f"{month:%Y%m}-{party}-{index}",
                        "date": month + pd.Timedelta(days=1),
                        "month": month,
                        "speaker_party": party,
                        "party_status": "Coalition" if party == "PP" else "Opposition",
                        "party_family": party,
                        "senti_n": 3.0 if party == "PP" else 1.0,
                        "negative": 0.0 if party == "PP" else 1.0,
                        "n_words": 100,
                        "bertopic_topic": 0 if index < topic else 1,
                        "is_outlier": False,
                    }
                )
    return pd.DataFrame(rows)


def _config(tmp_path: Path) -> ActorConfig:
    return ActorConfig(
        mapping_path=_mapping(tmp_path),
        interventions_path=tmp_path / "intervenciones.parquet",
        assignments_path=tmp_path / "topicos.parquet",
        monthly_series_path=tmp_path / "series.parquet",
        series_parquet_path=tmp_path / "actores.parquet",
        series_csv_path=tmp_path / "actores.csv",
        decomposition_path=tmp_path / "descomposicion.csv",
        counterfactual_path=tmp_path / "contrafactual.csv",
        tone_ci_path=tmp_path / "ic.csv",
        min_cell=10,
        bootstrap_n=100,
        baseline_start="2020-01",
        baseline_end="2020-06",
        seed=42,
    )


def _monthly_series() -> pd.DataFrame:
    before = pd.date_range("2020-01-01", periods=6, freq="MS")
    after = pd.date_range("2020-07-01", periods=6, freq="MS")
    rows = [
        {
            "month": month,
            "series_type": "topic",
            "series_id": "0",
            "value": 0.2,
            "n_interventions": 20,
            "has_session": True,
        }
        for month in before
    ] + [
        {
            "month": month,
            "series_type": "topic",
            "series_id": "0",
            "value": 0.35,
            "n_interventions": 20,
            "has_session": True,
        }
        for month in after
    ]
    return pd.DataFrame(rows)


def test_load_party_mapping_valida(tmp_path: Path) -> None:
    mapping = load_party_mapping(_mapping(tmp_path))
    assert len(mapping) == 4
    broken = tmp_path / "roto.csv"
    pd.DataFrame({"raw_label": ["PP"], "family": ["PP"]}).to_csv(broken, index=False)
    with pytest.raises(ValueError, match="Faltan columnas"):
        load_party_mapping(broken)


def test_assign_party_families_y_desconocidos(tmp_path: Path) -> None:
    mapping = load_party_mapping(_mapping(tmp_path))
    frame = pd.DataFrame(
        {
            "speaker_party": ["PP-Foro", None],
            "party_status": [None, "Coalition"],
        }
    )
    result = assign_party_families(frame, mapping)
    assert result["party_family"].tolist() == ["PP", "Otros"]
    assert result["party_status"].tolist() == ["Desconocido", "Coalition"]
    broken = frame.assign(speaker_party=["NUEVO", "PP"])
    with pytest.raises(ValueError, match="sin mapear"):
        assign_party_families(broken, mapping)


def test_build_actor_series_cuotas_y_global(tmp_path: Path) -> None:
    series = build_actor_series(_interventions(), _config(tmp_path))
    assert list(series.columns) == ACTOR_SERIES_COLUMNS
    january = series.loc[series["month"] == pd.Timestamp("2020-01-01")]
    assert january.loc[january["party_family"] == "Todos", "n"].item() == 20
    pp = january.loc[(january["party_family"] == "PP") & (january["party_status"] == "Todos")].iloc[
        0
    ]
    assert pp["share_all"] == pytest.approx(0.5)
    assert pp["tone_mean"] == pytest.approx(2.0)
    assert pp["negative_share"] == pytest.approx(0.0)


def test_decomposition_shift_share_identidad(tmp_path: Path) -> None:
    interventions = _interventions()
    monthly = _monthly_series()
    changes = pd.DataFrame(
        [
            {
                "serie": "topic",
                "serie_id": "0",
                "fecha": pd.Timestamp("2020-07-01"),
                "indice": 6,
                "tamano_serie": 240,
                "delta": 0.15,
            }
        ]
    )
    stats = pd.DataFrame(
        [
            {
                "serie": "topic",
                "serie_id": "0",
                "fecha": pd.Timestamp("2020-07-01"),
                "significativo_bh": 1,
            }
        ]
    )
    table = build_actor_decomposition(interventions, changes, stats, monthly)
    assert list(table.columns) == DECOMPOSITION_COLUMNS
    assert set(table["nivel"]) == {"partido", "partido_estatus"}
    for level in ("partido", "partido_estatus"):
        subset = table.loc[table["nivel"] == level]
        total = subset.loc[subset["partido"] != "__residual__"]
        assert total["contribucion_dentro"].sum() + total[
            "contribucion_composicion"
        ].sum() == pytest.approx(0.15)
        assert subset["contribucion_dentro"].sum() + subset[
            "contribucion_composicion"
        ].sum() == pytest.approx(0.15)
        assert subset["residual"].abs().max() < 1e-9


def test_counterfactual_sin_cambio_de_composicion(tmp_path: Path) -> None:
    interventions = _interventions()
    interventions = interventions.loc[interventions["month"] <= pd.Timestamp("2020-06-01")]
    counterfactual = build_tone_counterfactual(interventions, _config(tmp_path))
    assert not counterfactual.empty
    assert np.allclose(
        counterfactual["neg_share_real"], counterfactual["neg_share_ajustado"], atol=1e-9
    )


def test_bootstrap_delta_ci() -> None:
    observed, lower, upper = bootstrap_delta_ci(np.zeros(100), np.ones(100), 200, 42)
    assert observed == pytest.approx(1.0)
    assert lower == pytest.approx(1.0)
    assert upper == pytest.approx(1.0)
    with pytest.raises(ValueError, match="vacío"):
        bootstrap_delta_ci([], [1.0], 10, 42)
