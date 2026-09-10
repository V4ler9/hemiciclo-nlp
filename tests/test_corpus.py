"""Tests de la Fase 1: descarga, parseo y consolidación del corpus.

Los datos salen de dos fuentes: ParlaMint-ES 5.0 (texto y metadatos) y ParlaCAP
1.0 (sentimiento ParlaSent y tópico CAP). Los tests unitarios corren contra
mini-corpus sintéticos en ``tests/fixtures``; los marcados como ``integration``
requieren ``HEMICICLO_INTEGRATION=1`` y red o el corpus real en ``data/raw``.
"""

from __future__ import annotations

import hashlib
import os
import tarfile
import zipfile
from collections.abc import Iterator
from pathlib import Path
from typing import Any, cast

import pandas as pd
import pandera.pandas as pa
import pytest
import requests
import src.corpus.downloader as downloader
from src.corpus.parser import (
    INTERVENTION_COLUMNS,
    META_COLUMNS,
    PARLACAP_COLUMNS,
    build_corpus,
    build_interventions,
    find_component_bases,
    read_meta_tsv,
    read_parlacap_speeches,
    read_plain_text,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
FIXTURES_DIR = Path(__file__).parent / "fixtures" / "parlamint_es_mini"
COMPONENT_DIR = FIXTURES_DIR / "2023"
BASE_NAME = "ParlaMint-ES_2023-02-23-CD230223"
META_PATH = COMPONENT_DIR / f"{BASE_NAME}-meta.tsv"
TEXT_PATH = COMPONENT_DIR / f"{BASE_NAME}.txt"
U = f"{BASE_NAME}.u"

PARLACAP_FIXTURE = (
    Path(__file__).parent / "fixtures" / "parlacap_es_mini" / "ParlaCAP-ES_speeches_no_text.tsv"
)
RAW_CORPUS_DIR = PROJECT_ROOT / "data" / "raw" / "corpus"
PARLAMINT_TXT_DIR = RAW_CORPUS_DIR / "ParlaMint-ES.txt"
PARLACAP_REAL_PATH = RAW_CORPUS_DIR / "cda1055_dat_ParlaCAP-ES_speeches_no_text.tsv"

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
        "topic_prob": pa.Column(float, nullable=True),
        "text": pa.Column(str),
        "senti_n": pa.Column(float, nullable=True),
        "senti_3": pa.Column(str, nullable=True),
        "senti_6": pa.Column(str, nullable=True),
        "n_words": pa.Column("Int64", nullable=True),
    },
    strict=True,
    coerce=False,
)


def _load_fixture_frames() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    return (
        read_meta_tsv(META_PATH),
        read_plain_text(TEXT_PATH),
        read_parlacap_speeches(PARLACAP_FIXTURE),
    )


def _row(frame: pd.DataFrame, key: str, value: str) -> Any:
    """Devuelve la primera fila que cumple ``key == value`` como ``Any``."""
    return cast(Any, frame.loc[frame[key] == value].iloc[0])


def _is_na(value: Any) -> bool:
    return bool(cast(Any, pd.isna(value)))


def _empty_parlacap() -> pd.DataFrame:
    return pd.DataFrame({column: pd.Series(dtype="object") for column in PARLACAP_COLUMNS})


def _assert_schema(df: pd.DataFrame) -> None:
    INTERVENTION_SCHEMA.validate(df)
    assert df["year"].ge(2015).all()
    assert df["month"].between(1, 12).all()
    assert df["topic_prob"].dropna().between(0, 1).all()
    assert df["n_words"].dropna().ge(0).all()


# ---------------------------------------------------------------------------
# Parseo del TSV de metadatos de ParlaMint
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
# Parseo de ParlaCAP (sentimiento y tópico)
# ---------------------------------------------------------------------------


def test_read_parlacap_speeches_schema_y_tipos() -> None:
    parlacap = read_parlacap_speeches(PARLACAP_FIXTURE)
    assert list(parlacap.columns) == PARLACAP_COLUMNS
    assert len(parlacap) == 3
    assert parlacap["id"].is_unique
    assert pd.api.types.is_datetime64_any_dtype(parlacap["date"])
    assert parlacap["date"].eq(pd.Timestamp("2023-02-23")).all()
    assert pd.api.types.is_float_dtype(parlacap["sent_logit"])
    u2 = _row(parlacap, "id", f"{U}2")
    assert u2["sent_logit"] == pytest.approx(4.049)
    assert u2["CAP_category"] == "Macroeconomics"
    assert u2["CAP_prob"] == pytest.approx(0.903)
    assert u2["word_count"] == 40
    presidencia = _row(parlacap, "id", f"{U}1")
    assert _is_na(presidencia["speaker_party"])


