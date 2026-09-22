"""Pruebas mínimas de configuración y estructura del proyecto."""

from __future__ import annotations

import importlib
from pathlib import Path

from src.utils.config import CONFIG_DIR, DEFAULT_CONFIG_PATH, PROJECT_ROOT, SEED, load_config

DOCUMENTED_MODULES = (
    "src.corpus.downloader",
    "src.corpus.parser",
    "src.preprocessing.cleaner",
    "src.nlp.embeddings",
    "src.nlp.topic_model",
    "src.nlp.sentiment",
    "src.analysis.temporal",
    "src.analysis.regime_change",
    "src.visualization.charts",
)

CONFIG_FILES = ("default.yaml", "experiment_01.yaml", "experiment_02.yaml", "experiment_03.yaml")

CONTRACT_PATHS = (
    "src/__init__.py",
    "src/api/main.py",
    "src/analysis/temporal.py",
    "src/analysis/regime_change.py",
    "src/corpus/downloader.py",
    "src/corpus/parser.py",
    "src/nlp/embeddings.py",
    "src/nlp/topic_model.py",
    "src/nlp/sentiment.py",
    "src/preprocessing/cleaner.py",
    "src/preprocessing/segmenter.py",
    "src/utils/config.py",
    "src/visualization/charts.py",
    "app/app.py",
    "app/components",
    "configs/experiment_01.yaml",
    "configs/experiment_02.yaml",
    "configs/experiment_03.yaml",
    "docs/PROJECT_SPEC.md",
    "docs/DECISIONS.md",
    "docs/SOURCES.md",
    "tests/test_api.py",
    "tests/test_analysis.py",
    "tests/test_corpus.py",
    "tests/test_nlp.py",
    "tests/test_preprocessing.py",
    "tests/test_smoke.py",
    "Dockerfile",
    "compose.yaml",
    "structure.md",
)


def test_seed_is_fixed() -> None:
    assert SEED == 42


def test_default_config_loads() -> None:
    assert DEFAULT_CONFIG_PATH.exists()
    config = load_config()
    assert config["seed"] == SEED


def test_semilla_centralizada_en_todas_las_configs() -> None:
    for name in CONFIG_FILES:
        config = load_config(CONFIG_DIR / name)
        assert config["seed"] == SEED, name


def test_modulos_documentados_tienen_main() -> None:
    for module_name in DOCUMENTED_MODULES:
        module = importlib.import_module(module_name)
        assert callable(getattr(module, "main", None)), module_name


def test_rutas_del_contrato_existen() -> None:
    missing = [name for name in CONTRACT_PATHS if not (PROJECT_ROOT / name).exists()]
    assert not missing


def test_gitignore_protege_datos_y_modelos() -> None:
    content = (PROJECT_ROOT / ".gitignore").read_text(encoding="utf-8")
    assert "data/*" in content
    assert "models/*" in content


def test_fixture_del_mini_corpus_existe() -> None:
    fixture = PROJECT_ROOT / "tests" / "fixtures" / "parlamint_es_mini"
    assert fixture.is_dir()
    assert any(Path(fixture).iterdir())
