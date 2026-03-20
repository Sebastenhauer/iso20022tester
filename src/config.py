import yaml

from src.models.config import AppConfig


def load_config(config_path: str) -> AppConfig:
    """Lädt die Konfiguration aus einer YAML-Datei."""
    with open(config_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return AppConfig(**data)
