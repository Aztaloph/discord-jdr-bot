# jdr_engine/rules/spellcasting/preparation.py
"""Préparation / sorts connus — Barde, Clerc, Magicien & Ensorceleur SRD 2014."""
from __future__ import annotations

from jdr_engine.domain.character.character import Character
from jdr_engine.rules.spellcasting.state import get_spellcasting_state
from jdr_engine.rules.spellcasting.model import (
    BARD_CANTRIPS_BY_LEVEL,
    BARD_SPELLS_KNOWN_BY_LEVEL,
    WARLOCK_CANTRIPS_BY_LEVEL,
    WIZARD_SPELLBOOK_BY_LEVEL,
    SORCERER_SPELLS_KNOWN_BY_LEVEL,
    cantrips_known_capacity,
    cleric_prepared_capacity,
    druid_prepared_capacity,
    paladin_prepared_capacity,
    ranger_prepared_capacity,
    spellbook_capacity,
    spells_known_capacity,
    wizard_prepared_capacity,
)
from jdr_engine.rules.spellcasting.pools import (
    get_filtered_leveled_pool,
    get_leveled_spell_pool,
)
from jdr_engine.rules.spellcasting.slots import get_max_spell_slots
from jdr_engine.rules.spellcasting.spell_levels import get_spell_level
from jdr_engine.rules.spellcasting.spells_catalog import (
    BARD_CANTRIP_IDS,
    BARD_SPELL_IDS,
    CLERIC_CANTRIP_IDS,
    CLERIC_SPELL_IDS,
    DRUID_CANTRIP_IDS,
    SORCERER_CANTRIP_IDS,
    SORCERER_SPELL_IDS,
    WARLOCK_CANTRIP_IDS,
    WIZARD_CANTRIP_IDS,
    WIZARD_SPELLBOOK_POOL,
)

LIFE_DOMAIN_SPELLS_BY_LEVEL: dict[int, tuple[str, ...]] = {
    1: ("bless", "cure_wounds"),
    3: ("spiritual_weapon",),
}

DOMAIN_SPELLS_BY_DOMAIN: dict[str, dict[int, tuple[str, ...]]] = {
    "life": LIFE_DOMAIN_SPELLS_BY_LEVEL,
}


def get_domain_spells(domain_id: str | None, level: int) -> tuple[str, ...]:
    if not domain_id:
        return ()
    table = DOMAIN_SPELLS_BY_DOMAIN.get(domain_id, {})
    spells: list[str] = []
    for req_level, ids in sorted(table.items()):
        if level >= req_level:
            for spell_id in ids:
                if spell_id not in spells:
                    spells.append(spell_id)
    return tuple(spells)


def _default_cleric_prepared(
    capacity: int,
    *,
    domain_spells: tuple[str, ...],
) -> list[str]:
    pool = [s for s in CLERIC_SPELL_IDS if s not in domain_spells]
    return list(pool[:capacity])


def _bard_cantrips(level: int) -> list[str]:
    count = BARD_CANTRIPS_BY_LEVEL.get(level, 2)
    return list(BARD_CANTRIP_IDS[:count])


def _bard_spells_known(level: int) -> list[str]:
    count = BARD_SPELLS_KNOWN_BY_LEVEL.get(level, 4)
    cantrips = set(_bard_cantrips(level))
    leveled = [s for s in BARD_SPELL_IDS if s not in cantrips]
    return leveled[:count]


def build_bard_spellcasting(level: int) -> dict:
    cantrips = _bard_cantrips(level)
    known = _bard_spells_known(level)
    return {
        "cantrips_known": cantrips,
        "spells_known": known,
        "spells_prepared": known,
        "slots_used": {},
    }


def build_cleric_spellcasting(
    level: int,
    *,
    wis_mod: int,
    domain_id: str | None = None,
    prepared_spells: list[str] | tuple[str, ...] | None = None,
) -> dict:
    cantrip_count = cantrips_known_capacity("cleric", level)
    cantrips = list(CLERIC_CANTRIP_IDS[:cantrip_count])
    domain = list(get_domain_spells(domain_id, level))
    capacity = cleric_prepared_capacity(wis_mod, level)
    if prepared_spells is not None:
        prepared = [s for s in prepared_spells if s not in domain]
    else:
        prepared = _default_cleric_prepared(capacity, domain_spells=tuple(domain))
    return {
        "cantrips_known": cantrips,
        "spells_prepared": prepared,
        "domain_spells": domain,
        "slots_used": {},
        "prepared_rechoice_pending": False,
    }


