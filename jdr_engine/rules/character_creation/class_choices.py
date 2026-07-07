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


def get_sorcerous_origin_options(engine: RuleEngine) -> tuple[str, ...]:
    """Origines magiques SRD (Ensorceleur, niv. 1)."""
    from jdr_engine.rules.character_creation.subclass_choices import (
        get_subclass_choice_config,
    )

    config = get_subclass_choice_config(engine, "sorcerer")
    if config is None:
        return ()
    return tuple(o.id for o in config.options)


def get_sorcerer_dragon_type_options(
    engine: RuleEngine,
    origin_id: str,
) -> tuple[str, ...]:
    """Types de dragon pour la Lignée draconique."""
    from jdr_engine.rules.character_creation.subclass_choices import get_subclass_option

    option = get_subclass_option(engine, "sorcerer", origin_id)
    if option is None or option.subchoice is None:
        return ()
    return option.subchoice.options


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


def get_fighting_style_options(engine: RuleEngine) -> tuple[str, ...]:
    trait = engine.get_entity("trait", "fighting_style")
    if trait is None:
        return ()
    choice = trait.definition.mechanics.get("choice") or {}
    options = choice.get("options") or []
    return tuple(str(o) for o in options if o)


def validate_fighting_style(
    engine: RuleEngine,
    class_id: str,
    fighting_style: str | None,
) -> str | None:
    return validate_fighting_style_at_level(
        engine, class_id, fighting_style, character_level=1
    )


def get_fighting_style_options_for_class(
    engine: RuleEngine,
    class_id: str,
) -> tuple[str, ...]:
    entry = engine.get_entity("class", class_id)
    if entry is not None:
        raw = entry.definition.mechanics.get("fighting_style_options") or []
        if raw:
            return tuple(str(o) for o in raw if o)
    return get_fighting_style_options(engine)


def requires_fighting_style_at_level(
    engine: RuleEngine,
    class_id: str,
    level: int,
) -> bool:
    if class_id == "fighter":
        return False
    if class_id in ("ranger", "paladin") and level >= 2:
        return bool(get_fighting_style_options_for_class(engine, class_id))
    return False


def validate_fighting_style_at_level(
    engine: RuleEngine,
    class_id: str,
    fighting_style: str | None,
    *,
    character_level: int = 1,
) -> str | None:
    if class_id == "fighter":
        options = get_fighting_style_options(engine)
        if not options:
            raise CreationChoiceError("Aucun style de combat défini dans le compendium.")
        if not fighting_style or not str(fighting_style).strip():
            raise CreationChoiceError("Le guerrier doit choisir un style de combat.")
        style = str(fighting_style).strip()
        if style not in options:
            raise CreationChoiceError(f"Style de combat invalide : {style!r}")
        return style

    if class_id in ("ranger", "paladin"):
        if character_level < 2:
            if fighting_style:
                raise CreationChoiceError(
                    f"Le {class_id} choisit son style de combat au niveau 2."
                )
            return None
        options = get_fighting_style_options_for_class(engine, class_id)
        if not options:
            raise CreationChoiceError("Aucun style de combat défini pour cette classe.")
        if not fighting_style or not str(fighting_style).strip():
            raise CreationChoiceError("Style de combat requis au niveau 2.")
        style = str(fighting_style).strip()
        if style not in options:
            raise CreationChoiceError(f"Style de combat invalide : {style!r}")
        return style

    if fighting_style:
        raise CreationChoiceError(
            f"La classe {class_id!r} n'a pas de choix de style de combat."
        )
    return None


def requires_fighting_style_at_creation(engine: RuleEngine, class_id: str) -> bool:
    return class_id == "fighter" and bool(get_fighting_style_options(engine))


def get_ranger_favored_enemy_options() -> tuple[str, ...]:
    from jdr_engine.rules.class_features.ranger import FAVORED_ENEMY_TYPES

    return FAVORED_ENEMY_TYPES


def get_ranger_favored_terrain_options() -> tuple[str, ...]:
    from jdr_engine.rules.class_features.ranger import FAVORED_TERRAINS

    return FAVORED_TERRAINS


def requires_ranger_choices_at_creation(engine: RuleEngine, class_id: str) -> bool:
    return class_id == "ranger"


