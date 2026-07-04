# jdr_engine/rules/racial/resolve.py
"""Résolution traits raciaux — choix joueur + compendium."""
from __future__ import annotations

from typing import Any

from jdr_engine.compendium.entry import CompendiumEntry
from jdr_engine.domain.character.character import Character
from jdr_engine.rules.racial.draconic_ancestry import get_draconic_ancestry

HALF_ELF_FLEXIBLE_ABILITIES: tuple[str, ...] = ("str", "dex", "con", "int", "wis")

DAMAGE_TYPE_LABELS_FR: dict[str, str] = {
    "acid": "acide",
    "cold": "froid",
    "fire": "feu",
    "lightning": "foudre",
    "poison": "poison",
}


def get_draconic_ancestry_id(character: Character) -> str | None:
    raw = (character.choices or {}).get("draconic_ancestry")
    if raw is None:
        return None
    text = str(raw).strip().lower()
    return text or None


def get_racial_ability_bonuses(character: Character, engine: RuleEngine) -> dict[str, int]:
    """Bonus raciaux statiques + choix Demi-elfe."""
    bonuses = dict(engine.get_ability_bonuses(character.race_id))
    if character.race_id == "half_elf":
        for ability_id in (character.choices or {}).get("racial_ability_bonuses") or []:
            aid = str(ability_id).strip().lower()
            if aid in HALF_ELF_FLEXIBLE_ABILITIES:
                bonuses[aid] = bonuses.get(aid, 0) + 1
    return bonuses


def get_racial_skill_ids(character: Character) -> tuple[str, ...]:
    """Compétences raciales (Demi-elfe : 2 au choix)."""
    raw = (character.choices or {}).get("racial_skills") or []
    if not isinstance(raw, list):
        return ()
    return tuple(str(s) for s in raw if s)


def get_damage_resistances(character: Character) -> tuple[str, ...]:
    """Résistances aux dégâts actives (Drakéide, Tieffelin)."""
    resistances: list[str] = []
    if character.race_id == "tiefling":
        resistances.append("fire")
    if character.race_id == "dragonborn":
        color_id = get_draconic_ancestry_id(character)
        if color_id:
            ancestry = get_draconic_ancestry(color_id)
            if ancestry and ancestry.resistance not in resistances:
                resistances.append(ancestry.resistance)
    return tuple(resistances)


def get_innate_spells_state(character: Character) -> dict[str, Any]:
    """État sorts innés raciaux (Tieffelin — Legs infernal)."""
    raw = (character.choices or {}).get("innate_spells")
    return dict(raw) if isinstance(raw, dict) else {}


def resolve_race_traits(
    character: Character,
    engine: RuleEngine,
) -> list[CompendiumEntry]:
    """Traits raciaux effectifs (race + ascendance draconique)."""
    traits = list(engine.get_race_traits(character.race_id))
    if character.race_id == "dragonborn":
        color_id = get_draconic_ancestry_id(character)
        if color_id:
            breath = engine.get_entity("trait", "breath_weapon")
            if breath is not None:
                traits.append(breath)
            resistance_trait = engine.get_entity("trait", "draconic_damage_resistance")
            if resistance_trait is not None:
                traits.append(resistance_trait)
    return traits


def resolve_race_trait_labels(
    character: Character,
    engine: RuleEngine,
    *,
    locale: str = "fr",
) -> list[str]:
    """Libellés traits pour affichage fiche (ascendance draconique incluse)."""
    default_locale = engine.registry.manifest.default_locale
    ancestry = None
    if character.race_id == "dragonborn":
        color_id = get_draconic_ancestry_id(character)
        if color_id:
            ancestry = get_draconic_ancestry(color_id)

    labels: list[str] = []
    for trait in resolve_race_traits(character, engine):
        name = trait.get_name(locale, default_locale)
        if trait.entry_id == "draconic_ancestry" and ancestry is not None:
            name = f"{name} ({ancestry.label_fr})"
        labels.append(name)
    return labels


def format_resistances_display(resistances: tuple[str, ...]) -> str:
    if not resistances:
        return ""
    labels = [DAMAGE_TYPE_LABELS_FR.get(r, r) for r in resistances]
    return ", ".join(labels)


def format_innate_spells_display(
    character: Character,
    engine: RuleEngine,
    *,
    locale: str = "fr",
) -> str:
    """Texte sorts innés Tieffelin selon niveau."""
    if character.race_id != "tiefling":
        return ""
    state = get_innate_spells_state(character)
    cantrips = state.get("cantrips") or ["thaumaturgy"]
    parts: list[str] = []
    default_locale = engine.registry.manifest.default_locale
    for spell_id in cantrips:
        name = engine.get_display_name("spell", str(spell_id), locale=locale) or spell_id
        parts.append(f"{name} (tour de magie)")
    if character.level >= 3:
        for spell_id in state.get("spells_level_3") or ["hellish_rebuke"]:
            name = engine.get_display_name("spell", str(spell_id), locale=locale) or spell_id
            parts.append(f"{name} (1/repos long, niv. 3+)")
    if character.level >= 5:
        for spell_id in state.get("spells_level_5") or ["darkness"]:
            name = engine.get_display_name("spell", str(spell_id), locale=locale) or spell_id
            parts.append(f"{name} (1/repos long, niv. 5+)")
    return " · ".join(parts)


def build_tiefling_innate_spells() -> dict[str, Any]:
    return {
        "cantrips": ["thaumaturgy"],
        "spells_level_3": ["hellish_rebuke"],
        "spells_level_5": ["darkness"],
        "uses": {},
    }
