"""Tests de la Fase 3a: representación y embeddings.

Los tests unitarios no descargan ni ejecutan modelos: usan tokenizadores y
codificadores falsos. Los tests marcados ``heavy`` sí requieren los modelos
reales y se saltan salvo que se defina ``HEMICICLO_HEAVY=1`` (D-30).
"""

from __future__ import annotations

import os
from collections.abc import Sequence
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from src.nlp.embeddings import (
    EmbeddingConfig,
    aggregate_embeddings,
    build_embedding_config,
    build_embeddings,
    chunk_interventions,
    embed_chunks,
    embed_interventions,
    token_windows,
)
from src.nlp.sentiment import (
    SENTI6_LABELS,
    SentimentConfig,
    build_sentiment_config,
    evaluate_sentiment,
    proportional_sample,
    reweighted_accuracy,
    write_revision_tables,
)
from src.nlp.topic_model import (
    OUTLIER_TOPIC,
    TopicConfig,
    build_assignments,
    build_evidence,
    build_topic_config,
    coherence_score,
    diversity_score,
    grid_combinations,
    outlier_rate,
    select_best_run,
    tokenize_texts,
    topic_count,
)
from src.utils.config import CONFIG_DIR, load_config
from src.utils.helpers import import_optional

heavy = pytest.mark.skipif(
    not os.environ.get("HEMICICLO_HEAVY"),
    reason="requiere modelos reales y capacidad de cómputo (D-30)",
)


# ---------------------------------------------------------------------------
# Dobles de tokenizador y codificador
# ---------------------------------------------------------------------------


def fake_encode(text: str) -> list[int]:
    """Tokeniza por espacios: cada palabra es un token con su posición."""
    return list(range(len(text.split())))


def fake_decode(ids: Sequence[int]) -> str:
    return " ".join(str(token) for token in ids)


def fake_encoder(texts: Sequence[str]) -> np.ndarray:
    """Vector determinista según el texto, para poder comprobar la agregación."""
    rows: list[list[float]] = []
    for text in texts:
        if text == "a":
            rows.append([1.0, 0.0])
        elif text == "b":
            rows.append([0.0, 1.0])
        else:
            rows.append([1.0, 1.0])
    return np.asarray(rows, dtype=np.float64)


def _token_text(n: int) -> str:
    return " ".join(str(index) for index in range(n))


def _minimal_config(**overrides: object) -> EmbeddingConfig:
    section: dict[str, object] = {"model": "fake-model"}
    section.update(overrides)
    return build_embedding_config({"embeddings": section})


# ---------------------------------------------------------------------------
# Configuración
# ---------------------------------------------------------------------------


def test_build_embedding_config_aplica_defaults() -> None:
    config = _minimal_config()
    assert config.model == "fake-model"
    assert config.prefix == ""
    assert config.max_tokens == 384
    assert config.stride == 320
    assert config.min_tokens == 8
    assert config.batch_size == 32


def test_build_embedding_config_rechaza_stride_invalido() -> None:
    with pytest.raises(ValueError, match="stride"):
        _minimal_config(chunk_tokens=100, chunk_stride=100)


def test_experimento_01_usa_e5_large() -> None:
    config = build_embedding_config(load_config(CONFIG_DIR / "experiment_01.yaml"))
    assert config.model == "intfloat/multilingual-e5-large"
    assert config.prefix == "passage: "
    assert config.stride < config.max_tokens


def test_experimento_02_usa_bge_m3() -> None:
    config = build_embedding_config(load_config(CONFIG_DIR / "experiment_02.yaml"))
    assert config.model == "BAAI/bge-m3"
    assert config.prefix == ""


# ---------------------------------------------------------------------------
# Troceado en ventanas de tokens
# ---------------------------------------------------------------------------


def test_token_windows_texto_corto_es_una_ventana() -> None:
    windows = token_windows(
        _token_text(5), fake_encode, fake_decode, max_tokens=10, stride=8, min_tokens=1
    )
    assert windows == ["0 1 2 3 4"]


def test_token_windows_texto_vacio() -> None:
    windows = token_windows("", fake_encode, fake_decode, max_tokens=10, stride=8, min_tokens=1)
    assert windows == []


