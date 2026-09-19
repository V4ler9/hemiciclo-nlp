"""Modelado de tópicos con BERTopic para la Fase 3a.

Rejilla de hiperparámetros sobre los embeddings de intervención (UMAP →
HDBSCAN → c-TF-IDF), evaluación con coherencia c_v (gensim) y diversidad,
selección de granularidad según D-32 y exportación de la evidencia para el
etiquetado asistido (D-25).

Los outliers (tópico ``-1``) se conservan en las asignaciones, se excluyen de
las cuotas de la Fase 3b y su tasa se reporta (D-28). La regla de selección
descarta combinaciones con más de un 40 % de outliers o fuera del rango
[20, 60] tópicos, y elige el máximo c_v desempatando por diversidad; los
umbrales viven en ``configs/experiment_01.yaml``.

Las dependencias pesadas (bertopic, umap, hdbscan, gensim y sklearn) se cargan
en tiempo de ejecución con ``import_optional``: importar el módulo no las
exige (D-30).
"""

from __future__ import annotations

import argparse
import gc
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

import numpy as np
import numpy.typing as npt
import pandas as pd

from src.nlp.embeddings import output_paths as embedding_output_paths
from src.utils.config import CONFIG_DIR, PROJECT_ROOT, SEED, load_config
from src.utils.helpers import import_optional

OUTLIER_TOPIC = -1
DEFAULT_COHERENCE = "c_v"

GRID_PARAMS = ("min_topic_size", "n_neighbors", "min_samples")

ASSIGNMENT_COLUMNS = ["utterance_id", "bertopic_topic", "is_outlier"]
EVIDENCE_COLUMNS = [
    "topic",
    "size",
    "share",
    "top_terms",
    "representative_utterance_ids",
    "representative_texts",
]
SELECTION_COLUMNS = [
    "min_topic_size",
    "n_neighbors",
    "min_samples",
    "n_topics",
    "outlier_rate",
    "coherence",
    "diversity",
    "selected",
]
SENSITIVITY_FILENAME = "sensibilidad_embeddings.csv"
SENSITIVITY_COLUMNS = [
    "modelo",
    "n_topicos",
    "outlier_rate",
    "coherencia_cv",
    "diversidad",
    "ari_vs_e5",
    "nmi_vs_e5",
    "n_comparables",
]

TopicsArray = npt.NDArray[np.int64]
EmbeddingMatrix = npt.NDArray[np.float32]


@dataclass(frozen=True)
class TopicConfig:
    """Parámetros de la rejilla, la evaluación y la selección de tópicos."""

    language: str
    min_topic_size: tuple[int, ...]
    n_neighbors: tuple[int, ...]
    n_components: int
    min_dist: float
    metric: str
    min_samples: tuple[int, ...]
    ngram_range: tuple[int, int]
    min_df: int
    max_df: float
    top_n_words: int
    coherence: str
    diversity_top_n: int
    representative_docs: int
    outlier_strategy: str
    max_outlier_rate: float
    min_topics: int
    max_topics: int
    seed: int


def _as_int_tuple(value: Any, field: str) -> tuple[int, ...]:
    if isinstance(value, int):
        return (value,)
    try:
        return tuple(int(item) for item in value)
    except TypeError as exc:
        raise ValueError(f"{field} debe ser un entero o una lista de enteros") from exc


