# jdr_engine/rules/character_progression/level_up.py
"""Montée de niveau SRD 2014 — niv. 2–3 (Lots 1–3)."""
from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Literal

from jdr_engine.domain.character.character import Character
from jdr_engine.rules.calculator import build_character_sheet, parse_hit_die
from jdr_engine.rules.character_creation.class_choices import (
    CreationChoiceError,
    get_fighting_style_options_for_class,
    get_lore_bonus_skill_count,
    get_lore_bonus_skill_options,
    requires_expertise_at_level,
    requires_fighting_style_at_level,
    requires_lore_bonus_at_level,
    validate_expertise_skills,
    validate_fighting_style_at_level,
    validate_lore_bonus_skills,
    get_expertise_skill_count,
    get_eldritch_invocation_options,
    get_eldritch_invocation_pick_count,
    get_metamagic_options,
    get_metamagic_pick_count,
    get_pact_boon_options,
    requires_eldritch_invocations_at_level,
    requires_metamagic_at_level,
    requires_pact_boon_at_level,
    validate_eldritch_invocations,
    validate_metamagic_options,
    validate_pact_boon,
)
from jdr_engine.rules.character_creation.playable import LEVEL_UP_CLASSES
from jdr_engine.rules.derived_stats import collect_proficient_skills
from jdr_engine.domain.character.ability_scores import DEFAULT_ABILITY_IDS, ability_modifier
from jdr_engine.domain.character.choices_schema import get_specialization_id
from jdr_engine.rules.character_creation.starting_spells import (
    init_half_caster_spellcasting_if_needed,
    upgrade_full_caster_spellcasting,
    upgrade_half_caster_spellcasting,
    upgrade_pact_caster_spellcasting,
)
from jdr_engine.rules.character_creation.subclass_choices import (
    get_subclass_choice_config,
    get_subclass_option,
    requires_subclass_at_level,
    validate_subclass_choice,
)
from jdr_engine.rules.derived_stats import calculate_hp_gain_per_level
from jdr_engine.rules.engine import RuleEngine
from jdr_engine.rules.rest.state import hit_dice_remaining, hit_dice_total, sync_hit_dice_total
from jdr_engine.rules.character_progression.asi import (
    ABILITY_LABELS_FR,
    AsiValidationError,
    apply_asi_to_base,
    asi_already_applied,
    eligible_asi_abilities,
    record_asi_applied,
    requires_asi_at_level,
    validate_asi,
)
from jdr_engine.rules.racial.resolve import get_racial_ability_bonuses
from jdr_engine.rules.spellcasting.slots import get_max_spell_slots

from jdr_engine.rules.progression_constants import (
    MAX_CHARACTER_LEVEL,
    MAX_LEVEL_LOT2,
)


class LevelUpError(Exception):
    """Montée de niveau impossible (niveau max, classe non supportée, etc.)."""


@dataclass(frozen=True)
class LevelUpPending:
    """Choix requis avant de finaliser la montée de niveau."""

    character: Character
    target_level: int
    choice_type: Literal[
        "subclass",
        "subchoice",
        "fighting_style",
        "lore_bonus_skills",
        "expertise_skills",
        "metamagic_options",
        "eldritch_invocations",
        "pact_boon",
        "ability_score_improvement",
    ]
    options: tuple[str, ...]
    parent_subclass: str | None = None
    subchoice_storage_key: str | None = None
    required_count: int = 1

    @property
    def message(self) -> str:
        if self.choice_type == "fighting_style":
            return "Choisissez votre style de combat (niv. 2)."
        if self.choice_type == "subchoice":
            if self.subchoice_storage_key == "hunter_prey":
                return "Choisissez votre option de proie (Chasseur, niv. 3)."
            return "Choisissez une option de sous-classe (niv. 3)."
        if self.choice_type == "lore_bonus_skills":
            return (
                f"Choisissez **{self.required_count}** compétence(s) bonus "
                f"(Collège du Savoir, non déjà maîtrisées)."
            )
        if self.choice_type == "expertise_skills":
            return (
                f"Choisissez **{self.required_count}** compétence(s) "
                f"pour l'**Expertise** (parmi vos maîtrises)."
            )
        if self.choice_type == "metamagic_options":
            return (
                f"Choisissez **{self.required_count}** option(s) de **Métamagie**."
            )
        if self.choice_type == "eldritch_invocations":
            return (
                f"Choisissez **{self.required_count}** **Manifestation(s) occulte(s)**."
            )
        if self.choice_type == "pact_boon":
            return "Choisissez votre **Faveur du pacte**."
        if self.choice_type == "ability_score_improvement":
            return (
                "Choisissez **+2** à une caractéristique "
                "ou **+1** à deux caractéristiques (cap effectif **20**)."
            )
        return f"Choisissez votre sous-classe (niv. {self.target_level})."


