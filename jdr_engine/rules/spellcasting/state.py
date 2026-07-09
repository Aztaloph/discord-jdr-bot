# jdr_engine/rules/spellcasting/state.py
"""État persistant emplacements / grimoire (character.choices.spellcasting)."""
from __future__ import annotations

from typing import Any

from jdr_engine.domain.character.character import Character
from jdr_engine.rules.spellcasting.model import (
    SpellcastingFamily,
    get_spellcasting_family,
)
from jdr_engine.rules.spellcasting.slots import get_max_spell_slots, get_remaining_slots


class SpellcastingStateError(Exception):
    pass


def get_spellcasting_state(character: Character) -> dict[str, Any]:
    """Lit choices.spellcasting (dict vide si absent)."""
    raw = (character.choices or {}).get("spellcasting")
    return dict(raw) if isinstance(raw, dict) else {}


def _normalize_spell_id_list(raw: object) -> list[str]:
    if not isinstance(raw, list):
        return []
    return [str(spell_id) for spell_id in raw]


def _raw_spells_known_from_state(state: dict[str, Any]) -> list[str]:
    return _normalize_spell_id_list(state.get("spells_known"))


def _raw_spells_prepared_from_state(state: dict[str, Any]) -> list[str]:
    return _normalize_spell_id_list(state.get("spells_prepared"))


def _effective_prepared_leveled_spells(state: dict[str, Any]) -> list[str]:
    """
    Famille PREPARED — sorts niv. 1+ effectivement préparés.

    Priorité : ``spells_prepared``. Si vide, repli legacy ``spells_known``
    (persos druide/paladin créés avant P1b).
    """
    prepared = _raw_spells_prepared_from_state(state)
    if prepared:
        return prepared
    return _raw_spells_known_from_state(state)


def _effective_known_leveled_spells(state: dict[str, Any]) -> list[str]:
    """
    Famille KNOWN_FIXED — sorts niv. 1+ connus.

    Priorité : ``spells_known``. Si vide, repli legacy ``spells_prepared``
    (barde / rôdeur / paladin avec clés dupliquées).
    """
    known = _raw_spells_known_from_state(state)
    if known:
        return known
    return _raw_spells_prepared_from_state(state)


def get_slots_used(character: Character) -> dict[int, int]:
    state = get_spellcasting_state(character)
    used = state.get("slots_used") or {}
    if not isinstance(used, dict):
        return {}
    return {int(k): int(v) for k, v in used.items()}


def get_cantrips_known(character: Character) -> list[str]:
    state = get_spellcasting_state(character)
    return _normalize_spell_id_list(state.get("cantrips_known"))


def get_domain_spells(character: Character) -> list[str]:
    state = get_spellcasting_state(character)
    return _normalize_spell_id_list(state.get("domain_spells"))


def get_bonus_spell_ids(character: Character) -> list[str]:
    """
    Sorts lançables hors emplacements de classe — liste élargie occultiste,
    sorts innés tieffelin (niv. 3+), etc.
    """
    bonus: list[str] = []
    if character.class_id == "warlock":
        from jdr_engine.rules.class_features.warlock import get_warlock_expanded_spell_ids

        bonus.extend(
            get_warlock_expanded_spell_ids(
                character.choices or {}, level=character.level
            )
        )
    if character.race_id == "tiefling" and character.level >= 3:
        from jdr_engine.rules.racial.resolve import get_innate_spells_state

        innate = get_innate_spells_state(character)
        for spell_id in innate.get("spells_level_3") or ["hellish_rebuke"]:
            if spell_id not in bonus:
                bonus.append(str(spell_id))
    return bonus


def get_spellbook(character: Character) -> list[str]:
    """Grimoire du magicien — sorts appris (niv. 1+)."""
    state = get_spellcasting_state(character)
    raw = state.get("spellbook") or state.get("spells_known") or []
    book = _normalize_spell_id_list(raw)
    if not book and character.class_id == "wizard":
        # Legacy v1/v2 : ``spells_prepared`` seul, sans clé ``spellbook``.
        book = _raw_spells_prepared_from_state(state)
    return book


def get_spells_prepared_list(character: Character) -> list[str]:
    """Sorts préparés explicites (clerc, magicien…) — hors domaine et cantrips."""
    return _raw_spells_prepared_from_state(get_spellcasting_state(character))


def get_spells_known(character: Character) -> list[str]:
    """
    Sorts niv. 1+ connus ou préparés (lançables si emplacement dispo).

    Clerc : préparés + domaine. Magicien : sorts préparés uniquement.
    Druide / paladin : préparés (+ repli legacy ``spells_known``).
    Barde / ensorceleur / occultiste / rôdeur : sorts connus (+ repli legacy).
    """
    state = get_spellcasting_state(character)
    family = get_spellcasting_family(character.class_id)

    if family == SpellcastingFamily.WIZARD_HYBRID:
        return get_spells_prepared_list(character)

    if family == SpellcastingFamily.PREPARED:
        prepared = _effective_prepared_leveled_spells(state)
        if character.class_id == "cleric":
            domain = get_domain_spells(character)
            return list(dict.fromkeys(prepared + domain))
        return prepared

    if family == SpellcastingFamily.KNOWN_FIXED:
        return _effective_known_leveled_spells(state)

    raw = state.get("spells_known") or state.get("spells_prepared") or []
    return _normalize_spell_id_list(raw)


def get_spells_prepared(character: Character) -> list[str]:
    """Alias — voir ``get_spells_known``."""
    return get_spells_known(character)


def spell_is_known(character: Character, spell_id: str) -> bool:
    """True si le personnage peut lancer ce sort (tour de magie ou préparé/connu)."""
    if spell_id in get_cantrips_known(character):
        return True

    state = get_spellcasting_state(character)
    family = get_spellcasting_family(character.class_id)

    if family == SpellcastingFamily.PREPARED:
        if spell_id in get_domain_spells(character):
            return True
        return spell_id in _effective_prepared_leveled_spells(state)

    if family == SpellcastingFamily.WIZARD_HYBRID:
        return spell_id in get_spells_prepared_list(character)

    if family == SpellcastingFamily.KNOWN_FIXED:
        if spell_id in get_bonus_spell_ids(character):
            return True
        return spell_id in _effective_known_leveled_spells(state)

    if spell_id in get_bonus_spell_ids(character):
        return True
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
            get_cantrips_known(character)
            + get_spells_known(character)
            + get_bonus_spell_ids(character)
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
    from jdr_engine.rules.spellcasting.preparation import druid_prepared_capacity

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
