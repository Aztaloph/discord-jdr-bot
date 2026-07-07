# jdr_engine/rules/class_features/ranger.py
"""Rôdeur — libellés et choix SRD 2014."""
from __future__ import annotations

FAVORED_ENEMY_TYPES: tuple[str, ...] = (
    "aberrations",
    "beasts",
    "celestials",
    "constructs",
    "dragons",
    "elementals",
    "fey",
    "fiends",
    "giants",
    "monstrosities",
    "oozes",
    "plants",
    "undead",
    "humanoids",
)

FAVORED_TERRAINS: tuple[str, ...] = (
    "arctic",
    "coast",
    "desert",
    "forest",
    "grassland",
    "mountain",
    "swamp",
    "underdark",
)

FAVORED_ENEMY_LABELS_FR: dict[str, str] = {
    "aberrations": "Aberrations",
    "beasts": "Bêtes",
    "celestials": "Célestes",
    "constructs": "Artificiels",
    "dragons": "Dragons",
    "elementals": "Élémentaires",
    "fey": "Fées",
    "fiends": "Fiélons",
    "giants": "Géants",
    "monstrosities": "Monstruosités",
    "oozes": "Vases",
    "plants": "Plantes",
    "undead": "Morts-vivants",
    "humanoids": "Humanoïdes",
}

FAVORED_TERRAIN_LABELS_FR: dict[str, str] = {
    "arctic": "Arctique",
    "coast": "Côte",
    "desert": "Désert",
    "forest": "Forêt",
    "grassland": "Prairie",
    "mountain": "Montagne",
    "swamp": "Marais",
    "underdark": "Outreterre",
}

HUNTER_PREY_LABELS_FR: dict[str, str] = {
    "colossus_slayer": "Tueur de colosses",
    "giant_killer": "Tueur de géants",
    "horde_breaker": "Briseur de horde",
}


def favored_enemy_label(enemy_type: str) -> str:
    return FAVORED_ENEMY_LABELS_FR.get(enemy_type, enemy_type.replace("_", " ").title())


def favored_terrain_label(terrain: str) -> str:
    return FAVORED_TERRAIN_LABELS_FR.get(terrain, terrain.replace("_", " ").title())


def hunter_prey_label(prey_id: str) -> str:
    return HUNTER_PREY_LABELS_FR.get(prey_id, prey_id.replace("_", " ").title())
