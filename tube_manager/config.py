"""Configuration loader."""
from __future__ import annotations

import os
from pathlib import Path

import yaml


DEFAULT_CONFIG_PATH = str(
    Path(__file__).resolve().parent.parent / "config.example.yaml"
)


def load(path=None):
    target = path or os.getenv("TUBE_MANAGER_CONFIG", DEFAULT_CONFIG_PATH)
    with open(target, "r", encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}