def test_token_windows_con_solape() -> None:
    windows = token_windows(
        _token_text(800), fake_encode, fake_decode, max_tokens=384, stride=320, min_tokens=8
    )
    assert len(windows) == 3
    assert windows[0].split()[:2] == ["0", "1"]
    assert len(windows[0].split()) == 384
    assert windows[1].split()[0] == "320"
    assert len(windows[2].split()) == 160


def test_token_windows_descarta_ventana_demasiado_corta() -> None:
    windows = token_windows(
        _token_text(390), fake_encode, fake_decode, max_tokens=384, stride=320, min_tokens=100
    )
    assert len(windows) == 1
    assert len(windows[0].split()) == 384


def test_token_windows_no_repite_la_cola_final() -> None:
    windows = token_windows(
        _token_text(1000), fake_encode, fake_decode, max_tokens=384, stride=320, min_tokens=8
    )
    assert [len(window.split()) for window in windows] == [384, 384, 360]


def test_chunk_interventions_reinicia_indice_por_intervencion() -> None:
    frame = pd.DataFrame(
        {
            "utterance_id": ["u1", "u2"],
            "text": [_token_text(6), _token_text(3)],
        }
    )
    config = _minimal_config(chunk_tokens=4, chunk_stride=2, min_chunk_tokens=1)
    chunks = chunk_interventions(frame, config, encode=fake_encode, decode=fake_decode)
    assert list(chunks.columns) == ["utterance_id", "chunk_index", "text"]
    assert chunks["utterance_id"].tolist() == ["u1", "u1", "u2"]
    assert chunks["chunk_index"].tolist() == [0, 1, 0]


# ---------------------------------------------------------------------------
# Codificación y agregación
# ---------------------------------------------------------------------------


def test_embed_chunks_anade_prefijo_y_lotes() -> None:
    captured: list[str] = []

    def encoder(texts: Sequence[str]) -> np.ndarray:
        captured.extend(texts)
        return np.ones((len(texts), 3), dtype=np.float64)

    vectors = embed_chunks(["uno", "dos"], encoder, prefix="passage: ", batch_size=1)
    assert captured == ["passage: uno", "passage: dos"]
    assert vectors.shape == (2, 3)


def test_aggregate_embeddings_promedia_y_normaliza() -> None:
    result = aggregate_embeddings([np.array([3.0, 0.0]), np.array([0.0, 4.0])])
    expected = np.array([1.0, 1.0]) / np.sqrt(2.0)
    assert np.allclose(result, expected)
    assert np.isclose(np.linalg.norm(result), 1.0)


def test_aggregate_embeddings_de_vectores_iguales() -> None:
    result = aggregate_embeddings([np.array([2.0, 0.0]), np.array([2.0, 0.0])])
    assert np.allclose(result, np.array([1.0, 0.0]))


def test_aggregate_embeddings_exige_vectores() -> None:
    with pytest.raises(ValueError, match="vector"):
        aggregate_embeddings([])


def test_embed_interventions_media_por_intervencion() -> None:
    chunks = pd.DataFrame(
        {
            "utterance_id": ["u1", "u1", "u2"],
            "chunk_index": [0, 1, 0],
            "text": ["a", "b", "c"],
        }
    )
    result = embed_interventions(chunks, fake_encoder, _minimal_config())
    assert result["utterance_id"].tolist() == ["u1", "u2"]
    vectors = result["embedding"].to_numpy()
    expected = np.array([1.0, 1.0]) / np.sqrt(2.0)
    assert np.allclose(vectors[0], expected)
    assert np.allclose(vectors[1], expected)


def test_build_embeddings_con_dobles() -> None:
    frame = pd.DataFrame({"utterance_id": ["u1", "u2"], "text": ["a b", "c"]})
    chunks, embeddings = build_embeddings(
        frame,
        _minimal_config(min_chunk_tokens=1),
        tokenize=fake_encode,
        detokenize=fake_decode,
        encode=fake_encoder,
    )
    assert list(chunks.columns) == ["utterance_id", "chunk_index", "text"]
    assert list(embeddings.columns) == ["utterance_id", "embedding"]
    assert embeddings["utterance_id"].tolist() == ["u1", "u2"]
    matrix = np.asarray(list(embeddings["embedding"]), dtype=np.float64)
    assert np.allclose(np.linalg.norm(matrix, axis=1), 1.0)