def validate_ranger_choices(
    engine: RuleEngine,
    class_id: str,
    favored_enemy_type: str | None,
    favored_terrain: str | None,
) -> tuple[str | None, str | None]:
    if class_id != "ranger":
        if favored_enemy_type or favored_terrain:
            raise CreationChoiceError(
                f"Ennemi juré / terrain réservés au rôdeur."
            )
        return None, None

    enemy_options = get_ranger_favored_enemy_options()
    terrain_options = get_ranger_favored_terrain_options()

    if not favored_enemy_type or not str(favored_enemy_type).strip():
        raise CreationChoiceError("Le rôdeur doit choisir un type d'ennemi juré.")
    enemy = str(favored_enemy_type).strip()
    if enemy not in enemy_options:
        raise CreationChoiceError(f"Ennemi juré invalide : {enemy!r}")

    if not favored_terrain or not str(favored_terrain).strip():
        raise CreationChoiceError("Le rôdeur doit choisir un terrain favori.")
    terrain = str(favored_terrain).strip()
    if terrain not in terrain_options:
        raise CreationChoiceError(f"Terrain favori invalide : {terrain!r}")

    return enemy, terrain


def get_expertise_skill_count(
    engine: RuleEngine, class_id: str, *, level: int = 1
) -> int:
    if class_id == "rogue":
        trait = engine.get_entity("trait", "expertise")
        if trait is None:
            return 0
        choice = trait.definition.mechanics.get("choice") or {}
        return int(choice.get("skill_count", 2))
    if class_id == "bard" and level >= 3:
        return 2
    return 0


def requires_expertise_at_creation(
    engine: RuleEngine, class_id: str, *, level: int = 1
) -> bool:
    return get_expertise_skill_count(engine, class_id, level=level) > 0


def validate_expertise_skills(
    engine: RuleEngine,
    class_id: str,
    expertise_skills: list[str] | tuple[str, ...] | None,
    proficient_skills: list[str] | tuple[str, ...],
    *,
    level: int = 1,
) -> tuple[str, ...]:
    count = get_expertise_skill_count(engine, class_id, level=level)
    if count == 0:
        if expertise_skills:
            raise CreationChoiceError(
                f"La classe {class_id!r} n'a pas de choix d'expertise."
            )
        return ()

    chosen = list(dict.fromkeys(str(s) for s in (expertise_skills or [])))
    if len(chosen) != count:
        raise CreationChoiceError(
            f"Expertise : {count} compétence(s) requise(s), {len(chosen)} sélectionnée(s)."
        )
    invalid = [s for s in chosen if s not in proficient_skills]
    if invalid:
        raise CreationChoiceError(
            f"Expertise invalide (compétence non maîtrisée) : {', '.join(invalid)}"
        )
    return tuple(chosen)


def requires_expertise_at_level(
    engine: RuleEngine, class_id: str, *, level: int
) -> bool:
    return get_expertise_skill_count(engine, class_id, level=level) > 0


def requires_lore_bonus_at_level(
    engine: RuleEngine,
    class_id: str,
    specialization: str | None,
    *,
    level: int,
) -> bool:
    if class_id != "bard" or level < 3 or specialization != "lore":
        return False
    return get_lore_bonus_skill_count(engine) > 0


def get_lore_bonus_skill_count(engine: RuleEngine) -> int:
    trait = engine.get_entity("trait", "lore")
    if trait is None:
        return 3
    return int(trait.definition.mechanics.get("bonus_skill_count", 3))


def get_lore_bonus_skill_options(
    engine: RuleEngine,
    class_id: str,
    proficient_skills: list[str] | tuple[str, ...],
) -> tuple[str, ...]:
    """Compétences disponibles pour le Collège du Savoir (non déjà maîtrisées)."""
    config = get_skill_choice_config(engine, class_id)
    if config is None:
        return ()
    proficient = set(proficient_skills)
    return tuple(s for s in config.options if s not in proficient)


def validate_lore_bonus_skills(
    engine: RuleEngine,
    class_id: str,
    specialization: str | None,
    lore_bonus_skills: list[str] | tuple[str, ...] | None,
    *,
    level: int = 1,
) -> tuple[str, ...]:
    if class_id != "bard" or level < 3 or specialization != "lore":
        if lore_bonus_skills:
            raise CreationChoiceError(
                "Les compétences bonus du Collège du Savoir ne s'appliquent qu'au barde niv. 3+."
            )
        return ()

    trait = engine.get_entity("trait", "lore")
    count = 3
    if trait is not None:
        count = int(trait.definition.mechanics.get("bonus_skill_count", 3))

    config = get_skill_choice_config(engine, class_id)
    valid_options = set(config.options) if config else set()

    chosen = list(dict.fromkeys(str(s) for s in (lore_bonus_skills or [])))
    if len(chosen) != count:
        raise CreationChoiceError(
            f"Collège du Savoir : {count} compétence(s) requise(s), "
            f"{len(chosen)} sélectionnée(s)."
        )
    invalid = [s for s in chosen if s not in valid_options]
    if invalid:
        raise CreationChoiceError(
            f"Compétence(s) invalide(s) pour le Collège du Savoir : {', '.join(invalid)}"
        )
    return tuple(chosen)


