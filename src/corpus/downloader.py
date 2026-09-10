"""Descarga verificable de ficheros del corpus ParlaMint."""

from __future__ import annotations

import hashlib
from pathlib import Path
from urllib.parse import unquote, urlparse

import requests

DEFAULT_CHUNK_SIZE = 1 << 20
DEFAULT_TIMEOUT = 60


def filename_from_url(url: str) -> str:
    """Devuelve el nombre de fichero contenido en la URL."""
    path = urlparse(url).path
    name = unquote(path.rsplit("/", 1)[-1])
    if not name:
        raise ValueError(f"La URL no contiene nombre de fichero: {url}")
    return name


def _file_digest(path: Path, chunk_size: int = DEFAULT_CHUNK_SIZE) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(chunk_size), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_sha256(path: Path, expected_sha256: str) -> bool:
    """Comprueba que el SHA-256 del fichero coincide con el esperado."""
    return _file_digest(path).lower() == expected_sha256.lower()


def download_file(
    url: str,
    dest: Path,
    *,
    expected_sha256: str | None = None,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    timeout: int = DEFAULT_TIMEOUT,
) -> Path:
    """Descarga ``url`` en ``dest`` de forma atómica y verificable.

    - Si ``dest`` ya existe y no hay hash esperado (o coincide), no vuelve a
      descargar.
    - Escribe primero en ``<dest>.part`` y renombra al terminar, de modo que un
      fallo nunca deja un fichero a medias en su ubicación final.
    - Si algo falla, elimina el fichero parcial y propaga la excepción.
    """
    if dest.exists() and (expected_sha256 is None or verify_sha256(dest, expected_sha256)):
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
        if expected_sha256 is not None and not verify_sha256(part, expected_sha256):
            raise ValueError(f"El hash de {part.name} no coincide con el esperado")
        part.replace(dest)
    except BaseException:
        part.unlink(missing_ok=True)
        raise
    return dest