# ---------------------------------------------------------------------------
# Utilidades
# ---------------------------------------------------------------------------


def test_import_optional_carga_modulo() -> None:
    json_module = import_optional("json")
    assert json_module.dumps({"a": 1}) == '{"a": 1}'


def test_import_optional_falla_si_no_existe() -> None:
    with pytest.raises(ModuleNotFoundError):
        import_optional("modulo_que_no_existe_hemiciclo")


# ---------------------------------------------------------------------------
# Fase 3a: configuración, métricas y artefactos de tópicos
# ---------------------------------------------------------------------------


def _topic_config() -> TopicConfig:
    return build_topic_config(load_config(CONFIG_DIR / "experiment_01.yaml"))


def test_build_topic_config_alineado_con_experimento_01() -> None:
    config = _topic_config()
    assert config.coherence == "c_v"
    assert config.min_topic_size == (15, 30, 50, 100, 150, 200)
    assert config.n_neighbors == (10, 15, 30)
    assert config.min_samples == (5, 10)
    assert config.representative_docs == 8
    assert config.diversity_top_n == 10
    assert (config.min_topics, config.max_topics) == (20, 60)
    assert config.max_outlier_rate == 0.4
    assert config.seed == 42


def test_build_topic_config_rechaza_outlier_strategy() -> None:
    with pytest.raises(ValueError, match="outliers"):
        build_topic_config({"topics": {"outlier_strategy": "distributions"}})


def test_grid_combinations_producto_cartesiano() -> None:
    grid = grid_combinations(_topic_config())
    assert len(grid) == 36
    assert grid[0] == {"min_topic_size": 15, "n_neighbors": 10, "min_samples": 5}
    assert grid[-1] == {"min_topic_size": 200, "n_neighbors": 30, "min_samples": 10}


def test_tokenize_texts_normaliza_minusculas() -> None:
    assert tokenize_texts(["Hola   Mundo"]) == [["hola", "mundo"]]


def test_outlier_rate() -> None:
    assert outlier_rate([OUTLIER_TOPIC, 0, 1, OUTLIER_TOPIC]) == 0.5
    assert np.isnan(outlier_rate([]))


def test_topic_count_excluye_outliers() -> None:
    assert topic_count([OUTLIER_TOPIC, 0, 0, 2]) == 2


def test_diversity_score_palabras_unicas() -> None:
    topics = [["a", "b", "c"], ["b", "c", "d"]]
    assert diversity_score(topics, top_n=3) == 4 / 6
    assert np.isnan(diversity_score([], top_n=10))
    assert diversity_score(topics, top_n=1) == 1.0


def _selection_table() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "min_topic_size": 15,
                "n_neighbors": 10,
                "min_samples": 5,
                "n_topics": 30,
                "outlier_rate": 0.30,
                "coherence": 0.55,
                "diversity": 0.80,
            },
            {
                "min_topic_size": 30,
                "n_neighbors": 15,
                "min_samples": 5,
                "n_topics": 25,
                "outlier_rate": 0.50,
                "coherence": 0.70,
                "diversity": 0.90,
            },
            {
                "min_topic_size": 50,
                "n_neighbors": 30,
                "min_samples": 10,
                "n_topics": 80,
                "outlier_rate": 0.20,
                "coherence": 0.80,
                "diversity": 0.90,
            },
            {
                "min_topic_size": 30,
                "n_neighbors": 30,
                "min_samples": 10,
                "n_topics": 40,
                "outlier_rate": 0.25,
                "coherence": 0.50,
                "diversity": 0.70,
            },
        ]
    )


def test_select_best_run_filtra_y_maximiza_coherencia() -> None:
    best = select_best_run(_selection_table(), _topic_config())
    assert best["n_neighbors"] == 10
    assert best["coherence"] == 0.55