class LevelUpPendingChoice(Exception):
    """Interrompt la montée de niveau — le client Discord doit présenter un menu."""

    def __init__(self, pending: LevelUpPending):
        self.pending = pending
        super().__init__(pending.message)


@dataclass(frozen=True)
class LevelUpResult:
    character_name: str
    class_id: str
    old_level: int
    new_level: int
    hp_before: int
    hp_after: int
    hp_max_before: int
    hp_max_after: int
    hp_gain: int
    hit_dice_before: int
    hit_dice_after: int
    slots_max_before: str
    slots_max_after: str


def _format_max_slots(class_id: str, level: int) -> str:
    max_slots = get_max_spell_slots(class_id, level)
    if not max_slots:
        return "—"
    return ", ".join(f"niv.{lvl}: {count}" for lvl, count in sorted(max_slots.items()))


def _apply_subchoice_to_choices(
    choices: dict,
    storage_key: str,
    value: str,
) -> dict:
    updated = dict(choices)
    updated[storage_key] = value
    return updated


def _ensure_fighting_style_for_level(
    character: Character,
    engine: RuleEngine,
    new_level: int,
    *,
    fighting_style: str | None,
) -> Character:
    if not requires_fighting_style_at_level(engine, character.class_id, new_level):
        return character

    choices = dict(character.choices or {})
    if fighting_style:
        style = validate_fighting_style_at_level(
            engine,
            character.class_id,
            fighting_style,
            character_level=new_level,
        )
        choices["fighting_style"] = style
        return replace(character, choices=choices)

    if not choices.get("fighting_style"):
        options = get_fighting_style_options_for_class(engine, character.class_id)
        if not options:
            return character
        raise LevelUpPendingChoice(
            LevelUpPending(
                character=character,
                target_level=new_level,
                choice_type="fighting_style",
                options=options,
            )
        )
    return character


def _resolve_subchoice_value(
    choices: dict,
    engine: RuleEngine,
    class_id: str,
    spec_id: str,
    *,
    subchoice_value: str | None = None,
    totem_spirit: str | None = None,
) -> str | None:
    """Sous-choix explicite ou déjà stocké sur le personnage (ex. sorcerer_dragon_type)."""
    raw = subchoice_value if subchoice_value is not None else totem_spirit
    if raw and str(raw).strip():
        return str(raw).strip()
    option = get_subclass_option(engine, class_id, spec_id)
    if option is None or option.subchoice is None:
        return None
    stored = choices.get(option.subchoice.storage_key)
    if stored and str(stored).strip():
        return str(stored).strip()
    return None


def _subclass_choice_complete(
    choices: dict,
    engine: RuleEngine,
    class_id: str,
    spec_id: str,
) -> bool:
    """True si sous-classe + sous-choix requis déjà renseignés."""
    option = get_subclass_option(engine, class_id, spec_id)
    if option is None:
        return False
    if option.subchoice is None:
        return True
    return bool(_resolve_subchoice_value(choices, engine, class_id, spec_id))


