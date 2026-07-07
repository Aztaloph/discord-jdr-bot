# jdr_engine/compendium/schemas/spell.py
"""Schéma typé mechanics pour les sorts (Passe 1 — Lots A & B)."""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator


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


class SpellMechanics(BaseModel):
    """
    Champs mécaniques structurés d'un sort.

    Les champs Lot A/B (damage_dice, save, attack_roll, cantrip_scaling,
    slot_scaling, description) enrichissent le compendium ; optionnels pour
    rétrocompat. Le bloc ``effect`` reste la source du moteur de lancement.
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

    effect: dict[str, Any] | None = None
    buff_effect: dict[str, str] | str | None = None
    utility_effect: dict[str, str] | str | None = None

    model_config = {"extra": "allow"}

    @field_validator("save")
    @classmethod
    def normalize_save(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return value.strip().upper()