def test_select_best_run_desempata_por_diversidad() -> None:
    table = _selection_table()
    table.loc[0, "coherence"] = 0.60
    table.loc[0, "diversity"] = 0.50
    table.loc[3, "coherence"] = 0.60
    best = select_best_run(table, _topic_config())
    assert best["min_topic_size"] == 30
    assert best["diversity"] == 0.70


def test_select_best_run_falla_sin_candidatos() -> None:
    table = _selection_table()
    table.loc[:, "outlier_rate"] = 0.9
    with pytest.raises(ValueError, match="filtros"):
        select_best_run(table, _topic_config())


def test_build_assignments() -> None:
    frame = build_assignments(["u1", "u2", "u3"], [0, OUTLIER_TOPIC, 2])
    assert list(frame.columns) == ["utterance_id", "bertopic_topic", "is_outlier"]
    assert frame["is_outlier"].tolist() == [False, True, False]


def test_build_evidence_mapea_representativas() -> None:
    evidence = build_evidence(
        ["u1", "u2", "u3"],
        ["texto uno", "texto dos", "texto tres"],
        [0, 0, OUTLIER_TOPIC],
        {0: ["economía", "empleo"]},
        {0: ["texto dos"]},
    )
    assert list(evidence.columns) == [
        "topic",
        "size",
        "share",
        "top_terms",
        "representative_utterance_ids",
        "representative_texts",
    ]
    assert len(evidence) == 1
    row = evidence.iloc[0]
    assert row["topic"] == 0
    assert row["size"] == 2
    assert row["share"] == round(2 / 3, 6)
    assert row["top_terms"] == "economía; empleo"
    assert row["representative_utterance_ids"] == "u2"
    assert row["representative_texts"] == "texto dos"


# ---------------------------------------------------------------------------
# Fase 3a: validación de sentimiento (D-26)
# ---------------------------------------------------------------------------


def _sentiment_config() -> SentimentConfig:
    return build_sentiment_config(load_config(CONFIG_DIR / "experiment_01.yaml"))


def _validation_corpus() -> pd.DataFrame:
    combos = [
        ("A", "T1", 300),
        ("A", "T2", 100),
        ("B", "T1", 100),
        ("B", "T2", 50),
        ("C", "T1", 50),
        ("C", "T2", 20),
    ]
    rows: list[dict[str, object]] = []
    index = 0
    for senti, term, count in combos:
        for _ in range(count):
            rows.append(
                {
                    "utterance_id": f"u{index:04d}",
                    "text": f"texto {index}",
                    "date": pd.Timestamp("2020-01-01"),
                    "term": term,
                    "senti_3": senti,
                    "senti_6": f"{senti}-6",
                }
            )
            index += 1
    return pd.DataFrame(rows)


def test_build_sentiment_config_alineado_con_experimento_01() -> None:
    config = _sentiment_config()
    assert config.sample_size == 200
    assert config.strata == ("senti_3", "term")
    assert config.seed == 42
    assert config.bootstrap_n == 10000
    assert config.alpha == 0.05


def test_proportional_sample_determinista_y_proporcional() -> None:
    corpus = _validation_corpus()
    config = _sentiment_config()
    first = proportional_sample(corpus, config)
    second = proportional_sample(corpus, config)
    assert len(first) == config.sample_size
    assert first["utterance_id"].is_unique
    assert first["utterance_id"].tolist() == second["utterance_id"].tolist()
    assert list(first.columns) == ["utterance_id", "date", "term", "text"]

    joined = first.merge(corpus.loc[:, ["utterance_id", "senti_3"]], on="utterance_id")
    population_shares = pd.crosstab(corpus["senti_3"], corpus["term"], normalize="all")
    sample_shares = pd.crosstab(joined["senti_3"], joined["term"], normalize="all")
    difference = (sample_shares - population_shares).abs()
    assert float(difference.to_numpy().max()) < 0.01


