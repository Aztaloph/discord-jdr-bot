#!/usr/bin/env python3
"""Migration one-shot Lot B2 — sorts v1.0 → v2.0 (effects[], classes[], saving_throw)."""
from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
SPELLS_DIR = ROOT / "compendium" / "dnd5e" / "entries" / "spells"

# Membership + ordre dans les pools (iso-comportement spells_catalog.py legacy).
CLASS_POOLS: dict[str, dict[str, list[str]]] = {
    "cantrips": {
        "wizard": ["fire_bolt", "mage_hand", "light", "ray_of_frost"],
        "sorcerer": [
            "fire_bolt",
            "thaumaturgy",
            "guidance",
            "vicious_mockery",
            "sacred_flame",
        ],
        "cleric": ["sacred_flame", "guidance", "thaumaturgy"],
        "bard": ["vicious_mockery", "thaumaturgy"],
        "druid": ["druidcraft", "produce_flame", "guidance"],
        "warlock": ["eldritch_blast", "prestidigitation"],
    },
    "leveled": {
        "wizard": [
            "mage_armor",
            "burning_hands",
            "detect_magic",
            "magic_missile",
            "shield",
            "scorching_ray",
            "darkness",
            "flaming_sphere",
            "fireball",
            "lightning_bolt",
            "counterspell",
            "dispel_magic",
            "fly",
            "haste",
            "polymorph",
            "banishment",
            "dimension_door",
            "ice_storm",
        ],
        "sorcerer": [
            "chromatic_orb",
            "burning_hands",
            "detect_magic",
            "magic_missile",
            "shield",
            "scorching_ray",
            "hellish_rebuke",
        ],
        "cleric": [
            "cure_wounds",
            "inflict_wounds",
            "bless",
            "detect_magic",
            "spiritual_weapon",
        ],
        "bard": [
            "cure_wounds",
            "healing_word",
            "detect_magic",
            "bless",
        ],
        "druid": ["entangle", "cure_wounds", "faerie_fire", "flaming_sphere"],
        "warlock": ["hex", "armor_of_agathys", "darkness"],
        "ranger": ["hunters_mark", "cure_wounds", "detect_magic"],
        "paladin": ["bless", "cure_wounds", "detect_magic"],
    },
}

MULTI_EFFECT: dict[str, list[dict]] = {
    "vicious_mockery": [
        {
            "type": "saving_throw",
            "damage": "1d4",
            "damage_type": "psychic",
            "saving_throw": {"ability": "wis", "half_on_save": False},
        },
        {"type": "utility"},
    ],
}

UTILITY_WITH_SAVE: dict[str, dict] = {
    "entangle": {"ability": "str", "half_on_save": False},
    "faerie_fire": {"ability": "dex", "half_on_save": False},
}


def _classes_for(spell_id: str) -> list[str]:
    found: set[str] = set()
    for pools in CLASS_POOLS.values():
        for class_id, ids in pools.items():
            if spell_id in ids:
                found.add(class_id)
    return sorted(found)


def _pool_order_for(spell_id: str) -> dict[str, int]:
    order: dict[str, int] = {}
    for pools in CLASS_POOLS.values():
        for class_id, ids in pools.items():
            if spell_id in ids:
                order[class_id] = ids.index(spell_id)
    return order


def _convert_effect(effect: dict) -> list[dict]:
    spell_type = effect.get("type")
    if spell_type == "saving_throw":
        return [
            {
                "type": "saving_throw",
                "damage": effect.get("damage"),
                "damage_type": effect.get("damage_type"),
                "saving_throw": {
                    "ability": effect.get("ability", "dex"),
                    "half_on_save": effect.get("half_on_save", True),
                    "reaction": bool(effect.get("reaction", False)),
                },
            }
        ]
    converted = {"type": spell_type}
    for key in (
        "attack_type",
        "damage",
        "damage_type",
        "attacks",
        "instances",
        "auto_hit",
        "add_ability_mod",
        "invocation",
        "upcast_damage",
        "healing",
    ):
        if key in effect and effect[key] is not None:
            converted[key] = effect[key]
    return [converted]


def migrate_spell(path: Path) -> None:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    spell_id = data["id"]
    mechanics = data["mechanics"]

    if spell_id in MULTI_EFFECT:
        mechanics.pop("effect", None)
        effects = MULTI_EFFECT[spell_id]
    elif "effects" in mechanics:
        mechanics.pop("effect", None)
        effects = mechanics["effects"]
    else:
        legacy = mechanics.pop("effect", None)
        if not legacy:
            raise ValueError(f"{spell_id}: effect/effects manquant")
        effects = _convert_effect(legacy)
        if spell_id in UTILITY_WITH_SAVE and effects[0]["type"] == "utility":
            effects[0]["saving_throw"] = UTILITY_WITH_SAVE[spell_id]

    data["schema_version"] = "2.0"
    data["classes"] = _classes_for(spell_id)
    data["class_pool_order"] = _pool_order_for(spell_id)
    data["mechanics"]["effects"] = effects
    path.write_text(
        yaml.dump(data, allow_unicode=True, sort_keys=False, width=120),
        encoding="utf-8",
    )


def main() -> None:
    for spell_dir in sorted(SPELLS_DIR.iterdir()):
        definition = spell_dir / "definition.yaml"
        if definition.is_file():
            migrate_spell(definition)
            print(f"migrated {spell_dir.name}")


if __name__ == "__main__":
    main()
