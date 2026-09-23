"""Tests de la API FastAPI (Fase 5) con artefactos sintéticos en ``tmp_path``."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd
import pytest
from fastapi.testclient import TestClient
from src.api.main import create_app


def _fixtures(root: Path) -> tuple[Path, Path]:
    """Crea directorios ``reports/`` y ``data/`` mínimos y devuelve sus rutas."""
    reports = root / "reports"
    tables = reports / "tables"
    data = root / "data"
    (data / "processed").mkdir(parents=True)
    (data / "intermediate").mkdir(parents=True)
    tables.mkdir(parents=True)

    pd.DataFrame(
        {
            "topic": [0, 1],
            "size": [100, 50],
            "share": [0.6, 0.3],
            "top_terms": ["economía; empleo", "sanidad; vacuna"],
            "representative_utterance_ids": ["u1; u2", "u3"],
            "representative_texts": ["texto uno || texto dos", "texto tres"],
        }
    ).to_csv(tables / "topics_evidence.csv", index=False)
    pd.DataFrame(
        {
            "topic": [0, 1],
            "label": ["Economía", "Sanidad"],
            "description": ["Temas económicos", "Temas sanitarios"],
            "model": ["asistente"] * 2,
            "prompt_version": ["v1"] * 2,
            "date": ["2026-09-14"] * 2,
            "reviewed_by": [""] * 2,
        }
    ).to_csv(tables / "topics_labels.csv", index=False)
    pd.DataFrame(
        {
            "min_topic_size": [100],
            "n_neighbors": [30],
            "min_samples": [10],
            "n_topics": [2],
            "outlier_rate": [0.2],
            "coherence": [0.7],
            "diversity": [0.9],
            "selected": [True],
        }
    ).to_csv(tables / "topics_selection.csv", index=False)
    pd.DataFrame(
        {
            "serie": ["topic", "tone"],
            "serie_id": ["0", "tone"],
            "fecha": ["2020-01-01", "2020-02-01"],
            "indice": [3, 4],
            "media_antes": [0.1, 2.0],
            "media_despues": [0.2, 2.2],
            "delta": [0.1, 0.2],
            "pen_seleccionada": [0.05, 0.1],
            "n_cambios": [1, 1],
            "n_puntos": [10, 10],
            "tamano_serie": [100, 200],
        }
    ).to_csv(tables / "cambios_regimen.csv", index=False)
    pd.DataFrame(
        {
            "serie": ["topic"],
            "serie_id": ["0"],
            "factor": [1.0],
            "penalizacion": [0.05],
            "n_cambios": [1],
        }
    ).to_csv(tables / "cambios_regimen_sensibilidad.csv", index=False)
    pd.DataFrame(
        {
            "serie": ["topic", "tone"],
            "serie_id": ["0", "tone"],
            "fecha": ["2020-01-01", "2020-02-01"],
            "r": [0.5, -0.3],
            "p": [0.01, 0.02],
            "q": [0.04, 0.05],
            "n_antes": [5, 5],
            "n_despues": [5, 5],
            "n": [10, 10],
            "significativo_bh": [1, 1],
        }
    ).to_csv(tables / "cambios_regimen_test.csv", index=False)
    pd.DataFrame(
        {
            "evento": ["Evento A"],
            "fecha": ["2020-01-15"],
            "tipo": ["prueba"],
            "fuente": ["sintética"],
            "notas": [""],
        }
    ).to_csv(tables / "eventos.csv", index=False)
    pd.DataFrame(
        {
            "evento": ["Evento A"],
            "serie": ["topic"],
            "serie_id": ["0"],
            "rho": [0.5],
            "p": [0.01],
            "q": [0.04],
            "n": [10],
            "media_en_ventana": [0.2],
            "media_fuera": [0.1],
        }
    ).to_csv(tables / "eventos_relaciones.csv", index=False)
    pd.DataFrame(
        {
            "modelo": ["multilingual-e5-large", "bge-m3"],
            "n_topicos": [2, 3],
            "outlier_rate": [0.2, 0.3],
            "coherencia_cv": [0.7, 0.8],
            "diversidad": [0.9, 0.85],
            "ari_vs_e5": [1.0, 0.7],
            "nmi_vs_e5": [1.0, 0.9],
            "n_comparables": [100, 100],
        }
    ).to_csv(tables / "sensibilidad_embeddings.csv", index=False)
    pd.DataFrame(
        {
            "nivel": ["senti_3"],
            "n": [10],
            "accuracy": [0.6],
            "balanced_accuracy": [0.6],
            "reweighted_accuracy": [0.6],
            "f1_macro": [0.5],
            "kappa_linear": [0.4],
            "kappa_quadratic": [0.5],
        }
    ).to_csv(tables / "validacion_sentimiento_revision_metricas.csv", index=False)
    pd.DataFrame(
        {
            "nivel": ["senti_3"],
            "metrica": ["accuracy"],
            "variante": ["cruda"],
            "estimador": [0.6],
            "ic_inf": [0.5],
            "ic_sup": [0.7],
            "n_boot": [100],
            "alpha": [0.05],
        }
    ).to_csv(tables / "validacion_sentimiento_revision_ic.csv", index=False)
    pd.DataFrame(
        {
            "par": ["parlacap_humano"],
            "nivel": ["senti_3"],
            "n": [10],
            "acuerdo": [0.6],
            "kappa_linear": [0.4],
            "kappa_quadratic": [0.5],
            "fleiss_kappa": [float("nan")],
        }
    ).to_csv(tables / "validacion_sentimiento_acuerdo_3bandas.csv", index=False)
    pd.DataFrame(
        [[5, 1, 0], [1, 4, 1], [0, 0, 3]],
        index=["Negative", "Neutral", "Positive"],
        columns=["Negative", "Neutral", "Positive"],
    ).to_csv(tables / "validacion_sentimiento_revision_confusion_senti_3.csv")
    pd.DataFrame(
        {
            "utterance_id": ["u1", "u2", "u3"],
            "bertopic_topic": [0, 1, -1],
            "is_outlier": [False, False, True],
        }
    ).to_parquet(data / "processed" / "intervenciones_topicos.parquet", index=False)
    pd.DataFrame(
        {
            "month": pd.to_datetime(["2020-01-01", "2020-02-01"] * 2),
            "series_type": ["topic", "topic", "tone", "tone"],
            "series_id": ["0", "0", "tone", "tone"],
            "value": [0.5, 0.6, 2.0, 2.1],
            "n_interventions": [10, 12, 20, 22],
            "has_session": [True, True, True, True],
        }
    ).to_parquet(data / "intermediate" / "series_mensuales.parquet", index=False)
    return reports, data


@pytest.fixture()
def client(tmp_path: Path) -> Any:
    reports, data = _fixtures(tmp_path)
    return TestClient(create_app(reports_dir=reports, data_dir=data))


def test_health(client: Any) -> None:
    assert client.get("/health").json() == {"status": "ok"}


def test_meta_resume_corpus_y_rejilla(client: Any) -> None:
    payload = client.get("/meta").json()
    assert payload["intervenciones"] == 3
    assert payload["topicos"] == 2
    assert payload["tasa_outliers"] == pytest.approx(1 / 3, abs=1e-6)
    assert payload["rejilla_seleccionada"] == {
        "min_topic_size": 100,
        "n_neighbors": 30,
        "min_samples": 10,
    }


def test_topics_fusiona_etiquetas(client: Any) -> None:
    topics = client.get("/topics").json()
    assert topics[0]["label"] == "Economía"
    assert topics[0]["size"] == 100


def test_topics_selection_expone_la_rejilla_completa(client: Any) -> None:
    selection = client.get("/topics/selection").json()
    assert len(selection) == 1
    assert selection[0]["min_topic_size"] == 100
    assert selection[0]["selected"] == 1


def test_topic_detail_divide_representativas(client: Any) -> None:
    detail = client.get("/topics/0").json()
    assert detail["representative_texts"] == ["texto uno", "texto dos"]
    assert detail["representative_utterance_ids"] == ["u1", "u2"]
    assert client.get("/topics/99").status_code == 404


def test_series_filtra_y_falla_si_no_existe(client: Any) -> None:
    payload = client.get("/series", params={"series_type": "topic"}).json()
    assert len(payload) == 2
    assert payload[0]["series_id"] == "0"
    assert client.get("/series", params={"series_type": "volume"}).status_code == 404


def test_changes_y_sensibilidad(client: Any) -> None:
    changes = client.get("/changes", params={"serie": "tone"}).json()
    assert changes[0]["serie_id"] == "tone"
    sensitivity = client.get(
        "/changes/sensitivity", params={"serie": "topic", "serie_id": "0"}
    ).json()
    assert len(sensitivity) == 1


def test_changes_stats_filtra_y_ordena(client: Any) -> None:
    stats = client.get("/changes/stats").json()
    assert [row["serie"] for row in stats] == ["topic", "tone"]
    assert stats[0]["n"] == 10
    assert stats[0]["significativo_bh"] == 1
    filtered = client.get("/changes/stats", params={"serie": "tone"}).json()
    assert [row["serie_id"] for row in filtered] == ["tone"]
    assert len(client.get("/changes/stats", params={"max_q": 0.045}).json()) == 1
    assert client.get("/changes/stats", params={"max_q": 0.03}).json() == []


def test_eventos_y_relaciones(client: Any) -> None:
    assert client.get("/events").json()[0]["evento"] == "Evento A"
    relations = client.get("/events/relations", params={"max_q": 0.05}).json()
    assert len(relations) == 1
    assert client.get("/events/relations", params={"max_q": 0.01}).json() == []


def test_sentiment_y_confusion(client: Any) -> None:
    payload = client.get("/sentiment").json()
    assert payload["revision_metricas"][0]["nivel"] == "senti_3"
    confusion = client.get("/sentiment/confusion/senti_3").json()
    assert confusion["index"][0] == "Negative"
    assert confusion["values"][0][0] == 5
    assert client.get("/sentiment/confusion/senti_9").status_code == 404


def test_sensitivity(client: Any) -> None:
    payload = client.get("/sensitivity").json()
    assert payload[1]["modelo"] == "bge-m3"


def test_artefacto_ausente_devuelve_503(tmp_path: Path) -> None:
    reports = tmp_path / "reports"
    data = tmp_path / "data"
    (reports / "tables").mkdir(parents=True)
    (data / "processed").mkdir(parents=True)
    client: Any = TestClient(create_app(reports_dir=reports, data_dir=data))
    assert client.get("/topics").status_code == 503
    assert client.get("/meta").status_code == 503


def test_cors_permite_el_origen_del_frontend(tmp_path: Path) -> None:
    reports, data = _fixtures(tmp_path)
    client: Any = TestClient(create_app(reports_dir=reports, data_dir=data))
    response = client.get("/health", headers={"Origin": "http://localhost:3000"})
    assert response.headers["access-control-allow-origin"] == "http://localhost:3000"
    denied = client.get("/health", headers={"Origin": "http://localhost:9999"})
    assert "access-control-allow-origin" not in denied.headers


def test_export_openapi_expone_todos_los_endpoints(tmp_path: Path) -> None:
    from src.api.openapi import export_openapi

    destination = export_openapi(tmp_path / "openapi.json")
    schema = json.loads(destination.read_text(encoding="utf-8"))
    expected = {
        "/health",
        "/meta",
        "/topics",
        "/topics/selection",
        "/topics/{topic_id}",
        "/series",
        "/changes",
        "/changes/sensitivity",
        "/changes/stats",
        "/events",
        "/events/relations",
        "/sensitivity",
        "/sentiment",
        "/sentiment/confusion/{level}",
    }
    assert expected == set(schema["paths"])
