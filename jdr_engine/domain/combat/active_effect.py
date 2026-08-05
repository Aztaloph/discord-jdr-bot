# jdr_engine/domain/combat/active_effect.py
"""Effet actif de rencontre — lot ADR-006 (structure minimale)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

ExpiryMode = Literal["concentration", "rounds", "manual"]


class ActiveEffectValidationError(ValueError):
    """Champs incohérents pour un ``ActiveEffect``."""


@dataclass(frozen=True)
class ActiveEffect:
    """
    Snapshot d'un buff ou effet temporaire porté par la rencontre.

    ``duration_rounds`` n'est requis que si ``expiry_mode == "rounds"``.
    """

    effect_id: str
    source_id: str
    target_id: str
    applied_at_round: int
    expiry_mode: ExpiryMode
    duration_rounds: int | None = None

    def __post_init__(self) -> None:
        if self.expiry_mode == "rounds":
            if self.duration_rounds is None:
                raise ActiveEffectValidationError(
                    "duration_rounds est obligatoire si expiry_mode vaut 'rounds'."
                )
            if self.duration_rounds <= 0:
                raise ActiveEffectValidationError(
                    "duration_rounds doit être strictement positif."
                )

    @property
    def expires_at_round(self) -> int | None:
        """Borne exclusive d'expiration (décision 1 ADR-006)."""
        if self.expiry_mode != "rounds":
            return None
        assert self.duration_rounds is not None
        return self.applied_at_round + self.duration_rounds

    @property
    def identity(self) -> tuple[str, str, str]:
        """Clé stable pour add/remove dans le registre."""
        return (self.effect_id, self.source_id, self.target_id)
