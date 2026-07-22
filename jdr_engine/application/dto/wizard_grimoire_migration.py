# jdr_engine/application/dto/wizard_grimoire_migration.py
"""Rapport migration batch grimoires mage (P2h)."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from jdr_engine.application.dto.wizard_grimoire_reset import WizardGrimoireResetResult


class WizardGrimoireMigrationStatus(str, Enum):
    SKIP = "skip"
    WILL_MODIFY = "will_modify"
    MODIFIED = "modified"
    ERROR = "error"


@dataclass(frozen=True)
class WizardGrimoireMigrationEntry:
    character_id: str
    character_name: str
    status: WizardGrimoireMigrationStatus
    result: WizardGrimoireResetResult | None = None
    error: str | None = None


@dataclass(frozen=True)
class WizardGrimoireMigrationReport:
    guild_id: str
    dry_run: bool
    total_wizards: int
    to_modify: int
    skipped: int
    modified: int
    failed: int
    entries: tuple[WizardGrimoireMigrationEntry, ...]

    @classmethod
    def from_entries(
        cls,
        guild_id: str,
        dry_run: bool,
        entries: list[WizardGrimoireMigrationEntry],
    ) -> WizardGrimoireMigrationReport:
        to_modify = sum(
            1 for e in entries if e.status == WizardGrimoireMigrationStatus.WILL_MODIFY
        )
        skipped = sum(1 for e in entries if e.status == WizardGrimoireMigrationStatus.SKIP)
        modified = sum(
            1 for e in entries if e.status == WizardGrimoireMigrationStatus.MODIFIED
        )
        failed = sum(1 for e in entries if e.status == WizardGrimoireMigrationStatus.ERROR)
        return cls(
            guild_id=guild_id,
            dry_run=dry_run,
            total_wizards=len(entries),
            to_modify=to_modify,
            skipped=skipped,
            modified=modified,
            failed=failed,
            entries=tuple(entries),
        )