def _ensure_subclass_for_level(
    character: Character,
    engine: RuleEngine,
    new_level: int,
    *,
    subclass: str | None,
    totem_spirit: str | None = None,
    subchoice_value: str | None = None,
) -> Character:
    """Valide ou demande sous-classe / sous-choix avant montée au niv. 3."""
    if not requires_subclass_at_level(engine, character.class_id, new_level):
        return character

    choices = dict(character.choices or {})
    spec = choices.get("specialization")
    resolved_sub = _resolve_subchoice_value(
        choices,
        engine,
        character.class_id,
        str(subclass or spec or "").strip(),
        subchoice_value=subchoice_value,
        totem_spirit=totem_spirit,
    )

    if subclass:
        spec_id = str(subclass).strip()
        option = get_subclass_option(engine, character.class_id, spec_id)
        if spec == spec_id and _subclass_choice_complete(
            choices, engine, character.class_id, spec_id
        ):
            return character
        if option is None:
            validate_subclass_choice(
                engine,
                character.class_id,
                subclass,
                totem_spirit=totem_spirit,
                subchoice_value=resolved_sub,
                character_level=new_level,
            )
        elif option.subchoice is not None and not resolved_sub:
            key = option.subchoice.storage_key
            if not choices.get(key):
                raise LevelUpPendingChoice(
                    LevelUpPending(
                        character=character,
                        target_level=new_level,
                        choice_type="subchoice",
                        options=option.subchoice.options,
                        parent_subclass=spec_id,
                        subchoice_storage_key=key,
                    )
                )
        validated_spec, sub_id, sub_key = validate_subclass_choice(
            engine,
            character.class_id,
            subclass,
            totem_spirit=totem_spirit,
            subchoice_value=resolved_sub,
            character_level=new_level,
        )
        choices["specialization"] = validated_spec
        if sub_id and sub_key:
            choices[sub_key] = sub_id
        return replace(character, choices=choices)

    if not spec:
        config = get_subclass_choice_config(engine, character.class_id)
        if config is None:
            return character
        raise LevelUpPendingChoice(
            LevelUpPending(
                character=character,
                target_level=new_level,
                choice_type="subclass",
                options=tuple(o.id for o in config.options),
            )
        )

    option = get_subclass_option(engine, character.class_id, str(spec))
    if option and option.subchoice is not None:
        key = option.subchoice.storage_key
        stored_sub = _resolve_subchoice_value(
            choices,
            engine,
            character.class_id,
            str(spec),
            subchoice_value=subchoice_value,
            totem_spirit=totem_spirit,
        )
        if not choices.get(key):
            if stored_sub:
                _, sub_id, sub_key = validate_subclass_choice(
                    engine,
                    character.class_id,
                    str(spec),
                    totem_spirit=totem_spirit,
                    subchoice_value=stored_sub,
                    character_level=new_level,
                )
                if sub_id and sub_key:
                    choices[sub_key] = sub_id
                return replace(character, choices=choices)
            raise LevelUpPendingChoice(
                LevelUpPending(
                    character=character,
                    target_level=new_level,
                    choice_type="subchoice",
                    options=option.subchoice.options,
                    parent_subclass=str(spec),
                    subchoice_storage_key=key,
                )
            )

    return character


def _lore_bonus_already_set(choices: dict, *, required: int) -> bool:
    raw = choices.get("lore_bonus_skills") or []
    return isinstance(raw, list) and len(raw) == required


def _expertise_already_set(choices: dict, *, required: int) -> bool:
    raw = choices.get("expertise_skills") or []
    return isinstance(raw, list) and len(raw) == required


def _ensure_lore_bonus_for_level(
    character: Character,
    engine: RuleEngine,
    new_level: int,
    *,
    lore_bonus_skills: list[str] | tuple[str, ...] | None,
) -> Character:
    choices = dict(character.choices or {})
    spec = choices.get("specialization")
    if not requires_lore_bonus_at_level(
        engine, character.class_id, str(spec) if spec else None, level=new_level
    ):
        return character

    required = get_lore_bonus_skill_count(engine)
    if lore_bonus_skills is not None:
        try:
            validated = validate_lore_bonus_skills(
                engine,
                character.class_id,
                str(spec) if spec else None,
                lore_bonus_skills,
                level=new_level,
            )
        except CreationChoiceError as exc:
            raise LevelUpError(str(exc)) from exc
        choices["lore_bonus_skills"] = list(validated)
        return replace(character, choices=choices)

    if _lore_bonus_already_set(choices, required=required):
        return character

    proficient = collect_proficient_skills(character, engine)
    options = get_lore_bonus_skill_options(
        engine, character.class_id, proficient
    )
    if len(options) < required:
        raise LevelUpError(
            "Compétences bonus insuffisantes disponibles pour le Collège du Savoir."
        )
    raise LevelUpPendingChoice(
        LevelUpPending(
            character=character,
            target_level=new_level,
            choice_type="lore_bonus_skills",
            options=options,
            parent_subclass=str(spec) if spec else None,
            required_count=required,
        )
    )


