# jdr_engine/rules/spellcasting/spell_pool_builder.py
"""Construit les pools de sorts par classe depuis le compendium YAML (Lot B2 — D2)."""
from __future__ import annotations

import logging
from collections import defaultdict
from functools import lru_cache

from jdr_engine.compendium.loader import load_ruleset

logger = logging.getLogger(__name__)

SUPPORTED_SPELL_CLASSES: frozenset[str] = frozenset(
    {
        "wizard",
        "cleric",
        "druid",
        "bard",
        "sorcerer",
        "warlock",
        "ranger",
        "paladin",
    }
)


def _sort_pool(entries: list[tuple[int, str]]) -> tuple[str, ...]:
    """Trie par ``class_pool_order`` puis par id stable."""
    entries.sort(key=lambda item: (item[0], item[1]))
    return tuple(spell_id for _, spell_id in entries)


@lru_cache(maxsize=1)
def build_class_spell_pools(
    ruleset_id: str = "dnd5e",
) -> tuple[
    dict[str, tuple[str, ...]],
    dict[str, tuple[str, ...]],
]:
    """
    Retourne (cantrips_by_class, leveled_by_class) dérivés des fiches YAML.

    Chaque sort contribue à un pool si ``class_id in definition.classes`` ;
    l'ordre dans le pool vient de ``class_pool_order[class_id]`` (défaut : 999).
    """
    _, _, entries = load_ruleset(ruleset_id)
    cantrips: dict[str, list[tuple[int, str]]] = defaultdict(list)
    leveled: dict[str, list[tuple[int, str]]] = defaultdict(list)

    for entry in entries:
        if entry.definition.type != "spell":
            continue
        definition = entry.definition
        spell_id = entry.entry_id
        level = int(definition.mechanics.get("level", 0))
        for class_id in definition.classes:
            if class_id not in SUPPORTED_SPELL_CLASSES:
                logger.warning(
                    "Sort %s : classe inconnue %r ignorée", spell_id, class_id
                )
                continue
            order = definition.class_pool_order.get(class_id, 999)
            if level == 0:
                cantrips[class_id].append((order, spell_id))
            else:
                leveled[class_id].append((order, spell_id))

    cantrip_pools = {cls: _sort_pool(items) for cls, items in cantrips.items()}
    leveled_pools = {cls: _sort_pool(items) for cls, items in leveled.items()}
    return cantrip_pools, leveled_pools


def spell_ids_for_class(class_id: str, *, ruleset_id: str = "dnd5e") -> tuple[str, ...]:
    """Union cantrips + sorts niv. 1+ pour une classe."""
    cantrips, leveled = build_class_spell_pools(ruleset_id)
    return cantrips.get(class_id, ()) + leveled.get(class_id, ())


def all_spellcasting_spell_ids(*, ruleset_id: str = "dnd5e") -> tuple[str, ...]:
    """Tous les sorts uniques listés dans au moins un pool classe."""
    cantrips, leveled = build_class_spell_pools(ruleset_id)
    seen: list[str] = []
    for pools in (cantrips, leveled):
        for pool in pools.values():
            for spell_id in pool:
                if spell_id not in seen:
                    seen.append(spell_id)
    return tuple(seen)
