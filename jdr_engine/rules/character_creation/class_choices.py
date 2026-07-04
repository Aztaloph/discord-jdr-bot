# jdr_engine/rules/character_creation/class_choices.py
"""Choix de création niv. 1 — compétences, domaine clerc (SRD 2014)."""
from __future__ import annotations

from dataclasses import dataclass

from jdr_engine.rules.engine import RuleEngine


class CreationChoiceError(ValueError):
    """Choix de création invalides."""


@dataclass(frozen=True)
class SkillChoiceConfig:
    count: int
    options: tuple[str, ...]


def get_skill_choice_config(
    engine: RuleEngine,
    class_id: str,
) -> SkillChoiceConfig | None:
    entry = engine.get_entity("class", class_id)
    if entry is None:
        return None
    raw = entry.definition.mechanics.get("skill_choices")
    if not raw or not isinstance(raw, dict):
        return None
    count = int(raw.get("count", 0))
    options = raw.get("from") or raw.get("from_") or []
    if count <= 0 or not options:
        return None
    return SkillChoiceConfig(count=count, options=tuple(str(o) for o in options))


def get_cleric_domain_options(engine: RuleEngine) -> tuple[str, ...]:
    """Domaines divins SRD disponibles dans le compendium."""
    trait = engine.get_entity("trait", "divine_domain")
    if trait is None:
        return ()
    choice = trait.definition.mechanics.get("choice") or {}
    options = choice.get("options") or []
    return tuple(str(o) for o in options if o)


def cleric_requires_domain(engine: RuleEngine) -> bool:
    return bool(get_cleric_domain_options(engine))


def validate_skill_choices(
    engine: RuleEngine,
    class_id: str,
    skills: list[str] | tuple[str, ...] | None,
) -> tuple[str, ...]:
    config = get_skill_choice_config(engine, class_id)
    if config is None:
        if skills:
            raise CreationChoiceError(
                f"La classe {class_id!r} n'a pas de choix de compétences."
            )
        return ()

    chosen = list(dict.fromkeys(str(s) for s in (skills or [])))
    if len(chosen) != config.count:
        raise CreationChoiceError(
            f"Compétences : {config.count} requise(s), {len(chosen)} sélectionnée(s)."
        )
    invalid = [s for s in chosen if s not in config.options]
    if invalid:
        raise CreationChoiceError(
            f"Compétence(s) invalide(s) pour {class_id} : {', '.join(invalid)}"
        )
    return tuple(chosen)


def validate_cleric_domain(
    engine: RuleEngine,
    class_id: str,
    specialization: str | None,
) -> str | None:
    if class_id != "cleric":
        return None
    options = get_cleric_domain_options(engine)
    if not options:
        raise CreationChoiceError("Aucun domaine divin défini dans le compendium.")
    if not specialization or not str(specialization).strip():
        raise CreationChoiceError("Le clerc doit choisir un domaine divin.")
    domain = str(specialization).strip()
    if domain not in options:
        raise CreationChoiceError(f"Domaine divin invalide : {domain!r}")
    return domain


def requires_domain_at_creation(engine: RuleEngine, class_id: str) -> bool:
    return class_id == "cleric" and cleric_requires_domain(engine)
