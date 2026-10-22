"""Loads config/settings.yaml. Relative paths in it resolve against the repo root."""
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
SETTINGS_PATH = REPO_ROOT / "config" / "settings.yaml"


def load_settings() -> dict:
    with open(SETTINGS_PATH, encoding="utf-8") as f:
        return yaml.safe_load(f)


def repo_path(p: str | Path) -> Path:
    """Absolute path for a settings value; relative values are taken from the repo root."""
    p = Path(p)
    return p if p.is_absolute() else REPO_ROOT / p
