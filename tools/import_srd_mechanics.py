#!/usr/bin/env python
# tools/import_srd_mechanics.py
"""
Importe les données mécaniques SRD 5.1 (5e-database src/2014) vers definition.yaml.

Source : https://github.com/5e-bits/5e-database/tree/main/src/2014/en
Licence contenu : CC-BY-4.0 (SRD Wizards of the Coast)

Champs exclus (texte / lore / métadonnées API) :
  desc, age, alignment, size_description, language_desc, url

Non destructif :
  - name.fr jamais modifié
  - traits non vides conservés
  - languages.choose conservé
  - commentaires # TODO Phase 4.5 re-graftés (sans ruamel.yaml)
  - skip écriture si aucun changement de données
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from jdr_engine.compendium.srd_importer import (  # noqa: E402
    default_cache_dir,
    import_srd_mechanics,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Import SRD 5.1 (2014) -> definition.yaml / mechanics",
    )
    parser.add_argument(
        "--ruleset",
        default="dnd5e",
        help="ID du ruleset Compendium (défaut: dnd5e)",
    )
    parser.add_argument(
        "--types",
        default="races,classes",
        help="Types à importer, séparés par des virgules (défaut: races,classes)",
    )
    parser.add_argument(
        "--only",
        nargs="*",
        metavar="ID",
        help="Limiter à certains entry id (ex. halfling ranger)",
    )
    parser.add_argument(
        "--cache-dir",
        type=Path,
        default=None,
        help="Cache local des JSON SRD (défaut: compendium/.srd_cache/2014)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Affiche les changements réels sans écrire",
    )
    args = parser.parse_args()

    types = {t.strip() for t in args.types.split(",") if t.strip()}
    entry_ids = set(args.only) if args.only else None
    cache_dir = args.cache_dir or default_cache_dir()

    print(f"Import SRD 2014 -> compendium/{args.ruleset}/entries/")
    print(f"  Types    : {', '.join(sorted(types))}")
    print(f"  Cache    : {cache_dir}")
    print(f"  Dry-run  : {args.dry_run}")
    if entry_ids:
        print(f"  Filtre   : {', '.join(sorted(entry_ids))}")
    print()

    result = import_srd_mechanics(
        args.ruleset,
        entry_ids=entry_ids,
        types=types,
        cache_dir=cache_dir,
        dry_run=args.dry_run,
    )

    if result.changes:
        print("--- Changements mécaniques réels ---")
        for change in result.changes:
            parts = []
            if change.name_en_changed:
                parts.append("name.en")
            if change.mechanics_diff_keys:
                parts.append("mechanics:" + ",".join(change.mechanics_diff_keys))
            print(f"  [~] {change.ref}  ({'; '.join(parts)})")
            print(f"      name.fr (INCHANGE) : {change.name_fr!r}")
        print()

    if result.unchanged:
        print("--- Inchangées (skip écriture) ---")
        for ref in result.unchanged:
            print(f"  [=] {ref}")
        print()

    for ref in result.created:
        print(f"  [+] créé     {ref}")
    for ref in result.updated:
        if ref not in result.unchanged:
            print(f"  [~] mis à jour {ref}")
    for ref in result.skipped:
        print(f"  [-] ignoré   {ref}")
    for err in result.errors:
        print(f"  [X] erreur   {err}")

    if result.errors:
        return 1

    print()
    print(
        f"[OK] {len(result.created)} créé(s), "
        f"{len(result.updated)} modifié(s), "
        f"{len(result.unchanged)} inchangé(s), "
        f"{len(result.skipped)} ignoré(s) (SRD absent localement)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
