# jdr_engine/rules/spellcasting/cast.py
"""Lancement de sorts SRD 2014 — lanceurs niv. 1–20."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from jdr_engine.dice.d20 import D20RollContext, D20RollRequest, D20RollResult, roll_d20
from jdr_engine.dice.roller import roll
from jdr_engine.domain.character.character import Character
from jdr_engine.rules.calculator import build_character_sheet
from jdr_engine.rules.progression_constants import MAX_CHARACTER_LEVEL
from jdr_engine.rules.effective_scores import get_effective_ability_modifier
from jdr_engine.rules.engine import RuleEngine
from jdr_engine.rules.spellcasting.access import has_spellcasting_access
from jdr_engine.rules.spellcasting.mechanics_display import (
    build_spell_mechanics_reference_lines,
    resolve_cantrip_scaling_tier,
)
from jdr_engine.rules.spellcasting.slots import get_max_spell_slots, get_remaining_slots
from jdr_engine.rules.spellcasting.spells_catalog import SUPPORTED_SPELLCASTING_CLASSES
from jdr_engine.rules.spellcasting.state import (
    consume_spell_slot,
    get_spellbook,
    get_slots_used,
    get_spellcasting_state,
    get_spells_prepared_list,
    spell_in_spellbook,
    spell_is_known,
)
from jdr_engine.rules.spellcasting.state import _find_slot_to_consume
from jdr_engine.rules.spellcasting.stats import spell_attack_bonus, spell_save_dc

RandInt = Callable[[int, int], int]


class SpellCastError(Exception):
    pass


@dataclass
class SpellAttackRoll:
    index: int
    damage_total: int
    damage_notation: str
    damage_rolls: list[int]
    attack_bonus: int | None = None
    d20_result: D20RollResult | None = None
    auto_hit: bool = False


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
    healing_total: int | None = None
    healing_applied: int | None = None
    healing_rolls: list[int] = field(default_factory=list)
    hp_before: int | None = None
    hp_after: int | None = None
    hp_max: int | None = None
    healing_capped: bool = False
    utility_text: str | None = None
    buff_text: str | None = None
    concentration: bool = False
    slot_consumed_level: int | None = None
    slots_max: dict[int, int] = field(default_factory=dict)
    slots_remaining: dict[int, int] = field(default_factory=dict)
    damage_type: str = ""
    half_on_save: bool = True
    display_lines: list[str] = field(default_factory=list)
    updated_character: Character | None = None


def _spellcasting_ability(character: Character, engine: RuleEngine) -> str:
    class_entry = engine.get_entity("class", character.class_id)
    if class_entry is None:
        raise SpellCastError(f"Classe inconnue : {character.class_id!r}")
    spellcasting = class_entry.definition.mechanics.get("spellcasting") or {}
    pact = class_entry.definition.mechanics.get("pact_magic") or {}
    ability = spellcasting.get("ability") or pact.get("ability")
    if not ability:
        raise SpellCastError("Cette classe n'est pas lanceur de sorts.")
    return str(ability)


def _ability_mod_for_spellcasting(character: Character, engine: RuleEngine) -> int:
    ability_id = _spellcasting_ability(character, engine)
    return get_effective_ability_modifier(character, engine, ability_id)


def get_spellcasting_stats(
    character: Character,
    engine: RuleEngine,
) -> tuple[int, int, int]:
    """Retourne (mod carac., bonus attaque sort, DD sauvegarde)."""
    if character.class_id not in SUPPORTED_SPELLCASTING_CLASSES:
        raise SpellCastError(
            f"Lanceur de sorts non pris en charge : {character.class_id!r}."
        )
    if not has_spellcasting_access(character, engine):
        raise SpellCastError(
            "Cette classe n'a pas encore accès à la magie (niveau requis)."
        )
    if character.level < 1 or character.level > MAX_CHARACTER_LEVEL:
        raise SpellCastError(
            f"Niveaux 1 à {MAX_CHARACTER_LEVEL} uniquement pour cette phase."
        )

    prof = engine.get_proficiency_bonus(character.level)
    mod = _ability_mod_for_spellcasting(character, engine)
    return mod, spell_attack_bonus(prof, mod), spell_save_dc(prof, mod)


def _get_spell_level(spell_def: dict[str, Any]) -> int:
    return int(spell_def.get("mechanics", {}).get("level", 0))


def _get_effects(spell_def: dict[str, Any]) -> list[dict[str, Any]]:
    mechanics = spell_def.get("mechanics", {})
    effects = mechanics.get("effects")
    if isinstance(effects, list) and effects:
        return [e for e in effects if isinstance(e, dict)]
    legacy = mechanics.get("effect")
    if isinstance(legacy, dict):
        return [legacy]
    raise SpellCastError("Sort sans effet mécanique défini.")


def _primary_effect(effects: list[dict[str, Any]]) -> dict[str, Any]:
    """Effet principal pour le cast — priorité combat puis buff/utility."""
    priority = ("spell_attack", "saving_throw", "healing", "buff", "utility")
    for effect_type in priority:
        for effect in effects:
            if effect.get("type") == effect_type:
                return effect
    return effects[0]


def _save_spec(effect: dict[str, Any]) -> dict[str, Any]:
    nested = effect.get("saving_throw")
    if isinstance(nested, dict):
        return nested
    return {
        "ability": effect.get("ability", "dex"),
        "half_on_save": effect.get("half_on_save", True),
        "reaction": effect.get("reaction", False),
    }


def _localized(spell_def: dict[str, Any], field: str, locale: str = "fr") -> str:
    mechanics = spell_def.get("mechanics", {})
    block = mechanics.get(field) or {}
    if isinstance(block, dict):
        return str(block.get(locale) or block.get("fr") or block.get("en") or "")
    return str(block)


def _is_auto_hit_spell(spell_def: dict[str, Any], effect: dict[str, Any]) -> bool:
    """True si le sort touche automatiquement (ex. projectile magique SRD 2014)."""
    if effect.get("auto_hit"):
        return True
    mechanics = spell_def.get("mechanics", {})
    return mechanics.get("attack_roll") is False and effect.get("type") == "spell_attack"


def _resolve_damage_instance_count(
    spell_def: dict[str, Any],
    effect: dict[str, Any],
    *,
    spell_level: int,
    character: Character,
) -> int:
    """Nombre d'instances de dégâts (dards, rayons…) en tenant compte de l'upcasting."""
    base = int(effect.get("attacks", effect.get("instances", 1)))
    if spell_level <= 0:
        return base
    mechanics = spell_def.get("mechanics", {})
    scaling = mechanics.get("slot_scaling")
    if not isinstance(scaling, dict):
        return base
    increment = scaling.get("per_slot_above_base")
    if not isinstance(increment, dict):
        return base
    extra_missiles = increment.get("missiles")
    if not extra_missiles:
        return base
    max_slots = get_max_spell_slots(character.class_id, character.level)
    used = get_slots_used(character)
    slot_level = _find_slot_to_consume(spell_level, max_slots, used)
    if slot_level is None or slot_level <= spell_level:
        return base
    return base + int(extra_missiles) * (slot_level - spell_level)


def _resolve_damage_notation(
    spell_def: dict[str, Any],
    effect: dict[str, Any],
    *,
    spell_level: int,
    character_level: int,
) -> str:
    """Dégâts effectifs — cantrips : tier SRD selon le niveau de personnage."""
    notation = str(effect.get("damage", ""))
    if spell_level != 0:
        return notation
    mechanics = spell_def.get("mechanics", {})
    tier = resolve_cantrip_scaling_tier(mechanics, character_level)
    if tier and tier.get("damage_dice"):
        return str(tier["damage_dice"])
    return notation


def _roll_spell_attack(
    attack_bonus: int,
    ability_mod: int,
    proficiency: int,
    ability_id: str,
    *,
    rng: RandInt | None = None,
) -> D20RollResult:
    request = D20RollRequest(
        roll_type="attack",
        ability_modifier=ability_mod,
        proficiency_bonus=proficiency,
        is_proficient=True,
        ability=ability_id,
    )
    return roll_d20(D20RollContext(request=request), rng=rng)


def _roll_dice(notation: str, *, rng: RandInt | None = None) -> tuple[int, list[int]]:
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


def _apply_healing(
    character: Character,
    engine: RuleEngine,
    amount: int,
) -> tuple[Character, int, int, int, int, bool]:
    """
    Applique un soin SRD 2014 : PV = min(PV + soin, PV_max).

    Retourne (perso, pv_avant, pv_après, pv_max, soin_effectif, plafonné).
    """
    sheet = build_character_sheet(character, engine)
    hp_max = sheet.hp_max
    hp_before = character.hp_current if character.hp_current is not None else hp_max
    hp_before = min(hp_before, hp_max)
    hp_after = min(hp_max, hp_before + amount)
    healing_applied = hp_after - hp_before
    capped = healing_applied < amount
    character.hp_current = hp_after
    return character, hp_before, hp_after, hp_max, healing_applied, capped


def _set_concentration(character: Character, spell_id: str, spell_name: str) -> Character:
    choices = dict(character.choices or {})
    state = dict(get_spellcasting_state(character))
    state["concentration"] = {"spell_id": spell_id, "spell_name": spell_name}
    choices["spellcasting"] = state
    character.choices = choices
    return character


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

    ``persist_slots`` : si True, ``updated_character`` contient l'état mis à jour.
    """
    if character.class_id not in SUPPORTED_SPELLCASTING_CLASSES:
        raise SpellCastError(
            f"Lanceur de sorts non pris en charge : {character.class_id!r}."
        )
    if not has_spellcasting_access(character, engine):
        raise SpellCastError(
            "Cette classe n'a pas encore accès à la magie (niveau requis)."
        )
    if character.level < 1 or character.level > MAX_CHARACTER_LEVEL:
        raise SpellCastError(
            f"Niveaux 1 à {MAX_CHARACTER_LEVEL} uniquement pour cette phase."
        )

    entry = engine.get_entity("spell", spell_id)
    if entry is None:
        raise SpellCastError(f"Sort inconnu : {spell_id!r}")

    spell_def = entry.definition.model_dump()
    spell_level = _get_spell_level(spell_def)
    spell_name = entry.get_name(locale, engine.registry.manifest.default_locale)

    # Magicien : sort au grimoire mais non préparé.
    if (
        character.class_id == "wizard"
        and spell_level > 0
        and spell_in_spellbook(character, spell_id)
        and spell_id not in get_spells_prepared_list(character)
    ):
        raise SpellCastError(
            f"**{spell_name}** est dans votre grimoire mais n'est pas préparé aujourd'hui."
        )

    if not spell_is_known(character, spell_id):
        if spell_level == 0:
            raise SpellCastError(
                f"Vous ne connaissez pas ce tour de magie : **{spell_name}**."
            )
        raise SpellCastError(f"Vous ne connaissez pas ce sort : **{spell_name}**.")

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

    ability_id = _spellcasting_ability(character, engine)
    ability_mod, attack_bonus, save_dc = get_spellcasting_stats(character, engine)
    proficiency = engine.get_proficiency_bonus(character.level)
    effects = _get_effects(spell_def)
    effect = _primary_effect(effects)
    effect_type = str(effect.get("type", ""))
    damage_type = str(effect.get("damage_type", ""))

    mechanics = spell_def.get("mechanics", {})
    school = str(mechanics.get("school", ""))
    casting_time = _localized(spell_def, "casting_time", locale)
    range_text = _localized(spell_def, "range", locale)
    duration = _localized(spell_def, "duration", locale)
    concentration = bool(mechanics.get("concentration", False))

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
        concentration=concentration,
        slots_max=get_max_spell_slots(character.class_id, character.level),
    )

    updated = character

    if effect_type == "spell_attack":
        damage_notation = _resolve_damage_notation(
            spell_def,
            effect,
            spell_level=spell_level,
            character_level=character.level,
        )
        add_mod = bool(effect.get("add_ability_mod", False))
        auto_hit = _is_auto_hit_spell(spell_def, effect)
        instances = _resolve_damage_instance_count(
            spell_def,
            effect,
            spell_level=spell_level,
            character=updated,
        )
        attack_rolls: list[SpellAttackRoll] = []
        total_damage = 0
        all_damage_rolls: list[int] = []

        for index in range(1, instances + 1):
            if auto_hit:
                dmg_total, dmg_rolls = _roll_dice(damage_notation, rng=rng)
                if add_mod:
                    dmg_total += ability_mod
                total_damage += dmg_total
                all_damage_rolls.extend(dmg_rolls)
                attack_rolls.append(
                    SpellAttackRoll(
                        index=index,
                        damage_total=dmg_total,
                        damage_notation=damage_notation
                        + (f"+{ability_mod}" if add_mod else ""),
                        damage_rolls=dmg_rolls,
                        auto_hit=True,
                    )
                )
                continue

            d20 = _roll_spell_attack(
                attack_bonus, ability_mod, proficiency, ability_id, rng=rng
            )
            dmg_total, dmg_rolls = _roll_dice(damage_notation, rng=rng)
            if add_mod:
                dmg_total += ability_mod
            total_damage += dmg_total
            all_damage_rolls.extend(dmg_rolls)
            attack_rolls.append(
                SpellAttackRoll(
                    index=index,
                    attack_bonus=attack_bonus,
                    d20_result=d20,
                    damage_total=dmg_total,
                    damage_notation=damage_notation
                    + (f"+{ability_mod}" if add_mod else ""),
                    damage_rolls=dmg_rolls,
                )
            )

        if auto_hit:
            result.attack_bonus = None
        else:
            result.attack_bonus = attack_bonus
        result.attack_rolls = attack_rolls
        if auto_hit and instances > 1:
            result.damage_notation = f"{instances}×({damage_notation})"
        else:
            result.damage_notation = damage_notation + (
                f"+mod {ability_id}" if add_mod else ""
            )
        result.damage_total = total_damage
        result.damage_rolls = all_damage_rolls
        if updated.class_id == "sorcerer" and total_damage > 0 and damage_type:
            from jdr_engine.rules.class_features.sorcerer import elemental_affinity_bonus

            cha_score = updated.ability_scores.with_defaults(
                ["str", "dex", "con", "int", "wis", "cha"]
            ).scores.get("cha", 10)
            bonus = elemental_affinity_bonus(
                updated.choices or {},
                cha_score=cha_score,
                spell_damage_type=damage_type,
            )
            if bonus:
                result.damage_total = total_damage + bonus
        if (
            spell_id == "eldritch_blast"
            and updated.class_id == "warlock"
            and total_damage > 0
        ):
            from jdr_engine.rules.class_features.warlock import (
                agonizing_blast_bonus,
                has_agonizing_blast,
            )

            if has_agonizing_blast(updated.choices or {}):
                cha_score = updated.ability_scores.with_defaults(
                    ["str", "dex", "con", "int", "wis", "cha"]
                ).scores.get("cha", 10)
                ab_bonus = agonizing_blast_bonus(cha_score)
                if ab_bonus:
                    result.damage_total = (result.damage_total or 0) + ab_bonus
        if effect.get("invocation"):
            result.utility_text = _localized(spell_def, "invocation_effect", locale)

    elif effect_type == "saving_throw":
        save_info = _save_spec(effect)
        save_ability = str(save_info.get("ability", "dex"))
        damage_notation = str(effect.get("damage", ""))
        half_on_save = bool(save_info.get("half_on_save", True))
        dmg_total, dmg_rolls = _roll_dice(damage_notation, rng=rng)
        result.save_dc = save_dc
        result.save_ability = save_ability
        result.damage_total = dmg_total
        result.damage_notation = damage_notation
        result.damage_rolls = dmg_rolls
        result.half_on_save = half_on_save
        if save_info.get("reaction"):
            result.utility_text = "Réaction — en réponse à des dégâts reçus (SRD 2014)"
        if updated.class_id == "sorcerer" and dmg_total > 0 and damage_type:
            from jdr_engine.rules.class_features.sorcerer import elemental_affinity_bonus

            cha_score = updated.ability_scores.with_defaults(
                ["str", "dex", "con", "int", "wis", "cha"]
            ).scores.get("cha", 10)
            bonus = elemental_affinity_bonus(
                updated.choices or {},
                cha_score=cha_score,
                spell_damage_type=damage_type,
            )
            if bonus:
                result.damage_total = dmg_total + bonus

    elif effect_type == "healing":
        heal_notation = str(effect.get("healing", "1d8"))
        add_mod = bool(effect.get("add_ability_mod", True))
        heal_total, heal_rolls = _roll_dice(heal_notation, rng=rng)
        if add_mod:
            heal_total += ability_mod
        if (
            character.class_id == "cleric"
            and spell_level >= 1
        ):
            from jdr_engine.domain.character.choices_schema import get_specialization_id
            from jdr_engine.rules.class_features.cleric import disciple_of_life_bonus

            if get_specialization_id(character.choices) == "life":
                heal_total += disciple_of_life_bonus(spell_level)
        updated, hp_before, hp_after, hp_max, healing_applied, capped = _apply_healing(
            updated, engine, heal_total
        )
        result.healing_total = heal_total
        result.healing_applied = healing_applied
        result.healing_rolls = heal_rolls
        result.hp_before = hp_before
        result.hp_after = hp_after
        result.hp_max = hp_max
        result.healing_capped = capped
        result.damage_notation = heal_notation + (f"+mod {ability_id}" if add_mod else "")

    elif effect_type == "buff":
        result.buff_text = _localized(spell_def, "buff_effect", locale)
        if concentration:
            updated = _set_concentration(updated, spell_id, spell_name)

    elif effect_type == "utility":
        result.utility_text = _localized(spell_def, "utility_effect", locale)

    else:
        raise SpellCastError(f"Type d'effet non pris en charge : {effect_type!r}")

    slot_consumed: int | None = None
    if spell_level > 0:
        before_used = dict(get_slots_used(updated))
        updated = consume_spell_slot(updated, spell_level)
        after_used = get_slots_used(updated)
        for level in sorted(after_used.keys()):
            if after_used.get(level, 0) > before_used.get(level, 0):
                slot_consumed = level
                break

        upcast_die = effect.get("upcast_damage")
        if (
            slot_consumed
            and slot_consumed > spell_level
            and upcast_die
            and result.damage_total is not None
        ):
            extra_levels = slot_consumed - spell_level
            for _ in range(extra_levels):
                extra, extra_rolls = _roll_dice(str(upcast_die), rng=rng)
                result.damage_total += extra
                result.damage_rolls.extend(extra_rolls)
            result.damage_notation = (
                f"{result.damage_notation} + {extra_levels}×{upcast_die} (emplacement niv. {slot_consumed})"
            )

    remaining = get_remaining_slots(
        updated.class_id, updated.level, get_slots_used(updated)
    )
    result.slot_consumed_level = slot_consumed
    result.slots_remaining = remaining
    if persist_slots:
        result.updated_character = updated

    if character.class_id == "sorcerer" and spell_level >= 0:
        from jdr_engine.rules.class_features.sorcerer import (
            METAMAGIC_LABELS_FR,
            applicable_metamagic_for_spell,
        )

        meta = applicable_metamagic_for_spell(
            character.choices or {},
            spell_level=spell_level,
            targets_single_creature=effect_type == "spell_attack",
        )
        if meta:
            lines = [
                f"**{METAMAGIC_LABELS_FR.get(m, m)}** ({cost} pt{'s' if cost > 1 else ''})"
                for m, cost in meta
            ]
            result.display_lines = build_spell_display_lines(
                result,
                locale=locale,
                spell_mechanics=mechanics,
                character_level=character.level,
            )
            result.display_lines.append(
                "Métamagie disponible : " + ", ".join(lines)
            )
            return result

    result.display_lines = build_spell_display_lines(
        result,
        locale=locale,
        spell_mechanics=mechanics,
        character_level=character.level,
    )
    return result