def build_topic_config(config: Mapping[str, Any]) -> TopicConfig:
    """Construye la configuración de tópicos desde la sección ``topics``."""
    section = config["topics"]
    selection = section.get("selection", {})
    ngram_low, ngram_high = (int(item) for item in section.get("ngram_range", (1, 2)))
    topic_config = TopicConfig(
        language=str(section.get("language", "multilingual")),
        min_topic_size=_as_int_tuple(section.get("min_topic_size", 15), "min_topic_size"),
        n_neighbors=_as_int_tuple(section.get("n_neighbors", 15), "n_neighbors"),
        n_components=int(section.get("n_components", 5)),
        min_dist=float(section.get("min_dist", 0.0)),
        metric=str(section.get("metric", "cosine")),
        min_samples=_as_int_tuple(section.get("min_samples", 5), "min_samples"),
        ngram_range=(ngram_low, ngram_high),
        min_df=int(section.get("min_df", 5)),
        max_df=float(section.get("max_df", 0.9)),
        top_n_words=int(section.get("top_n_words", 10)),
        coherence=str(section.get("coherence", DEFAULT_COHERENCE)),
        diversity_top_n=int(section.get("diversity_top_n", 10)),
        representative_docs=int(section.get("representative_docs", 8)),
        outlier_strategy=str(section.get("outlier_strategy", "exclude")),
        max_outlier_rate=float(selection.get("max_outlier_rate", 0.4)),
        min_topics=int(selection.get("min_topics", 20)),
        max_topics=int(selection.get("max_topics", 60)),
        seed=int(config.get("seed", SEED)),
    )
    if topic_config.outlier_strategy != "exclude":
        raise ValueError(
            "Solo se implementa la estrategia de outliers 'exclude' (D-28): "
            f"se recibió {topic_config.outlier_strategy!r}"
        )
    return topic_config


def grid_combinations(config: TopicConfig) -> list[dict[str, int]]:
    """Producto cartesiano de la rejilla: tamaño mínimo, vecinos y min_samples."""
    return [
        {"min_topic_size": size, "n_neighbors": neighbors, "min_samples": samples}
        for size in config.min_topic_size
        for neighbors in config.n_neighbors
        for samples in config.min_samples
    ]


def build_topic_model(config: TopicConfig, params: Mapping[str, int]) -> Any:
    """Construye un BERTopic con UMAP, HDBSCAN y c-TF-IDF (requiere extras ``nlp``)."""
    bertopic_module = import_optional("bertopic")
    umap_module = import_optional("umap")
    hdbscan_module = import_optional("hdbscan")
    text_module = import_optional("sklearn.feature_extraction.text")

    umap_model = umap_module.UMAP(
        n_neighbors=int(params["n_neighbors"]),
        n_components=config.n_components,
        min_dist=config.min_dist,
        metric=config.metric,
        random_state=config.seed,
    )
    hdbscan_model = hdbscan_module.HDBSCAN(
        min_cluster_size=int(params["min_topic_size"]),
        min_samples=int(params["min_samples"]),
        metric="euclidean",
        cluster_selection_method="eom",
        prediction_data=True,
    )
    vectorizer = text_module.CountVectorizer(
        ngram_range=config.ngram_range,
        min_df=config.min_df,
        max_df=config.max_df,
    )
    return bertopic_module.BERTopic(
        top_n_words=config.top_n_words,
        umap_model=umap_model,
        hdbscan_model=hdbscan_model,
        vectorizer_model=vectorizer,
    )


def _topic_words(model: Any, topic: int) -> list[str]:
    representation: Any = model.get_topic(topic)
    if isinstance(representation, Mapping):
        mapping = cast(Mapping[str, Any], representation)
        return [str(key) for key in mapping]
    if not representation:
        return []
    entries: list[Any] = list(representation)
    return [str(entry[0]) for entry in entries]


def fit_topics(
    texts: Sequence[str],
    embeddings: EmbeddingMatrix,
    config: TopicConfig,
    params: Mapping[str, int],
) -> tuple[Any, TopicsArray, dict[int, list[str]]]:
    """Ajusta BERTopic a una combinación y devuelve modelo, tópicos y palabras."""
    model = build_topic_model(config, params)
    topics, _ = model.fit_transform(list(texts), embeddings)
    topics_array = np.asarray(topics, dtype=np.int64)
    topic_words: dict[int, list[str]] = {}
    for topic in sorted(int(value) for value in np.unique(topics_array)):
        if topic == OUTLIER_TOPIC:
            continue
        topic_words[topic] = _topic_words(model, topic)
    return model, topics_array, topic_words