def requires_domain_at_creation(engine: RuleEngine, class_id: str) -> bool:
    return class_id == "cleric" and cleric_requires_domain(engine)


def requires_sorcerous_origin_at_creation(engine: RuleEngine, class_id: str) -> bool:
    return class_id == "sorcerer"


def requires_patron_at_creation(engine: RuleEngine, class_id: str) -> bool:
    """Alias — voir ``requires_subclass_choice_step_at_creation``."""
    return requires_subclass_choice_step_at_creation(engine, class_id)


# Classes avec UI dédiée dans /creer-perso (domaine clerc, origine ensorceleur).
_SUBCLASS_CREATION_DEDICATED_UI: frozenset[str] = frozenset({"cleric", "sorcerer"})


def requires_subclass_choice_step_at_creation(
    engine: RuleEngine,
    class_id: str,
) -> bool:
    """
    Sous-classe requise au niv. 1 via l'étape générique /creer-perso.

    Exclut clerc et ensorceleur (étapes dédiées existantes).
    """
    if class_id in _SUBCLASS_CREATION_DEDICATED_UI:
        return False
    return requires_subclass_at_creation(engine, class_id, level=1)


def get_creation_subclass_options(
    engine: RuleEngine,
    class_id: str,
) -> tuple[tuple[str, str], ...]:
    """(id, label_fr) des sous-classes choisissables à la création (niv. 1)."""
    from jdr_engine.rules.character_creation.subclass_choices import (
        get_subclass_choice_config,
    )

    config = get_subclass_choice_config(engine, class_id)
    if config is None or config.level != 1:
        return ()
    return tuple((o.id, o.label_fr) for o in config.options)


def get_creation_subclass_step_label(
    engine: RuleEngine,
    class_id: str,
    *,
    locale: str = "fr",
) -> str:
    """Libellé de l'étape (ex. « Protecteur occulte », « Domaine divin »)."""
    from jdr_engine.rules.character_creation.subclass_choices import (
        CLASS_SUBCLASS_TRAIT,
    )

    trait_id = CLASS_SUBCLASS_TRAIT.get(class_id)
    if not trait_id:
        return "Sous-classe"
    trait = engine.get_entity("trait", trait_id)
    if trait is None:
        return "Sous-classe"
    return trait.get_name(locale, engine.registry.manifest.default_locale)


def requires_subclass_at_creation(
    engine: RuleEngine, class_id: str, *, level: int = 1
) -> bool:
    from jdr_engine.rules.character_creation.subclass_choices import (
        requires_subclass_at_level,
    )

    return requires_subclass_at_level(engine, class_id, level)


def get_metamagic_pick_count(engine: RuleEngine) -> int:
    trait = engine.get_entity("trait", "metamagic")
    if trait is None:
        return 2
    choice = trait.definition.mechanics.get("choice") or {}
    return int(choice.get("pick_count", 2))


def get_metamagic_options(engine: RuleEngine) -> tuple[str, ...]:
    trait = engine.get_entity("trait", "metamagic")
    if trait is None:
        return ("quickened", "subtle", "twinned", "extended")
    choice = trait.definition.mechanics.get("choice") or {}
    raw = choice.get("options") or []
    ids: list[str] = []
    for item in raw:
        if isinstance(item, dict):
            ids.append(str(item.get("id", "")))
        elif isinstance(item, str):
            ids.append(item)
    return tuple(i for i in ids if i)


def requires_metamagic_at_level(
    engine: RuleEngine, class_id: str, *, level: int
) -> bool:
    if class_id != "sorcerer" or level < 3:
        return False
    trait = engine.get_entity("trait", "metamagic")
    if trait is None:
        return False
    choice = trait.definition.mechanics.get("choice") or {}
    return level >= int(choice.get("level", 3))


def validate_metamagic_options(
    engine: RuleEngine,
    class_id: str,
    metamagic_options: list[str] | tuple[str, ...] | None,
    *,
    level: int = 1,
) -> tuple[str, ...]:
    if not requires_metamagic_at_level(engine, class_id, level=level):
        if metamagic_options:
            raise CreationChoiceError(
                "Les options de métamagie ne s'appliquent qu'à l'ensorceleur niv. 3+."
            )
        return ()

    count = get_metamagic_pick_count(engine)
    valid = set(get_metamagic_options(engine))
    chosen = list(dict.fromkeys(str(m) for m in (metamagic_options or [])))
    if len(chosen) != count:
        raise CreationChoiceError(
            f"Métamagie : {count} option(s) requise(s), {len(chosen)} sélectionnée(s)."
        )
    invalid = [m for m in chosen if m not in valid]
    if invalid:
        raise CreationChoiceError(
            f"Métamagie invalide : {', '.join(invalid)}"
        )
    return tuple(chosen)


