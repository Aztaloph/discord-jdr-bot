# jdr_engine/rules/spellcasting/spell_levels.py
"""Niveau d'emplacement des sorts — source : compendium (mechanics.level)."""
from __future__ import annotations

from jdr_engine.rules.engine import RuleEngine

_LEVEL_CACHE: dict[str, int] | None = None


def _build_level_cache(*, engine: RuleEngine | None = None) -> dict[str, int]:
    levels: dict[str, int] = {}
    if engine is not None:
        for entry in engine.registry.list_entries("spell"):
            mech = entry.definition.mechanics
            if isinstance(mech, dict):
                levels[entry.entry_id] = int(mech.get("level", 1))
        return levels

    from jdr_engine.compendium.loader import load_ruleset

    _, _, entries = load_ruleset("dnd5e")
    for entry in entries:
        if entry.definition.type != "spell":
            continue
        mech = entry.definition.mechanics
        if isinstance(mech, dict):
            levels[entry.entry_id] = int(mech.get("level", 1))
    return levels


def get_spell_level(spell_id: str, *, engine: RuleEngine | None = None) -> int:
    """
    Niveau d'emplacement SRD du sort (0 = tour de magie).

    Défaut 1 si id inconnu (rétrocompat avec l'ancien ``_SPELL_LEVEL_BY_ID``).
    """
    global _LEVEL_CACHE
    if _LEVEL_CACHE is None:
        _LEVEL_CACHE = _build_level_cache(engine=engine)
    elif engine is not None and spell_id not in _LEVEL_CACHE:
        _LEVEL_CACHE.update(_build_level_cache(engine=engine))
    return _LEVEL_CACHE.get(spell_id, 1)


def reset_spell_level_cache() -> None:
    """Tests uniquement — invalide le cache module."""
    global _LEVEL_CACHE
    _LEVEL_CACHE = None
