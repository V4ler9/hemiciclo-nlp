"""Parseo del corpus: ParlaMint-ES (texto y metadatos) + ParlaCAP (anotaciones)."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.utils.config import PROJECT_ROOT

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

PARLACAP_COLUMNS = [
    "id",
    "date",
    "lang_code",
    "lang",
    "vdem_country_id",
    "speaker_role",
    "speaker_MP",
    "speaker_minister",
    "speaker_party",
    "speaker_party_name",
    "party_status",
    "party_orientation",
    "partyfacts_id",
    "speaker_id",
    "speaker_name",
    "speaker_gender",
    "speaker_birth",
    "word_count",
    "CAP_category",
    "CAP_prob",
    "sent_logit",
    "sent3_category",
    "sent6_category",
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
    "topic_prob",
    "text",
    "senti_n",
    "senti_3",
    "senti_6",
    "n_words",
]

_META_RENAMES = {
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
}

_PARLACAP_RENAMES = {
    "id": "utterance_id",
    "sent_logit": "senti_n",
    "sent3_category": "senti_3",
    "sent6_category": "senti_6",
    "CAP_category": "topic",
    "CAP_prob": "topic_prob",
    "word_count": "n_words",
}

_ANNOTATION_COLUMNS = ["senti_n", "senti_3", "senti_6", "topic", "topic_prob", "n_words"]


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
    """Lee el TSV de metadatos por intervención de ParlaMint-ES."""
    frame = _read_tsv(path)
    _require_columns(frame, META_COLUMNS, path)
    frame = frame.loc[:, META_COLUMNS].copy()
    frame["Date"] = pd.to_datetime(frame["Date"])
    return frame


def read_plain_text(path: Path) -> pd.DataFrame:
    """Lee el fichero ``.txt`` de ParlaMint (``ID<TAB>texto`` por intervención)."""
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


def read_parlacap_speeches(path: Path) -> pd.DataFrame:
    """Lee el TSV de ParlaCAP a nivel de discurso (sentimiento y tópico)."""
    frame = _read_tsv(path)
    _require_columns(frame, PARLACAP_COLUMNS, path)
    frame = frame.loc[:, PARLACAP_COLUMNS].copy()
    frame["date"] = pd.to_datetime(frame["date"])
    frame["CAP_prob"] = pd.to_numeric(frame["CAP_prob"])
    frame["sent_logit"] = pd.to_numeric(frame["sent_logit"])
    frame["word_count"] = pd.to_numeric(frame["word_count"]).astype("Int64")
    return frame


def build_interventions(
    meta: pd.DataFrame,
    text: pd.DataFrame,
    parlacap: pd.DataFrame,
) -> pd.DataFrame:
    """Consolida metadatos, texto y anotaciones en una tabla por intervención."""
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

    text_frame = text.rename(columns={"ID": "utterance_id"})
    annotations = parlacap.rename(columns=_PARLACAP_RENAMES).loc[
        :, ["utterance_id", *_ANNOTATION_COLUMNS]
    ]
    annotations = annotations.loc[annotations["utterance_id"].isin(ids_meta), :]
    frame = meta.rename(columns=_META_RENAMES)
    frame = frame.merge(text_frame, on="utterance_id", how="left", validate="one_to_one")
    frame = frame.merge(annotations, on="utterance_id", how="left", validate="one_to_one")

    frame["speaker_birth"] = pd.to_datetime(frame["speaker_birth"], errors="coerce", format="mixed")
    frame["year"] = frame["date"].dt.year.astype("int64")
    frame["month"] = frame["date"].dt.month.astype("int64")
    frame["senti_n"] = pd.to_numeric(frame["senti_n"], errors="coerce").astype("float64")
    frame["topic_prob"] = pd.to_numeric(frame["topic_prob"], errors="coerce").astype("float64")
    frame["n_words"] = pd.to_numeric(frame["n_words"], errors="coerce").astype("Int64")
    return frame.loc[:, INTERVENTION_COLUMNS].copy()


def find_component_bases(raw_dir: Path) -> list[Path]:
    """Devuelve la ruta base (sin extensión) de cada componente con metadatos."""
    bases: list[Path] = []
    for meta_path in sorted(raw_dir.rglob("*-meta.tsv")):
        if meta_path.name.endswith("-ana-meta.tsv"):
            continue
        bases.append(meta_path.with_name(meta_path.name[: -len("-meta.tsv")]))
    return bases


def build_corpus(raw_dir: Path, parlacap_path: Path, output_path: Path) -> pd.DataFrame:
    """Construye la tabla consolidada del corpus y la guarda en parquet."""
    parlacap = read_parlacap_speeches(parlacap_path)
    frames: list[pd.DataFrame] = []
    for base in find_component_bases(raw_dir):
        meta = read_meta_tsv(base.with_name(base.name + "-meta.tsv"))
        text = read_plain_text(base.with_name(base.name + ".txt"))
        frames.append(build_interventions(meta, text, parlacap))
    if not frames:
        raise ValueError(f"No se han encontrado componentes en {raw_dir}")
    corpus = pd.concat(frames, ignore_index=True)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    corpus.to_parquet(output_path, index=False)
    return corpus


def main() -> None:
    """CLI: construye ``data/processed/intervenciones.parquet`` desde ``data/raw``."""
    raw_dir = PROJECT_ROOT / "data" / "raw" / "corpus" / "ParlaMint-ES.txt"
    parlacap_path = (
        PROJECT_ROOT / "data" / "raw" / "corpus" / "cda1055_dat_ParlaCAP-ES_speeches_no_text.tsv"
    )
    output_path = PROJECT_ROOT / "data" / "processed" / "intervenciones.parquet"
    frame = build_corpus(raw_dir, parlacap_path, output_path)
    print(f"{len(frame)} intervenciones -> {output_path}")


if __name__ == "__main__":
    main()
