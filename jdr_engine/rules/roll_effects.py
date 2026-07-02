# jdr_engine/rules/roll_effects.py
"""Collecte des effets Compendium actifs pour les jets de d20."""
from __future__ import annotations

from dataclasses import replace
from typing import Any

from jdr_engine.domain.character.character import Character
from jdr_engine.rules.class_features.barbarian import rage_active, reckless_active
from jdr_engine.rules.engine import RuleEngine


def _effects_from_entry(entry, *, source_id: str) -> list[dict[str, Any]]:
    """Extrait mechanics.effects en annotant la source."""
    raw = entry.definition.mechanics.get("effects") or []
    annotated: list[dict[str, Any]] = []
    for effect in raw:
        if isinstance(effect, dict):
            copy = dict(effect)
            copy.setdefault("source_id", source_id)
            annotated.append(copy)
    return annotated


def _choice_trait_effects(character: Character, engine: RuleEngine) -> list[dict[str, Any]]:
    """Effets issus de choix joueur (style de combat, etc.)."""
    effects: list[dict[str, Any]] = []
    choices = character.choices or {}

    fighting_style = choices.get("fighting_style")
    if fighting_style and character.class_id == "fighter":
        style_trait = engine.get_entity("trait", f"fighting_style_{fighting_style}")
        if style_trait is not None:
            effects.extend(
                _effects_from_entry(style_trait, source_id=f"fighting_style_{fighting_style}")
            )
    return effects


def collect_roll_effects(
    character: Character,
    engine: RuleEngine,
) -> list[dict[str, Any]]:
    """
    Agrège les effets mécaniques des traits raciaux et features de classe
    (niveau ≤ character.level) pour alimenter ``roll_d20``.
    """
    effects: list[dict[str, Any]] = []

    for trait in engine.get_race_traits(character.race_id):
        effects.extend(_effects_from_entry(trait, source_id=trait.entry_id))

    for feature in engine.get_class_features(character.class_id, character.level):
        effects.extend(_effects_from_entry(feature, source_id=feature.entry_id))

    effects.extend(_choice_trait_effects(character, engine))
    return effects


def enrich_roll_request(request, character: Character):
    """Injecte l'état persistant du personnage dans la requête de jet."""
    choices = character.choices or {}
    expertise = choices.get("expertise_skills") or []
    if isinstance(expertise, list):
        expertise_tuple = tuple(str(s) for s in expertise)
    else:
        expertise_tuple = ()

    return replace(
        request,
        rage_active=rage_active(choices),
        reckless_attack=reckless_active(choices),
        expertise_skills=expertise_tuple,
    )


def roll_d20_for_character(request, character, engine, *, rng=None):
    """Raccourci : collecte les effets puis délègue à ``roll_d20``."""
    from jdr_engine.dice.d20 import D20RollContext, roll_d20

    effects = collect_roll_effects(character, engine)
    enriched = enrich_roll_request(request, character)
    return roll_d20(D20RollContext(request=enriched, effects=effects), rng=rng)
