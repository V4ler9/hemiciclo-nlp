"""Tests de la Fase 2: limpieza de intervenciones y segmentación.

Los tests unitarios no tocan el disco salvo ``tmp_path``. El de integración
requiere ``HEMICICLO_INTEGRATION=1`` y el corpus consolidado de Fase 1 en
``data/processed/intervenciones.parquet``.
"""

from __future__ import annotations

import os
from pathlib import Path

import pandas as pd
import pytest
from src.preprocessing.cleaner import (
    CLEAN_COLUMNS,
    CleaningRules,
    build_clean_corpus,
    build_rules,
    clean_corpus,
    clean_text,
    count_words,
    normalize_whitespace,
    strip_annotations,
)
from src.preprocessing.segmenter import split_paragraphs, split_sentences
from src.utils.config import load_config

PROJECT_ROOT = Path(__file__).resolve().parents[1]
INTERVENTIONS_PATH = PROJECT_ROOT / "data" / "processed" / "intervenciones.parquet"

integration = pytest.mark.skipif(
    not os.environ.get("HEMICICLO_INTEGRATION"),
    reason="requiere HEMICICLO_INTEGRATION=1 y el corpus consolidado",
)


@pytest.fixture()
def rules() -> CleaningRules:
    """Reglas reales, cargadas de ``configs/default.yaml``."""
    return build_rules(load_config()["preprocessing"])


def _minimal_rules(min_words: int = 20) -> CleaningRules:
    return build_rules(
        {
            "min_words": min_words,
            "greetings": ["muchas gracias", "gracias"],
            "honorifics": ["presidenta", "presidente", "señora", "señor"],
        }
    )


# ---------------------------------------------------------------------------
# Anotaciones y normalización
# ---------------------------------------------------------------------------


def test_strip_annotations_elimina_notas_enteras() -> None:
    assert strip_annotations("Uno [[Aplausos]] dos") == "Uno dos"
    assert strip_annotations("[[Rumores]] El Gobierno comparece.") == "El Gobierno comparece."
    assert strip_annotations("Texto. [[Aplausos.-Risas]]") == "Texto."
    assert strip_annotations("Nota[[sic]]pegada") == "Nota pegada"


def test_strip_annotations_no_toca_corchetes_simples() -> None:
    assert strip_annotations("Texto con [corchete] simple.") == "Texto con [corchete] simple."


def test_strip_annotations_texto_solo_con_notas() -> None:
    assert strip_annotations("[[Continúa su intervención en catalán]]") == ""


def test_normalize_whitespace_colapsa_y_limpia_espacios() -> None:
    assert normalize_whitespace("  El   Gobierno\t\tsube.  ") == "El Gobierno sube."
    assert normalize_whitespace("Texto .") == "Texto."
    assert normalize_whitespace("A\n\nB") == "A B"
    assert normalize_whitespace("   ") == ""


def test_count_words() -> None:
    assert count_words("El Gobierno sube los impuestos.") == 5
    assert count_words("   ") == 0
    assert count_words("") == 0


# ---------------------------------------------------------------------------
# Limpieza de fórmulas de saludo y despedida
# ---------------------------------------------------------------------------


def test_clean_text_quita_saludo_con_punto(rules: CleaningRules) -> None:
    assert (
        clean_text("Gracias, señora presidenta. El Gobierno va a bajar los impuestos.", rules)
        == "El Gobierno va a bajar los impuestos."
    )


def test_clean_text_quita_vocativo_con_nombre(rules: CleaningRules) -> None:
    assert (
        clean_text(
            "Señor Montoro, ¿cree usted que la política de austeridad ha dado frutos?", rules
        )
        == "¿cree usted que la política de austeridad ha dado frutos?"
    )


def test_clean_text_quita_vocativo_compuesto(rules: CleaningRules) -> None:
    assert (
        clean_text("Señora presidenta, señorías, hoy debatimos los presupuestos.", rules)
        == "hoy debatimos los presupuestos."
    )


def test_clean_text_quita_despedida_final(rules: CleaningRules) -> None:
    assert (
        clean_text("El Gobierno defiende la ley. Muchas gracias. [[Aplausos]]", rules)
        == "El Gobierno defiende la ley."
    )
    assert (
        clean_text("El Gobierno defiende la ley. Muchísimas gracias, señora presidenta.", rules)
        == "El Gobierno defiende la ley."
    )


def test_clean_text_quita_despedida_sin_punto_previo(rules: CleaningRules) -> None:
    assert clean_text("No estamos de acuerdo y muchas gracias.", rules) == "No estamos de acuerdo"


