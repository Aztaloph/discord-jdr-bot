# jdr_engine/rules/effects/registry.py
"""Registre in-memory des effets actifs — lot ADR-006."""
from __future__ import annotations

from jdr_engine.domain.combat.active_effect import ActiveEffect


class ActiveEffectRegistry:
    """Source de vérité runtime pour les ``ActiveEffect`` d'une rencontre."""

    def __init__(self) -> None:
        self._effects: tuple[ActiveEffect, ...] = ()

    def all_effects(self) -> tuple[ActiveEffect, ...]:
        return self._effects

    def add(self, effect: ActiveEffect) -> None:
        key = effect.identity
        without = tuple(e for e in self._effects if e.identity != key)
        self._effects = without + (effect,)

    def remove(self, effect: ActiveEffect) -> bool:
        key = effect.identity
        before = len(self._effects)
        self._effects = tuple(e for e in self._effects if e.identity != key)
        return len(self._effects) < before

    def remove_matching(
        self,
        *,
        effect_id: str | None = None,
        source_id: str | None = None,
        target_id: str | None = None,
    ) -> tuple[ActiveEffect, ...]:
        """Retire les effets correspondant aux filtres fournis."""

        def _matches(effect: ActiveEffect) -> bool:
            if effect_id is not None and effect.effect_id != effect_id:
                return False
            if source_id is not None and effect.source_id != source_id:
                return False
            if target_id is not None and effect.target_id != target_id:
                return False
            return True

        removed = tuple(e for e in self._effects if _matches(e))
        if not removed:
            return ()
        self._effects = tuple(e for e in self._effects if not _matches(e))
        return removed

    def query(
        self,
        *,
        effect_id: str | None = None,
        source_id: str | None = None,
        target_id: str | None = None,
    ) -> tuple[ActiveEffect, ...]:
        return tuple(
            effect
            for effect in self._effects
            if (effect_id is None or effect.effect_id == effect_id)
            and (source_id is None or effect.source_id == source_id)
            and (target_id is None or effect.target_id == target_id)
        )

    def tick(self, round_number: int) -> tuple[ActiveEffect, ...]:
        """
        Décompte à l'entrée du round ``round_number`` (borne exclusive).

        Retire tout effet ``rounds`` où ``expires_at_round <= round_number``.
        """
        expired: list[ActiveEffect] = []
        kept: list[ActiveEffect] = []
        for effect in self._effects:
            if effect.expiry_mode != "rounds":
                kept.append(effect)
                continue
            expires = effect.expires_at_round
            if expires is not None and expires <= round_number:
                expired.append(effect)
            else:
                kept.append(effect)
        self._effects = tuple(kept)
        return tuple(expired)