# ---------------------------------------------------------------------------
# Consolidación
# ---------------------------------------------------------------------------


def test_build_interventions_une_las_tres_fuentes() -> None:
    meta, text, parlacap = _load_fixture_frames()
    df = build_interventions(meta, text, parlacap)
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
    assert u2["topic"] == "Macroeconomics"
    assert u2["topic_prob"] == pytest.approx(0.903)
    assert u2["senti_n"] == pytest.approx(4.049)
    assert u2["senti_3"] == "Positive"
    assert u2["senti_6"] == "Mixed Positive"
    assert u2["n_words"] == 40

    u1 = _row(df, "utterance_id", f"{U}1")
    assert _is_na(u1["speaker_party"])
    assert _is_na(u1["speaker_birth"])
    assert u1["topic"] == "Law and Crime"
    assert u1["senti_3"] == "Neutral"

    u4 = _row(df, "utterance_id", f"{U}4")
    assert _is_na(u4["topic"])
    assert _is_na(u4["senti_n"])
    assert _is_na(u4["n_words"])


def test_build_interventions_exige_texto_para_cada_intervencion() -> None:
    meta, text, parlacap = _load_fixture_frames()
    text_reducido = text[text["ID"] != f"{U}4"]
    with pytest.raises(ValueError, match="sin texto"):
        build_interventions(meta, text_reducido, parlacap)


def test_build_interventions_exige_metadatos_para_cada_texto() -> None:
    meta, text, parlacap = _load_fixture_frames()
    meta_reducida = meta[meta["ID"] != f"{U}4"]
    with pytest.raises(ValueError, match="sin metadatos"):
        build_interventions(meta_reducida, text, parlacap)


def test_intervenciones_cumplen_el_esquema() -> None:
    meta, text, parlacap = _load_fixture_frames()
    df = build_interventions(meta, text, parlacap)
    _assert_schema(df)


def test_find_component_bases_encuentra_el_componente() -> None:
    assert find_component_bases(FIXTURES_DIR) == [COMPONENT_DIR / BASE_NAME]


def test_build_corpus_escribe_parquet_reproducible(tmp_path: Path) -> None:
    out = tmp_path / "intervenciones.parquet"
    df = build_corpus(FIXTURES_DIR, PARLACAP_FIXTURE, out)
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


def test_verify_md5(tmp_path: Path) -> None:
    path = tmp_path / "f.bin"
    path.write_bytes(b"contenido")
    expected = hashlib.md5(b"contenido").hexdigest()
    assert downloader.verify_md5(path, expected)
    assert not downloader.verify_md5(path, "0" * 32)


def test_manifest_de_la_release() -> None:
    filenames = {remote.filename for remote in downloader.RELEASE_FILES}
    assert filenames == {"ParlaMint-ES.tgz", "ParlaCAP-ES_speeches_no_text.tsv.zip"}
    assert downloader.PARLAMINT_ES_PLAIN.md5 == "2ba1216f3fcf1300ee74f50efe42ec6a"
    assert downloader.PARLACAP_ES_NO_TEXT.md5 == "c7706d1f45f238b7bfdde6a503ee8d49"
    assert all(len(remote.md5) == 32 for remote in downloader.RELEASE_FILES)


