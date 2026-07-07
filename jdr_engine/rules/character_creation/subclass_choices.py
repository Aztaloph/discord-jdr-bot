# jdr_engine/rules/character_creation/subclass_choices.py
"""Choix de sous-classe SRD — données Compendium, extensible (SRD 2024+)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from jdr_engine.rules.engine import RuleEngine

# Classe → trait Compendium qui définit le choix de sous-classe (niv. 3 SRD 2014).
CLASS_SUBCLASS_TRAIT: dict[str, str] = {
    "fighter": "martial_archetype",
    "barbarian": "primal_path",
    "rogue": "roguish_archetype",
    "monk": "monastic_tradition",
    "ranger": "ranger_conclave",
    "paladin": "sacred_oath",
    "bard": "bard_college",
    "wizard": "arcane_tradition",
    "sorcerer": "sorcerous_origin",
    "druid": "druid_circle",
    "warlock": "otherworldly_patron",
}

SUBCLASS_CLASSES: frozenset[str] = frozenset(CLASS_SUBCLASS_TRAIT)


@dataclass(frozen=True)
class SubchoiceConfig:
    """Sous-choix optionnel (ex. esprit totémique du Guerrier totémique)."""

    storage_key: str
    options: tuple[str, ...]
    label_key: str = "label_fr"


@dataclass(frozen=True)
class SubclassOption:
    id: str
    label_fr: str
    subchoice: SubchoiceConfig | None = None


@dataclass(frozen=True)
class SubclassChoiceConfig:
    trait_id: str
    level: int
    options: tuple[SubclassOption, ...]


def _parse_subchoice(raw: dict[str, Any] | None) -> SubchoiceConfig | None:
    if not isinstance(raw, dict):
        return None
    options = raw.get("options") or []
    if not options:
        return None
    return SubchoiceConfig(
        storage_key=str(raw.get("storage_key", "subchoice")),
        options=tuple(str(o) for o in options),
    )


def _parse_subclass_options(raw_options: list[Any]) -> tuple[SubclassOption, ...]:
    parsed: list[SubclassOption] = []
    for item in raw_options:
        if isinstance(item, str):
            parsed.append(SubclassOption(id=item, label_fr=item.replace("_", " ").title()))
            continue
        if not isinstance(item, dict):
            continue
        option_id = str(item.get("id", "")).strip()
        if not option_id:
            continue
        label = str(item.get("label_fr") or option_id.replace("_", " ").title())
        parsed.append(
            SubclassOption(
                id=option_id,
                label_fr=label,
                subchoice=_parse_subchoice(item.get("subchoice")),
            )
        )
    return tuple(parsed)


def get_subclass_choice_config(
    engine: RuleEngine,
    class_id: str,
) -> SubclassChoiceConfig | None:
    trait_id = CLASS_SUBCLASS_TRAIT.get(class_id)
    if not trait_id:
        return None
    trait = engine.get_entity("trait", trait_id)
    if trait is None:
        return None
    choice = trait.definition.mechanics.get("choice") or {}
    options = _parse_subclass_options(list(choice.get("options") or []))
    if not options:
        return None
    return SubclassChoiceConfig(
        trait_id=trait_id,
        level=int(choice.get("level", 3)),
        options=options,
    )


def requires_subclass_at_level(
    engine: RuleEngine,
    class_id: str,
    level: int,
) -> bool:
    config = get_subclass_choice_config(engine, class_id)
    return config is not None and level >= config.level


def get_subclass_option(
    engine: RuleEngine,
    class_id: str,
    specialization: str,
) -> SubclassOption | None:
    config = get_subclass_choice_config(engine, class_id)
    if config is None:
        return None
    for option in config.options:
        if option.id == specialization:
            return option
    return None


def validate_subclass_choice(
    engine: RuleEngine,
    class_id: str,
    specialization: str | None,
    *,
    totem_spirit: str | None = None,
    subchoice_value: str | None = None,
    character_level: int = 3,
) -> tuple[str | None, str | None, str | None]:
    """
    Valide sous-classe (+ sous-choix optionnel si requis).

    Returns:
        (specialization_id, subchoice_id, subchoice_storage_key)
    """
    from jdr_engine.rules.character_creation.class_choices import CreationChoiceError

    config = get_subclass_choice_config(engine, class_id)
    if config is None:
        if specialization:
            raise CreationChoiceError(
                f"La classe {class_id!r} n'a pas de sous-classe SRD."
            )
        return None, None, None

    if character_level < config.level:
        if specialization:
            raise CreationChoiceError(
                f"Sous-classe disponible à partir du niveau {config.level}."
            )
        return None, None, None

    if not specialization or not str(specialization).strip():
        raise CreationChoiceError(
            f"Sous-classe requise au niveau {config.level} "
            f"({', '.join(o.id for o in config.options)})."
        )

    spec_id = str(specialization).strip()
    option = get_subclass_option(engine, class_id, spec_id)
    if option is None:
        valid = ", ".join(o.id for o in config.options)
        raise CreationChoiceError(
            f"Sous-classe invalide pour {class_id} : {spec_id!r} (attendu : {valid})."
        )

    sub_id: str | None = None
    sub_key: str | None = None
    if option.subchoice is not None:
        sub_key = option.subchoice.storage_key
        raw_sub = subchoice_value if subchoice_value is not None else totem_spirit
        if not raw_sub or not str(raw_sub).strip():
            raise CreationChoiceError(
                f"Choix « {sub_key} » requis pour {spec_id}."
            )
        sub_id = str(raw_sub).strip()
        if sub_id not in option.subchoice.options:
            valid = ", ".join(option.subchoice.options)
            raise CreationChoiceError(
                f"Sous-choix invalide pour {spec_id} : {sub_id!r} (attendu : {valid})."
            )

    return spec_id, sub_id, sub_key
