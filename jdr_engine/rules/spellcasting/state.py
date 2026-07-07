# jdr_engine/rules/spellcasting/state.py
"""État persistant emplacements / grimoire (character.choices.spellcasting)."""
from __future__ import annotations

from typing import Any

from jdr_engine.domain.character.character import Character
from jdr_engine.domain.character.choices_schema import get_specialization_id
from jdr_engine.rules.spellcasting.slots import get_max_spell_slots, get_remaining_slots


class SpellcastingStateError(Exception):
    pass


def get_spellcasting_state(character: Character) -> dict[str, Any]:
    """Lit choices.spellcasting (dict vide si absent)."""
    raw = (character.choices or {}).get("spellcasting")
    return dict(raw) if isinstance(raw, dict) else {}


def get_slots_used(character: Character) -> dict[int, int]:
    state = get_spellcasting_state(character)
    used = state.get("slots_used") or {}
    if not isinstance(used, dict):
        return {}
    return {int(k): int(v) for k, v in used.items()}


def get_cantrips_known(character: Character) -> list[str]:
    state = get_spellcasting_state(character)
    raw = state.get("cantrips_known") or []
    return [str(s) for s in raw] if isinstance(raw, list) else []


def get_domain_spells(character: Character) -> list[str]:
    state = get_spellcasting_state(character)
    raw = state.get("domain_spells") or []
    return [str(s) for s in raw] if isinstance(raw, list) else []


def get_spellbook(character: Character) -> list[str]:
    """Grimoire du magicien — sorts appris (niv. 1+)."""
    state = get_spellcasting_state(character)
    raw = state.get("spellbook") or state.get("spells_known") or []
    return [str(s) for s in raw] if isinstance(raw, list) else []


def get_spells_prepared_list(character: Character) -> list[str]:
    """Sorts préparés explicites (clerc) — hors domaine et cantrips."""
    state = get_spellcasting_state(character)
    raw = state.get("spells_prepared") or []
    return [str(s) for s in raw] if isinstance(raw, list) else []


def get_spells_known(character: Character) -> list[str]:
    """
    Sorts niv. 1+ connus ou préparés (lançables si emplacement dispo).

    Clerc : préparés + domaine. Ensorceleur/Barde : spells_known.
    Magicien : sorts préparés uniquement (grimoire séparé).
    """
    state = get_spellcasting_state(character)
    if character.class_id == "cleric":
        prepared = get_spells_prepared_list(character)
        domain = get_domain_spells(character)
        return list(dict.fromkeys(prepared + domain))
    if character.class_id == "wizard":
        return get_spells_prepared_list(character)
    raw = state.get("spells_known") or state.get("spells_prepared") or []
    return [str(s) for s in raw] if isinstance(raw, list) else []


def get_spells_prepared(character: Character) -> list[str]:
    """Alias — voir ``get_spells_known``."""
    return get_spells_known(character)


def spell_is_known(character: Character, spell_id: str) -> bool:
    """True si le personnage peut lancer ce sort (tour de magie ou préparé/connu)."""
    if spell_id in get_cantrips_known(character):
        return True
    if character.class_id == "cleric":
        if spell_id in get_domain_spells(character):
            return True
        return spell_id in get_spells_prepared_list(character)
    if character.class_id == "wizard":
        return spell_id in get_spells_prepared_list(character)
    if spell_id in get_domain_spells(character):
        return True
    return spell_id in get_spells_known(character)


def spell_in_spellbook(character: Character, spell_id: str) -> bool:
    if character.class_id != "wizard":
        return spell_is_known(character, spell_id)
    return spell_id in get_spellbook(character)


def spell_is_available(character: Character, spell_id: str) -> bool:
    return spell_is_known(character, spell_id)


def list_castable_spell_ids(character: Character) -> list[str]:
    """Tours de magie + sorts lançables (liste pour /sort et autocomplete)."""
    return list(
        dict.fromkeys(
            get_cantrips_known(character) + get_spells_known(character)
        )
    )


def list_spell_autocomplete_ids(character: Character) -> list[str]:
    """
    Sorts proposables dans l'autocomplete /sort.

    Magicien : grimoire + cantrips (visibilité complète ; le lancement exige
    la préparation via ``cast_spell``).
    """
    if character.class_id == "wizard":
        return list(
            dict.fromkeys(
                get_cantrips_known(character) + get_spellbook(character)
            )
        )
    return list_castable_spell_ids(character)


