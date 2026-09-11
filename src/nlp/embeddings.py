"""Embeddings de intervención para la Fase 3a.

El texto limpio se trocea en ventanas de tokens con solape y cada intervención se
representa con la media de los embeddings de sus ventanas, normalizada en L2. La
unidad de análisis sigue siendo la intervención (D-02) y el modelo es multilingüe
(D-22, D-24).

Los modelos pesados se cargan en tiempo de ejecución mediante ``import_optional``,
de modo que importar el módulo y ejecutar los tests unitarios no requiere torch ni
transformers (D-30).
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

import numpy as np
import numpy.typing as npt
import pandas as pd

from src.utils.config import PROJECT_ROOT, load_config
from src.utils.helpers import import_optional

Array = npt.NDArray[np.float64]
TokenizerFn = Callable[[str], list[int]]
DetokenizerFn = Callable[[Sequence[int]], str]
EncoderFn = Callable[[Sequence[str]], Array]

DEFAULT_MAX_TOKENS = 384
DEFAULT_STRIDE = 320
DEFAULT_MIN_TOKENS = 8

CHUNK_COLUMNS = ["utterance_id", "chunk_index", "text"]
EMBEDDING_COLUMNS = ["utterance_id", "embedding"]


@dataclass(frozen=True)
class EmbeddingConfig:
    """Parámetros de troceado y codificación."""

    model: str
    prefix: str = ""
    batch_size: int = 32
    device: str = "auto"
    max_tokens: int = DEFAULT_MAX_TOKENS
    stride: int = DEFAULT_STRIDE
    min_tokens: int = DEFAULT_MIN_TOKENS


def build_embedding_config(config: Mapping[str, Any]) -> EmbeddingConfig:
    """Construye la configuración de embeddings desde la sección ``embeddings``."""
    section = config["embeddings"]
    max_tokens = int(section.get("chunk_tokens", DEFAULT_MAX_TOKENS))
    stride = int(section.get("chunk_stride", DEFAULT_STRIDE))
    if stride >= max_tokens:
        raise ValueError("chunk_stride debe ser menor que chunk_tokens")
    return EmbeddingConfig(
        model=str(section["model"]),
        prefix=str(section.get("prefix", "")),
        batch_size=int(section.get("batch_size", 32)),
        device=str(section.get("device", "auto")),
        max_tokens=max_tokens,
        stride=stride,
        min_tokens=int(section.get("min_chunk_tokens", DEFAULT_MIN_TOKENS)),
    )


def token_windows(
    text: str,
    encode: TokenizerFn,
    decode: DetokenizerFn,
    *,
    max_tokens: int,
    stride: int,
    min_tokens: int,
) -> list[str]:
    """Divide el texto en ventanas de tokens con solape (D-23).

    Las posiciones de inicio y los tamaños se calculan vectorizados: se emiten
    ventanas completas cada ``stride`` tokens y se conserva la primera ventana
    que alcanza el final (puede ser parcial), descartando las colas redundantes.
    """
    token_ids = encode(text)
    total = len(token_ids)
    if total == 0:
        return []
    if total <= max_tokens:
        return [decode(token_ids)] if total >= min_tokens else []

    starts = np.arange(0, total, stride)
    last = int(np.searchsorted(starts + max_tokens, total, side="left"))
    starts = starts[: last + 1]
    sizes = np.minimum(total - starts, max_tokens)
    return [
        decode(token_ids[start : start + max_tokens])
        for start, size in zip(starts.tolist(), sizes.tolist(), strict=True)
        if size >= min_tokens
    ]


def chunk_interventions(
    frame: pd.DataFrame,
    config: EmbeddingConfig,
    *,
    encode: TokenizerFn,
    decode: DetokenizerFn,
) -> pd.DataFrame:
    """Trocea cada intervención en chunks, reiniciando el índice por intervención."""
    rows: list[dict[str, Any]] = []
    for utterance_id, text in zip(frame["utterance_id"], frame["text"].fillna(""), strict=True):
        windows = token_windows(
            str(text),
            encode,
            decode,
            max_tokens=config.max_tokens,
            stride=config.stride,
            min_tokens=config.min_tokens,
        )
        for index, window in enumerate(windows):
            rows.append({"utterance_id": utterance_id, "chunk_index": index, "text": window})
    return pd.DataFrame(rows, columns=CHUNK_COLUMNS)


def embed_chunks(
    texts: Sequence[str],
    encode: EncoderFn,
    *,
    prefix: str = "",
    batch_size: int = 32,
) -> Array:
    """Codifica los chunks por lotes, aplicando el prefijo que espera el modelo."""
    batches: list[Array] = []
    for start in range(0, len(texts), batch_size):
        batch = [f"{prefix}{text}" for text in texts[start : start + batch_size]]
        batches.append(np.asarray(encode(batch), dtype=np.float64))
    if not batches:
        return np.empty((0, 0), dtype=np.float64)
    return np.vstack(batches)


def aggregate_embeddings(vectors: Sequence[Array]) -> Array:
    """Media de vectores normalizados en L2, renormalizada."""
    if not vectors:
        raise ValueError("Se necesita al menos un vector para agregar")
    matrix = np.vstack([np.asarray(vector, dtype=np.float64) for vector in vectors])
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    norms[norms == 0.0] = 1.0
    normalized = matrix / norms
    mean = normalized.mean(axis=0)
    mean_norm = float(np.linalg.norm(mean))
    if mean_norm == 0.0:
        return mean
    return mean / mean_norm


def embed_interventions(
    chunks: pd.DataFrame,
    encode: EncoderFn,
    config: EmbeddingConfig,
) -> pd.DataFrame:
    """Representa cada intervención por la media normalizada de sus chunks."""
    if chunks.empty:
        return pd.DataFrame(columns=EMBEDDING_COLUMNS)
    texts = chunks["text"].astype(str).tolist()
    vectors = embed_chunks(texts, encode, prefix=config.prefix, batch_size=config.batch_size)
    indexed = chunks.reset_index(drop=True)
    rows: list[dict[str, Any]] = []
    for utterance_id, positions in indexed.groupby("utterance_id", sort=False).indices.items():
        rows.append(
            {
                "utterance_id": utterance_id,
                "embedding": aggregate_embeddings(list(vectors[positions])),
            }
        )
    return pd.DataFrame(rows, columns=EMBEDDING_COLUMNS)


def load_encoder(config: EmbeddingConfig) -> EncoderFn:
    """Carga ``sentence-transformers`` y devuelve la función de codificación."""
    module = import_optional("sentence_transformers")
    kwargs: dict[str, Any] = {}
    if config.device != "auto":
        kwargs["device"] = config.device
    model = module.SentenceTransformer(config.model, **kwargs)

    def encode(texts: Sequence[str]) -> Array:
        vectors = model.encode(list(texts), batch_size=config.batch_size)
        return np.asarray(vectors, dtype=np.float64)

    return encode


def load_tokenizer(config: EmbeddingConfig) -> tuple[TokenizerFn, DetokenizerFn]:
    """Carga el tokenizer del modelo para trocear por tokens."""
    module = import_optional("transformers")
    tokenizer = module.AutoTokenizer.from_pretrained(config.model)

    def tokenize(text: str) -> list[int]:
        token_ids = tokenizer.encode(text, add_special_tokens=False)
        return [int(token) for token in token_ids]

    def detokenize(ids: Sequence[int]) -> str:
        return str(tokenizer.decode(list(ids), skip_special_tokens=True))

    return tokenize, detokenize


def build_embeddings(
    frame: pd.DataFrame,
    config: EmbeddingConfig,
    *,
    tokenize: TokenizerFn | None = None,
    detokenize: DetokenizerFn | None = None,
    encode: EncoderFn | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Trocea y codifica el corpus; los dobles permiten testear sin modelos."""
    if (tokenize is None) != (detokenize is None):
        raise ValueError("tokenize y detokenize deben pasarse juntos")
    if tokenize is None or detokenize is None:
        tokenize, detokenize = load_tokenizer(config)
    if encode is None:
        encode = load_encoder(config)
    chunks = chunk_interventions(frame, config, encode=tokenize, decode=detokenize)
    embeddings = embed_interventions(chunks, encode, config)
    return chunks, embeddings


def main() -> None:
    """CLI: genera chunks y embeddings en ``data/intermediate``."""
    config = load_config()
    embedding_config = build_embedding_config(config)
    input_path = PROJECT_ROOT / "data" / "processed" / "intervenciones_limpias.parquet"
    output_dir = PROJECT_ROOT / "data" / "intermediate"
    frame = pd.read_parquet(input_path)
    chunks, embeddings = build_embeddings(frame, embedding_config)
    output_dir.mkdir(parents=True, exist_ok=True)
    chunks.to_parquet(output_dir / "chunks.parquet", index=False)
    embeddings.to_parquet(output_dir / "embeddings.parquet", index=False)
    print(f"{len(chunks)} chunks y {len(embeddings)} embeddings -> {output_dir}")


if __name__ == "__main__":
    main()
