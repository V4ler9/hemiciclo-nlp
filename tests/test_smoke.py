"""Pruebas mínimas de configuración y estructura del proyecto."""

from src.utils.config import DEFAULT_CONFIG_PATH, SEED, load_config


def test_seed_is_fixed() -> None:
    assert SEED == 42


def test_default_config_loads() -> None:
    assert DEFAULT_CONFIG_PATH.exists()
    config = load_config()
    assert config["seed"] == SEED