def upgrade_bard_spellcasting(choices: dict, *, new_level: int) -> dict:
    state = dict(choices.get("spellcasting") or {})
    state["cantrips_known"] = _bard_cantrips(new_level)
    known = _bard_spells_known(new_level)
    state["spells_known"] = known
    state["spells_prepared"] = known
    state.setdefault("slots_used", {})
    return {**choices, "spellcasting": state}


def upgrade_cleric_spellcasting(
    choices: dict,
    *,
    new_level: int,
    wis_mod: int,
    domain_id: str | None,
) -> dict:
    state = dict(choices.get("spellcasting") or {})
    cantrip_count = cantrips_known_capacity("cleric", new_level)
    state["cantrips_known"] = list(CLERIC_CANTRIP_IDS[:cantrip_count])
    domain = list(get_domain_spells(domain_id, new_level))
    state["domain_spells"] = domain
    capacity = cleric_prepared_capacity(wis_mod, new_level)
    existing = [s for s in (state.get("spells_prepared") or []) if s not in domain]
    if len(existing) < capacity:
        pool = _default_cleric_prepared(capacity, domain_spells=tuple(domain))
        merged = list(dict.fromkeys(existing + pool))[:capacity]
        state["spells_prepared"] = merged
    else:
        state["spells_prepared"] = existing[:capacity]
    state.setdefault("slots_used", {})
    return {**choices, "spellcasting": state}


def _spell_level(spell_id: str) -> int:
    return get_spell_level(spell_id)


def _rebalance_leveled_spells_for_slots(
    existing: list[str],
    pool: list[str],
    capacity: int,
    character_level: int,
    class_id: str,
) -> list[str]:
    """Sorts niv. 1+ ≤ capacité ; inclut un sort de niveau max si emplacements disponibles."""
    max_slot = max(
        get_max_spell_slots(class_id, character_level).keys(), default=1
    )
    result = [s for s in existing if s in pool]

    leveled = [
        s for s in pool if _spell_level(s) <= max_slot and _spell_level(s) > 1
    ]
    if leveled:
        best = max(leveled, key=lambda s: (_spell_level(s), -pool.index(s)))
        if best not in result:
            if len(result) >= capacity:
                droppable = [
                    s for s in reversed(result) if _spell_level(s) < _spell_level(best)
                ]
                if droppable:
                    result.remove(droppable[0])
            if len(result) < capacity:
                result.append(best)

    for sid in pool:
        if len(result) >= capacity:
            break
        if sid not in result:
            result.append(sid)
    return result[:capacity]


def _rebalance_wizard_prepared(
    existing: list[str],
    spellbook: list[str],
    capacity: int,
    wizard_level: int,
) -> list[str]:
    """Préparés ≤ capacité ; inclut un sort de niveau max si emplacements disponibles."""
    return _rebalance_leveled_spells_for_slots(
        existing, spellbook, capacity, wizard_level, "wizard"
    )


def _wizard_cantrips(level: int) -> list[str]:
    count = cantrips_known_capacity("wizard", level)
    return list(WIZARD_CANTRIP_IDS[:count])


def _wizard_spellbook(level: int) -> list[str]:
    count = spellbook_capacity("wizard", level)
    return list(WIZARD_SPELLBOOK_POOL[:count])


def _default_wizard_prepared(
    capacity: int,
    *,
    spellbook: tuple[str, ...],
) -> list[str]:
    return list(spellbook[:capacity])


def build_wizard_spellcasting(
    level: int,
    *,
    int_mod: int,
    prepared_spells: list[str] | tuple[str, ...] | None = None,
) -> dict:
    cantrips = _wizard_cantrips(level)
    spellbook = _wizard_spellbook(level)
    capacity = wizard_prepared_capacity(int_mod, level)
    if prepared_spells is not None:
        prepared = [s for s in prepared_spells if s in spellbook]
    else:
        prepared = _rebalance_wizard_prepared([], spellbook, capacity, level)
    return {
        "cantrips_known": cantrips,
        "spellbook": spellbook,
        "spells_prepared": prepared[:capacity],
        "slots_used": {},
    }