def consume_spell_slot(character: Character, spell_level: int) -> Character:
    """
    Consomme un emplacement de niveau ``spell_level`` (ou supérieur si épuisé).

    SRD : lancer un sort de niv. X consomme un slot de niv. X (ou supérieur).
    """
    if spell_level <= 0:
        return character

    max_slots = get_max_spell_slots(character.class_id, character.level)
    used = get_slots_used(character)

    slot_to_use = _find_slot_to_consume(spell_level, max_slots, used)
    if slot_to_use is None:
        raise SpellcastingStateError(
            f"Aucun emplacement de sort niv. {spell_level}+ disponible."
        )

    used[slot_to_use] = used.get(slot_to_use, 0) + 1
    return _update_spellcasting(character, slots_used=used)


def _find_slot_to_consume(
    spell_level: int,
    max_slots: dict[int, int],
    used: dict[int, int],
) -> int | None:
    for level in sorted(max_slots.keys()):
        if level < spell_level:
            continue
        remaining = max_slots[level] - used.get(level, 0)
        if remaining > 0:
            return level
    return None


def reset_spell_slots(character: Character) -> Character:
    """Repos long — réinitialise slots_used."""
    return _update_spellcasting(character, slots_used={})


def _update_spellcasting(
    character: Character,
    *,
    slots_used: dict[int, int] | None = None,
) -> Character:
    choices = dict(character.choices or {})
    state = get_spellcasting_state(character)
    if slots_used is not None:
        state["slots_used"] = {str(k): v for k, v in slots_used.items()}
    choices["spellcasting"] = state
    character.choices = choices
    return character


def format_slots_display(character: Character) -> str:
    """Texte compact pour embed Discord."""
    max_slots = get_max_spell_slots(character.class_id, character.level)
    if not max_slots:
        return "Aucun emplacement (non-lanceur ou niv. > 3)"
    used = get_slots_used(character)
    remaining = get_remaining_slots(character.class_id, character.level, used)
    parts = []
    for level in sorted(max_slots.keys()):
        parts.append(f"niv.{level}: {remaining[level]}/{max_slots[level]}")
    slots_text = ", ".join(parts)
    if character.class_id == "warlock":
        return f"{slots_text} (recharge repos court)"
    return slots_text


def format_spellcasting_detail(character: Character) -> str:
    """Résumé cantrips + sorts pour fiche personnage."""
    from jdr_engine.domain.character.ability_scores import ability_modifier
    from jdr_engine.rules.spellcasting.preparation import (
        cleric_prepared_capacity,
        druid_prepared_capacity,
    )

    cantrips = get_cantrips_known(character)
    known = get_spells_known(character)
    slots = format_slots_display(character)
    lines: list[str] = []
    if character.class_id == "warlock":
        lines.append(f"Magie de pacte — Emplacements : {slots}")
    else:
        lines.append(f"Emplacements : {slots}")
    if cantrips:
        lines.append(f"Tours de magie : {', '.join(cantrips)}")
    if character.class_id == "cleric":
        domain = get_domain_spells(character)
        prepared = get_spells_prepared_list(character)
        if prepared:
            lines.append(f"Préparés : {', '.join(prepared)}")
        if domain:
            lines.append(f"Domaine (gratuits) : {', '.join(domain)}")
    elif character.class_id == "wizard":
        spellbook = get_spellbook(character)
        prepared = get_spells_prepared_list(character)
        if spellbook:
            lines.append(f"Grimoire : {', '.join(spellbook)}")
        if prepared:
            lines.append(f"Préparés : {', '.join(prepared)}")
    elif character.class_id == "druid":
        wis_score = character.ability_scores.with_defaults(
            ["str", "dex", "con", "int", "wis", "cha"]
        ).scores.get("wis", 10)
        capacity = druid_prepared_capacity(ability_modifier(wis_score), character.level)
        lines.append(
            f"Préparation (affichage) : mod SAG + niveau = {capacity} sorts"
        )
        if known:
            lines.append(f"Sorts accessibles : {', '.join(known)}")
    elif character.class_id == "warlock" and known:
        lines.append(f"Sorts accessibles : {', '.join(known)}")
    elif known:
        lines.append(f"Sorts connus : {', '.join(known)}")
    return "\n".join(lines)
