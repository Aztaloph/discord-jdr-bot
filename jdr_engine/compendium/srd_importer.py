# jdr_engine/compendium/srd_importer.py
"""Import mécanique SRD 5.1 (5e-database src/2014) → definition.yaml."""
from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from jdr_engine.compendium.paths import get_compendium_root, get_ruleset_path

SRD_2014_BASE_URL = (
    "https://raw.githubusercontent.com/5e-bits/5e-database/main/src/2014/en"
)

EXCLUDED_SRD_FIELDS = frozenset({
    "desc",
    "age",
    "alignment",
    "size_description",
    "language_desc",
    "url",
    "name",
    "index",
})

ARMOR_PROFICIENCY_MAP = {
    "light-armor": "light",
    "medium-armor": "medium",
    "heavy-armor": "heavy",
    "shields": "shields",
}

WEAPON_PROFICIENCY_MAP = {
    "simple-weapons": "simple",
    "martial-weapons": "martial",
}


@dataclass
class ImportResult:
    updated: list[str] = field(default_factory=list)
    unchanged: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    created: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    changes: list["ImportChange"] = field(default_factory=list)


@dataclass
class ImportChange:
    ref: str
    name_fr: str | None
    name_en_changed: bool
    mechanics_diff_keys: list[str] = field(default_factory=list)

    @property
    def has_changes(self) -> bool:
        return self.name_en_changed or bool(self.mechanics_diff_keys)


def fetch_srd_json(filename: str, *, cache_dir: Path | None = None) -> list[dict]:
    """Télécharge un fichier JSON SRD 2014 (avec cache optionnel)."""
    if cache_dir:
        cache_dir.mkdir(parents=True, exist_ok=True)
        cache_path = cache_dir / filename
        if cache_path.exists():
            return json.loads(cache_path.read_text(encoding="utf-8"))

    url = f"{SRD_2014_BASE_URL}/{filename}"
    try:
        with urllib.request.urlopen(url, timeout=30) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Impossible de charger {url}: {exc}") from exc

    if cache_dir:
        cache_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload


def _skill_slug(proficiency_index: str) -> str:
    """skill-animal-handling → animal_handling."""
    slug = proficiency_index.removeprefix("skill-")
    return slug.replace("-", "_")


def _normalize_armor_weapon_proficiencies(proficiencies: list[dict]) -> tuple[list[str], list[str]]:
    armor: list[str] = []
    weapons: list[str] = []
    for item in proficiencies:
        index = item.get("index", "")
        if index.startswith("saving-throw-"):
            continue
        if index in ARMOR_PROFICIENCY_MAP:
            mapped = ARMOR_PROFICIENCY_MAP[index]
            if mapped not in armor:
                armor.append(mapped)
        elif index in WEAPON_PROFICIENCY_MAP:
            mapped = WEAPON_PROFICIENCY_MAP[index]
            if mapped not in weapons:
                weapons.append(mapped)
    return armor, weapons


def _infer_primary_abilities(class_data: dict[str, Any]) -> list[str]:
    abilities: set[str] = set()
    for save in class_data.get("saving_throws", []):
        if isinstance(save, dict) and save.get("index"):
            abilities.add(save["index"])
    spellcasting = class_data.get("spellcasting") or {}
    ability_ref = spellcasting.get("spellcasting_ability")
    if isinstance(ability_ref, dict) and ability_ref.get("index"):
        abilities.add(ability_ref["index"])
    order = ["str", "dex", "con", "int", "wis", "cha"]
    return [a for a in order if a in abilities]


def map_race_mechanics(race_data: dict[str, Any]) -> dict[str, Any]:
    """SRD race → mechanics (numérique / refs uniquement, pas de texte)."""
    mechanics: dict[str, Any] = {}

    increases = []
    for bonus in race_data.get("ability_bonuses", []) or []:
        ability_ref = bonus.get("ability_score") or {}
        ability = ability_ref.get("index")
        value = bonus.get("bonus")
        if ability and value is not None:
            increases.append({"ability": ability, "value": int(value)})
    mechanics["ability_score_increase"] = increases

    size = race_data.get("size")
    if isinstance(size, str):
        mechanics["size"] = size.strip().lower()

    if race_data.get("speed") is not None:
        mechanics["speed"] = int(race_data["speed"])

    # TODO Phase 4.5: traits actifs — refs non importées automatiquement
    mechanics["traits"] = []

    language_slugs: list[str] = []
    for lang in race_data.get("languages", []) or []:
        if isinstance(lang, dict) and lang.get("index"):
            language_slugs.append(lang["index"].replace(" ", "_").lower())
    if language_slugs:
        mechanics["languages"] = {"fixed": language_slugs}

    return mechanics