def test_download_release_descarga_cada_fichero(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[tuple[str, Path, str | None]] = []

    def _fake_download(
        url: str,
        dest: Path,
        *,
        expected_sha256: str | None = None,
        expected_md5: str | None = None,
        **kwargs: Any,
    ) -> Path:
        calls.append((url, Path(dest), expected_md5))
        return Path(dest)

    monkeypatch.setattr(downloader, "download_file", _fake_download)
    paths = downloader.download_release(tmp_path)
    assert [path.name for path in paths] == [
        "ParlaMint-ES.tgz",
        "ParlaCAP-ES_speeches_no_text.tsv.zip",
    ]
    assert calls[0][2] == downloader.PARLAMINT_ES_PLAIN.md5
    assert calls[1][2] == downloader.PARLACAP_ES_NO_TEXT.md5
    assert all(path.parent == tmp_path for path in paths)


def test_extract_archive_tgz(tmp_path: Path) -> None:
    source = tmp_path / "a.txt"
    source.write_text("hola", encoding="utf-8")
    archive = tmp_path / "x.tgz"
    with tarfile.open(archive, "w:gz") as handle:
        handle.add(source, arcname="a.txt")
    dest = tmp_path / "out"
    downloader.extract_archive(archive, dest)
    assert (dest / "a.txt").read_text(encoding="utf-8") == "hola"


def test_extract_archive_zip(tmp_path: Path) -> None:
    archive = tmp_path / "x.zip"
    with zipfile.ZipFile(archive, "w") as handle:
        handle.writestr("carpeta/b.txt", "adiós")
    dest = tmp_path / "out"
    downloader.extract_archive(archive, dest)
    assert (dest / "carpeta" / "b.txt").read_text(encoding="utf-8") == "adiós"


def test_extract_archive_rechaza_formatos_desconocidos(tmp_path: Path) -> None:
    archive = tmp_path / "x.rar"
    archive.write_bytes(b"nada")
    with pytest.raises(ValueError, match="Formato"):
        downloader.extract_archive(archive, tmp_path / "out")


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


def test_download_file_omite_si_el_md5_coincide(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    dest = tmp_path / "f.bin"
    dest.write_bytes(b"datos")
    expected = hashlib.md5(b"datos").hexdigest()

    def _no_descargar(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("no debería descargar")

    monkeypatch.setattr(downloader.requests, "get", _no_descargar)
    assert downloader.download_file("https://x/f.bin", dest, expected_md5=expected) == dest


def test_download_file_descarga_por_chunks_y_verifica(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(downloader.requests, "get", _fake_get([b"hola ", b"mundo"]))
    dest = tmp_path / "sub" / "f.txt"
    expected = hashlib.sha256(b"hola mundo").hexdigest()
    assert downloader.download_file("https://x/f.txt", dest, expected_sha256=expected) == dest
    assert dest.read_bytes() == b"hola mundo"
    assert not dest.with_name(dest.name + ".part").exists()


def test_download_file_verifica_md5(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(downloader.requests, "get", _fake_get([b"contenido"]))
    dest = tmp_path / "f.bin"
    expected = hashlib.md5(b"contenido").hexdigest()
    downloader.download_file("https://x/f.bin", dest, expected_md5=expected)
    assert dest.read_bytes() == b"contenido"


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
def test_muestra_real_parlamint_descarga_y_parsea(tmp_path: Path) -> None:
    for suffix in ("-meta.tsv", ".txt"):
        downloader.download_file(
            f"{SAMPLE_URL}/{BASE_NAME}{suffix}", tmp_path / f"{BASE_NAME}{suffix}"
        )
    meta = read_meta_tsv(tmp_path / f"{BASE_NAME}-meta.tsv")
    text = read_plain_text(tmp_path / f"{BASE_NAME}.txt")
    df = build_interventions(meta, text, _empty_parlacap())
    _assert_schema(df)
    assert df["date"].between(pd.Timestamp("2015-01-01"), pd.Timestamp("2023-02-23")).all()


@pytest.mark.integration
@integration
def test_corpus_real_calidad(tmp_path: Path) -> None:
    if not PARLAMINT_TXT_DIR.exists() or not PARLACAP_REAL_PATH.exists():
        pytest.skip("corpus real no descargado en data/raw/corpus")
    out = tmp_path / "intervenciones.parquet"
    df = build_corpus(PARLAMINT_TXT_DIR, PARLACAP_REAL_PATH, out)
    assert df["utterance_id"].is_unique
    assert df["date"].between(pd.Timestamp("2015-01-01"), pd.Timestamp("2023-02-23")).all()
    assert len(df) > 10_000
    _assert_schema(df)
    # La presidencia (UNKNOWN por diseño del corpus) no tiene metadatos; entre
    # los intervinientes regulares la cobertura es completa.
    regulares = df[df["speaker_role"] != "Presidencia"]
    assert regulares["speaker_gender"].notna().mean() >= 0.99
    assert df["speaker_gender"].notna().mean() >= 0.55
    assert df["senti_n"].notna().mean() >= 0.99
    assert df["topic"].notna().mean() >= 0.99
