"""Descarga verificable del corpus ParlaMint + ParlaCAP y extracción de archivos."""

from __future__ import annotations

import hashlib
import tarfile
import zipfile
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import unquote, urlparse

import requests

from src.utils.config import PROJECT_ROOT

DEFAULT_CHUNK_SIZE = 1 << 20
DEFAULT_TIMEOUT = 60


@dataclass(frozen=True)
class RemoteFile:
    """Fichero remoto de la release, con su MD5 publicado."""

    url: str
    filename: str
    md5: str


PARLAMINT_ES_PLAIN = RemoteFile(
    url=(
        "https://www.clarin.si/repository/xmlui/bitstream/handle/11356/2004/"
        "ParlaMint-ES.tgz?sequence=8&isAllowed=y"
    ),
    filename="ParlaMint-ES.tgz",
    md5="2ba1216f3fcf1300ee74f50efe42ec6a",
)

PARLACAP_ES_NO_TEXT = RemoteFile(
    url="https://data.crossda.hr/api/access/datafile/540",
    filename="ParlaCAP-ES_speeches_no_text.tsv.zip",
    md5="c7706d1f45f238b7bfdde6a503ee8d49",
)

RELEASE_FILES: tuple[RemoteFile, ...] = (PARLAMINT_ES_PLAIN, PARLACAP_ES_NO_TEXT)


def filename_from_url(url: str) -> str:
    """Devuelve el nombre de fichero contenido en la URL."""
    path = urlparse(url).path
    name = unquote(path.rsplit("/", 1)[-1])
    if not name:
        raise ValueError(f"La URL no contiene nombre de fichero: {url}")
    return name


def _file_digest(path: Path, algorithm: str, chunk_size: int = DEFAULT_CHUNK_SIZE) -> str:
    digest = hashlib.new(algorithm)
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(chunk_size), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_sha256(path: Path, expected_sha256: str) -> bool:
    """Comprueba que el SHA-256 del fichero coincide con el esperado."""
    return _file_digest(path, "sha256").lower() == expected_sha256.lower()


def verify_md5(path: Path, expected_md5: str) -> bool:
    """Comprueba que el MD5 del fichero coincide con el esperado."""
    return _file_digest(path, "md5").lower() == expected_md5.lower()


def _hashes_match(
    path: Path,
    expected_sha256: str | None,
    expected_md5: str | None,
) -> bool:
    if expected_sha256 is not None and not verify_sha256(path, expected_sha256):
        return False
    return expected_md5 is None or verify_md5(path, expected_md5)


def download_file(
    url: str,
    dest: Path,
    *,
    expected_sha256: str | None = None,
    expected_md5: str | None = None,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    timeout: int = DEFAULT_TIMEOUT,
) -> Path:
    """Descarga ``url`` en ``dest`` de forma atómica y verificable.

    - Si ``dest`` ya existe y los hashes esperados coinciden, no vuelve a descargar.
    - Escribe primero en ``<dest>.part`` y renombra al terminar, de modo que un
      fallo nunca deja un fichero a medias en su ubicación final.
    - Si algo falla, elimina el fichero parcial y propaga la excepción.
    """
    if dest.exists() and _hashes_match(dest, expected_sha256, expected_md5):
        return dest

    dest.parent.mkdir(parents=True, exist_ok=True)
    part = dest.with_name(dest.name + ".part")
    try:
        with requests.get(url, stream=True, timeout=timeout) as response:
            response.raise_for_status()
            with part.open("wb") as handle:
                for chunk in response.iter_content(chunk_size=chunk_size):
                    if chunk:
                        handle.write(chunk)
        if not _hashes_match(part, expected_sha256, expected_md5):
            raise ValueError(f"El hash de {part.name} no coincide con el esperado")
        part.replace(dest)
    except BaseException:
        part.unlink(missing_ok=True)
        raise
    return dest


def download_release(dest_root: Path) -> list[Path]:
    """Descarga todos los ficheros de la release en ``dest_root``."""
    dest_root.mkdir(parents=True, exist_ok=True)
    return [
        download_file(remote.url, dest_root / remote.filename, expected_md5=remote.md5)
        for remote in RELEASE_FILES
    ]


def extract_archive(path: Path, dest: Path) -> Path:
    """Extrae un ``.tgz``/``.tar.gz`` o ``.zip`` en ``dest``."""
    dest.mkdir(parents=True, exist_ok=True)
    name = path.name.lower()
    if name.endswith(".zip"):
        with zipfile.ZipFile(path) as handle:
            handle.extractall(dest)
    elif name.endswith((".tgz", ".tar.gz")):
        with tarfile.open(path) as handle:
            handle.extractall(dest, filter="data")
    else:
        raise ValueError(f"Formato de archivo no soportado: {path.name}")
    return dest


def main() -> None:
    """CLI: descarga y extrae la release en ``data/raw/corpus``."""
    dest = PROJECT_ROOT / "data" / "raw" / "corpus"
    for archive in download_release(dest):
        print(f"descargado: {archive}")
        extract_archive(archive, dest)
        print(f"extraído en: {dest}")


if __name__ == "__main__":
    main()
