# jdr_engine/application/dto/wizard_grimoire_reset.py
"""Résultat réinitialisation grimoire mage (P2g / P2h)."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class WizardGrimoireResetResult:
    character_id: str
    character_name: str
    already_clean: bool
    cantrips_before: tuple[str, ...]
    cantrips_after: tuple[str, ...]
    spellbook_before: tuple[str, ...]
    spellbook_after: tuple[str, ...]
    prepared_before: tuple[str, ...]
    prepared_after: tuple[str, ...]

    @property
    def removed_from_spellbook(self) -> tuple[str, ...]:
        after = set(self.spellbook_after)
        return tuple(s for s in self.spellbook_before if s not in after)

    @property
    def removed_from_prepared(self) -> tuple[str, ...]:
        after = set(self.prepared_after)
        return tuple(s for s in self.prepared_before if s not in after)
