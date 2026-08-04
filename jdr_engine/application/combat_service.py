# jdr_engine/application/combat_service.py
"""Use cases combat — lot C7 (couche application au-dessus de CombatManager)."""
from __future__ import annotations

from pathlib import Path

from jdr_engine.core.events.bus import EventBus
from jdr_engine.core.events.handlers.combat_auto_save import CombatAutoSaveHandler
from jdr_engine.domain.combat.combat_state import CombatState
from jdr_engine.game.combat_manager import (
    AttackRollResolution,
    CombatManager,
    DamageResolution,
    SpellAttackOutcome,
)
from jdr_engine.persistence.combat_log_repository import (
    CombatLogEntry,
    SqliteCombatLogRepository,
)
from jdr_engine.persistence.combat_repository import SqliteCombatRepository
from jdr_engine.persistence.sqlite_character_repository import (
    SqliteCharacterRepository,
)
from jdr_engine.rules.engine import RuleEngine


class CombatService:
    """
    Point d'entrée applicatif pour les rencontres.

    Délègue la logique métier à ``CombatManager`` ; enregistre le journal
    événementiel via ``CombatAutoSaveHandler``.
    """

    def __init__(
        self,
        event_bus: EventBus,
        combat_repository: SqliteCombatRepository,
        character_repository: SqliteCharacterRepository,
        combat_log_repository: SqliteCombatLogRepository,
        engine: RuleEngine,
        *,
        register_auto_save_handler: bool = True,
    ) -> None:
        self._bus = event_bus
        self._combats = combat_repository
        self._characters = character_repository
        self._log = combat_log_repository
        self._engine = engine
        self._manager = CombatManager(
            event_bus,
            combat_repository,
            character_repository,
            engine,
        )
        if register_auto_save_handler:
            CombatAutoSaveHandler(combat_log_repository).register(event_bus)

    @classmethod
    def from_db_path(
        cls,
        db_path: Path,
        engine: RuleEngine,
        *,
        event_bus: EventBus | None = None,
        register_auto_save_handler: bool = True,
    ) -> CombatService:
        """Fabrique un service partageant une base SQLite (tests, intégration)."""
        bus = event_bus or EventBus()
        return cls(
            bus,
            SqliteCombatRepository(db_path),
            SqliteCharacterRepository(db_path),
            SqliteCombatLogRepository(db_path),
            engine,
            register_auto_save_handler=register_auto_save_handler,
        )

    def create_combat(
        self,
        guild_id: str,
        channel_id: str,
        character_ids: list[str] | None = None,
    ) -> CombatState:
        return self._manager.create_combat(guild_id, channel_id, character_ids)

    def activate_combat(self, combat_id: int, *, rng=None) -> CombatState:
        return self._manager.activate_combat(combat_id, rng=rng)

    def load_combat(self, combat_id: int) -> CombatState:
        return self._manager.load_combat(combat_id)

    def load_open_combat(
        self,
        guild_id: str,
        channel_id: str,
    ) -> CombatState | None:
        return self._manager.load_open_combat(guild_id, channel_id)

    def close_combat(self, combat_id: int, *, reason: str = "closed") -> CombatState:
        return self._manager.close_combat(combat_id, reason=reason)

    def apply_condition(
        self,
        combat_id: int,
        combatant_id: str,
        condition_id: str,
    ) -> CombatState:
        return self._manager.apply_condition(combat_id, combatant_id, condition_id)

    def resolve_attack_roll(
        self,
        combat_id: int,
        attacker_id: str,
        target_id: str,
        request,
        *,
        rng=None,
    ) -> AttackRollResolution:
        return self._manager.resolve_attack_roll(
            combat_id, attacker_id, target_id, request, rng=rng
        )

    def apply_damage(
        self,
        combat_id: int,
        target_id: str,
        damage_notation: str = "",
        *,
        damage_amount: int | None = None,
        critical: bool = False,
        source_id: str | None = None,
        rng=None,
        dice_notation_label: str | None = None,
    ) -> tuple[CombatState, DamageResolution]:
        return self._manager.apply_damage(
            combat_id,
            target_id,
            damage_notation,
            damage_amount=damage_amount,
            critical=critical,
            source_id=source_id,
            rng=rng,
            dice_notation_label=dice_notation_label,
        )

    def cast_hunters_mark(
        self,
        combat_id: int,
        caster_id: str,
        target_id: str,
        *,
        locale: str = "fr",
    ) -> CombatState:
        return self._manager.cast_hunters_mark(
            combat_id, caster_id, target_id, locale=locale
        )

    def get_event_log(self, combat_id: int) -> list[CombatLogEntry]:
        """Retourne le journal append-only des événements publiés pour ce combat."""
        return self._log.list_for_combat(combat_id)
