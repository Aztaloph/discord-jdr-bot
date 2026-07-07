# jdr_engine/rules/spellcasting/mechanics_display.py
"""Affichage des métadonnées mécaniques structurées (Lots A & B)."""
from __future__ import annotations

from typing import Any


def _localized_block(value: dict[str, str] | str | None, locale: str = "fr") -> str:
    if value is None:
        return ""
    if isinstance(value, dict):
        return str(value.get(locale) or value.get("fr") or value.get("en") or "")
    return str(value)


def format_spell_components(
    mechanics: dict[str, Any],
    *,
    locale: str = "fr",
) -> str:
    components = mechanics.get("components") or {}
    if not isinstance(components, dict):
        return ""
    parts: list[str] = []
    if components.get("verbal"):
        parts.append("V")
    if components.get("somatic"):
        parts.append("S")
    if components.get("material"):
        mat = _localized_block(components.get("material_description"), locale)
        parts.append(f"M ({mat})" if mat else "M")
    return ", ".join(parts) if parts else "—"


def resolve_cantrip_scaling_tier(
    mechanics: dict[str, Any],
    character_level: int,
) -> dict[str, Any] | None:
    scaling = mechanics.get("cantrip_scaling")
    if not isinstance(scaling, dict):
        return None
    tiers = scaling.get("tiers")
    if not isinstance(tiers, list) or not tiers:
        return None
    sorted_tiers = sorted(
        (t for t in tiers if isinstance(t, dict)),
        key=lambda t: int(t.get("character_level", 0)),
    )
    active: dict[str, Any] | None = None
    for tier in sorted_tiers:
        if character_level >= int(tier.get("character_level", 0)):
            active = tier
    return active


def format_cantrip_scaling_summary(
    mechanics: dict[str, Any],
    *,
    character_level: int = 1,
) -> str | None:
    scaling = mechanics.get("cantrip_scaling")
    if not isinstance(scaling, dict):
        return None
    tiers = scaling.get("tiers")
    if not isinstance(tiers, list) or not tiers:
        return None
    parts: list[str] = []
    for tier in sorted(tiers, key=lambda t: int(t.get("character_level", 0))):
        if not isinstance(tier, dict):
            continue
        lvl = int(tier.get("character_level", 0))
        attacks = tier.get("attacks")
        dice = tier.get("damage_dice")
        if attacks and int(attacks) > 1:
            parts.append(f"niv. {lvl} : {attacks}×{dice or '?'}")
        elif dice:
            parts.append(f"niv. {lvl} : {dice}")
    if not parts:
        return None
    current = resolve_cantrip_scaling_tier(mechanics, character_level)
    suffix = ""
    if current and character_level <= 3:
        if current.get("attacks") and int(current.get("attacks", 1)) > 1:
            suffix = f" (actuel niv. {character_level} : {current['attacks']}×{current.get('damage_dice', '')})"
        elif current.get("damage_dice"):
            suffix = f" (actuel niv. {character_level} : {current['damage_dice']})"
    return "Montée cantrip : " + " · ".join(parts) + suffix


def format_slot_scaling_summary(
    mechanics: dict[str, Any],
    *,
    locale: str = "fr",
) -> str | None:
    scaling = mechanics.get("slot_scaling")
    if not isinstance(scaling, dict):
        return None
    increment = scaling.get("per_slot_above_base")
    if not isinstance(increment, dict):
        return None
    parts: list[str] = []
    if increment.get("damage_dice"):
        parts.append(f"+{increment['damage_dice']} dégâts / niveau")
    if increment.get("healing_dice"):
        parts.append(f"+{increment['healing_dice']} soins / niveau")
    if increment.get("missiles"):
        count = int(increment["missiles"])
        label = "dard" if count == 1 else "dards"
        parts.append(f"+{count} {label} / niveau")
    if increment.get("temp_hp") and increment.get("cold_damage"):
        parts.append(
            f"+{increment['temp_hp']} PV temp. et +{increment['cold_damage']} froid / niveau"
        )
    elif increment.get("temp_hp"):
        parts.append(f"+{increment['temp_hp']} PV temp. / niveau")
    elif increment.get("cold_damage"):
        parts.append(f"+{increment['cold_damage']} froid / niveau")
    if increment.get("extra_targets"):
        count = int(increment["extra_targets"])
        label = "cible" if count == 1 else "cibles"
        parts.append(f"+{count} {label} / niveau")
    if not parts:
        return None
    return "Emplacement supérieur : " + " · ".join(parts)


def build_spell_mechanics_reference_lines(
    mechanics: dict[str, Any],
    *,
    locale: str = "fr",
    character_level: int = 1,
) -> list[str]:
    """Lignes de référence mécanique pour embed /sort (données, pas combat)."""
    lines: list[str] = []
    components = format_spell_components(mechanics, locale=locale)
    if components:
        lines.append(f"Composants : **{components}**")

    description = _localized_block(mechanics.get("description"), locale)
    if description:
        lines.append(description)

    attack_roll = mechanics.get("attack_roll")
    save = mechanics.get("save")
    damage_dice = mechanics.get("damage_dice")
    damage_type = mechanics.get("damage_type")

    if attack_roll:
        lines.append("Jet d'attaque de sort requis")
    if save:
        lines.append(f"Jet de sauvegarde : **{save}**")
    if damage_dice and damage_type:
        lines.append(f"Dégâts de base : **{damage_dice}** ({damage_type})")
    elif damage_dice:
        lines.append(f"Dégâts de base : **{damage_dice}**")

    if bool(mechanics.get("concentration")):
        lines.append("**Concentration**")

    scaling_line = format_cantrip_scaling_summary(
        mechanics, character_level=character_level
    )
    if scaling_line:
        lines.append(scaling_line)

    slot_line = format_slot_scaling_summary(mechanics, locale=locale)
    if slot_line:
        lines.append(slot_line)

    return lines
