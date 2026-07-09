# jdr_engine/rules/spellcasting/autocomplete_availability.py
"""
États de disponibilité pour l'autocomplete /sort — libellés emoji (Discord).

Priorité : niveau/emplacement insuffisant (🔒) > non préparé (📘) > castable (✨).
"""
from __future__ import annotations

from enum import Enum

from jdr_engine.domain.character.character import Character
from jdr_engine.rules.engine import RuleEngine
from jdr_engine.rules.spellcasting.access import spellcasting_start_level
from jdr_engine.rules.spellcasting.model import SpellcastingFamily, get_spellcasting_family
from jdr_engine.rules.spellcasting.pools import get_filtered_leveled_pool, get_leveled_spell_pool
from jdr_engine.rules.spellcasting.slots import get_max_spell_slots, get_remaining_slots
from jdr_engine.rules.spellcasting.spell_levels import get_spell_level
from jdr_engine.rules.spellcasting.spells_catalog import HALF_CASTER_CLASSES
from jdr_engine.rules.spellcasting.state import (
    _effective_known_leveled_spells,
    _effective_prepared_leveled_spells,
    get_bonus_spell_ids,
    get_cantrips_known,
    get_domain_spells,
    get_spellbook,
    get_spellcasting_state,
    get_spells_prepared_list,
    get_slots_used,
    list_spell_autocomplete_ids,
)

DISCORD_AUTOCOMPLETE_NAME_MAX = 100


class SpellAutocompleteAvailability(str, Enum):
    CASTABLE = "castable"
    LEVEL_INSUFFICIENT = "level_insufficient"
    NOT_PREPARED = "not_prepared"


def list_autocomplete_spell_ids(
    character: Character,
    *,
    engine: RuleEngine | None = None,
) -> list[str]:
    """
    Sorts proposables dans l'autocomplete /sort (ids), avec visibilité élargie.

    Demi-lanceurs : catalogue de classe filtré par niveau d'emplacement (niv. 1 :
    catalogue complet visible, marqué 🔒).
    Magicien : grimoire + cantrips (inchangé).
    Autres : ``list_spell_autocomplete_ids`` existant.
    """
    cantrips = get_cantrips_known(character)
    if character.class_id == "wizard":
        return list(dict.fromkeys(cantrips + get_spellbook(character)))

    if character.class_id in HALF_CASTER_CLASSES:
        if character.level < 2 or not get_max_spell_slots(
            character.class_id, character.level
        ):
            leveled = list(get_leveled_spell_pool(character.class_id))
        else:
            leveled = get_filtered_leveled_pool(
                character.class_id, character.level, engine=engine
            )
        castable_leveled = [
            spell_id
            for spell_id in _effective_prepared_leveled_spells(
                get_spellcasting_state(character)
            )
            if spell_id not in cantrips
        ]
        merged = list(dict.fromkeys(leveled + castable_leveled))
        return list(dict.fromkeys(cantrips + merged))

    return list_spell_autocomplete_ids(character)


def _is_spell_prepared_for_cast(character: Character, spell_id: str) -> bool:
    if spell_id in get_cantrips_known(character):
        return True
    if spell_id in get_bonus_spell_ids(character):
        return True
    if character.class_id == "cleric" and spell_id in get_domain_spells(character):
        return True

    state = get_spellcasting_state(character)
    family = get_spellcasting_family(character.class_id)

    if family == SpellcastingFamily.WIZARD_HYBRID:
        return spell_id in get_spells_prepared_list(character)
    if family == SpellcastingFamily.PREPARED:
        return spell_id in _effective_prepared_leveled_spells(state)
    if family == SpellcastingFamily.KNOWN_FIXED:
        return spell_id in _effective_known_leveled_spells(state)
    return False


