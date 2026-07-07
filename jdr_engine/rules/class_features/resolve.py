# jdr_engine/rules/class_features/resolve.py
"""Résolution des traits de sous-classe actifs (données Compendium)."""
from __future__ import annotations

from jdr_engine.domain.character.character import Character
from jdr_engine.domain.character.choices_schema import get_specialization_id
from jdr_engine.rules.engine import RuleEngine

# Sous-classe → aptitudes accordées (extensible via grants_features dans le YAML).
SUBCLASS_GRANTED_FEATURES: dict[str, tuple[str, ...]] = {
    "berserker": ("frenzy",),
    "thief": ("fast_hands", "second_story_work"),
    "open_hand": ("open_hand_technique",),
    "hunter": (),
    "devotion": ("sacred_weapon", "turn_the_unholy"),
    "lore": ("cutting_words",),
    "evocation": ("evocation_savant", "sculpt_spells"),
    "draconic": ("elemental_affinity",),
    "land": ("natural_recovery",),
    "fiend": ("dark_ones_blessing",),
}


def _totem_spirit_trait_id(spirit: str) -> str:
    return f"totem_spirit_{spirit}"


def _grants_from_trait(engine: RuleEngine, trait_id: str) -> tuple[str, ...]:
    entry = engine.get_entity("trait", trait_id)
    if entry is None:
        return ()
    raw = entry.definition.mechanics.get("grants_features") or []
    return tuple(str(item) for item in raw if item)


def collect_subclass_trait_ids(character: Character, engine: RuleEngine | None = None) -> tuple[str, ...]:
    """IDs de traits issus du choix de sous-classe (+ esprit totémique)."""
    choices = character.choices or {}
    spec = get_specialization_id(choices)
    if not spec:
        return ()

    ids: list[str] = [spec]

    if engine is not None:
        ids.extend(_grants_from_trait(engine, spec))
    else:
        ids.extend(SUBCLASS_GRANTED_FEATURES.get(spec, ()))

    if spec == "totem_warrior":
        spirit = choices.get("totem_spirit")
        if spirit:
            ids.append(_totem_spirit_trait_id(str(spirit)))

    prey = choices.get("hunter_prey")
    if prey and spec == "hunter":
        ids.append(str(prey))

    return tuple(dict.fromkeys(ids))


def collect_subclass_traits(
    character: Character,
    engine: RuleEngine,
) -> list:
    """Entités trait Compendium pour la sous-classe active."""
    traits = []
    for trait_id in collect_subclass_trait_ids(character, engine):
        entry = engine.get_entity("trait", trait_id)
        if entry is not None:
            traits.append(entry)
    return traits