def upgrade_wizard_spellcasting(
    choices: dict,
    *,
    new_level: int,
    int_mod: int,
) -> dict:
    state = dict(choices.get("spellcasting") or {})
    state["cantrips_known"] = _wizard_cantrips(new_level)
    spellbook = _wizard_spellbook(new_level)
    state["spellbook"] = spellbook
    capacity = wizard_prepared_capacity(int_mod, new_level)
    existing = [s for s in (state.get("spells_prepared") or []) if s in spellbook]
    state["spells_prepared"] = _rebalance_wizard_prepared(
        existing, spellbook, capacity, new_level
    )
    state.setdefault("slots_used", {})
    return {**choices, "spellcasting": state}


class WizardSpellbookResetError(Exception):
    """Réinitialisation grimoire mage impossible ou non applicable."""


def _wizard_int_mod(character: Character) -> int:
    from jdr_engine.domain.character.ability_scores import ability_modifier
    from jdr_engine.rules.spellcasting.model import casting_ability_for_class

    ability_id = casting_ability_for_class("wizard")
    scores = character.ability_scores.with_defaults(
        ["str", "dex", "con", "int", "wis", "cha"]
    )
    return ability_modifier(scores.scores.get(ability_id, 10))


def rebuild_wizard_spellcasting_at_level(character: Character) -> Character:
    """
    Normalise cantrips, grimoire et sorts préparés au niveau actuel (pool curated).

    Conserve ``slots_used`` et ``prepared_rechoice_pending``. Réutilisable P2g / P2h.
    """
    if character.class_id != "wizard":
        raise WizardSpellbookResetError(
            "Seuls les magiciens possèdent un grimoire réinitialisable."
        )

    int_mod = _wizard_int_mod(character)
    choices = dict(character.choices or {})
    old_state = dict(get_spellcasting_state(character))
    slots_used = dict(old_state.get("slots_used") or {})
    pending = old_state.get("prepared_rechoice_pending")

    choices = upgrade_wizard_spellcasting(
        choices,
        new_level=character.level,
        int_mod=int_mod,
    )
    state = dict(choices.get("spellcasting") or {})
    state["slots_used"] = slots_used
    if pending:
        state["prepared_rechoice_pending"] = True
    else:
        state.pop("prepared_rechoice_pending", None)
    choices["spellcasting"] = state
    character.choices = choices
    return character


def project_wizard_spellcasting_reset(character: Character) -> Character:
    """Projection sans persistance — preview / test idempotence."""
    return rebuild_wizard_spellcasting_at_level(
        Character.from_dict(character.to_dict())
    )


def is_wizard_spellcasting_canonical(character: Character) -> bool:
    """True si cantrips, grimoire et préparés correspondent déjà au canon curated."""
    if character.class_id != "wizard":
        return False
    from jdr_engine.rules.spellcasting.state import (
        get_cantrips_known,
        get_spellbook,
        get_spells_prepared_list,
    )

    projected = project_wizard_spellcasting_reset(character)
    return (
        get_cantrips_known(character) == get_cantrips_known(projected)
        and get_spellbook(character) == get_spellbook(projected)
        and get_spells_prepared_list(character) == get_spells_prepared_list(projected)
    )


def _sorcerer_cantrips(level: int) -> list[str]:
    count = cantrips_known_capacity("sorcerer", level)
    return list(SORCERER_CANTRIP_IDS[:count])


def _sorcerer_spell_pool(level: int) -> list[str]:
    cantrips = set(_sorcerer_cantrips(level))
    return [s for s in SORCERER_SPELL_IDS if s not in cantrips]


def _sorcerer_spells_known(level: int) -> list[str]:
    count = spells_known_capacity("sorcerer", level)
    pool = _sorcerer_spell_pool(level)
    return _rebalance_leveled_spells_for_slots([], pool, count, level, "sorcerer")