def _level_insufficient_reason(
    character: Character,
    spell_level: int,
    *,
    engine: RuleEngine,
) -> str:
    if spell_level <= 0:
        return ""

    if character.class_id in HALF_CASTER_CLASSES:
        start_level = spellcasting_start_level(engine, character.class_id)
        if character.level < start_level:
            return f"niv. {start_level} requis"

    max_slots = get_max_spell_slots(character.class_id, character.level)
    if not max_slots or not any(slot_lvl >= spell_level for slot_lvl in max_slots):
        return f"niv. {spell_level} requis"

    remaining = get_remaining_slots(
        character.class_id, character.level, get_slots_used(character)
    )
    if not any(
        rem > 0 and slot_lvl >= spell_level
        for slot_lvl, rem in remaining.items()
    ):
        min_slot = min(
            (slot_lvl for slot_lvl in max_slots if slot_lvl >= spell_level),
            default=spell_level,
        )
        return f"niv. {min_slot} requis"

    return f"niv. {spell_level} requis"


def _is_level_insufficient(
    character: Character,
    spell_level: int,
    *,
    engine: RuleEngine,
) -> bool:
    if spell_level <= 0:
        return False

    if character.class_id in HALF_CASTER_CLASSES:
        if character.level < spellcasting_start_level(engine, character.class_id):
            return True

    max_slots = get_max_spell_slots(character.class_id, character.level)
    if spell_level not in max_slots and not any(
        slot_lvl >= spell_level for slot_lvl in max_slots
    ):
        return True

    remaining = get_remaining_slots(
        character.class_id, character.level, get_slots_used(character)
    )
    return not any(
        rem > 0 and slot_lvl >= spell_level
        for slot_lvl, rem in remaining.items()
    )


def compute_spell_autocomplete_availability(
    character: Character,
    spell_id: str,
    *,
    engine: RuleEngine,
    spell_level: int | None = None,
) -> tuple[SpellAutocompleteAvailability, str | None]:
    """
    Détermine l'état autocomplete d'un sort.

    Retourne ``(état, suffixe niveau)`` — suffixe uniquement pour ``LEVEL_INSUFFICIENT``.
    """
    level = (
        spell_level
        if spell_level is not None
        else get_spell_level(spell_id, engine=engine)
    )

    if level <= 0:
        return SpellAutocompleteAvailability.CASTABLE, None

    if _is_level_insufficient(character, level, engine=engine):
        return (
            SpellAutocompleteAvailability.LEVEL_INSUFFICIENT,
            _level_insufficient_reason(character, level, engine=engine),
        )

    if not _is_spell_prepared_for_cast(character, spell_id):
        return SpellAutocompleteAvailability.NOT_PREPARED, None

    return SpellAutocompleteAvailability.CASTABLE, None


def format_autocomplete_choice_name(
    display_name: str,
    spell_id: str,
    availability: SpellAutocompleteAvailability,
    *,
    level_reason: str | None = None,
    max_length: int = DISCORD_AUTOCOMPLETE_NAME_MAX,
) -> str:
    """Libellé Discord (emoji + texte brut, ≤ 100 caractères)."""
    id_part = f"({spell_id})"
    if availability == SpellAutocompleteAvailability.CASTABLE:
        prefix, suffix = "✨ ", ""
    elif availability == SpellAutocompleteAvailability.LEVEL_INSUFFICIENT:
        prefix = "🔒 "
        suffix = f" — {level_reason or 'niv. requis'}"
    else:
        prefix = "📘 "
        suffix = " — non préparé"

    name = f"{prefix}{display_name} {id_part}{suffix}"
    if len(name) <= max_length:
        return name

    fixed_len = len(prefix) + len(suffix) + len(id_part) + 1
    budget = max_length - fixed_len
    if budget < 1:
        return (prefix + id_part + suffix)[:max_length]

    truncated = display_name[:budget].rstrip()
    if len(truncated) < len(display_name):
        if budget >= 2:
            truncated = truncated[: budget - 1].rstrip(" .") + "…"
        else:
            truncated = truncated[:budget]
    result = f"{prefix}{truncated} {id_part}{suffix}"
    return result[:max_length]