def build_spell_display_lines(
    result: SpellCastResult,
    *,
    locale: str = "fr",
    spell_mechanics: dict[str, Any] | None = None,
    character_level: int = 1,
) -> list[str]:
    """Lignes style « Traits actifs » pour embed Discord."""
    lines: list[str] = []
    if spell_mechanics:
        lines.extend(
            build_spell_mechanics_reference_lines(
                spell_mechanics,
                locale=locale,
                character_level=character_level,
                spell_id=result.spell_id,
            )
        )
    level_label = "tour de magie" if result.spell_level == 0 else f"sort niv. {result.spell_level}"
    lines.append(f"{result.spell_name} ({level_label}) — {result.school}")

    if result.effect_type == "spell_attack" and result.attack_rolls:
        auto_hit = result.attack_bonus is None
        if auto_hit:
            lines.append("Touché automatiquement (SRD 2014)")
            label = "Dard" if result.spell_id == "magic_missile" else "Projectile"
            for atk in result.attack_rolls:
                prefix = (
                    f"{label} {atk.index}"
                    if len(result.attack_rolls) > 1
                    else label
                )
                lines.append(
                    f"{prefix} : **{atk.damage_total}** ({atk.damage_notation})"
                )
        elif result.attack_bonus is not None:
            lines.append(f"Jet d'attaque de sort : **+{result.attack_bonus}**")
            for atk in result.attack_rolls:
                if atk.d20_result is None:
                    continue
                prefix = (
                    f"Attaque {atk.index}" if len(result.attack_rolls) > 1 else "d20"
                )
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
        if result.utility_text:
            lines.append(result.utility_text)

    elif result.effect_type == "saving_throw":
        ability = (result.save_ability or "dex").upper()
        lines.append(f"DD de sauvegarde {ability} : **{result.save_dc}**")
        dmg_label = _damage_type_label(result.damage_type)
        lines.append(
            f"Dégâts{dmg_label} (échec) : **{result.damage_total}** ({result.damage_notation})"
        )
        if result.half_on_save:
            lines.append("Demi-dégâts en cas de réussite (SRD 2014)")
        else:
            lines.append("Aucun dégât en cas de réussite (SRD 2014)")

    elif result.effect_type == "healing" and result.healing_total is not None:
        notation = result.damage_notation or "1d8+mod"
        applied = result.healing_applied if result.healing_applied is not None else 0
        if applied <= 0 and result.hp_before == result.hp_max:
            lines.append(
                f"PV : **{result.hp_before}** / **{result.hp_max}** (déjà au maximum)"
            )
        else:
            if result.healing_capped and applied < result.healing_total:
                lines.append(
                    f"Soins : **+{applied} PV** (jet {result.healing_total}, plafonné — {notation})"
                )
            else:
                lines.append(f"Soins : **+{applied} PV** ({notation})")
            if (
                result.hp_before is not None
                and result.hp_after is not None
                and result.hp_max is not None
            ):
                if result.hp_after >= result.hp_max:
                    lines.append(
                        f"PV : **{result.hp_before}** → **{result.hp_after}** / **{result.hp_max}** (maximum atteint)"
                    )
                else:
                    lines.append(
                        f"PV : **{result.hp_before}** → **{result.hp_after}** / **{result.hp_max}**"
                    )

    elif result.effect_type == "buff" and result.buff_text:
        if result.concentration:
            lines.append(f"**Concentration** — {result.duration}")
        lines.append(result.buff_text)

    elif result.effect_type == "utility" and result.utility_text:
        if result.concentration:
            lines.append(f"**Concentration** — {result.duration}")
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
        "radiant": " radiants",
        "necrotic": " nécrotiques",
        "force": " de force",
        "psychic": " psychiques",
        "variable": " (type au choix)",
    }
    return labels.get(damage_type, f" {damage_type}")
