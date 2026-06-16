"""Database configuration loaded from configs/config.yaml."""

from __future__ import annotations

import os
from pathlib import Path

import yaml

_REPO_ROOT = Path(__file__).resolve().parents[2]
_CONFIG_PATH = _REPO_ROOT / "configs" / "config.yaml"


def repo_root() -> Path:
    return _REPO_ROOT


def load_config() -> dict:
    with _CONFIG_PATH.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def database_config() -> dict:
    return load_config().get("database", {})


def credentials_path() -> Path:
    db_cfg = database_config()
    rel_path = db_cfg.get("credentials_file", "configs/security_key.json")
    return (_REPO_ROOT / rel_path).resolve()


def number_of_tables() -> int:
    return int(database_config().get("number_of_tables", 5))


def collection_name(key: str) -> str:
    collections = database_config().get("collections", {})
    return collections.get(key, key)
