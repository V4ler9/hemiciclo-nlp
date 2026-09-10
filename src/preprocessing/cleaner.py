"""Limpieza de intervenciones: anotaciones, fórmulas procedimentales y longitud.

La unidad de análisis de la Fase 2 es la intervención: se eliminan las notas no
verbales (``[[...]]``), los saludos, vocativos y despedidas de trámite, se
normalizan los espacios y se descartan las intervenciones que, tras la limpieza,
quedan por debajo de ``min_words``. Las listas de fórmulas viven en
``configs/default.yaml``.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

from src.corpus.parser import INTERVENTION_COLUMNS
from src.utils.config import PROJECT_ROOT, load_config

CLEAN_COLUMNS = [*INTERVENTION_COLUMNS, "n_words_clean"]

ANNOTATION_PATTERN = re.compile(r"\s*\[\[.*?\]\]\s*", re.DOTALL)
WHITESPACE_PATTERN = re.compile(r"\s+")
SPACE_BEFORE_PUNCTUATION = re.compile(r"\s+([,.;:!?…])")

TRAILING_SEPARATORS = " ,;:"
MAX_ITERATIONS = 10


@dataclass(frozen=True)
class CleaningRules:
    """Reglas de limpieza ya compiladas."""

    min_words: int
    prefix_patterns: tuple[re.Pattern[str], ...]
    suffix_patterns: tuple[re.Pattern[str], ...]


def _alternation(tokens: Sequence[str]) -> str:
    """Une los tokens en una alternancia que prioriza los más largos."""
    unique = sorted({token.strip() for token in tokens if token.strip()}, key=len, reverse=True)
    return "|".join(re.escape(token) for token in unique)


def build_rules(config: Mapping[str, Any]) -> CleaningRules:
    """Compila la sección ``preprocessing`` de la configuración.

    Los patrones trabajan con fronteras de palabra para no partir términos como
    ``vicepresidenta`` al buscar ``presidenta``.
    """
    min_words = int(config["min_words"])
    greeting = rf"\b(?:{_alternation([str(item) for item in config['greetings']])})\b"
    honorific = rf"\b(?:{_alternation([str(item) for item in config['honorifics']])})\b"
    proper_name = r"[A-ZÁÉÍÓÚÜÑ][^\s,.;:!?]*"

    prefix_patterns = (
        re.compile(rf"^{greeting}\s*[,.:;]\s*", re.IGNORECASE),
        re.compile(
            rf"^{greeting}(?:\s*,?\s*{honorific}){{1,4}}(?:\s+{proper_name}){{0,2}}\s*[,.:;]?\s*",
            re.IGNORECASE,
        ),
        re.compile(rf"^{honorific}(?:\s*,?\s*{honorific}){{0,3}}\s*[,.:;]\s*", re.IGNORECASE),
        re.compile(rf"^{honorific}(?:\s+[^\s,.;:!?]+){{1,6}}\s*[,.:;]\s*", re.IGNORECASE),
    )
    suffix_patterns = (
        re.compile(
            rf"{greeting}(?:\s*,?\s*{honorific}){{0,4}}\s*[.!?…]?\s*$",
            re.IGNORECASE,
        ),
        re.compile(
            rf"{honorific}(?:\s*,?\s*{honorific}){{0,3}}\s*[.!?…]?\s*$",
            re.IGNORECASE,
        ),
    )
    return CleaningRules(
        min_words=min_words,
        prefix_patterns=prefix_patterns,
        suffix_patterns=suffix_patterns,
    )


def strip_annotations(text: str) -> str:
    """Elimina las notas no verbales ``[[...]]`` y los espacios que dejan."""
    return ANNOTATION_PATTERN.sub(" ", text).strip()


def normalize_whitespace(text: str) -> str:
    """Colapsa espacios y quita el espacio que queda antes de puntuación."""
    text = WHITESPACE_PATTERN.sub(" ", text)
    text = SPACE_BEFORE_PUNCTUATION.sub(r"\1", text)
    return text.strip()


def count_words(text: str) -> int:
    """Cuenta palabras separadas por espacios."""
    return len(text.split())


def _suffix_boundary_ok(text: str, start: int) -> bool:
    """Acepta quitar un sufijo si antes hay un separador de frase.

    Evita borrar usos con contenido, como ``dar las gracias``.
    """
    prefix = text[:start].rstrip()
    if not prefix:
        return True
    if prefix[-1] in ".!?…,;:":
        return True
    return prefix.lower().rsplit(maxsplit=1)[-1] in {"y", "e"}


def _strip_prefixes(text: str, patterns: Sequence[re.Pattern[str]]) -> str:
    for pattern in patterns:
        text = pattern.sub("", text, count=1)
    return text


def _strip_suffixes(text: str, patterns: Sequence[re.Pattern[str]]) -> str:
    for pattern in patterns:
        for match in pattern.finditer(text):
            if match.end() == len(text) and _suffix_boundary_ok(text, match.start()):
                candidate = text[: match.start()].rstrip(TRAILING_SEPARATORS)
                if candidate.lower().endswith((" y", " e")):
                    candidate = candidate[:-2].rstrip(TRAILING_SEPARATORS)
                text = candidate
                break
    return text


def clean_text(text: str, rules: CleaningRules) -> str:
    """Aplica anotaciones, fórmulas y normalización hasta que el texto es estable."""
    cleaned = normalize_whitespace(strip_annotations(text))
    for _ in range(MAX_ITERATIONS):
        previous = cleaned
        cleaned = _strip_prefixes(cleaned, rules.prefix_patterns)
        cleaned = _strip_suffixes(cleaned, rules.suffix_patterns)
        cleaned = normalize_whitespace(cleaned)
        if cleaned == previous:
            break
    return cleaned


def clean_corpus(frame: pd.DataFrame, rules: CleaningRules) -> pd.DataFrame:
    """Limpia la tabla de intervenciones y descarta las que no llegan al umbral."""
    if "text" not in frame.columns:
        raise ValueError("La tabla de intervenciones debe contener la columna 'text'")
    cleaned = frame.copy()
    cleaned["text"] = [clean_text(str(value), rules) for value in frame["text"].fillna("")]
    word_counts = pd.Series(
        [count_words(value) for value in cleaned["text"]],
        index=cleaned.index,
        dtype="int64",
    )
    cleaned["n_words_clean"] = word_counts
    cleaned = cleaned.loc[cleaned["n_words_clean"] >= rules.min_words, :]
    return cleaned.reset_index(drop=True)


def build_clean_corpus(input_path: Path, output_path: Path, rules: CleaningRules) -> pd.DataFrame:
    """Lee el corpus consolidado, lo limpia y guarda el parquet de la Fase 2."""
    frame = pd.read_parquet(input_path)
    cleaned = clean_corpus(frame, rules)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    cleaned.to_parquet(output_path, index=False)
    return cleaned


def main() -> None:
    """CLI: construye ``data/processed/intervenciones_limpias.parquet``."""
    config = load_config()
    rules = build_rules(config["preprocessing"])
    input_path = PROJECT_ROOT / "data" / "processed" / "intervenciones.parquet"
    output_path = PROJECT_ROOT / "data" / "processed" / "intervenciones_limpias.parquet"
    frame = build_clean_corpus(input_path, output_path, rules)
    print(f"{len(frame)} intervenciones limpias -> {output_path}")


if __name__ == "__main__":
    main()
