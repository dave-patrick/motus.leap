"""Configuration loader."""


import os
from pathlib import Path

import yaml


DEFAULT_CONFIG_PATH = Path(__file__).resolve().parent.parent / "config.example.yaml"


def load(path: Path | None = None):
    target = path or Path(os.getenv("TUBE_MANAGER_CONFIG", DEFAULT_CONFIG_PATH))
    with open(target, "r", encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}
