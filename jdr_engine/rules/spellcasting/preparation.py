# jdr_engine/rules/spellcasting/preparation.py
"""Préparation / sorts connus — Barde, Clerc, Magicien & Ensorceleur SRD 2014."""
from __future__ import annotations

from jdr_engine.rules.spellcasting.slots import get_max_spell_slots
from jdr_engine.rules.spellcasting.spells_catalog import (
    BARD_CANTRIP_IDS,
    BARD_SPELL_IDS,
    CLERIC_CANTRIP_IDS,
    CLERIC_SPELL_IDS,
    DRUID_CANTRIP_IDS,
    DRUID_SPELL_IDS,
    SORCERER_CANTRIP_IDS,
    SORCERER_SPELL_IDS,
    WARLOCK_CANTRIP_IDS,
    WARLOCK_SPELL_IDS,
    WIZARD_CANTRIP_IDS,
    WIZARD_SPELLBOOK_POOL,
)

BARD_CANTRIPS_BY_LEVEL: dict[int, int] = {1: 2, 2: 2, 3: 2}
BARD_SPELLS_KNOWN_BY_LEVEL: dict[int, int] = {1: 4, 2: 5, 3: 6}

CLERIC_CANTRIPS_BY_LEVEL: dict[int, int] = {1: 3, 2: 3, 3: 3}

LIFE_DOMAIN_SPELLS_BY_LEVEL: dict[int, tuple[str, ...]] = {
    1: ("bless", "cure_wounds"),
    3: ("spiritual_weapon",),
}

DOMAIN_SPELLS_BY_DOMAIN: dict[str, dict[int, tuple[str, ...]]] = {
    "life": LIFE_DOMAIN_SPELLS_BY_LEVEL,
}


def cleric_prepared_capacity(wis_mod: int, level: int) -> int:
    return max(1, wis_mod + level)


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
    cantrip_count = CLERIC_CANTRIPS_BY_LEVEL.get(level, 3)
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
    cantrip_count = CLERIC_CANTRIPS_BY_LEVEL.get(new_level, 3)
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


WIZARD_CANTRIPS_BY_LEVEL: dict[int, int] = {1: 3, 2: 3, 3: 4}
WIZARD_SPELLBOOK_BY_LEVEL: dict[int, int] = {1: 6, 2: 8, 3: 10}

# Niveau d'emplacement SRD (niv. 1–3) pour la préparation du magicien / druide.
_SPELL_LEVEL_BY_ID: dict[str, int] = {
    "scorching_ray": 2,
    "darkness": 2,
    "spiritual_weapon": 2,
    "flaming_sphere": 2,
    "hex": 1,
    "armor_of_agathys": 1,
}


def _spell_level(spell_id: str) -> int:
    return _SPELL_LEVEL_BY_ID.get(spell_id, 1)


def _rebalance_wizard_prepared(
    existing: list[str],
    spellbook: list[str],
    capacity: int,
    wizard_level: int,
) -> list[str]:
    """Préparés ≤ capacité ; inclut un sort de niveau max si emplacements disponibles."""
    from jdr_engine.rules.spellcasting.slots import get_max_spell_slots

    max_slot = max(get_max_spell_slots("wizard", wizard_level).keys(), default=1)
    result = [s for s in existing if s in spellbook]

    leveled = [
        s for s in spellbook if _spell_level(s) <= max_slot and _spell_level(s) > 1
    ]
    if leveled:
        best = max(leveled, key=lambda s: (_spell_level(s), -spellbook.index(s)))
        if best not in result:
            if len(result) >= capacity:
                droppable = [
                    s for s in reversed(result) if _spell_level(s) < _spell_level(best)
                ]
                if droppable:
                    result.remove(droppable[0])
            if len(result) < capacity:
                result.append(best)

    for sid in spellbook:
        if len(result) >= capacity:
            break
        if sid not in result:
            result.append(sid)
    return result[:capacity]

SORCERER_CANTRIPS_BY_LEVEL: dict[int, int] = {1: 4, 2: 4, 3: 5}
SORCERER_SPELLS_KNOWN_BY_LEVEL: dict[int, int] = {1: 2, 2: 3, 3: 4}


def wizard_prepared_capacity(int_mod: int, level: int) -> int:
    return max(1, int_mod + level)


