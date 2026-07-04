# jdr_engine/rules/racial/draconic_ancestry.py
"""Ascendance draconique SRD 2014 — 10 couleurs, souffle et résistance."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

DamageShape = Literal["line", "cone"]

DRAGON_COLORS: tuple[str, ...] = (
    "black",
    "blue",
    "brass",
    "bronze",
    "copper",
    "gold",
    "green",
    "red",
    "silver",
    "white",
)


@dataclass(frozen=True)
class DraconicAncestry:
    color_id: str
    label_fr: str
    damage_type: str
    shape: DamageShape
    area_ft: int
    resistance: str


DRACONIC_ANCESTRIES: dict[str, DraconicAncestry] = {
    "black": DraconicAncestry("black", "Noir", "acid", "line", 30, "acid"),
    "blue": DraconicAncestry("blue", "Bleu", "lightning", "line", 30, "lightning"),
    "brass": DraconicAncestry("brass", "Airain", "fire", "line", 30, "fire"),
    "bronze": DraconicAncestry("bronze", "Bronze", "lightning", "line", 30, "lightning"),
    "copper": DraconicAncestry("copper", "Cuivre", "acid", "line", 30, "acid"),
    "gold": DraconicAncestry("gold", "Or", "fire", "cone", 15, "fire"),
    "green": DraconicAncestry("green", "Vert", "poison", "cone", 15, "poison"),
    "red": DraconicAncestry("red", "Rouge", "fire", "cone", 15, "fire"),
    "silver": DraconicAncestry("silver", "Argent", "cold", "cone", 15, "cold"),
    "white": DraconicAncestry("white", "Blanc", "cold", "cone", 15, "cold"),
}


def get_draconic_ancestry(color_id: str) -> DraconicAncestry | None:
    return DRACONIC_ANCESTRIES.get(str(color_id).strip().lower())