def map_class_mechanics(class_data: dict[str, Any]) -> dict[str, Any]:
    """SRD class → mechanics (numérique / slugs uniquement)."""
    mechanics: dict[str, Any] = {}

    hit_die = class_data.get("hit_die")
    if hit_die is not None:
        mechanics["hit_die"] = f"d{int(hit_die)}"

    primary = _infer_primary_abilities(class_data)
    if primary:
        mechanics["primary_abilities"] = primary

    saves = [
        item["index"]
        for item in class_data.get("saving_throws", [])
        if isinstance(item, dict) and item.get("index")
    ]
    mechanics["saving_throw_proficiencies"] = saves

    armor, weapons = _normalize_armor_weapon_proficiencies(
        class_data.get("proficiencies", []) or []
    )
    if armor:
        mechanics["armor_proficiencies"] = armor
    if weapons:
        mechanics["weapon_proficiencies"] = weapons

    for choice in class_data.get("proficiency_choices", []) or []:
        if not isinstance(choice, dict):
            continue
        if choice.get("type") != "proficiencies":
            continue
        from_block = choice.get("from") or {}
        options = from_block.get("options") or []
        skills = []
        for opt in options:
            item = (opt or {}).get("item") or {}
            index = item.get("index", "")
            if index.startswith("skill-"):
                skills.append(_skill_slug(index))
        if skills:
            mechanics["skill_choices"] = {
                "count": int(choice.get("choose", 0)),
                "from": skills,
            }
        break

    spellcasting = class_data.get("spellcasting")
    if isinstance(spellcasting, dict):
        ability_ref = spellcasting.get("spellcasting_ability") or {}
        ability = ability_ref.get("index") if isinstance(ability_ref, dict) else None
        level = spellcasting.get("level")
        if ability and level is not None:
            mechanics["spellcasting"] = {
                "level": int(level),
                "ability": ability,
            }

    return mechanics


def _is_non_empty(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, (list, dict, str)):
        return len(value) > 0
    return True


def merge_mechanics_preserve_existing(
    existing: dict[str, Any],
    incoming: dict[str, Any],
    *,
    preserve_keys: tuple[str, ...] = ("features_by_level",),
) -> dict[str, Any]:
    """
    Fusion non destructive : SRD incoming + données locales à ne pas écraser.
    - traits non vides conservés
    - languages.choose conservé
    - preserve_keys (ex. features_by_level) si absent de incoming
    """
    merged = dict(incoming)

    existing_traits = existing.get("traits")
    if _is_non_empty(existing_traits):
        merged["traits"] = existing_traits

    existing_languages = existing.get("languages")
    incoming_languages = merged.get("languages")
    if isinstance(existing_languages, dict):
        languages = dict(incoming_languages) if isinstance(incoming_languages, dict) else {}
        if existing_languages.get("choose"):
            languages["choose"] = existing_languages["choose"]
        if existing_languages.get("fixed"):
            # Garde fixed SRD si présent, sinon fallback local
            languages.setdefault("fixed", existing_languages["fixed"])
        merged["languages"] = languages

    for key in preserve_keys:
        if key in existing and key not in incoming:
            merged[key] = existing[key]

    return merged


def _mechanics_diff_keys(before: dict[str, Any], after: dict[str, Any]) -> list[str]:
    keys = set(before) | set(after)
    return sorted(k for k in keys if before.get(k) != after.get(k))


TODO_PHASE_MARKER = "# TODO Phase 4.5"


def _find_parent_key(lines: list[str], comment_index: int) -> str | None:
    for idx in range(comment_index - 1, -1, -1):
        line = lines[idx].strip()
        if line and not line.startswith("#"):
            return line.split(":")[0].strip()
    return None