def _validation_frames() -> tuple[pd.DataFrame, pd.DataFrame]:
    reference = pd.DataFrame(
        {
            "utterance_id": ["u1", "u2", "u3", "u4"],
            "senti_3": ["Positive", "Neutral", "Negative", "Negative"],
            "senti_6": ["Positive", "Neutral Negative", "Negative", "Mixed Negative"],
        }
    )
    annotations = pd.DataFrame(
        {
            "utterance_id": ["u1", "u2", "u3", "u4"],
            "senti_3_final": ["Positive", "Neutral", "Negative", "Neutral"],
            "senti_6_final": ["Positive", "Neutral Negative", "Negative", "Mixed Negative"],
            "model": ["asistente"] * 4,
            "prompt_version": ["v1"] * 4,
            "date": ["2026-09-14"] * 4,
            "reviewed_by": ["autor"] * 4,
        }
    )
    return annotations, reference


def test_evaluate_sentiment_calcula_accuracy_f1_y_confusion() -> None:
    annotations, reference = _validation_frames()
    report = evaluate_sentiment(annotations, reference)
    assert list(report.summary["nivel"]) == ["senti_3", "senti_6"]
    summary = report.summary.set_index("nivel")
    assert summary.loc["senti_3", "accuracy"] == 0.75
    assert summary.loc["senti_6", "accuracy"] == 1.0
    assert summary.loc["senti_6", "f1_macro"] == 1.0
    assert summary.loc["senti_6", "kappa_quadratic"] == 1.0
    assert report.confusions["senti_3"].loc["Negative", "Neutral"] == 1
    assert report.confusions["senti_3"].index.name == "real"
    assert report.confusions["senti_3"].columns.name == "anotado"
    assert list(report.confusions["senti_6"].index) == list(SENTI6_LABELS)
    assert len(report.per_class) == 3 + 6
    assert report.ic.empty


def test_evaluate_sentiment_falla_sin_columnas() -> None:
    annotations, reference = _validation_frames()
    with pytest.raises(ValueError, match="columnas"):
        evaluate_sentiment(annotations.drop(columns=["senti_3_final"]), reference)


def test_evaluate_sentiment_falla_con_ids_desconocidos() -> None:
    annotations, reference = _validation_frames()
    unknown = pd.DataFrame(
        {
            "utterance_id": ["u9"],
            "senti_3_final": ["Neutral"],
            "senti_6_final": ["Neutral"],
        }
    )
    with pytest.raises(ValueError, match="sin referencia"):
        evaluate_sentiment(pd.concat([annotations, unknown], ignore_index=True), reference)


def test_evaluate_sentiment_falla_con_etiqueta_fuera_de_taxonomia() -> None:
    annotations, reference = _validation_frames()
    broken = annotations.copy()
    broken.loc[0, "senti_3_final"] = "Positivo"
    with pytest.raises(ValueError, match="taxonom"):
        evaluate_sentiment(broken, reference)


def test_evaluate_sentiment_bootstrap_determinista() -> None:
    annotations, reference = _validation_frames()
    first = evaluate_sentiment(annotations, reference, n_boot=25, seed=7)
    second = evaluate_sentiment(annotations, reference, n_boot=25, seed=7)
    assert first.ic.equals(second.ic)
    assert not first.ic.empty
    usable = first.ic.dropna(subset=["ic_inf", "ic_sup"])
    assert (usable["ic_inf"] <= usable["ic_sup"]).all()


def test_write_revision_tables_escribe_artefactos(tmp_path: Path) -> None:
    annotations, reference = _validation_frames()
    report = evaluate_sentiment(annotations, reference)
    paths = write_revision_tables(report, tmp_path)
    names = {path.name for path in paths}
    assert names == {
        "validacion_sentimiento_revision_metricas.csv",
        "validacion_sentimiento_revision_por_clase.csv",
        "validacion_sentimiento_revision_ic.csv",
        "validacion_sentimiento_revision_confusion_senti_3.csv",
        "validacion_sentimiento_revision_confusion_senti_6.csv",
    }
    assert all(path.exists() for path in paths)


def test_reweighted_accuracy_por_probabilidad_inversa() -> None:
    y_true = ["A", "A", "B", "B"]
    y_pred = ["A", "B", "B", "B"]
    weighted = reweighted_accuracy(y_true, y_pred, {"A": 0.9, "B": 0.1})
    assert weighted == pytest.approx(2.2 / 4.0)
    assert weighted != pytest.approx(0.75)


