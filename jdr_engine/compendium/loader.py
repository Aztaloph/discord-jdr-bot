# jdr_engine/compendium/loader.py
"""Charge manifest, config et entries depuis le disque."""
from __future__ import annotations

import logging
from pathlib import Path

import yaml

from jdr_engine.compendium.entry import CompendiumEntry
from jdr_engine.compendium.paths import get_ruleset_path
from jdr_engine.compendium.schemas import (
    DefinitionSchema,
    ENTRY_TYPE_PLURAL_TO_SINGULAR,
    RulesetConfig,
    RulesetManifest,
)

logger = logging.getLogger(__name__)


class CompendiumLoadError(Exception):
    """Erreur de chargement du Compendium."""


def _load_yaml(path: Path) -> dict:
    if not path.exists():
        raise CompendiumLoadError(f"Fichier introuvable : {path}")
    with open(path, "r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle)
    if not isinstance(data, dict):
        raise CompendiumLoadError(f"YAML invalide (dict attendu) : {path}")
    return data


def load_manifest(ruleset_id: str, base_path: Path | None = None) -> RulesetManifest:
    root = base_path or get_ruleset_path(ruleset_id)
    return RulesetManifest.model_validate(_load_yaml(root / "manifest.yaml"))


def load_config(ruleset_id: str, base_path: Path | None = None) -> RulesetConfig:
    root = base_path or get_ruleset_path(ruleset_id)
    return RulesetConfig.model_validate(_load_yaml(root / "config.yaml"))


def load_definition(definition_path: Path) -> DefinitionSchema:
    raw = _load_yaml(definition_path)
    definition = DefinitionSchema.model_validate(raw)
    definition.validate_mechanics_typed()
    return definition


def load_entries(
    ruleset_id: str,
    base_path: Path | None = None,
    entry_types: list[str] | None = None,
) -> list[CompendiumEntry]:
    """
    Scanne compendium/{ruleset}/entries/{type}/{id}/definition.yaml
    """
    root = base_path or get_ruleset_path(ruleset_id)
    entries_dir = root / "entries"
    if not entries_dir.is_dir():
        raise CompendiumLoadError(f"Dossier entries/ introuvable : {entries_dir}")

    types_to_scan = entry_types or list(ENTRY_TYPE_PLURAL_TO_SINGULAR.keys())
    entries: list[CompendiumEntry] = []

    for plural_type in types_to_scan:
        type_dir = entries_dir / plural_type
        if not type_dir.is_dir():
            continue
        expected_singular = ENTRY_TYPE_PLURAL_TO_SINGULAR.get(plural_type)
        if expected_singular is None:
            logger.warning("Type de dossier non reconnu ignoré : %s", plural_type)
            continue

        for entry_dir in sorted(type_dir.iterdir()):
            if not entry_dir.is_dir():
                continue
            definition_path = entry_dir / "definition.yaml"
            if not definition_path.exists():
                logger.warning("definition.yaml manquant : %s", entry_dir)
                continue

            try:
                definition = load_definition(definition_path)
            except Exception as exc:
                raise CompendiumLoadError(
                    f"Erreur definition {definition_path}: {exc}"
                ) from exc

            if definition.type != expected_singular:
                raise CompendiumLoadError(
                    f"{definition_path}: type={definition.type!r} "
                    f"≠ attendu {expected_singular!r} pour dossier {plural_type}/"
                )
            if definition.id != entry_dir.name:
                raise CompendiumLoadError(
                    f"{definition_path}: id={definition.id!r} "
                    f"≠ nom dossier {entry_dir.name!r}"
                )

            entries.append(
                CompendiumEntry(
                    ruleset_id=ruleset_id,
                    entity_type=expected_singular,
                    plural_type=plural_type,
                    entry_id=definition.id,
                    definition=definition,
                    entry_dir=entry_dir,
                )
            )

    logger.info(
        "Compendium %s : %d entrée(s) chargée(s)", ruleset_id, len(entries)
    )
    return entries


def load_ruleset(
    ruleset_id: str,
    base_path: Path | None = None,
) -> tuple[RulesetManifest, RulesetConfig, list[CompendiumEntry]]:
    """Charge manifest + config + toutes les entries d'un ruleset."""
    root = base_path or get_ruleset_path(ruleset_id)
    manifest = load_manifest(ruleset_id, root)
    if manifest.id != ruleset_id:
        raise CompendiumLoadError(
            f"manifest.id={manifest.id!r} ≠ ruleset demandé {ruleset_id!r}"
        )
    config = load_config(ruleset_id, root)
    entries = load_entries(
        ruleset_id,
        root,
        entry_types=manifest.entry_types or None,
    )
    return manifest, config, entries
