# jdr_engine/rules/spellcasting/starting_spells.py
"""Sorts de départ — lanceurs complets (niv. 1) & demi-lanceurs (rôdeur / paladin)."""

from __future__ import annotations

from jdr_engine.rules.spellcasting.preparation import (
    build_bard_spellcasting,
    build_cleric_spellcasting,
    build_druid_spellcasting,
    build_paladin_spellcasting,
    build_ranger_spellcasting,
    build_sorcerer_spellcasting,
    build_warlock_spellcasting,
    build_wizard_spellcasting,
    upgrade_bard_spellcasting,
    upgrade_cleric_spellcasting,
    upgrade_druid_spellcasting,
    upgrade_paladin_spellcasting,
    upgrade_ranger_spellcasting,
    upgrade_sorcerer_spellcasting,
    upgrade_warlock_spellcasting,
    upgrade_wizard_spellcasting,
)
from jdr_engine.rules.spellcasting.spells_catalog import (
    FULL_CASTER_CLASSES,
    HALF_CASTER_CLASSES,
    PACT_CASTER_CLASSES,
    SUPPORTED_SPELLCASTING_CLASSES,
)


def build_starting_spellcasting(
    class_id: str,
    *,
    level: int = 1,
    casting_ability_mod: int = 0,
    domain_id: str | None = None,
) -> dict:
    """
    État spellcasting initial.

    Lanceurs complets : niv. 1. Demi-lanceurs : sorts visibles dès niv. 1 (sans emplacements).
    """
    if class_id not in SUPPORTED_SPELLCASTING_CLASSES:
        return {}

    if class_id == "bard":
        return build_bard_spellcasting(level)

    if class_id == "cleric":
        return build_cleric_spellcasting(
            level,
            wis_mod=casting_ability_mod,
            domain_id=domain_id,
        )

    if class_id == "wizard":
        return build_wizard_spellcasting(level, int_mod=casting_ability_mod)

    if class_id == "sorcerer":
        return build_sorcerer_spellcasting(level)

    if class_id == "druid":
        return build_druid_spellcasting(level, wis_mod=casting_ability_mod)

    if class_id == "warlock":
        return build_warlock_spellcasting(level)

    if class_id == "ranger":
        return build_ranger_spellcasting(level, wis_mod=casting_ability_mod)

    if class_id == "paladin":
        return build_paladin_spellcasting(level, cha_mod=casting_ability_mod)

    if class_id in FULL_CASTER_CLASSES:
        return {}

    return {}


def upgrade_half_caster_spellcasting(
    choices: dict,
    class_id: str,
    *,
    new_level: int,
    casting_ability_mod: int = 0,
) -> dict:
    """Met à jour les sorts préparés d'un demi-lanceur après montée de niveau."""
    if class_id not in HALF_CASTER_CLASSES or new_level < 1:
        return choices

    if class_id == "ranger":
        return upgrade_ranger_spellcasting(
            choices,
            new_level=new_level,
            wis_mod=casting_ability_mod,
        )
    if class_id == "paladin":
        return upgrade_paladin_spellcasting(
            choices,
            new_level=new_level,
            cha_mod=casting_ability_mod,
        )
    return choices


def upgrade_full_caster_spellcasting(
    choices: dict,
    class_id: str,
    *,
    new_level: int,
    casting_ability_mod: int = 0,
    domain_id: str | None = None,
) -> dict:
    if class_id == "bard":
        return upgrade_bard_spellcasting(choices, new_level=new_level)
    if class_id == "cleric":
        return upgrade_cleric_spellcasting(
            choices,
            new_level=new_level,
            wis_mod=casting_ability_mod,
            domain_id=domain_id,
        )
    if class_id == "wizard":
        return upgrade_wizard_spellcasting(
            choices,
            new_level=new_level,
            int_mod=casting_ability_mod,
        )
    if class_id == "sorcerer":
        return upgrade_sorcerer_spellcasting(choices, new_level=new_level)
    if class_id == "druid":
        return upgrade_druid_spellcasting(
            choices,
            new_level=new_level,
            wis_mod=casting_ability_mod,
        )
    return choices


def upgrade_pact_caster_spellcasting(
    choices: dict,
    class_id: str,
    *,
    new_level: int,
    old_level: int,
) -> dict:
    if class_id == "warlock":
        return upgrade_warlock_spellcasting(
            choices, new_level=new_level, old_level=old_level
        )
    return choices


def init_half_caster_spellcasting_if_needed(
    choices: dict,
    class_id: str,
    *,
    level: int,
    casting_ability_mod: int = 0,
) -> dict:
    """Initialise ou met à jour spellcasting demi-lanceur."""
    if class_id not in HALF_CASTER_CLASSES or level < 1:
        return choices
    if choices.get("spellcasting"):
        return upgrade_half_caster_spellcasting(
            choices,
            class_id,
            new_level=level,
            casting_ability_mod=casting_ability_mod,
        )
    sc = build_starting_spellcasting(
        class_id,
        level=level,
        casting_ability_mod=casting_ability_mod,
    )
    if sc:
        return {**choices, "spellcasting": sc}
    return choices