def _ensure_expertise_for_level(
    character: Character,
    engine: RuleEngine,
    new_level: int,
    *,
    expertise_skills: list[str] | tuple[str, ...] | None,
) -> Character:
    if not requires_expertise_at_level(engine, character.class_id, level=new_level):
        return character

    choices = dict(character.choices or {})
    required = get_expertise_skill_count(engine, character.class_id, level=new_level)

    if expertise_skills is not None:
        proficient = collect_proficient_skills(character, engine)
        try:
            validated = validate_expertise_skills(
                engine,
                character.class_id,
                expertise_skills,
                proficient,
                level=new_level,
            )
        except CreationChoiceError as exc:
            raise LevelUpError(str(exc)) from exc
        choices["expertise_skills"] = list(validated)
        return replace(character, choices=choices)

    if _expertise_already_set(choices, required=required):
        return character

    proficient = collect_proficient_skills(character, engine)
    if len(proficient) < required:
        raise LevelUpError(
            f"Expertise : {required} maîtrise(s) requise(s), "
            f"{len(proficient)} disponible(s)."
        )
    raise LevelUpPendingChoice(
        LevelUpPending(
            character=character,
            target_level=new_level,
            choice_type="expertise_skills",
            options=tuple(proficient),
            parent_subclass=choices.get("specialization"),
            required_count=required,
        )
    )


def _metamagic_already_set(choices: dict, *, required: int) -> bool:
    raw = choices.get("metamagic_options") or []
    return isinstance(raw, list) and len(raw) == required


def _ensure_metamagic_for_level(
    character: Character,
    engine: RuleEngine,
    new_level: int,
    *,
    metamagic_options: list[str] | tuple[str, ...] | None,
) -> Character:
    if not requires_metamagic_at_level(engine, character.class_id, level=new_level):
        return character

    choices = dict(character.choices or {})
    required = get_metamagic_pick_count(engine)

    if metamagic_options is not None:
        try:
            validated = validate_metamagic_options(
                engine,
                character.class_id,
                metamagic_options,
                level=new_level,
            )
        except CreationChoiceError as exc:
            raise LevelUpError(str(exc)) from exc
        choices["metamagic_options"] = list(validated)
        return replace(character, choices=choices)

    if _metamagic_already_set(choices, required=required):
        return character

    options = get_metamagic_options(engine)
    raise LevelUpPendingChoice(
        LevelUpPending(
            character=character,
            target_level=new_level,
            choice_type="metamagic_options",
            options=options,
            required_count=required,
        )
    )


def _invocations_already_set(choices: dict, *, required: int) -> bool:
    raw = choices.get("eldritch_invocations") or []
    return isinstance(raw, list) and len(raw) == required


def _ensure_eldritch_invocations_for_level(
    character: Character,
    engine: RuleEngine,
    new_level: int,
    *,
    eldritch_invocations: list[str] | tuple[str, ...] | None,
) -> Character:
    if not requires_eldritch_invocations_at_level(
        engine, character.class_id, level=new_level
    ):
        return character

    choices = dict(character.choices or {})
    required = get_eldritch_invocation_pick_count(engine)

    if eldritch_invocations is not None:
        try:
            validated = validate_eldritch_invocations(
                engine,
                character.class_id,
                eldritch_invocations,
                level=new_level,
            )
        except CreationChoiceError as exc:
            raise LevelUpError(str(exc)) from exc
        choices["eldritch_invocations"] = list(validated)
        return replace(character, choices=choices)

    if _invocations_already_set(choices, required=required):
        return character

    options = get_eldritch_invocation_options(engine)
    raise LevelUpPendingChoice(
        LevelUpPending(
            character=character,
            target_level=new_level,
            choice_type="eldritch_invocations",
            options=options,
            required_count=required,
        )
    )


def _pact_boon_already_set(choices: dict) -> bool:
    raw = choices.get("pact_boon")
    return bool(raw and str(raw).strip())


def _ensure_pact_boon_for_level(
    character: Character,
    engine: RuleEngine,
    new_level: int,
    *,
    pact_boon: str | None,
) -> Character:
    if not requires_pact_boon_at_level(engine, character.class_id, level=new_level):
        return character

    choices = dict(character.choices or {})

    if pact_boon is not None:
        try:
            validated = validate_pact_boon(
                engine,
                character.class_id,
                pact_boon,
                level=new_level,
            )
        except CreationChoiceError as exc:
            raise LevelUpError(str(exc)) from exc
        if validated:
            choices["pact_boon"] = validated
        return replace(character, choices=choices)

    if _pact_boon_already_set(choices):
        return character

    options = get_pact_boon_options(engine)
    raise LevelUpPendingChoice(
        LevelUpPending(
            character=character,
            target_level=new_level,
            choice_type="pact_boon",
            options=options,
            required_count=1,
        )
    )


