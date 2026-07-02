# jdr_engine/rules/engine.py
"""Façade publique du Rule Engine — query & résolution."""
from __future__ import annotations

from typing import Any

from jdr_engine.compendium.entry import CompendiumEntry, EntitySummary
from jdr_engine.compendium.presenter import CompendiumPresenter
from jdr_engine.compendium.registry import CompendiumRegistry
from jdr_engine.compendium.schemas import normalize_entity_type
from jdr_engine.rules.resolver import resolve_trait_refs
from jdr_engine.rules.ruleset import RulesetContext


class RuleEngine:
    """
    Point d'entrée du Rule Engine pour un ruleset.

    Stateless — toutes les requêtes lisent le Compendium chargé.
    """

    def __init__(self, context: RulesetContext):
        self._context = context
        self._registry = context.registry
        self.presenter = CompendiumPresenter(self._registry)

    @classmethod
    def load(
        cls,
        ruleset_id: str,
        *,
        validate: bool = True,
        strict: bool = True,
    ) -> RuleEngine:
        return cls(RulesetContext.load(ruleset_id, validate=validate, strict=strict))

    @property
    def ruleset_id(self) -> str:
        return self._registry.ruleset_id

    @property
    def ruleset_version(self) -> str:
        return self._registry.version

    @property
    def registry(self) -> CompendiumRegistry:
        return self._registry

    # ── Query ─────────────────────────────────────────────────────────

    def list_entities(self, entity_type: str) -> list[EntitySummary]:
        """Liste les entités d'un type (race, class, trait…)."""
        return self._registry.list_summaries(entity_type)

    def get_entity(self, entity_type: str, entry_id: str) -> CompendiumEntry | None:
        """Retourne une entrée par type et id."""
        return self._registry.get(entity_type, entry_id)

    def get_display_name(
        self,
        entity_type: str,
        entry_id: str,
        locale: str = "fr",
    ) -> str | None:
        entry = self.get_entity(entity_type, entry_id)
        if entry is None:
            return None
        return entry.get_name(locale, self._registry.manifest.default_locale)

    def get_definition(
        self,
        entity_type: str,
        entry_id: str,
    ) -> dict[str, Any] | None:
        """Retourne definition.yaml parsé (dict) ou None."""
        entry = self.get_entity(entity_type, entry_id)
        if entry is None:
            return None
        return entry.definition.model_dump()

    # ── Résolution ────────────────────────────────────────────────────

    def get_race_traits(self, race_id: str) -> list[CompendiumEntry]:
        """Retourne les traits résolus d'une race."""
        entry = self.get_entity("race", race_id)
        if entry is None:
            return []
        return resolve_trait_refs(self._registry, entry.definition.mechanics)

    def get_class_features(
        self,
        class_id: str,
        level: int,
    ) -> list[CompendiumEntry]:
        """Retourne les features de classe débloquées (refs trait/*)."""
        entry = self.get_entity("class", class_id)
        if entry is None:
            return []
        features_by_level = entry.definition.mechanics.get("features_by_level") or {}
        feature_ids: list[str] = []
        for lvl_str, ids in features_by_level.items():
            try:
                lvl = int(lvl_str)
            except (TypeError, ValueError):
                continue
            if lvl <= level and isinstance(ids, list):
                feature_ids.extend(str(fid) for fid in ids)
        resolved: list[CompendiumEntry] = []
        for fid in feature_ids:
            trait = self.get_entity("trait", fid)
            if trait is not None:
                resolved.append(trait)
        return resolved

    def get_ability_bonuses(self, race_id: str) -> dict[str, int]:
        """Bonus raciaux aux caractéristiques (ex. elf → {dex: 2})."""
        entry = self.get_entity("race", race_id)
        if entry is None:
            return {}
        bonuses: dict[str, int] = {}
        for item in entry.definition.mechanics.get("ability_score_increase", []):
            if isinstance(item, dict):
                ability = item.get("ability")
                value = item.get("value", 0)
                if ability:
                    bonuses[ability] = bonuses.get(ability, 0) + int(value)
        return bonuses

    def get_class_hit_die(self, class_id: str) -> str | None:
        entry = self.get_entity("class", class_id)
        if entry is None:
            return None
        return entry.definition.mechanics.get("hit_die")

    def get_proficiency_bonus(self, level: int) -> int:
        return self._registry.config.proficiency_bonus_at_level(level)

    def entity_exists(self, entity_type: str, entry_id: str) -> bool:
        return self.get_entity(entity_type, entry_id) is not None

    def normalize_type(self, entity_type: str) -> str:
        return normalize_entity_type(entity_type)
