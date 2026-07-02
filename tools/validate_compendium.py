#!/usr/bin/env python
# tools/validate_compendium.py
"""Valide l'intégrité d'un ruleset Compendium."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Racine projet sur sys.path
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from jdr_engine.compendium.loader import CompendiumLoadError, load_ruleset
from jdr_engine.compendium.registry import CompendiumRegistry
from jdr_engine.compendium.validator import validate_registry


def validate_ruleset(ruleset_id: str, *, strict: bool = True) -> int:
    try:
        manifest, config, entries = load_ruleset(ruleset_id)
    except CompendiumLoadError as exc:
        print(f"[ERREUR] Chargement {ruleset_id}: {exc}")
        return 1

    registry = CompendiumRegistry(manifest, config, entries)
    report = validate_registry(
        registry,
        schema_strict=strict,
    )

    print(f"Compendium : {ruleset_id}@{manifest.version}")
    print(f"  Entrées  : {len(registry)}")
    print(f"  Erreurs  : {report.error_count}")
    print(f"  Warnings : {report.warning_count}")

    for issue in report.issues:
        icon = "[X]" if issue.level == "error" else "[!]"
        ref = f" ({issue.ref})" if issue.ref else ""
        print(f"  {icon} [{issue.code}] {issue.message}{ref}")

    if report.ok:
        print("[OK] Compendium valide")
        return 0

    if strict:
        print("[X] Validation echouee (mode strict)")
        return 1

    print("[!] Compendium avec erreurs (mode warn)")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Valide un ruleset Compendium")
    parser.add_argument(
        "ruleset",
        nargs="?",
        default="dnd5e",
        help="ID du ruleset (défaut: dnd5e)",
    )
    parser.add_argument(
        "--warn",
        action="store_true",
        help="Ne pas échouer sur les erreurs (mode warn)",
    )
    args = parser.parse_args()
    return validate_ruleset(args.ruleset, strict=not args.warn)


if __name__ == "__main__":
    raise SystemExit(main())