def preserve_todo_comments(original_text: str, new_text: str) -> str:
    """
    Re-grafte les commentaires # TODO Phase 4.5 depuis le fichier original.
    Alternative légère à ruamel.yaml (inline + commentaires sur ligne dédiée).
    """
    if TODO_PHASE_MARKER not in original_text:
        return new_text

    orig_lines = original_text.splitlines()
    inline_suffixes: dict[str, str] = {}
    block_comments: list[tuple[str, str]] = []

    for idx, line in enumerate(orig_lines):
        if TODO_PHASE_MARKER not in line:
            continue
        if line.lstrip().startswith("# TODO"):
            parent = _find_parent_key(orig_lines, idx)
            if parent:
                block_comments.append((parent, line))
        elif ":" in line:
            key = line.split(":")[0].strip()
            pos = line.index(TODO_PHASE_MARKER)
            inline_suffixes[key] = line[pos:]

    if not inline_suffixes and not block_comments:
        return new_text

    new_lines = new_text.splitlines()
    output: list[str] = []
    for line in new_lines:
        if ":" in line:
            key = line.split(":")[0].strip()
            if key in inline_suffixes and TODO_PHASE_MARKER not in line:
                line = f"{line.rstrip()}  {inline_suffixes[key]}"
            output.append(line)
            for parent, comment_line in block_comments:
                if parent == key:
                    output.append(comment_line)
            continue
        output.append(line)

    result = "\n".join(output)
    return result + ("\n" if new_text.endswith("\n") else "")


def build_merged_definition(
    definition_path: Path,
    *,
    entity_type: str,
    entry_id: str,
    name_en: str,
    mechanics: dict[str, Any],
    preserve_keys: tuple[str, ...] = ("features_by_level",),
) -> tuple[dict[str, Any], bool, list[str], bool]:
    """
    Calcule definition.yaml fusionné sans écrire.
    Retourne (data, created, mechanics_diff_keys, name_en_changed).
    """
    created = not definition_path.exists()
    if created:
        data: dict[str, Any] = {
            "schema_version": "1.0",
            "type": entity_type,
            "id": entry_id,
            "name": {"en": name_en, "fr": name_en},
            "mechanics": mechanics,
        }
        return data, True, list(mechanics.keys()), False

    data = _load_yaml(definition_path)
    name = data.setdefault("name", {})
    if not isinstance(name, dict):
        name = {}
        data["name"] = name

    name_en_before = name.get("en")
    name_en_changed = name_en_before != name_en
    name["en"] = name_en

    existing = data.get("mechanics") or {}
    if not isinstance(existing, dict):
        existing = {}

    merged = merge_mechanics_preserve_existing(
        existing, mechanics, preserve_keys=preserve_keys
    )
    diff_keys = _mechanics_diff_keys(existing, merged)
    data["mechanics"] = merged
    return data, False, diff_keys, name_en_changed