def build_sorcerer_spellcasting(level: int) -> dict:
    cantrips = _sorcerer_cantrips(level)
    known = _sorcerer_spells_known(level)
    return {
        "cantrips_known": cantrips,
        "spells_known": known,
        "slots_used": {},
    }


def upgrade_sorcerer_spellcasting(choices: dict, *, new_level: int) -> dict:
    state = dict(choices.get("spellcasting") or {})
    state["cantrips_known"] = _sorcerer_cantrips(new_level)
    count = spells_known_capacity("sorcerer", new_level)
    pool = _sorcerer_spell_pool(new_level)
    existing_raw = state.get("spells_known") or state.get("spells_prepared") or []
    existing = (
        [str(spell_id) for spell_id in existing_raw]
        if isinstance(existing_raw, list)
        else []
    )
    state["spells_known"] = _rebalance_leveled_spells_for_slots(
        existing, pool, count, new_level, "sorcerer"
    )
    state.setdefault("slots_used", {})
    return {**choices, "spellcasting": state}


def _druid_cantrips(level: int) -> list[str]:
    count = cantrips_known_capacity("druid", level)
    return list(DRUID_CANTRIP_IDS[:count])


def _default_druid_prepared(capacity: int, *, druid_level: int) -> list[str]:
    pool = get_filtered_leveled_pool("druid", druid_level)
    return list(pool[:capacity])


def _merge_druid_prepared(
    existing: list[str],
    *,
    capacity: int,
    druid_level: int,
) -> list[str]:
    pool = get_filtered_leveled_pool("druid", druid_level)
    valid_existing = [spell_id for spell_id in existing if spell_id in pool]
    if len(valid_existing) >= capacity:
        return valid_existing[:capacity]
    default = list(pool[:capacity])
    return list(dict.fromkeys(valid_existing + default))[:capacity]


def build_druid_spellcasting(level: int, *, wis_mod: int) -> dict:
    cantrips = _druid_cantrips(level)
    capacity = druid_prepared_capacity(wis_mod, level)
    prepared = _default_druid_prepared(capacity, druid_level=level)
    return {
        "cantrips_known": cantrips,
        "spells_prepared": prepared,
        "slots_used": {},
        "prepared_rechoice_pending": False,
    }


def upgrade_druid_spellcasting(
    choices: dict,
    *,
    new_level: int,
    wis_mod: int,
) -> dict:
    state = dict(choices.get("spellcasting") or {})
    state["cantrips_known"] = _druid_cantrips(new_level)
    capacity = druid_prepared_capacity(wis_mod, new_level)
    existing_raw = state.get("spells_prepared") or state.get("spells_known") or []
    existing = (
        [str(spell_id) for spell_id in existing_raw]
        if isinstance(existing_raw, list)
        else []
    )
    state["spells_prepared"] = _merge_druid_prepared(
        existing,
        capacity=capacity,
        druid_level=new_level,
    )
    state.setdefault("slots_used", {})
    return {**choices, "spellcasting": state}


def _warlock_cantrips(level: int) -> list[str]:
    count = WARLOCK_CANTRIPS_BY_LEVEL.get(level, 2)
    return list(WARLOCK_CANTRIP_IDS[:count])


def _warlock_spells_known(level: int) -> list[str]:
    """Sorts niv. 1+ connus — quota fixe, sans filtre emplacement (connu ≠ lançable)."""
    count = spells_known_capacity("warlock", level)
    if count <= 0:
        return []
    pool = list(get_leveled_spell_pool("warlock"))
    return pool[:count]


def _merge_warlock_known(existing: list[str], *, warlock_level: int) -> list[str]:
    count = spells_known_capacity("warlock", warlock_level)
    pool = list(get_leveled_spell_pool("warlock"))
    valid_existing = [spell_id for spell_id in existing if spell_id in pool]
    if len(valid_existing) >= count:
        return valid_existing[:count]
    default = pool[:count]
    return list(dict.fromkeys(valid_existing + default))[:count]


def _pact_slot_level(warlock_level: int) -> int:
    max_slots = get_max_spell_slots("warlock", warlock_level)
    return max(max_slots.keys(), default=1)


def build_warlock_spellcasting(level: int) -> dict:
    cantrips = _warlock_cantrips(level)
    known = _warlock_spells_known(level)
    return {
        "cantrips_known": cantrips,
        "spells_known": known,
        "slots_used": {},
        "pact_magic": True,
    }