def _ensure_asi_for_level(
    character: Character,
    engine: RuleEngine,
    new_level: int,
    *,
    asi_choice: dict[str, int] | None = None,
) -> Character:
    if not requires_asi_at_level(new_level):
        return character

    choices = dict(character.choices or {})
    if asi_already_applied(choices, new_level):
        return character

    base_scores = character.ability_scores.with_defaults(list(DEFAULT_ABILITY_IDS)).scores
    racial_bonuses = get_racial_ability_bonuses(character, engine)

    if asi_choice is not None:
        try:
            bonuses = validate_asi(base_scores, racial_bonuses, asi_choice)
        except AsiValidationError as exc:
            raise LevelUpError(str(exc)) from exc
        new_scores = apply_asi_to_base(character.ability_scores, bonuses)
        choices = record_asi_applied(choices, new_level, bonuses)
        return replace(character, ability_scores=new_scores, choices=choices)

    options = eligible_asi_abilities(base_scores, racial_bonuses, increment=1)
    if not options:
        raise LevelUpError(
            "Aucune caractéristique n'est éligible à un ASI (cap 20 atteint)."
        )
    raise LevelUpPendingChoice(
        LevelUpPending(
            character=character,
            target_level=new_level,
            choice_type="ability_score_improvement",
            options=options,
            required_count=2,
        )
    )