def _load_yaml(path: Path) -> dict[str, Any]:
    with open(path, "r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"YAML invalide : {path}")
    return data


def _dump_yaml(data: dict[str, Any]) -> str:
    return yaml.dump(
        data,
        allow_unicode=True,
        default_flow_style=False,
        sort_keys=False,
        width=120,
    )


def merge_definition_file(
    definition_path: Path,
    *,
    entity_type: str,
    entry_id: str,
    name_en: str,
    mechanics: dict[str, Any],
    preserve_keys: tuple[str, ...] = ("features_by_level",),
) -> tuple[bool, bool]:
    """
    Fusionne mechanics dans definition.yaml (non destructif).
    Préserve name.fr, traits, languages.choose, commentaires TODO Phase 4.5.
    Retourne (created, written) — written=False si aucun changement de données.
    """
    original_text = (
        definition_path.read_text(encoding="utf-8") if definition_path.exists() else ""
    )
    data, created, diff_keys, name_en_changed = build_merged_definition(
        definition_path,
        entity_type=entity_type,
        entry_id=entry_id,
        name_en=name_en,
        mechanics=mechanics,
        preserve_keys=preserve_keys,
    )

    if not created and not diff_keys and not name_en_changed:
        return created, False

    new_text = _dump_yaml(data)
    if original_text:
        new_text = preserve_todo_comments(original_text, new_text)

    definition_path.parent.mkdir(parents=True, exist_ok=True)
    definition_path.write_text(new_text, encoding="utf-8")
    return created, True


def _process_import_entry(
    result: ImportResult,
    *,
    ref: str,
    target: Path,
    entity_type: str,
    entry_id: str,
    name_en: str,
    mechanics: dict[str, Any],
    preserve_keys: tuple[str, ...] = ("features_by_level",),
    dry_run: bool = False,
) -> None:
    try:
        data, created, diff_keys, name_en_changed = build_merged_definition(
            target,
            entity_type=entity_type,
            entry_id=entry_id,
            name_en=name_en,
            mechanics=mechanics,
            preserve_keys=preserve_keys,
        )
        name_fr = (data.get("name") or {}).get("fr") if isinstance(data.get("name"), dict) else None
        change = ImportChange(
            ref=ref,
            name_fr=name_fr,
            name_en_changed=name_en_changed,
            mechanics_diff_keys=diff_keys,
        )

        if not created and not change.has_changes:
            result.unchanged.append(ref)
            return

        result.changes.append(change)
        if dry_run:
            result.updated.append(ref)
            return

        _, written = merge_definition_file(
            target,
            entity_type=entity_type,
            entry_id=entry_id,
            name_en=name_en,
            mechanics=mechanics,
            preserve_keys=preserve_keys,
        )
        if not written:
            result.unchanged.append(ref)
            return
        (result.created if created else result.updated).append(ref)
    except (OSError, ValueError, yaml.YAMLError) as exc:
        result.errors.append(f"{ref}: {exc}")


def import_srd_mechanics(
    ruleset_id: str,
    *,
    entry_ids: set[str] | None = None,
    types: set[str] | None = None,
    cache_dir: Path | None = None,
    dry_run: bool = False,
) -> ImportResult:
    """
    Importe les champs mécaniques SRD 2014 vers compendium/{ruleset}/entries/.
    Idempotent : ne modifie pas name.fr.
    """
    result = ImportResult()
    ruleset_path = get_ruleset_path(ruleset_id)
    entries_root = ruleset_path / "entries"

    want_races = types is None or "races" in types
    want_classes = types is None or "classes" in types

    if want_races:
        try:
            races = fetch_srd_json("5e-SRD-Races.json", cache_dir=cache_dir)
        except RuntimeError as exc:
            result.errors.append(str(exc))
            races = []

        races_dir = entries_root / "races"
        local_race_ids = (
            {p.name for p in races_dir.iterdir() if p.is_dir()}
            if races_dir.is_dir()
            else set()
        )

        for race in races:
            race_id = race.get("index")
            if not race_id or (entry_ids and race_id not in entry_ids):
                continue
            if race_id not in local_race_ids:
                result.skipped.append(f"races/{race_id} (absent du Compendium local)")
                continue

            mechanics = map_race_mechanics(race)
            target = entries_root / "races" / race_id / "definition.yaml"
            ref = f"races/{race_id}"

            _process_import_entry(
                result,
                ref=ref,
                target=target,
                entity_type="race",
                entry_id=race_id,
                name_en=race.get("name", race_id),
                mechanics=mechanics,
                dry_run=dry_run,
            )

    if want_classes:
        try:
            classes = fetch_srd_json("5e-SRD-Classes.json", cache_dir=cache_dir)
        except RuntimeError as exc:
            result.errors.append(str(exc))
            classes = []

        classes_dir = entries_root / "classes"
        local_class_ids = (
            {p.name for p in classes_dir.iterdir() if p.is_dir()}
            if classes_dir.is_dir()
            else set()
        )

        for cls in classes:
            class_id = cls.get("index")
            if not class_id or (entry_ids and class_id not in entry_ids):
                continue
            if class_id not in local_class_ids:
                result.skipped.append(f"classes/{class_id} (absent du Compendium local)")
                continue

            mechanics = map_class_mechanics(cls)
            target = classes_dir / class_id / "definition.yaml"
            ref = f"classes/{class_id}"

            _process_import_entry(
                result,
                ref=ref,
                target=target,
                entity_type="class",
                entry_id=class_id,
                name_en=cls.get("name", class_id),
                mechanics=mechanics,
                preserve_keys=("features_by_level",),
                dry_run=dry_run,
            )

    return result


def default_cache_dir() -> Path:
    return get_compendium_root() / ".srd_cache" / "2014"