def upgrade_warlock_spellcasting(
    choices: dict,
    *,
    new_level: int,
    old_level: int,
) -> dict:
    state = dict(choices.get("spellcasting") or {})
    state["cantrips_known"] = _warlock_cantrips(new_level)
    existing_raw = state.get("spells_known") or state.get("spells_prepared") or []
    existing = (
        [str(spell_id) for spell_id in existing_raw]
        if isinstance(existing_raw, list)
        else []
    )
    state["spells_known"] = _merge_warlock_known(existing, warlock_level=new_level)
    state["pact_magic"] = True
    if _pact_slot_level(new_level) != _pact_slot_level(old_level):
        state["slots_used"] = {}
    else:
        state.setdefault("slots_used", {})
    return {**choices, "spellcasting": state}


def _half_caster_level1_prepared_pool(class_id: str) -> list[str]:
    """Niv. 1 : catalogue visible dans /sort, sans emplacements."""
    return list(get_leveled_spell_pool(class_id))


def _default_half_caster_prepared(
    class_id: str,
    level: int,
    *,
    ability_mod: int,
) -> list[str]:
    if level < 2:
        return _half_caster_level1_prepared_pool(class_id)
    pool = get_filtered_leveled_pool(class_id, level)
    if class_id == "ranger":
        capacity = ranger_prepared_capacity(level)
    else:
        capacity = paladin_prepared_capacity(ability_mod, level)
    return list(pool[:capacity])


def _merge_half_caster_prepared(
    existing: list[str],
    class_id: str,
    level: int,
    *,
    ability_mod: int,
) -> list[str]:
    if level < 2:
        return _half_caster_level1_prepared_pool(class_id)
    pool = get_filtered_leveled_pool(class_id, level)
    if class_id == "ranger":
        capacity = ranger_prepared_capacity(level)
    else:
        capacity = paladin_prepared_capacity(ability_mod, level)
    valid_existing = [spell_id for spell_id in existing if spell_id in pool]
    if len(valid_existing) >= capacity:
        return valid_existing[:capacity]
    default = list(pool[:capacity])
    return list(dict.fromkeys(valid_existing + default))[:capacity]


def build_ranger_spellcasting(level: int, *, wis_mod: int = 0) -> dict:
    prepared = _default_half_caster_prepared("ranger", level, ability_mod=wis_mod)
    return {
        "cantrips_known": [],
        "spells_prepared": prepared,
        "slots_used": {},
    }


def build_paladin_spellcasting(level: int, *, cha_mod: int) -> dict:
    prepared = _default_half_caster_prepared("paladin", level, ability_mod=cha_mod)
    return {
        "cantrips_known": [],
        "spells_prepared": prepared,
        "slots_used": {},
        "prepared_rechoice_pending": False,
    }


def upgrade_ranger_spellcasting(
    choices: dict,
    *,
    new_level: int,
    wis_mod: int = 0,
) -> dict:
    state = dict(choices.get("spellcasting") or {})
    state["cantrips_known"] = []
    existing_raw = state.get("spells_prepared") or state.get("spells_known") or []
    existing = (
        [str(spell_id) for spell_id in existing_raw]
        if isinstance(existing_raw, list)
        else []
    )
    state["spells_prepared"] = _merge_half_caster_prepared(
        existing,
        "ranger",
        new_level,
        ability_mod=wis_mod,
    )
    state.setdefault("slots_used", {})
    return {**choices, "spellcasting": state}


def upgrade_paladin_spellcasting(
    choices: dict,
    *,
    new_level: int,
    cha_mod: int,
) -> dict:
    state = dict(choices.get("spellcasting") or {})
    state["cantrips_known"] = []
    existing_raw = state.get("spells_prepared") or state.get("spells_known") or []
    existing = (
        [str(spell_id) for spell_id in existing_raw]
        if isinstance(existing_raw, list)
        else []
    )
    state["spells_prepared"] = _merge_half_caster_prepared(
        existing,
        "paladin",
        new_level,
        ability_mod=cha_mod,
    )
    state.setdefault("slots_used", {})
    return {**choices, "spellcasting": state}