def apply_level_up(
    character: Character,
    engine: RuleEngine,
    *,
    subclass: str | None = None,
    totem_spirit: str | None = None,
    subchoice_value: str | None = None,
    fighting_style: str | None = None,
    expertise_skills: list[str] | tuple[str, ...] | None = None,
    lore_bonus_skills: list[str] | tuple[str, ...] | None = None,
    metamagic_options: list[str] | tuple[str, ...] | None = None,
    eldritch_invocations: list[str] | tuple[str, ...] | None = None,
    pact_boon: str | None = None,
    asi_choice: dict[str, int] | None = None,
) -> tuple[Character, LevelUpResult]:
    """
    Monte le personnage d'un niveau (SRD 2014, niv. 2–3).

    Si choix requis (style niv. 2, sous-classe niv. 3) : ``LevelUpPendingChoice``.
    """
    if character.class_id not in LEVEL_UP_CLASSES:
        raise LevelUpError(
            f"Montée de niveau non supportée pour la classe « {character.class_id} »."
        )
    if character.level >= MAX_CHARACTER_LEVEL:
        raise LevelUpError(
            f"**{character.name}** est déjà au niveau maximum (niv. {MAX_CHARACTER_LEVEL})."
        )

    old_level = character.level
    new_level = old_level + 1

    character = _ensure_fighting_style_for_level(
        character,
        engine,
        new_level,
        fighting_style=fighting_style,
    )
    character = _ensure_subclass_for_level(
        character,
        engine,
        new_level,
        subclass=subclass,
        totem_spirit=totem_spirit,
        subchoice_value=subchoice_value,
    )
    character = _ensure_lore_bonus_for_level(
        character,
        engine,
        new_level,
        lore_bonus_skills=lore_bonus_skills,
    )
    character = _ensure_expertise_for_level(
        character,
        engine,
        new_level,
        expertise_skills=expertise_skills,
    )
    character = _ensure_metamagic_for_level(
        character,
        engine,
        new_level,
        metamagic_options=metamagic_options,
    )
    character = _ensure_eldritch_invocations_for_level(
        character,
        engine,
        new_level,
        eldritch_invocations=eldritch_invocations,
    )
    character = _ensure_pact_boon_for_level(
        character,
        engine,
        new_level,
        pact_boon=pact_boon,
    )
    character = _ensure_asi_for_level(
        character,
        engine,
        new_level,
        asi_choice=asi_choice,
    )

    sheet = build_character_sheet(character, engine)
    hit_die = engine.get_class_hit_die(character.class_id)
    if not hit_die:
        raise LevelUpError(f"Dé de vie introuvable pour {character.class_id!r}.")
    hit_die_faces = parse_hit_die(hit_die)
    con_mod = sheet.ability_modifiers.get("con", 0)

    hp_before = sheet.hp_current
    hp_max_before = sheet.hp_max
    hp_gain = calculate_hp_gain_per_level(hit_die_faces, con_mod)
    if character.class_id == "sorcerer" and get_specialization_id(character.choices) == "draconic":
        hp_gain += 1
    hp_max_after = hp_max_before + hp_gain
    hp_after = min(hp_before + hp_gain, hp_max_after)

    dice_before = hit_dice_remaining(character)
    slots_max_before = _format_max_slots(character.class_id, old_level)

    character.level = new_level
    character.hp_max = hp_max_after
    character.hp_current = hp_after
    character = sync_hit_dice_total(character)

    choices = dict(character.choices or {})

    if character.class_id == "barbarian":
        from jdr_engine.rules.class_features.barbarian import init_rage_uses

        choices = init_rage_uses(choices, level=new_level)

    if character.class_id == "monk" and new_level >= 2:
        from jdr_engine.rules.class_features.monk import init_ki_points

        choices = init_ki_points(choices, level=new_level)

    if character.class_id in ("ranger", "paladin"):
        from jdr_engine.rules.spellcasting.model import casting_ability_for_class

        ability_id = casting_ability_for_class(character.class_id)
        half_casting_mod = ability_modifier(sheet.ability_scores.get(ability_id, 10))
        choices = init_half_caster_spellcasting_if_needed(
            choices,
            character.class_id,
            level=new_level,
            casting_ability_mod=half_casting_mod,
        )
        if old_level >= 2 and new_level > old_level:
            choices = upgrade_half_caster_spellcasting(
                choices,
                character.class_id,
                new_level=new_level,
                casting_ability_mod=half_casting_mod,
            )

    if character.class_id in ("bard", "cleric", "wizard", "sorcerer", "druid"):
        wis_mod = ability_modifier(sheet.ability_scores.get("wis", 10))
        int_mod = ability_modifier(sheet.ability_scores.get("int", 10))
        casting_mod = int_mod if character.class_id == "wizard" else wis_mod
        domain_id = get_specialization_id(choices) if character.class_id == "cleric" else None
        if new_level > old_level:
            choices = upgrade_full_caster_spellcasting(
                choices,
                character.class_id,
                new_level=new_level,
                casting_ability_mod=casting_mod,
                domain_id=domain_id,
            )

    if character.class_id == "warlock" and new_level > old_level:
        choices = upgrade_pact_caster_spellcasting(
            choices,
            character.class_id,
            new_level=new_level,
            old_level=old_level,
        )

    if character.class_id == "wizard":
        from jdr_engine.rules.class_features.wizard import init_wizard_features

        choices = init_wizard_features(choices, level=new_level)

    if character.class_id == "sorcerer":
        from jdr_engine.rules.class_features.sorcerer import init_sorcerer_features

        choices = init_sorcerer_features(choices, level=new_level)

    if character.class_id == "druid":
        from jdr_engine.rules.class_features.druid import init_druid_features

        choices = init_druid_features(choices, level=new_level)

    if character.class_id == "bard":
        from jdr_engine.rules.class_features.bard import init_bard_features

        cha_score = sheet.ability_scores.get("cha", 10)
        choices = init_bard_features(choices, level=new_level, cha_score=cha_score)

    if character.class_id == "cleric":
        from jdr_engine.rules.class_features.cleric import (
            init_cleric_features,
            refresh_preserve_life_on_level_up,
        )

        choices = init_cleric_features(choices, level=new_level)
        choices = refresh_preserve_life_on_level_up(
            choices, old_level=old_level, new_level=new_level
        )

    if character.class_id == "paladin":
        from jdr_engine.rules.class_features.paladin import (
            init_paladin_features,
            refresh_lay_on_hands_on_level_up,
        )

        cha_score = sheet.ability_scores.get("cha", 10)
        choices = refresh_lay_on_hands_on_level_up(
            choices, old_level=old_level, new_level=new_level
        )
        choices = init_paladin_features(
            choices, level=new_level, cha_score=cha_score
        )

    character.choices = choices

    dice_after = hit_dice_total(character)
    slots_max_after = _format_max_slots(character.class_id, new_level)

    result = LevelUpResult(
        character_name=character.name,
        class_id=character.class_id,
        old_level=old_level,
        new_level=new_level,
        hp_before=hp_before,
        hp_after=hp_after,
        hp_max_before=hp_max_before,
        hp_max_after=hp_max_after,
        hp_gain=hp_gain,
        hit_dice_before=dice_before,
        hit_dice_after=dice_after,
        slots_max_before=slots_max_before,
        slots_max_after=slots_max_after,
    )
    return character, result
