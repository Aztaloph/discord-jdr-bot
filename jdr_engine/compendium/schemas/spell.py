# jdr_engine/compendium/schemas/spell.py
"""Schéma typé mechanics pour les sorts — v2.0 (Lot B2)."""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator

EffectType = Literal["spell_attack", "saving_throw", "healing", "buff", "utility"]


class SpellComponents(BaseModel):
    verbal: bool = False
    somatic: bool = False
    material: bool = False
    material_description: dict[str, str] | str | None = None

    @model_validator(mode="before")
    @classmethod
    def normalize_legacy_material(cls, data: Any) -> Any:
        """Rétrocompat : ``material: "diamond..."`` → bool + description."""
        if not isinstance(data, dict):
            return data
        material = data.get("material")
        if isinstance(material, str):
            data = dict(data)
            if not data.get("material_description"):
                data["material_description"] = material
            data["material"] = True
        return data


class CantripScalingTier(BaseModel):
    """Palier de montée d'un tour de magie (niveau de personnage SRD 2014)."""

    character_level: int = Field(..., ge=1, le=20)
    damage_dice: str | None = None
    attacks: int | None = Field(default=None, ge=1)


class CantripScaling(BaseModel):
    tiers: list[CantripScalingTier] = Field(..., min_length=1)


class SlotScalingIncrement(BaseModel):
    """Gain par niveau d'emplacement au-dessus du niveau de base du sort."""

    damage_dice: str | None = None
    healing_dice: str | None = None
    missiles: int | None = Field(default=None, ge=1)
    temp_hp: int | None = Field(default=None, ge=0)
    cold_damage: int | None = Field(default=None, ge=0)
    extra_targets: int | None = Field(default=None, ge=1)


class SlotScaling(BaseModel):
    per_slot_above_base: SlotScalingIncrement


class SavingThrowSpec(BaseModel):
    """Jet de sauvegarde porté par un effet (D7 — sous-objet, pas au niveau mechanics)."""

    ability: str
    half_on_save: bool = True
    reaction: bool = False

    @field_validator("ability")
    @classmethod
    def normalize_ability(cls, value: str) -> str:
        return value.strip().lower()


class SpellEffect(BaseModel):
    """Un effet exécutable ou descriptif d'un sort (D4 — tableau multi-effets)."""

    type: EffectType
    attack_type: str | None = None
    damage: str | None = None
    damage_type: str | None = None
    attacks: int | None = Field(default=None, ge=1)
    instances: int | None = Field(default=None, ge=1)
    auto_hit: bool | None = None
    add_ability_mod: bool | None = None
    invocation: bool | None = None
    upcast_damage: str | None = None
    healing: str | None = None
    saving_throw: SavingThrowSpec | None = None

    model_config = {"extra": "forbid"}


class SpellMechanics(BaseModel):
    """
    Champs mécaniques structurés d'un sort (schema mechanics v2.0).

    ``effects[]`` est la source du moteur de lancement ; les champs
    ``damage_dice``, ``save``, etc. restent des miroirs d'affichage.
    """

    level: int = Field(..., ge=0, le=9)
    school: str
    casting_time: dict[str, str] | str
    range: dict[str, str] | str
    duration: dict[str, str] | str
    components: SpellComponents
    concentration: bool = False
    ritual: bool = False

    damage_dice: str | None = None
    damage_type: str | None = None
    save: str | None = None
    attack_roll: bool | None = None
    cantrip_scaling: CantripScaling | None = None
    slot_scaling: SlotScaling | None = None
    description: dict[str, str] | str | None = None

    effects: list[SpellEffect] = Field(..., min_length=1)
    buff_effect: dict[str, str] | str | None = None
    utility_effect: dict[str, str] | str | None = None

    model_config = {"extra": "allow"}

    @field_validator("save")
    @classmethod
    def normalize_save(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return value.strip().upper()

    @model_validator(mode="after")
    def validate_cantrip_scaling_level(self) -> SpellMechanics:
        if self.level > 0 and self.cantrip_scaling is not None:
            raise ValueError("cantrip_scaling interdit si level > 0")
        return self

    @model_validator(mode="after")
    def validate_saving_throw_effects(self) -> SpellMechanics:
        for effect in self.effects:
            if effect.type == "saving_throw" and effect.saving_throw is None:
                raise ValueError(
                    f"effet saving_throw sans sous-objet saving_throw"
                )
        return self
