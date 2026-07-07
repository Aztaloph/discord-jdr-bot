# jdr_engine/rules/character_creation/class_basics.py
"""Données de base SRD 2014 — affichage fiche / validation création."""
from __future__ import annotations

from jdr_engine.rules.engine import RuleEngine

ARMOR_LABELS_FR: dict[str, str] = {
    "light": "Armures légères",
    "medium": "Armures intermédiaires",
    "heavy": "Armures lourdes",
    "shields": "Boucliers",
}

WEAPON_LABELS_FR: dict[str, str] = {
    "simple": "Armes simples",
    "martial": "Armes martiales",
    "hand_crossbow": "Arbalètes de poing",
    "crossbow": "Arbalètes légères",
    "longsword": "Epées longues",
    "rapier": "Rapières",
    "shortsword": "Epées courtes",
    "shortbow": "Arcs courts",
    "longbow": "Arcs longs",
    "dagger": "Dagues",
    "dart": "Fléchettes",
    "quarterstaff": "Bâtons",
    "sling": "Frondes",
}

ABILITY_LABELS_FR: dict[str, str] = {
    "str": "FOR",
    "dex": "DEX",
    "con": "CON",
    "int": "INT",
    "wis": "SAG",
    "cha": "CHA",
}


def _class_mechanics(engine: RuleEngine, class_id: str) -> dict:
    entry = engine.get_entity("class", class_id)
    if entry is None:
        return {}
    return dict(entry.definition.mechanics or {})


def format_armor_proficiencies(
    engine: RuleEngine,
    class_id: str,
    *,
    bonus: tuple[str, ...] = (),
) -> str:
    mechanics = _class_mechanics(engine, class_id)
    raw = list(mechanics.get("armor_proficiencies") or [])
    for item in bonus:
        if item not in raw:
            raw.append(item)
    if not raw:
        return "Aucune"
    labels = [ARMOR_LABELS_FR.get(str(item), str(item)) for item in raw]
    return ", ".join(labels)


def format_weapon_proficiencies(engine: RuleEngine, class_id: str) -> str:
    mechanics = _class_mechanics(engine, class_id)
    raw = mechanics.get("weapon_proficiencies") or []
    if not raw:
        return "Aucune"
    labels = [WEAPON_LABELS_FR.get(str(item), str(item)) for item in raw]
    return ", ".join(labels)


def format_spellcasting_summary(
    engine: RuleEngine,
    class_id: str,
    *,
    character_level: int = 1,
) -> str | None:
    """Résumé incantation SRD (capacité + niveau d'accès)."""
    mechanics = _class_mechanics(engine, class_id)
    pact = mechanics.get("pact_magic")
    if isinstance(pact, dict):
        ability = str(pact.get("ability", "")).lower()
        ability_label = ABILITY_LABELS_FR.get(ability, ability.upper())
        recovery = str(pact.get("recovery", "short_rest"))
        recovery_label = (
            "recharge repos court"
            if recovery == "short_rest"
            else f"recharge {recovery.replace('_', ' ')}"
        )
        return f"Pact Magic · {ability_label} ({recovery_label})"
    spellcasting = mechanics.get("spellcasting")
    if not isinstance(spellcasting, dict):
        return None
    ability = str(spellcasting.get("ability", "")).lower()
    ability_label = ABILITY_LABELS_FR.get(ability, ability.upper())
    start_level = int(spellcasting.get("level", 1))
    if character_level >= start_level:
        return f"{ability_label} (actif niv. {character_level})"
    return f"{ability_label} (à partir du niv. {start_level})"