def get_eldritch_invocation_pick_count(engine: RuleEngine) -> int:
    trait = engine.get_entity("trait", "eldritch_invocations")
    if trait is None:
        return 2
    choice = trait.definition.mechanics.get("choice") or {}
    return int(choice.get("pick_count", 2))


def get_eldritch_invocation_options(engine: RuleEngine) -> tuple[str, ...]:
    trait = engine.get_entity("trait", "eldritch_invocations")
    if trait is None:
        return (
            "eldritch_sight",
            "devils_sight",
            "eldritch_spear",
            "agonizing_blast",
            "armor_of_shadows",
        )
    choice = trait.definition.mechanics.get("choice") or {}
    raw = choice.get("options") or []
    ids: list[str] = []
    for item in raw:
        if isinstance(item, dict):
            ids.append(str(item.get("id", "")))
        elif isinstance(item, str):
            ids.append(item)
    return tuple(i for i in ids if i)


def requires_eldritch_invocations_at_level(
    engine: RuleEngine, class_id: str, *, level: int
) -> bool:
    if class_id != "warlock" or level < 2:
        return False
    trait = engine.get_entity("trait", "eldritch_invocations")
    if trait is None:
        return False
    choice = trait.definition.mechanics.get("choice") or {}
    return level >= int(choice.get("level", 2))


def validate_eldritch_invocations(
    engine: RuleEngine,
    class_id: str,
    eldritch_invocations: list[str] | tuple[str, ...] | None,
    *,
    level: int = 1,
) -> tuple[str, ...]:
    if not requires_eldritch_invocations_at_level(engine, class_id, level=level):
        if eldritch_invocations:
            raise CreationChoiceError(
                "Les manifestations occultes ne s'appliquent qu'à l'occultiste niv. 2+."
            )
        return ()

    count = get_eldritch_invocation_pick_count(engine)
    valid = set(get_eldritch_invocation_options(engine))
    chosen = list(dict.fromkeys(str(m) for m in (eldritch_invocations or [])))
    if len(chosen) != count:
        raise CreationChoiceError(
            f"Manifestations occultes : {count} requise(s), "
            f"{len(chosen)} sélectionnée(s)."
        )
    invalid = [m for m in chosen if m not in valid]
    if invalid:
        raise CreationChoiceError(
            f"Manifestation(s) occulte(s) invalide(s) : {', '.join(invalid)}"
        )
    return tuple(chosen)


def get_pact_boon_options(engine: RuleEngine) -> tuple[str, ...]:
    trait = engine.get_entity("trait", "pact_boon")
    if trait is None:
        return ("pact_of_the_chain", "pact_of_the_blade", "pact_of_the_tome")
    choice = trait.definition.mechanics.get("choice") or {}
    raw = choice.get("options") or []
    ids: list[str] = []
    for item in raw:
        if isinstance(item, dict):
            ids.append(str(item.get("id", "")))
        elif isinstance(item, str):
            ids.append(item)
    return tuple(i for i in ids if i)


def requires_pact_boon_at_level(
    engine: RuleEngine, class_id: str, *, level: int
) -> bool:
    if class_id != "warlock" or level < 3:
        return False
    trait = engine.get_entity("trait", "pact_boon")
    if trait is None:
        return False
    choice = trait.definition.mechanics.get("choice") or {}
    return level >= int(choice.get("level", 3))


def validate_pact_boon(
    engine: RuleEngine,
    class_id: str,
    pact_boon: str | None,
    *,
    level: int = 1,
) -> str | None:
    if not requires_pact_boon_at_level(engine, class_id, level=level):
        if pact_boon:
            raise CreationChoiceError(
                "La faveur du pacte ne s'applique qu'à l'occultiste niv. 3+."
            )
        return None

    if not pact_boon or not str(pact_boon).strip():
        raise CreationChoiceError("Faveur du pacte requise au niveau 3.")
    boon_id = str(pact_boon).strip()
    valid = set(get_pact_boon_options(engine))
    if boon_id not in valid:
        raise CreationChoiceError(
            f"Faveur du pacte invalide : {boon_id!r} (attendu : {', '.join(sorted(valid))})."
        )
    return boon_id
