"""Segmentación de texto: párrafos y frases.

El TXT plano de ParlaMint no conserva los saltos de párrafo del TEI, de modo
que en la práctica cada intervención es un único párrafo; la segmentación queda
como utilidad para limpieza fina, control de calidad y usos posteriores.
"""

from __future__ import annotations

import re

PARAGRAPH_SEPARATOR = re.compile(r"\n\s*\n+")
SENTENCE_BOUNDARY = re.compile(r"[.!?…]+(?=\s+|$)")
ABBREVIATIONS = frozenset(
    {"sr", "sra", "srta", "d", "dña", "dr", "dra", "art", "núm", "pág", "etc", "ee", "uu"}
)


def split_paragraphs(text: str) -> list[str]:
    """Divide por líneas en blanco y descarta fragmentos vacíos."""
    return [part.strip() for part in PARAGRAPH_SEPARATOR.split(text) if part.strip()]


def split_sentences(text: str) -> list[str]:
    """Divide en frases con una heurística de puntuación y abreviaturas."""
    stripped = text.strip()
    if not stripped:
        return []
    sentences: list[str] = []
    start = 0
    for match in SENTENCE_BOUNDARY.finditer(stripped):
        previous = stripped[start : match.start()].rsplit(maxsplit=1)[-1]
        previous = previous.lower().strip("¿¡«»\"'()[]")
        if previous in ABBREVIATIONS and match.end() < len(stripped):
            continue
        following = stripped[match.end() :].lstrip().lstrip("¿¡«»\"'([")
        if following and following[0].islower():
            continue
        sentences.append(stripped[start : match.end()].strip())
        start = match.end()
    tail = stripped[start:].strip()
    if tail:
        sentences.append(tail)
    return sentences
