# jdr_engine/rules/spellcasting/cast.py
"""Lancement de sorts SRD 2014 — Magicien niv. 1-3 (Lot B)."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from jdr_engine.dice.d20 import D20RollContext, D20RollRequest, D20RollResult, roll_d20
from jdr_engine.dice.roller import roll
from jdr_engine.domain.character.ability_scores import ability_modifier
from jdr_engine.domain.character.character import Character
from jdr_engine.rules.engine import RuleEngine
from jdr_engine.rules.spellcasting.slots import get_max_spell_slots, get_remaining_slots
from jdr_engine.rules.spellcasting.state import (
    consume_spell_slot,
    get_slots_used,
    spell_is_available,
)
from jdr_engine.rules.spellcasting.stats import spell_attack_bonus, spell_save_dc

RandInt = Callable[[int, int], int]


class SpellCastError(Exception):
    pass


@dataclass
class SpellAttackRoll:
    index: int
    attack_bonus: int
    d20_result: D20RollResult
    damage_total: int
    damage_notation: str
    damage_rolls: list[int]


@dataclass
class SpellCastResult:
    spell_id: str
    spell_name: str
    spell_level: int
    school: str
    casting_time: str
    range_text: str
    duration: str
    effect_type: str
    attack_bonus: int | None = None
    save_dc: int | None = None
    save_ability: str | None = None
    attack_rolls: list[SpellAttackRoll] = field(default_factory=list)
    damage_total: int | None = None
    damage_notation: str | None = None
    damage_rolls: list[int] = field(default_factory=list)
    utility_text: str | None = None
    slot_consumed_level: int | None = None
    slots_max: dict[int, int] = field(default_factory=dict)
    slots_remaining: dict[int, int] = field(default_factory=dict)
    damage_type: str = ""
    display_lines: list[str] = field(default_factory=list)
    updated_character: Character | None = None


def _spellcasting_ability(character: Character, engine: RuleEngine) -> str:
    class_entry = engine.get_entity("class", character.class_id)
    if class_entry is None:
        raise SpellCastError(f"Classe inconnue : {character.class_id!r}")
    spellcasting = class_entry.definition.mechanics.get("spellcasting") or {}
    ability = spellcasting.get("ability")
    if not ability:
        raise SpellCastError("Cette classe n'est pas lanceur de sorts.")
    return str(ability)


def _ability_mod_for_spellcasting(character: Character, engine: RuleEngine) -> int:
    ability_id = _spellcasting_ability(character, engine)
    scores = character.ability_scores.with_defaults(["str", "dex", "con", "int", "wis", "cha"])
    return ability_modifier(scores.scores.get(ability_id, 10))


def get_spellcasting_stats(
    character: Character,
    engine: RuleEngine,
) -> tuple[int, int, int]:
    """Retourne (mod carac., bonus attaque sort, DD sauvegarde)."""
    if character.class_id != "wizard" or character.level < 1 or character.level > 3:
        raise SpellCastError("Lot B : Magicien niveaux 1 à 3 uniquement.")
    prof = engine.get_proficiency_bonus(character.level)
    mod = _ability_mod_for_spellcasting(character, engine)
    return mod, spell_attack_bonus(prof, mod), spell_save_dc(prof, mod)


def _get_spell_level(spell_def: dict[str, Any]) -> int:
    return int(spell_def.get("mechanics", {}).get("level", 0))


def _get_effect(spell_def: dict[str, Any]) -> dict[str, Any]:
    mechanics = spell_def.get("mechanics", {})
    effect = mechanics.get("effect")
    if not isinstance(effect, dict):
        raise SpellCastError("Sort sans effet mécanique défini.")
    return effect


def _localized(spell_def: dict[str, Any], field: str, locale: str = "fr") -> str:
    mechanics = spell_def.get("mechanics", {})
    block = mechanics.get(field) or {}
    if isinstance(block, dict):
        return str(block.get(locale) or block.get("fr") or block.get("en") or "")
    return str(block)


def _roll_spell_attack(
    attack_bonus: int,
    ability_mod: int,
    proficiency: int,
    *,
    rng: RandInt | None = None,
) -> D20RollResult:
    request = D20RollRequest(
        roll_type="attack",
        ability_modifier=ability_mod,
        proficiency_bonus=proficiency,
        is_proficient=True,
        ability="int",
    )
    return roll_d20(D20RollContext(request=request), rng=rng)


def _roll_damage(notation: str, *, rng: RandInt | None = None) -> tuple[int, list[int]]:
    if rng is not None:
        from jdr_engine.dice.parser import parse

        count, faces, modifier, sign = parse(notation)
        rolls = [rng(1, faces) for _ in range(count)]
        total = sum(rolls)
        if modifier:
            total = total + modifier if sign == "+" else total - modifier
        return total, rolls
    result = roll(notation)
    return result.total, result.rolls


def cast_spell(
    character: Character,
    spell_id: str,
    engine: RuleEngine,
    *,
    locale: str = "fr",
    rng: RandInt | None = None,
    persist_slots: bool = True,
) -> SpellCastResult:
    """
    Lance un sort connu/préparé, consomme l'emplacement si niv. ≥ 1.

    ``persist_slots`` : si True, ``updated_character`` contient slots_used mis à jour.
    """
    if character.class_id != "wizard":
        raise SpellCastError("Lot B : seul le Magicien est pris en charge.")
    if character.level < 1 or character.level > 3:
        raise SpellCastError("Lot B : Magicien niveaux 1 à 3 uniquement.")

    entry = engine.get_entity("spell", spell_id)
    if entry is None:
        raise SpellCastError(f"Sort inconnu : {spell_id!r}")

    spell_def = entry.definition.model_dump()
    spell_level = _get_spell_level(spell_def)
    if not spell_is_available(character, spell_id):
        if spell_level == 0:
            raise SpellCastError(f"Tour de magie non connu : {spell_id!r}.")
        raise SpellCastError(f"Sort non préparé : {spell_id!r}.")

    if spell_level > 0:
        max_slots = get_max_spell_slots(character.class_id, character.level)
        if spell_level not in max_slots and not any(
            lvl >= spell_level for lvl in max_slots
        ):
            raise SpellCastError(
                f"Aucun emplacement de sort niv. {spell_level} à ce niveau de classe."
            )
        remaining = get_remaining_slots(
            character.class_id, character.level, get_slots_used(character)
        )
        if not any(
            rem > 0 and lvl >= spell_level for lvl, rem in remaining.items()
        ):
            raise SpellCastError("Aucun emplacement de sort disponible.")

    ability_mod, attack_bonus, save_dc = get_spellcasting_stats(character, engine)
    proficiency = engine.get_proficiency_bonus(character.level)
    effect = _get_effect(spell_def)
    effect_type = str(effect.get("type", ""))
    damage_type = str(effect.get("damage_type", ""))
    spell_name = entry.get_name(locale, engine.registry.manifest.default_locale)

    mechanics = spell_def.get("mechanics", {})
    school = str(mechanics.get("school", ""))
    casting_time = _localized(spell_def, "casting_time", locale)
    range_text = _localized(spell_def, "range", locale)
    duration = _localized(spell_def, "duration", locale)

    result = SpellCastResult(
        spell_id=spell_id,
        spell_name=spell_name,
        spell_level=spell_level,
        school=school,
        casting_time=casting_time,
        range_text=range_text,
        duration=duration,
        effect_type=effect_type,
        damage_type=damage_type,
        slots_max=get_max_spell_slots(character.class_id, character.level),
    )

    if effect_type == "spell_attack":
        attacks = int(effect.get("attacks", 1))
        damage_notation = str(effect.get("damage", ""))
        attack_rolls: list[SpellAttackRoll] = []
        total_damage = 0
        all_damage_rolls: list[int] = []

        for index in range(1, attacks + 1):
            d20 = _roll_spell_attack(
                attack_bonus, ability_mod, proficiency, rng=rng
            )
            dmg_total, dmg_rolls = _roll_damage(damage_notation, rng=rng)
            total_damage += dmg_total
            all_damage_rolls.extend(dmg_rolls)
            attack_rolls.append(
                SpellAttackRoll(
                    index=index,
                    attack_bonus=attack_bonus,
                    d20_result=d20,
                    damage_total=dmg_total,
                    damage_notation=damage_notation,
                    damage_rolls=dmg_rolls,
                )
            )

        result.attack_bonus = attack_bonus
        result.attack_rolls = attack_rolls
        result.damage_total = total_damage
        result.damage_notation = damage_notation
        result.damage_rolls = all_damage_rolls

    elif effect_type == "saving_throw":
        save_ability = str(effect.get("ability", "dex"))
        damage_notation = str(effect.get("damage", ""))
        dmg_total, dmg_rolls = _roll_damage(damage_notation, rng=rng)
        result.save_dc = save_dc
        result.save_ability = save_ability
        result.damage_total = dmg_total
        result.damage_notation = damage_notation
        result.damage_rolls = dmg_rolls

    elif effect_type == "utility":
        result.utility_text = _localized(spell_def, "utility_effect", locale)

    else:
        raise SpellCastError(f"Type d'effet non pris en charge : {effect_type!r}")

    updated = character
    slot_consumed: int | None = None
    if spell_level > 0:
        before_used = dict(get_slots_used(character))
        updated = consume_spell_slot(character, spell_level)
        after_used = get_slots_used(updated)
        for level in sorted(after_used.keys()):
            if after_used.get(level, 0) > before_used.get(level, 0):
                slot_consumed = level
                break

    remaining = get_remaining_slots(
        updated.class_id, updated.level, get_slots_used(updated)
    )
    result.slot_consumed_level = slot_consumed
    result.slots_remaining = remaining
    if persist_slots:
        result.updated_character = updated

    result.display_lines = build_spell_display_lines(result, locale=locale)
    return result


def build_spell_display_lines(
    result: SpellCastResult,
    *,
    locale: str = "fr",
) -> list[str]:
    """Lignes style « Traits actifs » pour embed Discord."""
    lines: list[str] = []
    level_label = "tour de magie" if result.spell_level == 0 else f"sort niv. {result.spell_level}"
    lines.append(f"{result.spell_name} ({level_label}) — {result.school}")

    if result.effect_type == "spell_attack" and result.attack_bonus is not None:
        lines.append(f"Jet d'attaque de sort : **+{result.attack_bonus}**")
        for atk in result.attack_rolls:
            prefix = f"Attaque {atk.index}" if len(result.attack_rolls) > 1 else "d20"
            nat = ""
            if atk.d20_result.natural_20:
                nat = " — **20 naturel !**"
            elif atk.d20_result.natural_1:
                nat = " — **1 naturel**"
            lines.append(
                f"{prefix} : **{atk.d20_result.kept_value}** → total **{atk.d20_result.total}**{nat}"
            )
        dmg_label = _damage_type_label(result.damage_type)
        lines.append(
            f"Dégâts{dmg_label} : **{result.damage_total}** ({result.damage_notation})"
        )

    elif result.effect_type == "saving_throw":
        ability = (result.save_ability or "dex").upper()
        lines.append(f"DD de sauvegarde {ability} : **{result.save_dc}**")
        dmg_label = _damage_type_label(result.damage_type)
        lines.append(
            f"Dégâts{dmg_label} (échec) : **{result.damage_total}** ({result.damage_notation})"
        )
        lines.append("Demi-dégâts en cas de réussite (SRD 2014)")

    elif result.effect_type == "utility" and result.utility_text:
        lines.append(result.utility_text)

    if result.spell_level == 0:
        lines.append("Emplacements : aucun consommé (tour de magie)")
    elif result.slot_consumed_level is not None:
        lines.append(
            f"Emplacement consommé : niv. **{result.slot_consumed_level}**"
        )

    if result.slots_remaining:
        slot_parts = [
            f"niv.{lvl}: {rem}/{result.slots_max.get(lvl, rem)}"
            for lvl, rem in sorted(result.slots_remaining.items())
        ]
        lines.append(f"Emplacements restants : {', '.join(slot_parts)}")

    return lines


def _damage_type_label(damage_type: str) -> str:
    if not damage_type:
        return ""
    labels = {
        "fire": " feu",
        "acid": " acide",
        "cold": " froid",
        "lightning": " foudre",
        "poison": " poison",
        "thunder": " tonnerre",
        "variable": " (type au choix)",
    }
    return labels.get(damage_type, f" {damage_type}")
