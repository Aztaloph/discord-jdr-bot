#!/usr/bin/env python
"""Injecte la fiche test « Joe le mage » dans data/characters/v2/characters.json."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from jdr_engine.compendium.paths import get_project_root
from jdr_engine.persistence.character_repository import (
    PERSISTENCE_SCHEMA_VERSION,
    get_v2_characters_path,
)

FIXTURE_PATH = (
    get_project_root() / "fixtures" / "characters" / "joe_le_mage.v2.json"
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Crée ou met à jour Joe le mage (Magicien niv. 3, Lot B sorts)."
    )
    parser.add_argument(
        "--owner-id",
        required=True,
        help="Votre identifiant Discord (clic droit profil → Copier l'identifiant)",
    )
    args = parser.parse_args()
    owner_id = str(args.owner_id).strip()

    if not FIXTURE_PATH.is_file():
        print(f"Fixture introuvable : {FIXTURE_PATH}", file=sys.stderr)
        return 1

    fixture = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    joe_raw = fixture["characters"]["joe00001"]
    joe_raw["owner_id"] = owner_id

    target = get_v2_characters_path()
    target.parent.mkdir(parents=True, exist_ok=True)

    if target.exists():
        data = json.loads(target.read_text(encoding="utf-8"))
    else:
        data = {"schema_version": PERSISTENCE_SCHEMA_VERSION, "characters": {}}

    chars = data.setdefault("characters", {})
    existing_id = None
    for cid, raw in chars.items():
        if (
            str(raw.get("owner_id")) == owner_id
            and str(raw.get("name", "")).lower() == "joe le mage"
        ):
            existing_id = cid
            break

    char_id = existing_id or joe_raw["id"]
    joe_raw["id"] = char_id
    chars[char_id] = joe_raw
    data["schema_version"] = PERSISTENCE_SCHEMA_VERSION

    target.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Fiche « Joe le mage » enregistrée dans {target} (id={char_id}, owner={owner_id})")
    print("Grimoire : fire_bolt + chromatic_orb, burning_hands, detect_magic, scorching_ray")
    print("Emplacements niv. 3 : 4× niv.1, 2× niv.2 (slots_used vide)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
