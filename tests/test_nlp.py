"""Tests de la Fase 3a: representación y embeddings.

Los tests unitarios no descargan ni ejecutan modelos: usan tokenizadores y
codificadores falsos. Los tests marcados ``heavy`` sí requieren los modelos
reales y se saltan salvo que se defina ``HEMICICLO_HEAVY=1`` (D-30).
"""

from __future__ import annotations

import os
from collections.abc import Sequence

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
