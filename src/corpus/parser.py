"""Parseo del corpus ParlaMint-ES: metadatos, texto plano y sentimiento."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

MISSING = "-"

META_COLUMNS = [
    "Text_ID",
    "ID",
    "Title",
    "Date",
    "Body",
    "Term",
    "Session",
    "Meeting",
    "Sitting",
    "Agenda",
    "Subcorpus",
    "Lang",
    "Speaker_role",
    "Speaker_MP",
    "Speaker_minister",
    "Speaker_party",
    "Speaker_party_name",
    "Party_status",
    "Party_orientation",
    "Speaker_ID",
    "Speaker_name",
    "Speaker_gender",
    "Speaker_birth",
    "Topic",
]

ANA_META_COLUMNS = [
    "ID",
    "Parent_ID",
    "Element",
    "Language",
    "Senti_3",
    "Senti_6",
    "Senti_n",
    "Sents",
    "Words",
    "Tokens",
    "Names",
]

INTERVENTION_COLUMNS = [
    "utterance_id",
    "component_id",
    "date",
    "year",
    "month",
    "term",
    "session",
    "subcorpus",
    "speaker_role",
    "speaker_party",
    "speaker_party_name",
    "party_status",
    "party_orientation",
    "speaker_gender",
    "speaker_birth",
    "speaker_minister",
    "topic",
    "text",
    "senti_n_mean",
    "senti_3",
    "senti_6",
    "n_sents",
    "n_words",
    "n_tokens",
    "n_names",
]

_SENTIMENT_COLUMNS = [
    "senti_n_mean",
    "senti_3",
    "senti_6",
    "n_sents",
    "n_words",
    "n_tokens",
    "n_names",
]

_COUNT_COLUMNS = ["n_sents", "n_words", "n_tokens", "n_names"]

_RENAMES = {
    "ID": "utterance_id",
    "Text_ID": "component_id",
    "Date": "date",
    "Term": "term",
    "Session": "session",
    "Subcorpus": "subcorpus",
    "Speaker_role": "speaker_role",
    "Speaker_party": "speaker_party",
    "Speaker_party_name": "speaker_party_name",
    "Party_status": "party_status",
    "Party_orientation": "party_orientation",
    "Speaker_gender": "speaker_gender",
    "Speaker_birth": "speaker_birth",
    "Speaker_minister": "speaker_minister",
    "Topic": "topic",
}


def _read_tsv(path: Path) -> pd.DataFrame:
    """Lee un TSV como cadenas, trata ``-`` como NA y descarta columnas vacías."""
    frame = pd.read_csv(
        path,
        sep="\t",
        dtype=str,
        encoding="utf-8",
        keep_default_na=False,
        na_values=[MISSING],
    )
    unnamed = [column for column in frame.columns if str(column).startswith("Unnamed:")]
    return frame.drop(columns=unnamed)


def _require_columns(frame: pd.DataFrame, columns: list[str], path: Path) -> None:
    missing = [column for column in columns if column not in frame.columns]
    if missing:
        raise ValueError(f"Faltan columnas en {path.name}: {', '.join(missing)}")


def read_meta_tsv(path: Path) -> pd.DataFrame:
    """Lee el TSV de metadatos por intervención."""
    frame = _read_tsv(path)
    _require_columns(frame, META_COLUMNS, path)
    frame = frame.loc[:, META_COLUMNS].copy()
    frame["Date"] = pd.to_datetime(frame["Date"])
    return frame


def read_plain_text(path: Path) -> pd.DataFrame:
    """Lee el fichero ``.txt`` (``ID<TAB>texto`` por intervención)."""
    ids: list[str] = []
    texts: list[str] = []
    seen: set[str] = set()
    with path.open(encoding="utf-8") as handle:
        for number, raw_line in enumerate(handle, start=1):
            line = raw_line.rstrip("\r\n")
            if not line.strip():
                continue
            parts = line.split("\t", 1)
            if len(parts) != 2:
                raise ValueError(f"Línea {number} sin tabulador en {path.name}")
            utterance_id, text = parts
            if utterance_id in seen:
                raise ValueError(f"ID duplicado en {path.name}: {utterance_id}")
            seen.add(utterance_id)
            ids.append(utterance_id)
            texts.append(text.strip())
    return pd.DataFrame({"ID": ids, "text": texts})


def read_ana_meta(path: Path) -> pd.DataFrame:
    """Lee el TSV de anotación y normaliza ``Senti_n`` a numérico."""
    frame = _read_tsv(path)
    _require_columns(frame, ANA_META_COLUMNS, path)
    frame = frame.loc[:, ANA_META_COLUMNS].copy()
    frame["Senti_n"] = pd.to_numeric(frame["Senti_n"])
    return frame


def _majority(values: pd.Series[Any]) -> str | None:
    modes = values.dropna().mode()
    if modes.empty:
        return None
    return str(modes.iloc[0])


def aggregate_sentiment(ana_meta: pd.DataFrame) -> pd.DataFrame:
    """Agrega el sentimiento por frase al nivel de intervención.

    ``senti_n_mean`` es la media de las frases, ``senti_3`` y ``senti_6`` la clase
    mayoritaria, y los conteos se toman de las filas ``u`` del corpus anotado.
    """
    sentences = ana_meta.loc[ana_meta["Element"] == "s", :]
    utterances = ana_meta.loc[ana_meta["Element"] == "u", :]

    grouped = sentences.groupby("Parent_ID", sort=False)
    sentiment = pd.DataFrame(
        {
            "senti_n_mean": grouped["Senti_n"].mean(),
            "senti_3": grouped["Senti_3"].agg(_majority),
            "senti_6": grouped["Senti_6"].agg(_majority),
        }
    )

    counts = utterances.assign(
        n_sents=pd.to_numeric(utterances["Sents"]),
        n_words=pd.to_numeric(utterances["Words"]),
        n_tokens=pd.to_numeric(utterances["Tokens"]),
        n_names=pd.to_numeric(utterances["Names"]),
    ).set_index("ID")

    result = counts.loc[:, _COUNT_COLUMNS].join(sentiment, how="left")
    for column in _COUNT_COLUMNS:
        result[column] = result[column].fillna(0).astype("int64")
    result = result.loc[:, _SENTIMENT_COLUMNS]
    return result.reset_index()


def build_interventions(
    meta: pd.DataFrame,
    text: pd.DataFrame,
    sentiment: pd.DataFrame,
) -> pd.DataFrame:
    """Consolida metadatos, texto y sentimiento en una tabla por intervención."""
    ids_meta = set(meta["ID"])
    ids_text = set(text["ID"])
    sin_texto = ids_meta - ids_text
    if sin_texto:
        raise ValueError(
            f"{len(sin_texto)} intervenciones sin texto, p. ej. {sorted(sin_texto)[0]}"
        )
    sin_metadatos = ids_text - ids_meta
    if sin_metadatos:
        raise ValueError(
            f"{len(sin_metadatos)} textos sin metadatos, p. ej. {sorted(sin_metadatos)[0]}"
        )

    frame = meta.merge(text, on="ID", how="left", validate="one_to_one")
    frame = frame.merge(sentiment, on="ID", how="left", validate="one_to_one")
    frame = frame.rename(columns=_RENAMES)
    frame["speaker_birth"] = pd.to_datetime(frame["speaker_birth"], errors="coerce", format="mixed")
    frame["year"] = frame["date"].dt.year.astype("int64")
    frame["month"] = frame["date"].dt.month.astype("int64")
    frame["senti_n_mean"] = pd.to_numeric(frame["senti_n_mean"], errors="coerce").astype("float64")
    for column in _COUNT_COLUMNS:
        frame[column] = frame[column].fillna(0).astype("int64")
    return frame.loc[:, INTERVENTION_COLUMNS].copy()


def find_component_bases(raw_dir: Path) -> list[Path]:
    """Devuelve la ruta base (sin extensión) de cada componente con metadatos."""
    bases: list[Path] = []
    for meta_path in sorted(raw_dir.rglob("*-meta.tsv")):
        if meta_path.name.endswith("-ana-meta.tsv"):
            continue
        bases.append(meta_path.with_name(meta_path.name[: -len("-meta.tsv")]))
    return bases


def _empty_sentiment() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "ID": pd.Series(dtype="object"),
            "senti_n_mean": pd.Series(dtype="float64"),
            "senti_3": pd.Series(dtype="object"),
            "senti_6": pd.Series(dtype="object"),
            "n_sents": pd.Series(dtype="int64"),
            "n_words": pd.Series(dtype="int64"),
            "n_tokens": pd.Series(dtype="int64"),
            "n_names": pd.Series(dtype="int64"),
        }
    )


def build_corpus(raw_dir: Path, output_path: Path) -> pd.DataFrame:
    """Construye la tabla consolidada de todo el corpus y la guarda en parquet."""
    frames: list[pd.DataFrame] = []
    for base in find_component_bases(raw_dir):
        meta = read_meta_tsv(base.with_name(base.name + "-meta.tsv"))
        text = read_plain_text(base.with_name(base.name + ".txt"))
        ana_path = base.with_name(base.name + "-ana-meta.tsv")
        sentiment = (
            aggregate_sentiment(read_ana_meta(ana_path))
            if ana_path.exists()
            else _empty_sentiment()
        )
        frames.append(build_interventions(meta, text, sentiment))
    if not frames:
        raise ValueError(f"No se han encontrado componentes en {raw_dir}")
    corpus = pd.concat(frames, ignore_index=True)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    corpus.to_parquet(output_path, index=False)
    return corpus