def test_metricas_por_conteos_coinciden_con_sklearn() -> None:
    from src.nlp.sentiment import (
        _confusion_counts,  # pyright: ignore[reportPrivateUsage]
        _label_codes,  # pyright: ignore[reportPrivateUsage]
        _metrics,  # pyright: ignore[reportPrivateUsage]
        _metrics_from_counts,  # pyright: ignore[reportPrivateUsage]
    )

    labels = SENTI6_LABELS
    rng = np.random.default_rng(0)
    y_true = rng.choice(labels, size=120).tolist()
    y_pred = rng.choice(labels, size=120).tolist()
    prevalence = {label: 0.1 + 0.02 * index for index, label in enumerate(labels)}
    codes_true = _label_codes(y_true, labels)
    codes_pred = _label_codes(y_pred, labels)
    counts = _confusion_counts(codes_true, codes_pred, len(labels))
    prevalence_vector = np.asarray([prevalence[label] for label in labels], dtype=float)
    from_counts = _metrics_from_counts(counts, prevalence_vector)
    from_sklearn = _metrics(y_true, y_pred, labels, prevalence)
    for key, value in from_sklearn.items():
        assert from_counts[key] == pytest.approx(value, nan_ok=True), key


# ---------------------------------------------------------------------------
# Integración pesada (no se ejecuta en el portátil, D-30)
# ---------------------------------------------------------------------------


@pytest.mark.heavy
@heavy
def test_encoder_real_produce_vectores() -> None:
    from src.nlp.embeddings import load_encoder

    config = build_embedding_config(load_config(CONFIG_DIR / "experiment_01.yaml"))
    encode = load_encoder(config)
    vectors = embed_chunks(
        ["La economía crece.", "El empleo mejora."],
        encode,
        prefix=config.prefix,
        batch_size=2,
    )
    assert vectors.shape == (2, 1024)


@pytest.mark.heavy
@heavy
def test_coherence_c_v_real() -> None:
    economy = ["economía", "empleo", "inversión"]
    health = ["sanidad", "hospital", "vacuna"]
    texts: list[str] = []
    for index in range(20):
        base = economy if index % 2 == 0 else health
        texts.append(" ".join([*base, f"documento{index}"]))
    value = coherence_score([economy, health], tokenize_texts(texts), "c_v")
    assert np.isfinite(value)


@pytest.mark.heavy
@heavy
def test_bertopic_real_encuentra_topicos_sinteticos(tmp_path: Path) -> None:
    from dataclasses import replace

    from src.nlp.topic_model import evaluate_run, fit_topics

    bertopic_module = import_optional("bertopic")

    rng = np.random.default_rng(42)
    centers = rng.normal(size=(3, 16))
    vectors = np.vstack(
        [center + rng.normal(scale=0.05, size=(30, 16)) for center in centers]
    ).astype(np.float32)
    vectors /= np.linalg.norm(vectors, axis=1, keepdims=True)
    vocabulary = {
        0: ["economía", "empleo", "inversión"],
        1: ["sanidad", "hospital", "vacuna"],
        2: ["educación", "escuela", "profesorado"],
    }
    texts = [" ".join([*vocabulary[index // 30], f"documento{index}"]) for index in range(90)]
    # El c-TF-IDF ajusta el vectorizador sobre un documento por tópico: con
    # min_df=5 harían falta >=6 tópicos, así que la prueba relaja esos valores.
    config = replace(_topic_config(), min_df=1, max_df=1.0)
    model, topics, topic_words = fit_topics(
        texts,
        vectors,
        config,
        {"min_topic_size": 5, "n_neighbors": 5, "min_samples": 2},
    )
    assert model is not None
    metrics = evaluate_run(topics, topic_words, tokenize_texts(texts), config)
    assert metrics["n_topics"] >= 2
    assert metrics["outlier_rate"] < 0.5
    assert np.isfinite(metrics["diversity"])
    assert np.isfinite(metrics["coherence"])

    saved = tmp_path / "bertopic"
    model.save(
        str(saved), serialization="safetensors", save_embedding_model=False, save_ctfidf=True
    )
    loaded = bertopic_module.BERTopic.load(str(saved))
    assert len(loaded.get_topic_info()) == len(model.get_topic_info())
