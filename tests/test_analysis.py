"""Tests de la Fase 3b: series mensuales, regímenes, eventos y figuras."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from src.analysis.regime_change import (
    CHANGE_TEST_COLUMNS,
    REGIME_COLUMNS,
    RELATION_COLUMNS,
    RegimeConfig,
    bic_like,
    build_changes_stats,
    build_event_relations,
    build_regime_config,
    detect_changes,
    event_indicator,
    load_events,
    mirror_events,
    penalty_grid,
    rss_of_breaks,
    segment_boundaries,
)
from src.analysis.temporal import (
    TemporalConfig,
    build_series,
    build_temporal_config,
    monthly_grid,
)
from src.utils.config import CONFIG_DIR, load_config


def _temporal_config() -> TemporalConfig:
    return build_temporal_config(load_config(CONFIG_DIR / "experiment_03.yaml"))


def _regime_config() -> RegimeConfig:
    return build_regime_config(load_config(CONFIG_DIR / "experiment_03.yaml"))


def _interventions() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "utterance_id": ["u1", "u2", "u3", "u4", "u5"],
            "date": pd.to_datetime(
                ["2020-01-10", "2020-01-20", "2020-01-25", "2020-01-30", "2020-03-05"]
            ),
            "bertopic_topic": [0, 0, 1, -1, 0],
            "is_outlier": [False, False, False, True, False],
            "senti_n": [3.0, 5.0, 1.0, 0.0, 4.0],
            "n_words": [100, 50, 50, 10, 100],
        }
    )


# ---------------------------------------------------------------------------
# Series mensuales
# ---------------------------------------------------------------------------


def test_build_temporal_config_alineado_con_experimento_03() -> None:
    config = _temporal_config()
    assert config.start == "2015-01"
    assert config.end == "2023-02"
    assert config.outlier_strategy == "exclude"


def test_monthly_grid_cubre_la_cobertura_del_corpus() -> None:
    grid = monthly_grid("2015-01", "2023-02")
    assert len(grid) == 98
    assert grid[0] == pd.Timestamp("2015-01-01")
    assert grid[-1] == pd.Timestamp("2023-02-01")


def test_build_series_cuotas_tono_y_outliers() -> None:
    config = TemporalConfig(start="2020-01", end="2020-03", outlier_strategy="exclude")
    series = build_series(_interventions(), config)
    january = series.loc[series["month"] == pd.Timestamp("2020-01-01")]
    assert january.loc[january["series_type"] == "volume", "value"].item() == 4
    quotas = (
        january.loc[january["series_type"] == "topic"].set_index("series_id")["value"].to_dict()
    )
    assert quotas == {"0": 2 / 3, "1": 1 / 3}
    assert january.loc[january["series_type"] == "outliers", "value"].item() == 0.25
    assert january.loc[january["series_type"] == "tone", "value"].item() == pytest.approx(2.25)
    weighted = january.loc[january["series_type"] == "tone_weighted", "value"].item()
    assert weighted == pytest.approx(600 / 210)
    assert (january["has_session"]).all()

    february = series.loc[series["month"] == pd.Timestamp("2020-02-01")]
    assert not february["has_session"].any()
    assert february.loc[february["series_type"] == "tone", "value"].isna().all()
    assert (february.loc[february["series_type"] == "volume", "value"] == 0).all()

    march = series.loc[series["month"] == pd.Timestamp("2020-03-01")]
    assert march["has_session"].any()
    assert march.loc[march["series_type"] == "topic", "n_interventions"].sum() == 1


def test_build_series_falla_sin_columnas() -> None:
    broken = _interventions().drop(columns=["senti_n"])
    config = TemporalConfig(start="2020-01", end="2020-03", outlier_strategy="exclude")
    with pytest.raises(ValueError, match="Faltan columnas"):
        build_series(broken, config)


# ---------------------------------------------------------------------------
# Regímenes
# ---------------------------------------------------------------------------


def test_build_regime_config_alineado_con_experimento_03() -> None:
    config = _regime_config()
    assert (config.model, config.min_size, config.jump) == ("l2", 6, 1)
    assert (config.penalty_start, config.penalty_stop, config.penalty_num) == (1e-6, 1000.0, 60)
    assert config.sensitivity_factors == (0.25, 0.5, 1.0, 2.0, 4.0)
    assert config.window_months == 3


def test_penalty_grid_es_logaritmica() -> None:
    grid = penalty_grid(_regime_config())
    assert len(grid) == 60
    assert grid[0] == pytest.approx(1e-6)
    assert grid[-1] == pytest.approx(1000.0)
    ratios = grid[1:] / grid[:-1]
    assert np.allclose(ratios, ratios[0])


def test_segment_boundaries_y_rss() -> None:
    assert segment_boundaries([3, 6], 6) == [(0, 3), (3, 6)]
    values = np.array([0.0, 0.0, 0.0, 10.0, 10.0, 10.0])
    assert rss_of_breaks(values, [3, 6]) == 0.0
    assert rss_of_breaks(values, [6]) == pytest.approx(150.0)


def test_bic_like_premia_la_segmentacion_correcta() -> None:
    values = np.array([0.1, 0.0, 0.0, 10.0, 9.9, 10.0])
    assert bic_like(values, [3, 6]) < bic_like(values, [6])


def test_detect_changes_encuentra_el_escalon() -> None:
    values = np.concatenate([np.zeros(30), np.full(30, 5.0)])
    result = detect_changes(values, _regime_config())
    changes = list(result.breaks[:-1])
    assert any(abs(change - 30) <= 2 for change in changes)
    assert len(changes) <= 3
    assert len(result.sensitivity) == 5
    assert all(n_changes >= 0 for _, _, n_changes in result.sensitivity)


def test_detect_changes_falla_con_serie_corta() -> None:
    with pytest.raises(ValueError, match="corta"):
        detect_changes(np.zeros(5), _regime_config())


# ---------------------------------------------------------------------------
# Contraste por cambio (Mann-Whitney + BH)
# ---------------------------------------------------------------------------


def _stepped_tone_series() -> pd.DataFrame:
    months = pd.date_range("2018-01-01", periods=60, freq="MS")
    values = np.concatenate([np.zeros(30), np.full(30, 5.0)])
    return pd.DataFrame(
        {
            "month": months,
            "series_type": "tone",
            "series_id": "tone",
            "value": values,
            "n_interventions": 40,
            "has_session": True,
        }
    )


def _stepped_change() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "serie": "tone",
                "serie_id": "tone",
                "fecha": pd.Timestamp("2020-07-01"),
                "indice": 30,
                "media_antes": 0.0,
                "media_despues": 5.0,
                "delta": 5.0,
                "pen_seleccionada": 1.0,
                "n_cambios": 1,
                "n_puntos": 60,
                "tamano_serie": 2400,
            }
        ],
        columns=REGIME_COLUMNS,
    )


def test_build_changes_stats_escalon_significativo() -> None:
    stats = build_changes_stats(_stepped_tone_series(), _stepped_change())
    assert list(stats.columns) == CHANGE_TEST_COLUMNS
    row = stats.iloc[0]
    assert row["r"] == pytest.approx(1.0)
    assert float(row["p"]) < 0.001
    assert float(row["q"]) == pytest.approx(float(row["p"]))
    assert (row["n_antes"], row["n_despues"], row["n"]) == (30, 30, 60)
    assert int(row["significativo_bh"]) == 1


def test_build_changes_stats_signo_concordante_con_delta() -> None:
    descent = _stepped_tone_series()
    descent.loc[descent["month"] >= "2020-07-01", "value"] = -5.0
    row = build_changes_stats(descent, _stepped_change()).iloc[0]
    assert row["r"] == pytest.approx(-1.0)
    assert int(row["significativo_bh"]) == 1


def test_build_changes_stats_serie_degenerada_sin_efecto() -> None:
    flat = _stepped_tone_series()
    flat["value"] = 1.0
    row = build_changes_stats(flat, _stepped_change()).iloc[0]
    assert row["r"] == 0.0
    assert float(row["p"]) == 1.0
    assert int(row["significativo_bh"]) == 0


def test_build_changes_stats_valida_serie_e_indice() -> None:
    missing = _stepped_change().assign(serie="topic")
    with pytest.raises(ValueError, match="Sin serie mensual"):
        build_changes_stats(_stepped_tone_series(), missing)
    out_of_range = _stepped_change().assign(indice=60)
    with pytest.raises(ValueError, match="fuera de rango"):
        build_changes_stats(_stepped_tone_series(), out_of_range)


# ---------------------------------------------------------------------------
# Eventos
# ---------------------------------------------------------------------------


def _synthetic_event_series() -> pd.DataFrame:
    months = pd.date_range("2020-01-01", "2020-12-01", freq="MS")
    window = pd.date_range("2020-03-01", "2020-09-01", freq="MS")
    rows = [
        {
            "month": month,
            "series_type": "topic",
            "series_id": "0",
            "value": 10.0 if month in set(window) else 0.0,
            "n_interventions": 10,
            "has_session": True,
        }
        for month in months
    ]
    return pd.DataFrame(rows)


def _synthetic_events() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "evento": ["Evento A"],
            "fecha": pd.to_datetime(["2020-06-01"]),
            "tipo": ["prueba"],
            "fuente": ["sintética"],
            "notas": [""],
        }
    )


def test_event_indicator_ventana_simetrica() -> None:
    months = pd.date_range("2020-01-01", "2020-12-01", freq="MS")
    indicator = event_indicator(months, pd.Timestamp("2020-06-15"), 3)
    assert int(indicator.sum()) == 7
    assert bool(indicator[2]) is True  # marzo
    assert bool(indicator[1]) is False  # febrero
    assert bool(indicator[8]) is True  # septiembre
    assert bool(indicator[9]) is False  # octubre


def test_build_event_relations_detecta_asociacion() -> None:
    relations = build_event_relations(
        _synthetic_event_series(), _synthetic_events(), _regime_config()
    )
    assert list(relations.columns) == RELATION_COLUMNS
    assert len(relations) == 1
    row = relations.iloc[0]
    assert row["rho"] == pytest.approx(1.0)
    assert row["p"] < 0.05
    assert row["q"] <= row["p"]
    assert row["media_en_ventana"] == pytest.approx(10.0)
    assert row["media_fuera"] == pytest.approx(0.0)


def test_load_events_valida_y_parsea(tmp_path: Path) -> None:
    path = tmp_path / "eventos.csv"
    _synthetic_events().to_csv(path, index=False)
    events = load_events(path)
    assert pd.api.types.is_datetime64_any_dtype(events["fecha"])
    broken = tmp_path / "rotos.csv"
    _synthetic_events().drop(columns=["fuente"]).to_csv(broken, index=False)
    with pytest.raises(ValueError, match="Faltan columnas"):
        load_events(broken)


def test_mirror_events_copia_bytes(tmp_path: Path) -> None:
    source = tmp_path / "origen.csv"
    _synthetic_events().to_csv(source, index=False)
    destination = tmp_path / "espejo" / "eventos.csv"
    mirror_events(source, destination)
    assert destination.read_bytes() == source.read_bytes()