def _wizard_cantrips(level: int) -> list[str]:
    count = WIZARD_CANTRIPS_BY_LEVEL.get(level, 3)
    return list(WIZARD_CANTRIP_IDS[:count])


def _wizard_spellbook(level: int) -> list[str]:
    count = WIZARD_SPELLBOOK_BY_LEVEL.get(level, 6)
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


def _sorcerer_cantrips(level: int) -> list[str]:
    count = SORCERER_CANTRIPS_BY_LEVEL.get(level, 4)
    return list(SORCERER_CANTRIP_IDS[:count])


def _sorcerer_spells_known(level: int) -> list[str]:
    count = SORCERER_SPELLS_KNOWN_BY_LEVEL.get(level, 2)
    cantrips = set(_sorcerer_cantrips(level))
    leveled = [s for s in SORCERER_SPELL_IDS if s not in cantrips]
    return leveled[:count]


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
    state["spells_known"] = _sorcerer_spells_known(new_level)
    state.setdefault("slots_used", {})
    return {**choices, "spellcasting": state}


DRUID_CANTRIPS_BY_LEVEL: dict[int, int] = {1: 2, 2: 2, 3: 2}


def druid_prepared_capacity(wis_mod: int, level: int) -> int:
    """Capacité affichée — mod SAG + niveau (SRD 2014)."""
    return max(1, wis_mod + level)


def _druid_cantrips(level: int) -> list[str]:
    count = DRUID_CANTRIPS_BY_LEVEL.get(level, 2)
    return list(DRUID_CANTRIP_IDS[:count])


def _druid_spells_accessible(level: int) -> list[str]:
    """Tous les sorts druide accessibles par niveau d'emplacement (pas de préparation interactive)."""
    max_slots = get_max_spell_slots("druid", level)
    max_spell_level = max(max_slots.keys(), default=1)
    cantrips = set(_druid_cantrips(level))
    accessible: list[str] = []
    for spell_id in DRUID_SPELL_IDS:
        if spell_id in cantrips:
            continue
        if _spell_level(spell_id) <= max_spell_level:
            accessible.append(spell_id)
    return accessible


def build_druid_spellcasting(level: int) -> dict:
    cantrips = _druid_cantrips(level)
    known = _druid_spells_accessible(level)
    return {
        "cantrips_known": cantrips,
        "spells_known": known,
        "slots_used": {},
    }


def upgrade_druid_spellcasting(choices: dict, *, new_level: int) -> dict:
    state = dict(choices.get("spellcasting") or {})
    state["cantrips_known"] = _druid_cantrips(new_level)
    state["spells_known"] = _druid_spells_accessible(new_level)
    state.setdefault("slots_used", {})
    return {**choices, "spellcasting": state}


WARLOCK_CANTRIPS_BY_LEVEL: dict[int, int] = {1: 2, 2: 2, 3: 2}


def _warlock_cantrips(level: int) -> list[str]:
    count = WARLOCK_CANTRIPS_BY_LEVEL.get(level, 2)
    return list(WARLOCK_CANTRIP_IDS[:count])


def _warlock_spells_accessible(level: int) -> list[str]:
    max_slots = get_max_spell_slots("warlock", level)
    if not max_slots:
        return []
    max_spell_level = max(max_slots.keys())
    cantrips = set(_warlock_cantrips(level))
    accessible: list[str] = []
    for spell_id in WARLOCK_SPELL_IDS:
        if spell_id in cantrips:
            continue
        if _spell_level(spell_id) <= max_spell_level:
            accessible.append(spell_id)
    return accessible


def _pact_slot_level(warlock_level: int) -> int:
    max_slots = get_max_spell_slots("warlock", warlock_level)
    return max(max_slots.keys(), default=1)


def build_warlock_spellcasting(level: int) -> dict:
    cantrips = _warlock_cantrips(level)
    known = _warlock_spells_accessible(level)
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
    state["spells_known"] = _warlock_spells_accessible(new_level)
    state["pact_magic"] = True
    if _pact_slot_level(new_level) != _pact_slot_level(old_level):
        state["slots_used"] = {}
    else:
        state.setdefault("slots_used", {})
    return {**choices, "spellcasting": state}