def test_clean_text_quita_tratamiento_final(rules: CleaningRules) -> None:
    assert clean_text("Voy acabando, señora presidenta.", rules) == "Voy acabando"
    assert (
        clean_text(
            "Sí, por favor. Estamos tratando un tema importante, señora vicepresidenta.", rules
        )
        == "Sí, por favor. Estamos tratando un tema importante"
    )


def test_clean_text_no_parte_palabras_por_dentro(rules: CleaningRules) -> None:
    assert clean_text("La vicepresidenta del Gobierno comparece.", rules) == (
        "La vicepresidenta del Gobierno comparece."
    )


def test_clean_text_textos_solo_formula_quedan_vacios(rules: CleaningRules) -> None:
    assert clean_text("Muchas gracias, señor presidente.", rules) == ""
    assert clean_text("Muchas gracias. [[Aplausos]]", rules) == ""
    assert clean_text("Grazas, señor presidente.", rules) == ""
    assert clean_text("Eskerrik asko.", rules) == ""
    assert clean_text("MUCHAS GRACIAS, SEÑORA PRESIDENTA.", rules) == ""


def test_clean_text_respeta_expresiones_con_contenido(rules: CleaningRules) -> None:
    assert clean_text("Gracias a la mayoría, se aprobó la ley.", rules) == (
        "Gracias a la mayoría, se aprobó la ley."
    )
    assert clean_text("Doy las gracias a todos los diputados.", rules) == (
        "Doy las gracias a todos los diputados."
    )
    assert clean_text("Agradezco mucho su respuesta pero no la comparto.", rules) == (
        "Agradezco mucho su respuesta pero no la comparto."
    )


def test_clean_text_conserva_contenido_tras_la_cortesia(rules: CleaningRules) -> None:
    cleaned = clean_text("Muchas gracias, señor presidente, por su comparecencia.", rules)
    assert "gracias" not in cleaned.lower()
    assert "comparecencia" in cleaned


def test_clean_text_multilingue(rules: CleaningRules) -> None:
    assert (
        clean_text("Moltes gràcies, senyora presidenta. Comencem el debat.", rules)
        == "Comencem el debat."
    )
    assert (
        clean_text("Buenos días, señorías. Comparezco para explicar el proyecto.", rules)
        == "Comparezco para explicar el proyecto."
    )


def test_clean_text_es_idempotente(rules: CleaningRules) -> None:
    textos = [
        "Gracias, señora presidenta. El Gobierno va a bajar los impuestos.",
        "El Gobierno defiende la ley. Muchas gracias. [[Aplausos]]",
        "Señor Montoro, ¿cree usted que la política de austeridad ha dado frutos?",
        "",
    ]
    for texto in textos:
        una_vez = clean_text(texto, rules)
        assert clean_text(una_vez, rules) == una_vez


# ---------------------------------------------------------------------------
# Limpieza tabular y umbral de longitud
# ---------------------------------------------------------------------------


def test_clean_corpus_filtra_por_umbral_y_añade_palabras() -> None:
    rules = _minimal_rules(min_words=5)
    frame = pd.DataFrame(
        {
            "utterance_id": ["a", "b", "c", "d"],
            "text": [
                "Gracias, presidenta. " + "contenido " * 8,
                "Solo cuatro palabras aquí.",
                "Muchas gracias.",
                "Muchas gracias, presidenta.",
            ],
            "speaker_party": ["GP-A", "GP-B", "GP-C", "GP-D"],
        }
    )
    clean = clean_corpus(frame, rules)
    assert list(clean.columns) == ["utterance_id", "text", "speaker_party", "n_words_clean"]
    assert clean["utterance_id"].tolist() == ["a"]
    assert clean["n_words_clean"].tolist() == [8]
    assert clean.loc[0, "text"] == ("contenido " * 8).strip()
    assert clean["speaker_party"].tolist() == ["GP-A"]


def test_clean_corpus_conserva_justo_en_el_umbral() -> None:
    rules = _minimal_rules(min_words=3)
    frame = pd.DataFrame(
        {
            "utterance_id": ["justo", "corto"],
            "text": ["Tres palabras exactas.", "Solo dos."],
        }
    )
    clean = clean_corpus(frame, rules)
    assert clean["utterance_id"].tolist() == ["justo"]
    assert clean["n_words_clean"].tolist() == [3]