def collect_representative_docs(model: Any, topics: Sequence[int]) -> dict[int, list[str]]:
    """Documentos representativos por tópico para la evidencia de etiquetado."""
    return {
        int(topic): [str(document) for document in model.get_representative_docs(int(topic))]
        for topic in topics
    }


def tokenize_texts(texts: Sequence[str]) -> list[list[str]]:
    """Tokenización mínima (minúsculas y espacios) para la coherencia."""
    return [str(text).lower().split() for text in texts]


def outlier_rate(topics: npt.ArrayLike) -> float:
    """Proporción de intervenciones asignadas al tópico de outliers."""
    values = np.asarray(topics, dtype=np.int64)
    if values.size == 0:
        return float("nan")
    return int(np.count_nonzero(values == OUTLIER_TOPIC)) / values.size


def topic_count(topics: npt.ArrayLike) -> int:
    """Número de tópicos distintos excluyendo los outliers."""
    values = np.asarray(topics)
    return int(np.unique(values[values != OUTLIER_TOPIC]).size)


def diversity_score(topic_words: Sequence[Sequence[str]], top_n: int) -> float:
    """Proporción de palabras únicas en el top-n de cada tópico (tipo OCTIS)."""
    selected = [word for words in topic_words for word in list(words)[:top_n]]
    if not selected:
        return float("nan")
    return len(set(selected)) / len(selected)


def _unigram_words(words: Sequence[str]) -> list[str]:
    """Descarta bigramas: gensim evalúa coherencia a nivel de palabra."""
    return [word for word in words if " " not in word]


def build_dictionary(tokenized_texts: Sequence[Sequence[str]]) -> Any:
    """Diccionario de gensim sobre el corpus tokenizado, reutilizable en la rejilla."""
    gensim_corpora = import_optional("gensim.corpora")
    return gensim_corpora.Dictionary([list(text) for text in tokenized_texts])


def coherence_score(
    topic_words: Sequence[Sequence[str]],
    tokenized_texts: Sequence[Sequence[str]],
    metric: str = DEFAULT_COHERENCE,
    dictionary: Any | None = None,
) -> float:
    """Coherencia de los tópicos según gensim (parte del extra ``nlp``).

    Los bigramas del c-TF-IDF se excluyen porque el léxico de gensim es de
    palabras sueltas; si ningún tópico conserva al menos dos palabras, la
    métrica es ``nan``. gensim 4 exige un diccionario cuando se pasan
    ``topics``; conviene construirlo una vez con ``build_dictionary`` y
    reutilizarlo en toda la rejilla.
    """
    filtered = [_unigram_words(list(words)) for words in topic_words]
    filtered = [words for words in filtered if len(words) >= 2]
    if not filtered or not tokenized_texts:
        return float("nan")
    if dictionary is None:
        dictionary = build_dictionary(tokenized_texts)
    gensim_models = import_optional("gensim.models")
    model = gensim_models.CoherenceModel(
        topics=filtered,
        texts=[list(text) for text in tokenized_texts],
        dictionary=dictionary,
        coherence=metric,
        processes=1,
    )
    return float(model.get_coherence())


def evaluate_run(
    topics: npt.ArrayLike,
    topic_words: Mapping[int, Sequence[str]],
    tokenized_texts: Sequence[Sequence[str]],
    config: TopicConfig,
    dictionary: Any | None = None,
) -> dict[str, float | int]:
    """Métricas de una combinación: tópicos, outliers, coherencia y diversidad."""
    words = list(topic_words.values())
    coherence = coherence_score(words, tokenized_texts, config.coherence, dictionary)
    return {
        "n_topics": topic_count(topics),
        "outlier_rate": round(outlier_rate(topics), 4),
        "coherence": round(coherence, 6),
        "diversity": round(diversity_score(words, config.diversity_top_n), 6),
    }


