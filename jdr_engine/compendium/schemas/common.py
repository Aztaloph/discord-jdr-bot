# jdr_engine/compendium/schemas/common.py
"""Types partagés pour les schémas Compendium."""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, field_validator

# Dossiers entries/ (pluriel) ↔ type dans definition.yaml (singulier)
ENTRY_TYPE_PLURAL_TO_SINGULAR: dict[str, str] = {
    "races": "race",
    "classes": "class",
    "traits": "trait",
    "spells": "spell",
    "weapons": "weapon",
    "armor": "armor",
    "conditions": "condition",
    "monsters": "monster",
    "feats": "feat",
    "skills": "skill",
    "backgrounds": "background",
    "languages": "language",
    "actions": "action",
}

ENTRY_TYPE_SINGULAR_TO_PLURAL: dict[str, str] = {
    v: k for k, v in ENTRY_TYPE_PLURAL_TO_SINGULAR.items()
}


def normalize_entity_type(entity_type: str) -> str:
    """Accepte 'race' ou 'races' et retourne le singulier."""
    if entity_type in ENTRY_TYPE_PLURAL_TO_SINGULAR:
        return ENTRY_TYPE_PLURAL_TO_SINGULAR[entity_type]
    return entity_type


def plural_entity_type(entity_type: str) -> str:
    """Retourne le nom de dossier (pluriel)."""
    singular = normalize_entity_type(entity_type)
    try:
        return ENTRY_TYPE_SINGULAR_TO_PLURAL[singular]
    except KeyError as exc:
        raise ValueError(f"Type d'entité inconnu : {entity_type}") from exc


class EntityRef(BaseModel):
    """Référence vers une autre entrée du Compendium (ex. traits/darkvision)."""

    ref: str

    @field_validator("ref")
    @classmethod
    def ref_must_have_slash(cls, value: str) -> str:
        if "/" not in value:
            raise ValueError(f"Référence invalide (attendu type/id) : {value!r}")
        return value

    @property
    def plural_type(self) -> str:
        return self.ref.split("/", 1)[0]

    @property
    def entry_id(self) -> str:
        return self.ref.split("/", 1)[1]


class AbilityScoreIncrease(BaseModel):
    ability: str
    value: int = Field(..., ge=1, le=2)


class LanguageChoice(BaseModel):
    fixed: list[str] = Field(default_factory=list)
    choose: dict[str, Any] | None = None


class SkillChoice(BaseModel):
    count: int = Field(..., ge=1)
    from_: list[str] = Field(..., alias="from")

    model_config = {"populate_by_name": True}


class RaceMechanics(BaseModel):
    ability_score_increase: list[AbilityScoreIncrease] = Field(default_factory=list)
    size: str
    speed: int = Field(..., ge=0)
    traits: list[EntityRef | str] = Field(default_factory=list)
    languages: LanguageChoice | dict[str, Any] | None = None


class ClassMechanics(BaseModel):
    hit_die: str
    primary_abilities: list[str] = Field(default_factory=list)
    saving_throw_proficiencies: list[str] = Field(default_factory=list)
    armor_proficiencies: list[str] = Field(default_factory=list)
    weapon_proficiencies: list[str] = Field(default_factory=list)
    skill_choices: SkillChoice | None = None
    spellcasting: dict[str, Any] | None = None
    pact_magic: dict[str, Any] | None = None
    features_by_level: dict[str, list[str]] = Field(default_factory=dict)


class TraitMechanics(BaseModel):
    """Effets génériques — structure libre (EffectProcessor futur)."""

    effects: list[dict[str, Any]] = Field(default_factory=list)

    model_config = {"extra": "allow"}


def _spell_mechanics_model():
    from jdr_engine.compendium.schemas.spell import SpellMechanics

    return SpellMechanics


class DefinitionSchema(BaseModel):
    """Schéma commun de definition.yaml."""

    schema_version: str
    type: str
    id: str
    name: dict[str, str]
    mechanics: dict[str, Any]

    @field_validator("name")
    @classmethod
    def name_not_empty(cls, value: dict[str, str]) -> dict[str, str]:
        if not value:
            raise ValueError("name ne peut pas être vide")
        return value

    def validate_mechanics_typed(self) -> BaseModel:
        """Valide mechanics selon le type d'entité (L1)."""
        if self.type == "race":
            return RaceMechanics.model_validate(self.mechanics)
        if self.type == "class":
            return ClassMechanics.model_validate(self.mechanics)
        if self.type == "trait":
            return TraitMechanics.model_validate(self.mechanics)
        if self.type == "spell":
            return _spell_mechanics_model().model_validate(self.mechanics)
        return self.mechanics
