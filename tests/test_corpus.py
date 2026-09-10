"""Tests de la Fase 1: descarga, parseo y consolidación del corpus.

Los tests unitarios corren contra un mini-corpus sintético en ``tests/fixtures``.
Los marcados como ``integration`` requieren ``HEMICICLO_INTEGRATION=1`` y red o
el corpus real descargado en ``data/raw``.
"""

from __future__ import annotations

import hashlib
import os
from collections.abc import Iterator
from pathlib import Path
from typing import Any, cast

import pandas as pd
import pandera.pandas as pa
import pytest
import requests
import src.corpus.downloader as downloader
from src.corpus.parser import (
    ANA_META_COLUMNS,
    INTERVENTION_COLUMNS,
    META_COLUMNS,
    aggregate_sentiment,
    build_corpus,
    build_interventions,
    find_component_bases,
    read_ana_meta,
    read_meta_tsv,
    read_plain_text,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
FIXTURES_DIR = Path(__file__).parent / "fixtures" / "parlamint_es_mini"
COMPONENT_DIR = FIXTURES_DIR / "2023"
BASE_NAME = "ParlaMint-ES_2023-02-23-CD230223"
META_PATH = COMPONENT_DIR / f"{BASE_NAME}-meta.tsv"
TEXT_PATH = COMPONENT_DIR / f"{BASE_NAME}.txt"
ANA_META_PATH = COMPONENT_DIR / f"{BASE_NAME}-ana-meta.tsv"
U = f"{BASE_NAME}.u"

RAW_DIR = PROJECT_ROOT / "data" / "raw"
SAMPLE_URL = (
    "https://raw.githubusercontent.com/clarin-eric/ParlaMint/main/Samples/ParlaMint-ES/2023"
)

integration = pytest.mark.skipif(
    not os.environ.get("HEMICICLO_INTEGRATION"),
    reason="requiere HEMICICLO_INTEGRATION=1, red y/o corpus descargado",
)

INTERVENTION_SCHEMA = pa.DataFrameSchema(
    {
        "utterance_id": pa.Column(str, unique=True),
        "component_id": pa.Column(str),
        "date": pa.Column("datetime64[ns]"),
        "year": pa.Column("int64"),
        "month": pa.Column("int64"),
        "term": pa.Column(str, nullable=True),
        "session": pa.Column(str, nullable=True),
        "subcorpus": pa.Column(str, nullable=True),
        "speaker_role": pa.Column(str, nullable=True),
        "speaker_party": pa.Column(str, nullable=True),
        "speaker_party_name": pa.Column(str, nullable=True),
        "party_status": pa.Column(str, nullable=True),
        "party_orientation": pa.Column(str, nullable=True),
        "speaker_gender": pa.Column(str, nullable=True),
        "speaker_birth": pa.Column("datetime64[ns]", nullable=True),
        "speaker_minister": pa.Column(str, nullable=True),
        "topic": pa.Column(str, nullable=True),
        "text": pa.Column(str),
        "senti_n_mean": pa.Column(float, nullable=True),
        "senti_3": pa.Column(str, nullable=True),
        "senti_6": pa.Column(str, nullable=True),
        "n_sents": pa.Column("int64"),
        "n_words": pa.Column("int64"),
        "n_tokens": pa.Column("int64"),
        "n_names": pa.Column("int64"),
    },
    strict=True,
    coerce=False,
)


def _load_fixture_frames() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    return read_meta_tsv(META_PATH), read_plain_text(TEXT_PATH), read_ana_meta(ANA_META_PATH)


def _row(frame: pd.DataFrame, key: str, value: str) -> Any:
    """Devuelve la primera fila que cumple ``key == value`` como ``Any``."""
    return cast(Any, frame.loc[frame[key] == value].iloc[0])


def _is_na(value: Any) -> bool:
    return bool(cast(Any, pd.isna(value)))


def _assert_schema(df: pd.DataFrame) -> None:
    INTERVENTION_SCHEMA.validate(df)
    assert df["year"].ge(2015).all()
    assert df["month"].between(1, 12).all()
    for column in ("n_sents", "n_words", "n_tokens", "n_names"):
        assert df[column].ge(0).all()


# ---------------------------------------------------------------------------
# Parseo del TSV de metadatos
# ---------------------------------------------------------------------------


def test_read_meta_tsv_schema_y_tipos() -> None:
    meta = read_meta_tsv(META_PATH)
    assert list(meta.columns) == META_COLUMNS
    assert len(meta) == 4
    assert meta["ID"].is_unique
    assert pd.api.types.is_datetime64_any_dtype(meta["Date"])
    assert meta["Date"].eq(pd.Timestamp("2023-02-23")).all()
    assert meta["Subcorpus"].eq("COVID,Guerra").all()


def test_read_meta_tsv_marca_guiones_como_na() -> None:
    meta = read_meta_tsv(META_PATH)
    presidencia = _row(meta, "ID", f"{U}1")
    assert _is_na(presidencia["Speaker_party"])
    assert _is_na(presidencia["Party_status"])
    assert _is_na(presidencia["Topic"])
    diputada = _row(meta, "ID", f"{U}2")
    assert diputada["Speaker_party"] == "GP-Socialista"
    assert diputada["Speaker_gender"] == "Mujer"


# ---------------------------------------------------------------------------
# Parseo del texto plano
# ---------------------------------------------------------------------------


def test_read_plain_text_lee_intervenciones_con_acentos() -> None:
    text = read_plain_text(TEXT_PATH)
    assert list(text.columns) == ["ID", "text"]
    assert len(text) == 4
    assert text["ID"].is_unique
    assert "señorías" in str(_row(text, "ID", f"{U}1")["text"])


def test_read_plain_text_rechaza_ids_duplicados(tmp_path: Path) -> None:
    path = tmp_path / "duplicados.txt"
    path.write_text("a.u1\tHola\na.u1\tAdiós\n", encoding="utf-8")
    with pytest.raises(ValueError, match="duplicad"):
        read_plain_text(path)


# ---------------------------------------------------------------------------
# Parseo del TSV anotado (sentimiento)
# ---------------------------------------------------------------------------


def test_read_ana_meta_separa_frases_de_intervenciones() -> None:
    ana = read_ana_meta(ANA_META_PATH)
    assert list(ana.columns) == ANA_META_COLUMNS
    frases = ana[ana["Element"] == "s"]
    intervenciones = ana[ana["Element"] == "u"]
    assert pd.api.types.is_float_dtype(frases["Senti_n"])
    assert frases["Senti_n"].notna().all()
    assert intervenciones["Senti_n"].isna().all()
    assert frases["Parent_ID"].str.startswith(U).all()


def test_read_ana_meta_tolera_tab_final(tmp_path: Path) -> None:
    path = tmp_path / "con-tab-ana-meta.tsv"
    path.write_text(
        "ID\tParent_ID\tElement\tLanguage\tSenti_3\tSenti_6\tSenti_n"
        "\tSents\tWords\tTokens\tNames\t\n"
        "x.u1\tx\tu\tEspañol\t-\t-\t-\t0\t0\t0\t0\t\n",
        encoding="utf-8",
    )
    ana = read_ana_meta(path)
    assert list(ana.columns) == ANA_META_COLUMNS
    assert len(ana) == 1


def test_aggregate_sentiment_por_intervencion() -> None:
    agg = aggregate_sentiment(read_ana_meta(ANA_META_PATH))
    assert agg["ID"].tolist() == [f"{U}1", f"{U}2", f"{U}3", f"{U}4"]
    assert list(agg.columns) == [
        "ID",
        "senti_n_mean",
        "senti_3",
        "senti_6",
        "n_sents",
        "n_words",
        "n_tokens",
        "n_names",
    ]
    fila_u1 = _row(agg, "ID", f"{U}1")
    assert fila_u1["senti_n_mean"] == pytest.approx((4.557 + 3.846) / 2)
    assert fila_u1["senti_3"] == "Positivo"
    assert fila_u1["senti_6"] == "positivo"
    assert fila_u1["n_sents"] == 2
    fila_u2 = _row(agg, "ID", f"{U}2")
    assert fila_u2["senti_n_mean"] == pytest.approx((0.349 + 0.253 + 4.049) / 3)
    assert fila_u2["senti_3"] == "Negativo"
    assert fila_u2["senti_6"] == "negativo"
    assert fila_u2["n_words"] == 40
    fila_u4 = _row(agg, "ID", f"{U}4")
    assert _is_na(fila_u4["senti_n_mean"])
    assert fila_u4["n_sents"] == 0
    assert fila_u4["n_words"] == 8


# ---------------------------------------------------------------------------
# Consolidación
# ---------------------------------------------------------------------------


def test_build_interventions_une_las_tres_fuentes() -> None:
    meta, text, ana = _load_fixture_frames()
    df = build_interventions(meta, text, aggregate_sentiment(ana))
    assert list(df.columns) == INTERVENTION_COLUMNS
    assert len(df) == 4
    assert df["utterance_id"].is_unique

    u2 = _row(df, "utterance_id", f"{U}2")
    assert u2["component_id"] == BASE_NAME
    assert u2["text"].startswith("Gracias, señoría")
    assert u2["date"] == pd.Timestamp("2023-02-23")
    assert (u2["year"], u2["month"]) == (2023, 2)
    assert u2["speaker_party"] == "GP-Socialista"
    assert u2["party_status"] == "Gobierno"
    assert u2["speaker_birth"] == pd.Timestamp("1975-06-15")
    assert u2["topic"] == "Macroeconomía"
    assert u2["senti_n_mean"] == pytest.approx((0.349 + 0.253 + 4.049) / 3)

    u1 = _row(df, "utterance_id", f"{U}1")
    assert _is_na(u1["speaker_party"])
    assert _is_na(u1["speaker_birth"])

    u4 = _row(df, "utterance_id", f"{U}4")
    assert _is_na(u4["senti_n_mean"])
    assert u4["n_sents"] == 0


def test_build_interventions_exige_texto_para_cada_intervencion() -> None:
    meta, text, ana = _load_fixture_frames()
    text_reducido = text[text["ID"] != f"{U}4"]
    with pytest.raises(ValueError, match="sin texto"):
        build_interventions(meta, text_reducido, aggregate_sentiment(ana))


def test_build_interventions_exige_metadatos_para_cada_texto() -> None:
    meta, text, ana = _load_fixture_frames()
    meta_reducida = meta[meta["ID"] != f"{U}4"]
    with pytest.raises(ValueError, match="sin metadatos"):
        build_interventions(meta_reducida, text, aggregate_sentiment(ana))


def test_intervenciones_cumplen_el_esquema() -> None:
    meta, text, ana = _load_fixture_frames()
    df = build_interventions(meta, text, aggregate_sentiment(ana))
    _assert_schema(df)


def test_find_component_bases_encuentra_el_componente() -> None:
    assert find_component_bases(FIXTURES_DIR) == [COMPONENT_DIR / BASE_NAME]


def test_build_corpus_escribe_parquet_reproducible(tmp_path: Path) -> None:
    out = tmp_path / "intervenciones.parquet"
    df = build_corpus(FIXTURES_DIR, out)
    assert out.exists()
    assert len(df) == 4
    recovered = pd.read_parquet(out)
    pd.testing.assert_frame_equal(df, recovered)


# ---------------------------------------------------------------------------
# Descarga
# ---------------------------------------------------------------------------


class _FakeResponse:
    """Respuesta HTTP falsa para testear el descargador sin red."""

    def __init__(
        self,
        chunks: list[bytes],
        status: int = 200,
        error_after: int | None = None,
    ) -> None:
        self._chunks = list(chunks)
        self.status_code = status
        self._error_after = error_after

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise requests.HTTPError(f"HTTP {self.status_code}")

    def iter_content(self, chunk_size: int) -> Iterator[bytes]:
        for index, chunk in enumerate(self._chunks):
            yield chunk
            if self._error_after is not None and index + 1 >= self._error_after:
                raise RuntimeError("conexión interrumpida")

    def __enter__(self) -> _FakeResponse:
        return self

    def __exit__(self, *exc_info: Any) -> bool:
        return False


def _fake_get(chunks: list[bytes], status: int = 200, error_after: int | None = None) -> Any:
    def _get(*args: Any, **kwargs: Any) -> _FakeResponse:
        return _FakeResponse(chunks, status=status, error_after=error_after)

    return _get


def test_filename_from_url() -> None:
    assert (
        downloader.filename_from_url("https://x/y/ParlaMint-ES.tgz?download=1")
        == "ParlaMint-ES.tgz"
    )
    assert downloader.filename_from_url("https://x/a%20b.tar.gz") == "a b.tar.gz"


def test_verify_sha256(tmp_path: Path) -> None:
    path = tmp_path / "f.bin"
    path.write_bytes(b"contenido")
    expected = hashlib.sha256(b"contenido").hexdigest()
    assert downloader.verify_sha256(path, expected)
    assert not downloader.verify_sha256(path, "0" * 64)


def test_download_file_omite_si_el_hash_coincide(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    dest = tmp_path / "f.bin"
    dest.write_bytes(b"datos")
    expected = hashlib.sha256(b"datos").hexdigest()

    def _no_descargar(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("no debería descargar")

    monkeypatch.setattr(downloader.requests, "get", _no_descargar)
    assert downloader.download_file("https://x/f.bin", dest, expected_sha256=expected) == dest


def test_download_file_descarga_por_chunks_y_verifica(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(downloader.requests, "get", _fake_get([b"hola ", b"mundo"]))
    dest = tmp_path / "sub" / "f.txt"
    expected = hashlib.sha256(b"hola mundo").hexdigest()
    assert downloader.download_file("https://x/f.txt", dest, expected_sha256=expected) == dest
    assert dest.read_bytes() == b"hola mundo"
    assert not dest.with_name(dest.name + ".part").exists()


def test_download_file_limpia_parcial_si_falla(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(downloader.requests, "get", _fake_get([b"parcial"], error_after=1))
    dest = tmp_path / "f.bin"
    with pytest.raises(RuntimeError, match="interrumpida"):
        downloader.download_file("https://x/f.bin", dest)
    assert not dest.exists()
    assert not dest.with_name(dest.name + ".part").exists()


def test_download_file_propaga_errores_http(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(downloader.requests, "get", _fake_get([], status=404))
    with pytest.raises(requests.HTTPError):
        downloader.download_file("https://x/no-existe.bin", tmp_path / "no-existe.bin")


# ---------------------------------------------------------------------------
# Integración (red / corpus real)
# ---------------------------------------------------------------------------


@pytest.mark.integration
@integration
def test_muestra_real_descarga_y_parsea(tmp_path: Path) -> None:
    for suffix in ("-meta.tsv", ".txt", "-ana-meta.tsv"):
        downloader.download_file(
            f"{SAMPLE_URL}/{BASE_NAME}{suffix}", tmp_path / f"{BASE_NAME}{suffix}"
        )
    meta = read_meta_tsv(tmp_path / f"{BASE_NAME}-meta.tsv")
    text = read_plain_text(tmp_path / f"{BASE_NAME}.txt")
    agg = aggregate_sentiment(read_ana_meta(tmp_path / f"{BASE_NAME}-ana-meta.tsv"))
    df = build_interventions(meta, text, agg)
    _assert_schema(df)
    assert df["date"].between(pd.Timestamp("2015-01-01"), pd.Timestamp("2023-02-23")).all()


@pytest.mark.integration
@integration
def test_corpus_real_calidad(tmp_path: Path) -> None:
    if not RAW_DIR.exists() or not find_component_bases(RAW_DIR):
        pytest.skip("corpus no descargado en data/raw")
    out = tmp_path / "intervenciones.parquet"
    df = build_corpus(RAW_DIR, out)
    assert df["utterance_id"].is_unique
    assert df["date"].between(pd.Timestamp("2015-01-01"), pd.Timestamp("2023-02-23")).all()
    assert len(df) > 10_000
    _assert_schema(df)
    assert df["speaker_gender"].notna().mean() >= 0.9