def select_best_run(results: pd.DataFrame, config: TopicConfig) -> dict[str, Any]:
    """Aplica los filtros de D-32 y devuelve la combinación con mayor c_v."""
    candidates = results.loc[
        results["n_topics"].between(config.min_topics, config.max_topics)
        & (results["outlier_rate"] <= config.max_outlier_rate)
        & results["coherence"].notna()
    ]
    if candidates.empty:
        raise ValueError(
            "Ninguna combinación de la rejilla cumple los filtros de D-32: "
            f"outliers <= {config.max_outlier_rate}, tópicos en "
            f"[{config.min_topics}, {config.max_topics}] y coherencia finita"
        )
    ordered = candidates.sort_values(
        by=["coherence", "diversity"], ascending=[False, False], kind="stable"
    )
    return dict(ordered.iloc[0])


def build_assignments(utterance_ids: Sequence[str], topics: npt.ArrayLike) -> pd.DataFrame:
    """Tabla por intervención con el tópico BERTopic y la marca de outlier."""
    frame = pd.DataFrame(
        {
            "utterance_id": list(utterance_ids),
            "bertopic_topic": np.asarray(topics, dtype=np.int64),
        }
    )
    frame["is_outlier"] = frame["bertopic_topic"] == OUTLIER_TOPIC
    return frame.loc[:, ASSIGNMENT_COLUMNS]


def build_evidence(
    utterance_ids: Sequence[str],
    texts: Sequence[str],
    topics: npt.ArrayLike,
    topic_words: Mapping[int, Sequence[str]],
    representative_docs: Mapping[int, Sequence[str]],
) -> pd.DataFrame:
    """Evidencia por tópico para el etiquetado asistido (D-25)."""
    text_to_id: dict[str, str] = {}
    for utterance_id, text in zip(utterance_ids, texts, strict=True):
        text_to_id.setdefault(str(text), str(utterance_id))
    values = np.asarray(topics)
    total = int(values.size)
    rows: list[dict[str, Any]] = []
    for topic in sorted(int(value) for value in np.unique(values)):
        if topic == OUTLIER_TOPIC:
            continue
        size = int(np.count_nonzero(values == topic))
        documents = [str(document) for document in representative_docs.get(topic, [])]
        rows.append(
            {
                "topic": topic,
                "size": size,
                "share": round(size / total, 6) if total else float("nan"),
                "top_terms": "; ".join(str(word) for word in topic_words.get(topic, [])),
                "representative_utterance_ids": "; ".join(
                    text_to_id.get(document, "") for document in documents
                ),
                "representative_texts": " || ".join(documents),
            }
        )
    return pd.DataFrame(rows, columns=EVIDENCE_COLUMNS)


def _grid_key(values: Mapping[str, Any]) -> tuple[int, int, int]:
    return (
        int(values["min_topic_size"]),
        int(values["n_neighbors"]),
        int(values["min_samples"]),
    )