def test_clean_corpus_preserva_columnas_y_no_muta_la_entrada() -> None:
    rules = _minimal_rules(min_words=1)
    frame = pd.DataFrame(
        {
            "utterance_id": ["a"],
            "text": ["Gracias, presidenta. El Gobierno sube el salario mínimo."],
            "speaker_party": ["GP-X"],
            "senti_n": [3.5],
        }
    )
    clean = clean_corpus(frame, rules)
    assert clean.loc[0, "text"] == "El Gobierno sube el salario mínimo."
    assert clean.loc[0, "speaker_party"] == "GP-X"
    assert clean.loc[0, "senti_n"] == 3.5
    assert frame.loc[0, "text"] == "Gracias, presidenta. El Gobierno sube el salario mínimo."
    assert "n_words_clean" not in frame.columns


def test_clean_corpus_exige_columna_text() -> None:
    with pytest.raises(ValueError, match="text"):
        clean_corpus(pd.DataFrame({"utterance_id": ["a"]}), _minimal_rules())


def test_build_clean_corpus_escribe_parquet(tmp_path: Path) -> None:
    source = tmp_path / "intervenciones.parquet"
    pd.DataFrame(
        {
            "utterance_id": ["a", "b"],
            "text": [
                "Gracias, presidenta. " + "contenido " * 20,
                "Muchas gracias.",
            ],
        }
    ).to_parquet(source, index=False)
    output = tmp_path / "intervenciones_limpias.parquet"
    clean = build_clean_corpus(source, output, _minimal_rules(min_words=5))
    assert output.exists()
    recovered = pd.read_parquet(output)
    pd.testing.assert_frame_equal(clean, recovered)
    assert clean["utterance_id"].tolist() == ["a"]


# ---------------------------------------------------------------------------
# Segmentación
# ---------------------------------------------------------------------------


def test_split_paragraphs_separa_por_lineas_vacias() -> None:
    assert split_paragraphs("Uno.\n\nDos.\n\n\nTres.") == ["Uno.", "Dos.", "Tres."]


def test_split_paragraphs_texto_plano_es_un_solo_parrafo() -> None:
    assert split_paragraphs("Uno. Dos.") == ["Uno. Dos."]


def test_split_paragraphs_vacio() -> None:
    assert split_paragraphs("   ") == []


def test_split_sentences_basico() -> None:
    assert split_sentences("Hola. ¿Qué tal? Bien!") == ["Hola.", "¿Qué tal?", "Bien!"]


def test_split_sentences_respeta_abreviaturas() -> None:
    assert split_sentences("El Sr. García vino. Se fue.") == ["El Sr. García vino.", "Se fue."]


def test_split_sentences_respeta_decimales() -> None:
    assert split_sentences("Subió un 3.5 por ciento.") == ["Subió un 3.5 por ciento."]


def test_split_sentences_no_parte_si_sigue_minuscula() -> None:
    assert split_sentences("Hola. ¿qué tal?") == ["Hola. ¿qué tal?"]


def test_split_sentences_vacio() -> None:
    assert split_sentences("") == []


# ---------------------------------------------------------------------------
# Configuración
# ---------------------------------------------------------------------------


def test_default_config_incluye_reglas_de_limpieza() -> None:
    preprocessing = load_config()["preprocessing"]
    assert preprocessing["min_words"] == 20
    greetings = preprocessing["greetings"]
    honorifics = preprocessing["honorifics"]
    assert greetings and all(isinstance(item, str) for item in greetings)
    assert honorifics and all(isinstance(item, str) for item in honorifics)


# ---------------------------------------------------------------------------
# Integración (corpus real)
# ---------------------------------------------------------------------------


@pytest.mark.integration
@integration
def test_limpieza_corpus_real(tmp_path: Path) -> None:
    if not INTERVENTIONS_PATH.exists():
        pytest.skip("corpus consolidado no disponible en data/processed")
    config = load_config()
    rules = build_rules(config["preprocessing"])
    raw = pd.read_parquet(INTERVENTIONS_PATH)
    output = tmp_path / "intervenciones_limpias.parquet"
    clean = build_clean_corpus(INTERVENTIONS_PATH, output, rules)

    assert output.exists()
    assert list(clean.columns) == CLEAN_COLUMNS
    assert len(clean) < len(raw)
    assert len(clean) > 25_000
    assert clean["utterance_id"].is_unique
    assert clean["n_words_clean"].ge(rules.min_words).all()
    expected_words = pd.Series(
        [len(text.split()) for text in clean["text"]], index=clean.index, dtype="int64"
    )
    assert clean["n_words_clean"].eq(expected_words).all()
    assert clean["text"].ne("").all()
    assert clean["text"].str.strip().eq(clean["text"]).all()
    assert not clean["text"].str.contains(r"\[\[|\]\]", regex=True).any()
    assert clean["senti_n"].notna().mean() >= 0.99

    again = clean_corpus(raw, rules)
    pd.testing.assert_frame_equal(clean, again)
