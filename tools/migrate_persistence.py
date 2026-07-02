#!/usr/bin/env python
# tools/migrate_persistence.py
"""Migre les personnages v1 → v2."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from jdr_engine.persistence.migrations.v1_to_v2 import (
    backup_v1,
    migrate_v1_to_v2,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Migration personnages v1 → v2")
    parser.add_argument(
        "--no-backup",
        action="store_true",
        help="Ne pas sauvegarder le v2 existant",
    )
    parser.add_argument(
        "--backup-v1",
        action="store_true",
        help="Copie aussi characters.json v1 avant migration",
    )
    args = parser.parse_args()

    if args.backup_v1:
        path = backup_v1()
        if path:
            print(f"[OK] Backup v1 : {path}")

    try:
        migrated = migrate_v1_to_v2(backup=not args.no_backup)
    except Exception as exc:
        print(f"[ERREUR] Migration : {exc}")
        return 1

    print(f"[OK] {len(migrated)} personnage(s) migre(s) vers data/characters/v2/")
    for char in migrated:
        print(f"  - {char.name} ({char.id}) : {char.race_id} / {char.class_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