def _load_previous_results(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    frame = pd.read_csv(path)
    records: list[dict[str, Any]] = []
    for row in frame.to_dict(orient="records"):
        record = {str(key): value for key, value in row.items()}
        for key in GRID_PARAMS:
            if key in record:
                record[key] = int(record[key])
        records.append(record)
    return records


def _load_inputs(embeddings_path: Path) -> tuple[pd.DataFrame, list[str], EmbeddingMatrix]:
    embeddings = pd.read_parquet(embeddings_path)
    corpus = pd.read_parquet(PROJECT_ROOT / "data" / "processed" / "intervenciones_limpias.parquet")
    merged = embeddings.merge(
        corpus.loc[:, ["utterance_id", "text"]],
        on="utterance_id",
        how="left",
        validate="one_to_one",
    )
    if merged["text"].isna().any() or merged["embedding"].isna().any():
        raise ValueError("Hay intervenciones sin texto o sin embedding; revisa fases previas")
    texts = merged["text"].astype(str).tolist()
    matrix = np.vstack([np.asarray(vector, dtype=np.float32) for vector in merged["embedding"]])
    return merged, texts, matrix


def topic_output_paths(config_stem: str) -> dict[str, Path]:
    """Rutas de los artefactos del modelado; la config principal conserva nombres."""
    suffix = "" if config_stem == "experiment_01" else f"_{config_stem}"
    model_name = (
        "bertopic_experiment_01" if config_stem == "experiment_01" else f"bertopic_{config_stem}"
    )
    return {
        "selection": PROJECT_ROOT / "reports" / "tables" / f"topics_selection{suffix}.csv",
        "assignments": PROJECT_ROOT
        / "data"
        / "processed"
        / f"intervenciones_topicos{suffix}.parquet",
        "evidence": PROJECT_ROOT / "reports" / "tables" / f"topics_evidence{suffix}.csv",
        "model": PROJECT_ROOT / "models" / model_name,
    }


def agreement_scores(left: npt.ArrayLike, right: npt.ArrayLike) -> tuple[float, float]:
    """ARI y NMI entre dos asignaciones de tópicos (anexo de sensibilidad)."""
    metrics = import_optional("sklearn.metrics")
    return (
        float(metrics.adjusted_rand_score(left, right)),
        float(metrics.normalized_mutual_info_score(left, right)),
    )


def run_grid(config_path: Path) -> None:
    """Rejilla de BERTopic, selección (D-32) y artefactos de la Fase 3a."""
    raw_config = load_config(config_path)
    config = build_topic_config(raw_config)
    merged, texts, matrix = _load_inputs(embedding_output_paths(config_path)[1])
    tokenized = tokenize_texts(texts)
    dictionary = build_dictionary(tokenized)

    grid = grid_combinations(config)
    paths = topic_output_paths(config_path.stem)
    selection_path = paths["selection"]
    selection_path.parent.mkdir(parents=True, exist_ok=True)
    results: list[dict[str, Any]] = _load_previous_results(selection_path)
    completed = {_grid_key(row) for row in results}
    for index, params in enumerate(grid, start=1):
        if _grid_key(params) in completed:
            print(f"[{index}/{len(grid)}] {params} -> ya evaluado, se omite", flush=True)
            continue
        started = time.perf_counter()
        model, topics, topic_words = fit_topics(texts, matrix, config, params)
        metrics = evaluate_run(topics, topic_words, tokenized, config, dictionary)
        results.append({**params, **metrics})
        elapsed = time.perf_counter() - started
        print(f"[{index}/{len(grid)}] {params} -> {metrics} ({elapsed:.0f}s)", flush=True)
        pd.DataFrame(results, columns=SELECTION_COLUMNS[:-1]).to_csv(selection_path, index=False)
        del model
        gc.collect()

    selection = pd.DataFrame(results, columns=SELECTION_COLUMNS[:-1])
    best = select_best_run(selection, config)
    is_best = np.ones(len(selection), dtype=bool)
    for key in GRID_PARAMS:
        is_best &= selection[key].to_numpy() == int(best[key])
    selection["selected"] = is_best
    selection.to_csv(selection_path, index=False)
    print(f"Rejilla -> {selection_path}")
    print(f"Combinación seleccionada: { {key: int(best[key]) for key in GRID_PARAMS} }")

    model, topics, topic_words = fit_topics(
        texts, matrix, config, {key: int(best[key]) for key in GRID_PARAMS}
    )
    utterance_ids = merged["utterance_id"].tolist()
    assignments = build_assignments(utterance_ids, topics)
    evidence = build_evidence(
        utterance_ids,
        texts,
        topics,
        topic_words,
        collect_representative_docs(model, list(topic_words)),
    )

    assignments_path = paths["assignments"]
    assignments_path.parent.mkdir(parents=True, exist_ok=True)
    assignments.to_parquet(assignments_path, index=False)
    evidence_path = paths["evidence"]
    evidence_path.parent.mkdir(parents=True, exist_ok=True)
    evidence.to_csv(evidence_path, index=False)
    model_dir = paths["model"]
    model.save(
        str(model_dir),
        serialization="safetensors",
        save_embedding_model=str(raw_config["embeddings"]["model"]),
        save_ctfidf=True,
    )
    print(
        f"{len(assignments)} asignaciones ({int(assignments['is_outlier'].sum())} outliers), "
        f"{len(evidence)} tópicos -> {assignments_path} | modelo: {model_dir}\n"
        f"Evidencia -> {evidence_path}"
    )


def sensitivity_main() -> None:
    """Anexo de sensibilidad (D-24): bge-m3 con el troceado y la granularidad del principal."""
    e5_config_path = CONFIG_DIR / "experiment_01.yaml"
    bge_config_path = CONFIG_DIR / "experiment_02.yaml"
    e5_paths = topic_output_paths(e5_config_path.stem)
    selection = pd.read_csv(e5_paths["selection"])
    selected = selection.loc[selection["selected"]]
    if selected.empty:
        raise ValueError("La rejilla principal no tiene combinación seleccionada")
    best = selected.iloc[0]
    params = {key: int(best[key]) for key in GRID_PARAMS}
    e5_assignments = pd.read_parquet(e5_paths["assignments"])

    bge_embeddings_path = embedding_output_paths(bge_config_path)[1]
    bge_config = build_topic_config(load_config(bge_config_path))
    merged, texts, matrix = _load_inputs(bge_embeddings_path)
    tokenized = tokenize_texts(texts)
    dictionary = build_dictionary(tokenized)
    model, topics, topic_words = fit_topics(texts, matrix, bge_config, params)
    metrics = evaluate_run(topics, topic_words, tokenized, bge_config, dictionary)
    del model
    gc.collect()

    joined = pd.DataFrame({"utterance_id": merged["utterance_id"], "topic_bge": topics}).merge(
        e5_assignments, on="utterance_id", how="left", validate="one_to_one"
    )
    mask = (~joined["is_outlier"].astype(bool)) & (joined["topic_bge"] != OUTLIER_TOPIC)
    ari, nmi = agreement_scores(
        joined.loc[mask, "bertopic_topic"].to_numpy(),
        joined.loc[mask, "topic_bge"].to_numpy(),
    )
    table = pd.DataFrame(
        [
            {
                "modelo": "multilingual-e5-large",
                "n_topicos": int(best["n_topics"]),
                "outlier_rate": float(best["outlier_rate"]),
                "coherencia_cv": float(best["coherence"]),
                "diversidad": float(best["diversity"]),
                "ari_vs_e5": 1.0,
                "nmi_vs_e5": 1.0,
                "n_comparables": int(mask.sum()),
            },
            {
                "modelo": "bge-m3",
                "n_topicos": int(metrics["n_topics"]),
                "outlier_rate": float(metrics["outlier_rate"]),
                "coherencia_cv": float(metrics["coherence"]),
                "diversidad": float(metrics["diversity"]),
                "ari_vs_e5": round(ari, 6),
                "nmi_vs_e5": round(nmi, 6),
                "n_comparables": int(mask.sum()),
            },
        ],
        columns=SENSITIVITY_COLUMNS,
    )
    output_path = PROJECT_ROOT / "reports" / "tables" / SENSITIVITY_FILENAME
    output_path.parent.mkdir(parents=True, exist_ok=True)
    table.to_csv(output_path, index=False)
    print(table.to_string(index=False))
    print(f"escrito: {output_path}")


def main() -> None:
    """CLI: rejilla de tópicos (``--config``) o anexo de sensibilidad (``--sensitivity``)."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=CONFIG_DIR / "experiment_01.yaml")
    parser.add_argument("--sensitivity", action="store_true", help="anexo bge-m3 de D-24")
    args = parser.parse_args()
    if args.sensitivity:
        sensitivity_main()
        return
    run_grid(args.config)


if __name__ == "__main__":
    main()
