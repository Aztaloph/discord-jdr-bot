# jdr_engine/domain/character/choices_schema.py
"""
Schéma extensible des choix persistés (character.choices).

Tous les choix joueur / état mécanique non-stat vit ici (JSON SQLite).
"""
from __future__ import annotations

from typing import Any

# Clés reconnues au niveau racine (documentation + évolution future).
CHOICE_KEYS: frozenset[str] = frozenset(
    {
        "skills",
        "specialization",
        "fighting_style",
        "expertise_skills",
        "spellcasting",
        "rest",
        "feature_state",
        "draconic_ancestry",
        "racial_ability_bonuses",
        "racial_skills",
        "innate_spells",
        "totem_spirit",
        "favored_enemy_type",
        "favored_terrain",
        "hunter_prey",
        "lore_bonus_skills",
        "sorcerer_dragon_type",
        "druid_land_terrain",
        "metamagic_options",
        "eldritch_invocations",
        "pact_boon",
    }
)


def _normalize_string_list(raw: Any) -> list[str]:
    if raw is None:
        return []
    if isinstance(raw, str):
        return [raw.strip()] if raw.strip() else []
    if not isinstance(raw, list):
        return []
    return [str(item).strip() for item in raw if item is not None and str(item).strip()]


def _normalize_specialization(raw: Any) -> str | None:
    if raw is None:
        return None
    if isinstance(raw, dict):
        value = raw.get("id") or raw.get("specialization")
        return str(value).strip() if value else None
    text = str(raw).strip()
    return text or None


def normalize_character_choices(raw: dict[str, Any] | None) -> dict[str, Any]:
    """
    Normalise choices pour persistance et lecture (rétrocompatibilité).

    - Fusionne ``skill_proficiencies`` / ``subclass`` (legacy) vers les clés canoniques.
    - Garantit des types stables ; n'écrase pas les clés inconnues (extensibilité).
    """
    if not raw or not isinstance(raw, dict):
        return {}

    choices = dict(raw)

    skills = _normalize_string_list(
        choices.get("skills") or choices.get("skill_proficiencies")
    )
    if skills:
        choices["skills"] = skills
    elif "skills" in choices:
        choices["skills"] = []
    choices.pop("skill_proficiencies", None)

    spec = _normalize_specialization(
        choices.get("specialization") or choices.get("subclass")
    )
    if spec:
        choices["specialization"] = spec
    else:
        choices.pop("specialization", None)
    choices.pop("subclass", None)

    fighting_style = choices.get("fighting_style")
    if fighting_style is not None:
        text = str(fighting_style).strip()
        if text:
            choices["fighting_style"] = text
        else:
            choices.pop("fighting_style", None)

    expertise = _normalize_string_list(choices.get("expertise_skills"))
    if expertise:
        choices["expertise_skills"] = expertise
    elif "expertise_skills" in choices:
        choices["expertise_skills"] = []

    return choices


def get_skill_choices(choices: dict[str, Any] | None) -> tuple[str, ...]:
    """Compétences maîtrisées choisies par le joueur."""
    normalized = normalize_character_choices(choices)
    return tuple(normalized.get("skills") or [])


def get_specialization_id(choices: dict[str, Any] | None) -> str | None:
    normalized = normalize_character_choices(choices)
    return normalized.get("specialization")


def get_fighting_style_id(choices: dict[str, Any] | None) -> str | None:
    normalized = normalize_character_choices(choices)
    return normalized.get("fighting_style")


def get_expertise_skills(choices: dict[str, Any] | None) -> tuple[str, ...]:
    normalized = normalize_character_choices(choices)
    return tuple(normalized.get("expertise_skills") or [])
