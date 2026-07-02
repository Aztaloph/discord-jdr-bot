# jdr_engine/compendium/mechanics_schema.py
"""Validation JSON Schema des sections mechanics (race / class)."""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError

from jdr_engine.compendium.paths import get_compendium_root


class MechanicsSchemaError(Exception):
    """Erreur de chargement ou validation JSON Schema."""


@lru_cache(maxsize=1)
def _schemas_dir() -> Path:
    return get_compendium_root() / "schemas"


@lru_cache(maxsize=2)
def _load_validator(schema_name: str) -> Draft202012Validator:
    path = _schemas_dir() / schema_name
    if not path.exists():
        raise MechanicsSchemaError(f"Schéma introuvable : {path}")
    with open(path, "r", encoding="utf-8") as handle:
        schema = json.load(handle)
    try:
        Draft202012Validator.check_schema(schema)
    except SchemaError as exc:
        raise MechanicsSchemaError(f"Schéma invalide {path}: {exc}") from exc
    return Draft202012Validator(schema)


def validate_race_mechanics(mechanics: dict) -> list[str]:
    validator = _load_validator("race-mechanics.schema.json")
    errors = sorted(validator.iter_errors(mechanics), key=lambda e: list(e.path))
    return [f"{list(e.path)}: {e.message}" if e.path else e.message for e in errors]


def validate_class_mechanics(mechanics: dict) -> list[str]:
    validator = _load_validator("class-mechanics.schema.json")
    errors = sorted(validator.iter_errors(mechanics), key=lambda e: list(e.path))
    return [f"{list(e.path)}: {e.message}" if e.path else e.message for e in errors]


def validate_entry_mechanics(entity_type: str, mechanics: dict) -> list[str]:
    if entity_type == "race":
        return validate_race_mechanics(mechanics)
    if entity_type == "class":
        return validate_class_mechanics(mechanics)
    return []
