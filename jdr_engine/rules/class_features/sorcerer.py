# jdr_engine/rules/class_features/sorcerer.py
"""Ensorceleur — SRD 5.1 2014, niveaux 1-3."""
from __future__ import annotations

from jdr_engine.domain.character.ability_scores import ability_modifier
from jdr_engine.rules.class_features.common import feature_state, set_feature_state
from jdr_engine.rules.racial.draconic_ancestry import get_draconic_ancestry

CREATE_SLOT_COST: dict[int, int] = {1: 2, 2: 3}
METAMAGIC_COST: dict[str, int] = {
    "quickened": 2,
    "subtle": 1,
    "twinned": 1,
    "extended": 1,
}
METAMAGIC_LABELS_FR: dict[str, str] = {
    "quickened": "Sort accéléré",
    "subtle": "Sort subtil",
    "twinned": "Sort jumelé",
    "extended": "Sort prolongé",
}


def sorcery_points_max(level: int) -> int:
    return level if level >= 2 else 0


def sorcery_points_remaining(choices: dict, *, level: int) -> int:
    state = feature_state(choices)
    maximum = sorcery_points_max(level)
    if maximum <= 0:
        return 0
    if "sorcery_points_remaining" not in state:
        return maximum
    return max(0, min(int(state["sorcery_points_remaining"]), maximum))


def draconic_hp_bonus(level: int, specialization: str | None) -> int:
    if specialization != "draconic":
        return 0
    return level


def get_sorcerer_dragon_type(choices: dict) -> str | None:
    raw = (choices or {}).get("sorcerer_dragon_type")
    return str(raw).strip() if raw else None


def get_lineage_damage_type(choices: dict) -> str | None:
    dragon_type = get_sorcerer_dragon_type(choices)
    if not dragon_type:
        return None
    ancestry = get_draconic_ancestry(dragon_type)
    return ancestry.damage_type if ancestry else None


def elemental_affinity_bonus(choices: dict, *, cha_score: int, spell_damage_type: str) -> int:
    if (choices or {}).get("specialization") != "draconic":
        return 0
    lineage = get_lineage_damage_type(choices)
    if not lineage or lineage != spell_damage_type:
        return 0
    return ability_modifier(cha_score)


def init_sorcerer_features(choices: dict, *, level: int) -> dict:
    state = feature_state(choices)
    maximum = sorcery_points_max(level)
    if maximum > 0:
        state.setdefault("sorcery_points_remaining", maximum)
    return set_feature_state(choices, state)


def reset_sorcery_points_on_long_rest(choices: dict, *, level: int) -> dict:
    state = feature_state(choices)
    maximum = sorcery_points_max(level)
    if maximum > 0:
        state["sorcery_points_remaining"] = maximum
    return set_feature_state(choices, state)


def spend_sorcery_points(choices: dict, *, level: int, amount: int) -> dict:
    if amount <= 0:
        raise ValueError("Montant de points invalide.")
    remaining = sorcery_points_remaining(choices, level=level)
    if amount > remaining:
        raise ValueError(f"Points de sorcellerie insuffisants ({remaining}).")
    state = feature_state(choices)
    state["sorcery_points_remaining"] = remaining - amount
    return set_feature_state(choices, state)


def gain_sorcery_points(choices: dict, *, level: int, amount: int) -> dict:
    if amount <= 0:
        raise ValueError("Montant de points invalide.")
    state = feature_state(choices)
    maximum = sorcery_points_max(level)
    current = sorcery_points_remaining(choices, level=level)
    state["sorcery_points_remaining"] = min(maximum, current + amount)
    return set_feature_state(choices, state)


def convert_slot_to_sorcery_points(
    choices: dict,
    *,
    level: int,
    slot_level: int,
    slots_used: dict[int, int],
) -> tuple[dict, dict[int, int]]:
    """1 emplacement niv.X → X points de sorcellerie (SRD 2014)."""
    if slot_level <= 0:
        raise ValueError("Niveau d'emplacement invalide.")
    used = dict(slots_used)
    if used.get(slot_level, 0) <= 0:
        raise ValueError(f"Aucun emplacement niv. {slot_level} à convertir.")
    used[slot_level] -= 1
    choices = gain_sorcery_points(choices, level=level, amount=slot_level)
    return choices, used


def convert_sorcery_points_to_slot(
    choices: dict,
    *,
    level: int,
    slot_level: int,
    slots_used: dict[int, int],
    max_slots: dict[int, int],
) -> tuple[dict, dict[int, int]]:
    """Crée un emplacement en dépensant des points (SRD 2014)."""
    cost = CREATE_SLOT_COST.get(slot_level)
    if cost is None:
        raise ValueError(f"Conversion vers emplacement niv. {slot_level} non supportée.")
    maximum = max_slots.get(slot_level, 0)
    used = dict(slots_used)
    if used.get(slot_level, 0) >= maximum:
        raise ValueError(f"Emplacements niv. {slot_level} déjà au maximum.")
    choices = spend_sorcery_points(choices, level=level, amount=cost)
    used[slot_level] = used.get(slot_level, 0) + 1
    return choices, used


def get_metamagic_options(choices: dict) -> tuple[str, ...]:
    raw = (choices or {}).get("metamagic_options") or []
    if isinstance(raw, list):
        return tuple(str(x) for x in raw if x)
    return ()


def format_metamagic_display(choices: dict) -> str:
    options = get_metamagic_options(choices)
    if not options:
        return ""
    parts = []
    for opt in options:
        label = METAMAGIC_LABELS_FR.get(opt, opt.replace("_", " ").title())
        cost = METAMAGIC_COST.get(opt, 0)
        parts.append(f"{label} ({cost} pt{'s' if cost > 1 else ''})")
    return ", ".join(parts)


def applicable_metamagic_for_spell(
    choices: dict,
    *,
    spell_level: int,
    targets_single_creature: bool = False,
) -> list[tuple[str, int]]:
    """Métamagies choisies applicables avec leur coût."""
    result: list[tuple[str, int]] = []
    for opt in get_metamagic_options(choices):
        cost = METAMAGIC_COST.get(opt, 0)
        if cost <= 0:
            continue
        if opt == "twinned" and spell_level <= 1 and targets_single_creature:
            result.append((opt, max(1, spell_level)))
        elif opt in ("quickened", "subtle", "extended"):
            result.append((opt, cost))
    return result
