# jdr_engine/compendium/paths.py
"""Chemins vers le Compendium à la racine du projet."""
from pathlib import Path


def get_project_root() -> Path:
    return Path(__file__).resolve().parent.parent.parent


def get_compendium_root() -> Path:
    return get_project_root() / "compendium"


def get_ruleset_path(ruleset_id: str) -> Path:
    return get_compendium_root() / ruleset_id
