# jdr_engine/rules/derived_stats.py
"""Calculs dérivés SRD 2014 — fonctions pures réutilisables."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from jdr_engine.domain.character.ability_scores import DEFAULT_ABILITY_IDS, format_modifier
from jdr_engine.domain.character.character import Character
from jdr_engine.domain.character.choices_schema import (
    get_fighting_style_id,
    get_skill_choices,
    get_specialization_id,
)
from jdr_engine.rules.engine import RuleEngine

# Compétences SRD — libellés FR pour affichage (pas d'entités skills/ dans le compendium).
SKILL_LABELS_FR: dict[str, str] = {
    "acrobatics": "Acrobaties",
    "animal_handling": "Dressage",
    "arcana": "Arcanes",
    "athletics": "Athlétisme",
    "deception": "Tromperie",
    "history": "Histoire",
    "insight": "Perspicacité",
    "intimidation": "Intimidation",
    "investigation": "Investigation",
    "medicine": "Médecine",
    "nature": "Nature",
    "perception": "Perception",
    "performance": "Représentation",
    "persuasion": "Persuasion",
    "religion": "Religion",
    "sleight_of_hand": "Escamotage",
    "stealth": "Discrétion",
    "survival": "Survie",
}

FIGHTING_STYLE_LABELS_FR: dict[str, str] = {
    "archery": "Archerie",
    "defense": "Défense",
    "dueling": "Duelliste",
    "great_weapon_fighting": "Combat à deux armes lourdes",
    "protection": "Protection",
    "two_weapon_fighting": "Combat à deux armes",
}

ABILITY_LABELS_FR: dict[str, str] = {
    "str": "FOR",
    "dex": "DEX",
    "con": "CON",
    "int": "INT",
    "wis": "SAG",
    "cha": "CHA",
}


@dataclass(frozen=True)
class SavingThrowLine:
    ability_id: str
    modifier: int
    proficient: bool

    @property
    def label(self) -> str:
        return ABILITY_LABELS_FR.get(self.ability_id, self.ability_id.upper())

    def format_display(self) -> str:
        mod = format_modifier(self.modifier)
        mark = " ●" if self.proficient else ""
        return f"{self.label} {mod}{mark}"


def skill_label_fr(skill_id: str) -> str:
    return SKILL_LABELS_FR.get(skill_id, skill_id.replace("_", " ").title())


def fighting_style_label_fr(style_id: str) -> str:
    return FIGHTING_STYLE_LABELS_FR.get(
        style_id, style_id.replace("_", " ").title()
    )


def specialization_label_fr(spec_id: str) -> str:
    return spec_id.replace("_", " ").title()


def calculate_initiative(dex_modifier: int) -> int:
    """Initiative de base SRD : modificateur de Dextérité."""
    return dex_modifier


def calculate_saving_throw_modifier(
    ability_modifier: int,
    *,
    proficient: bool,
    proficiency_bonus: int,
) -> int:
    """Modificateur de jet de sauvegarde (affichage / jets futurs)."""
    return ability_modifier + (proficiency_bonus if proficient else 0)


def get_class_saving_throw_proficiencies(
    engine: RuleEngine,
    class_id: str,
) -> frozenset[str]:
    entry = engine.get_entity("class", class_id)
    if entry is None:
        return frozenset()
    raw = entry.definition.mechanics.get("saving_throw_proficiencies") or []
    return frozenset(str(a) for a in raw if a)


def build_saving_throws(
    ability_modifiers: dict[str, int],
    *,
    proficient_abilities: frozenset[str],
    proficiency_bonus: int,
) -> tuple[SavingThrowLine, ...]:
    lines: list[SavingThrowLine] = []
    for ability_id in DEFAULT_ABILITY_IDS:
        proficient = ability_id in proficient_abilities
        mod = calculate_saving_throw_modifier(
            ability_modifiers.get(ability_id, 0),
            proficient=proficient,
            proficiency_bonus=proficiency_bonus,
        )
        lines.append(
            SavingThrowLine(
                ability_id=ability_id,
                modifier=mod,
                proficient=proficient,
            )
        )
    return tuple(lines)


def _eval_ac_formula(
    ac_formula: dict,
    ability_modifiers: dict[str, int],
) -> int:
    base = int(ac_formula.get("base", 10))
    total = base
    for ability_id in ac_formula.get("plus") or []:
        total += ability_modifiers.get(str(ability_id), 0)
    return total


def calculate_armor_class(
    character: Character,
    engine: RuleEngine,
    ability_modifiers: dict[str, int],
) -> int:
    """
    CA de base SRD (sans armure équipée).

    Utilise ``ac_formula`` des aptitudes de classe (Barbare, Moine) si applicable ;
    sinon 10 + mod DEX.
    """
    for feature in engine.get_class_features(character.class_id, character.level):
        ac_formula = feature.definition.mechanics.get("ac_formula")
        if isinstance(ac_formula, dict):
            return _eval_ac_formula(ac_formula, ability_modifiers)
    return 10 + ability_modifiers.get("dex", 0)


def calculate_hp_max(
    level: int,
    hit_die_faces: int,
    con_modifier: int,
    *,
    persisted_hp_max: int | None = None,
) -> int:
    """PV maximum SRD (niv.1 : max dé ; niveaux suivants : moyenne arrondie + mod CON)."""
    if level < 1:
        level = 1
    hp = max(1, hit_die_faces + con_modifier)
    if level > 1:
        per_level = calculate_hp_gain_per_level(hit_die_faces, con_modifier)
        hp += (level - 1) * per_level
        hp = max(1, hp)
    if persisted_hp_max is not None:
        return max(1, int(persisted_hp_max))
    return hp


def calculate_hp_gain_per_level(hit_die_faces: int, con_modifier: int) -> int:
    """Gain de PV à chaque montée de niveau (moyenne SRD : dé/2 arrondi sup. + mod CON)."""
    return max(1, hit_die_faces // 2 + 1 + con_modifier)


def collect_racial_skill_proficiencies(
    engine: RuleEngine,
    race_id: str,
) -> list[str]:
    """Compétences accordées par les traits raciaux (ex. Perception halfelin)."""
    granted: list[str] = []
    for trait in engine.get_race_traits(race_id):
        for effect in trait.definition.mechanics.get("effects") or []:
            if not isinstance(effect, dict):
                continue
            if effect.get("type") == "grant_proficiency":
                skill = effect.get("skill")
                if skill and str(skill) not in granted:
                    granted.append(str(skill))
    return granted


def _get_racial_skill_ids(character: Character) -> tuple[str, ...]:
    raw = (character.choices or {}).get("racial_skills") or []
    if not isinstance(raw, list):
        return ()
    return tuple(str(s) for s in raw if s)


def collect_proficient_skills(
    character: Character,
    engine: RuleEngine,
) -> tuple[str, ...]:
    """Compétences maîtrisées = choix joueur + bonus raciaux + compétences raciales."""
    chosen = list(get_skill_choices(character.choices))
    for skill_id in _get_racial_skill_ids(character):
        if skill_id not in chosen:
            chosen.append(skill_id)
    for skill_id in collect_racial_skill_proficiencies(engine, character.race_id):
        if skill_id not in chosen:
            chosen.append(skill_id)
    return tuple(sorted(chosen))


def read_hit_dice(character: Character) -> tuple[int, int]:
    """(restants, total) — lecture seule, sans mutation."""
    raw = (character.choices or {}).get("rest")
    state = dict(raw) if isinstance(raw, dict) else {}
    total = max(1, int(character.level))
    if state.get("hit_dice_total") is not None:
        total = max(1, int(state["hit_dice_total"]))
    remaining = int(state.get("hit_dice_remaining", total))
    remaining = max(0, min(remaining, total))
    return remaining, total


def resolve_specialization_label(
    choices: dict[str, Any] | None,
    engine: RuleEngine | None = None,
    *,
    locale: str = "fr",
) -> tuple[str | None, str | None]:
    spec_id = get_specialization_id(choices)
    if not spec_id:
        return None, None
    if engine is not None:
        for trait_id in (f"{spec_id}_domain", spec_id):
            trait = engine.get_entity("trait", trait_id)
            if trait is not None:
                name = trait.get_name(locale, engine.registry.manifest.default_locale)
                return spec_id, name
    return spec_id, specialization_label_fr(spec_id)


def resolve_fighting_style_label(
    choices: dict[str, Any] | None,
    engine: RuleEngine,
    *,
    locale: str = "fr",
) -> tuple[str | None, str | None]:
    style_id = get_fighting_style_id(choices)
    if not style_id:
        return None, None
    trait = engine.get_entity("trait", f"fighting_style_{style_id}")
    if trait is not None:
        name = trait.get_name(locale, engine.registry.manifest.default_locale)
        return style_id, name
    return style_id, fighting_style_label_fr(style_id)
