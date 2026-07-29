# tests/unit/test_cast_concentration.py
"""Concentration — pose, remplacement, repos, persistance, affichage (Lot 1)."""
from __future__ import annotations

import tempfile
import unittest
from dataclasses import dataclass
from pathlib import Path

import yaml

from jdr_engine.domain.character.ability_scores import AbilityScores
from jdr_engine.domain.character.character import Character
from jdr_engine.persistence.database import init_database
from jdr_engine.persistence.sqlite_character_repository import SqliteCharacterRepository
from jdr_engine.rules import RuleEngine
from jdr_engine.rules.calculator import build_character_sheet
from jdr_engine.rules.rest import apply_long_rest, apply_short_rest
from jdr_engine.rules.spellcasting.cast import (
    build_spell_display_lines,
    cast_spell,
)
from jdr_engine.rules.spellcasting.state import format_spellcasting_detail, get_spellcasting_state

from interfaces.discord.formatters.character_embed import build_character_display


CONCENTRATION_SPELL_IDS: frozenset[str] = frozenset(
    {
        "banishment",
        "bless",
        "darkness",
        "detect_magic",
        "entangle",
        "faerie_fire",
        "flaming_sphere",
        "fly",
        "guidance",
        "haste",
        "hex",
        "hunters_mark",
        "polymorph",
    }
)


def _collect_compendium_concentration_spell_ids() -> frozenset[str]:
    """Ids des sorts curated déclarant mechanics.concentration: true."""
    spells_dir = Path("compendium/dnd5e/entries/spells")
    ids: set[str] = set()
    for yaml_path in spells_dir.glob("*/definition.yaml"):
        data = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
        mechanics = (data or {}).get("mechanics") or {}
        if mechanics.get("concentration") is True:
            ids.add(yaml_path.parent.name)
    return frozenset(ids)


class SequenceRng:
    def __init__(self, values: list[int]):
        self._values = list(values)
        self._index = 0

    def __call__(self, low: int, high: int) -> int:
        value = self._values[self._index]
        self._index += 1
        return value


@dataclass(frozen=True)
class ConcentrationCastSetup:
    class_id: str
    level: int
    ability: str = "wis"
    cantrips: tuple[str, ...] = ()
    prepared: tuple[str, ...] = ()
    known: tuple[str, ...] = ()
    rng: tuple[int, ...] = ()


CONCENTRATION_CAST_SETUP: dict[str, ConcentrationCastSetup] = {
    "banishment": ConcentrationCastSetup(
        "cleric", 9, "wis", prepared=("banishment",)
    ),
    "bless": ConcentrationCastSetup("cleric", 1, "wis", prepared=("bless",)),
    "darkness": ConcentrationCastSetup(
        "warlock", 3, "cha", known=("darkness",)
    ),
    "detect_magic": ConcentrationCastSetup(
        "cleric", 1, "wis", prepared=("detect_magic",)
    ),
    "entangle": ConcentrationCastSetup(
        "druid", 1, "wis", prepared=("entangle",)
    ),
    "faerie_fire": ConcentrationCastSetup(
        "bard", 1, "cha", known=("faerie_fire",), rng=(10, 3, 4)
    ),
    "flaming_sphere": ConcentrationCastSetup(
        "druid", 3, "wis", prepared=("flaming_sphere",), rng=(3, 4)
    ),
    "fly": ConcentrationCastSetup("wizard", 5, "int", prepared=("fly",)),
    "guidance": ConcentrationCastSetup(
        "cleric", 1, "wis", cantrips=("guidance",)
    ),
    "haste": ConcentrationCastSetup("wizard", 5, "int", prepared=("haste",)),
    "hex": ConcentrationCastSetup("warlock", 1, "cha", known=("hex",)),
    "hunters_mark": ConcentrationCastSetup(
        "ranger", 2, "wis", known=("hunters_mark",)
    ),
    "polymorph": ConcentrationCastSetup(
        "wizard", 7, "int", prepared=("polymorph",)
    ),
}


def _make_caster(setup: ConcentrationCastSetup) -> Character:
    scores = dict.fromkeys(("str", "dex", "con", "int", "wis", "cha"), 10)
    scores[setup.ability] = 16
    spellcasting: dict = {"slots_used": {}}
    if setup.cantrips:
        spellcasting["cantrips_known"] = list(setup.cantrips)
    if setup.prepared:
        spellcasting["spells_prepared"] = list(setup.prepared)
    if setup.known:
        spellcasting["spells_known"] = list(setup.known)
    return Character(
        owner_id="1",
        name="Concentrateur",
        race_id="human",
        class_id=setup.class_id,
        level=setup.level,
        ability_scores=AbilityScores(scores=scores),
        hp_current=30,
        choices={"spellcasting": spellcasting},
    )


def _warlock_with_spells(*spell_ids: str, level: int = 3) -> Character:
    return Character(
        owner_id="1",
        name="Occultiste",
        race_id="human",
        class_id="warlock",
        level=level,
        ability_scores=AbilityScores(
            scores={
                "str": 10,
                "dex": 10,
                "con": 10,
                "int": 10,
                "wis": 10,
                "cha": 16,
            }
        ),
        hp_current=20,
        choices={
            "spellcasting": {
                "cantrips_known": ["eldritch_blast"],
                "spells_known": list(spell_ids),
                "slots_used": {},
            }
        },
    )


class TestConcentrationPose(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not Path("compendium/dnd5e").is_dir():
            raise unittest.SkipTest("compendium absent")
        cls.engine = RuleEngine.load("dnd5e", validate=True, strict=True)

    def test_concentration_spell_ids_match_compendium(self):
        catalog_ids = _collect_compendium_concentration_spell_ids()
        missing_from_constant = catalog_ids - CONCENTRATION_SPELL_IDS
        extra_in_constant = CONCENTRATION_SPELL_IDS - catalog_ids
        if missing_from_constant or extra_in_constant:
            parts: list[str] = []
            if missing_from_constant:
                parts.append(
                    "présent au catalogue (concentration: true) mais absent de "
                    f"CONCENTRATION_SPELL_IDS : {sorted(missing_from_constant)}"
                )
            if extra_in_constant:
                parts.append(
                    "présent dans CONCENTRATION_SPELL_IDS mais absent du catalogue "
                    f"(concentration: true) : {sorted(extra_in_constant)}"
                )
            self.fail(" ; ".join(parts))
        self.assertEqual(CONCENTRATION_SPELL_IDS, catalog_ids)

    def test_all_concentration_spells_set_state(self):
        for spell_id in sorted(CONCENTRATION_SPELL_IDS):
            with self.subTest(spell_id=spell_id):
                self.assertIn(
                    spell_id,
                    CONCENTRATION_CAST_SETUP,
                    f"CONCENTRATION_CAST_SETUP sans entrée pour {spell_id!r}",
                )
                setup = CONCENTRATION_CAST_SETUP[spell_id]
                char = _make_caster(setup)
                rng = SequenceRng(list(setup.rng)) if setup.rng else None
                result = cast_spell(
                    char,
                    spell_id,
                    self.engine,
                    persist_slots=True,
                    rng=rng,
                )
                self.assertTrue(result.concentration, spell_id)
                conc = get_spellcasting_state(result.updated_character).get(
                    "concentration"
                )
                self.assertIsInstance(conc, dict)
                assert isinstance(conc, dict)
                self.assertEqual(conc["spell_id"], spell_id)
                entry = self.engine.get_entity("spell", spell_id)
                assert entry is not None
                expected_name = entry.get_name(
                    "fr", self.engine.registry.manifest.default_locale
                )
                self.assertEqual(conc["spell_name"], expected_name)

    def test_non_concentration_spells_do_not_set_state(self):
        wizard = Character(
            owner_id="1",
            name="Mage",
            race_id="human",
            class_id="wizard",
            level=5,
            ability_scores=AbilityScores(
                scores={
                    "str": 8,
                    "dex": 14,
                    "con": 12,
                    "int": 16,
                    "wis": 10,
                    "cha": 10,
                }
            ),
            hp_current=20,
            choices={
                "spellcasting": {
                    "cantrips_known": ["fire_bolt"],
                    "spells_prepared": ["fireball", "magic_missile"],
                    "slots_used": {},
                }
            },
        )
        for spell_id, rng_values in (
            ("fireball", [4, 4, 4, 4, 4, 4, 4, 4]),
            ("magic_missile", [4, 4, 4]),
        ):
            with self.subTest(spell_id=spell_id):
                char = wizard
                rng = SequenceRng(rng_values)
                result = cast_spell(
                    char,
                    spell_id,
                    self.engine,
                    persist_slots=True,
                    rng=rng,
                )
                self.assertFalse(result.concentration)
                conc = get_spellcasting_state(result.updated_character).get(
                    "concentration"
                )
                self.assertIsNone(conc)
                wizard = result.updated_character


class TestConcentrationReplacement(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not Path("compendium/dnd5e").is_dir():
            raise unittest.SkipTest("compendium absent")
        cls.engine = RuleEngine.load("dnd5e", validate=True, strict=True)

    def test_replacement_mentions_previous_spell(self):
        char = _warlock_with_spells("bless", "hex")
        bless_result = cast_spell(char, "bless", self.engine, persist_slots=True)
        hex_result = cast_spell(
            bless_result.updated_character,
            "hex",
            self.engine,
            persist_slots=True,
        )
        conc = get_spellcasting_state(hex_result.updated_character)["concentration"]
        self.assertEqual(conc["spell_id"], "hex")
        bless_name = self.engine.get_entity("spell", "bless").get_name(
            "fr", self.engine.registry.manifest.default_locale
        )
        self.assertEqual(hex_result.interrupted_concentration, bless_name)
        text = "\n".join(build_spell_display_lines(hex_result))
        self.assertIn(bless_name, text)
        self.assertIn("Concentration interrompue", text)

    def test_recast_same_spell_no_interruption_message(self):
        char = _warlock_with_spells("bless")
        first = cast_spell(char, "bless", self.engine, persist_slots=True)
        second = cast_spell(
            first.updated_character,
            "bless",
            self.engine,
            persist_slots=True,
        )
        conc = get_spellcasting_state(second.updated_character)["concentration"]
        self.assertEqual(conc["spell_id"], "bless")
        self.assertIsNone(second.interrupted_concentration)
        text = "\n".join(build_spell_display_lines(second))
        self.assertNotIn("Concentration interrompue", text)


class TestConcentrationRest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not Path("compendium/dnd5e").is_dir():
            raise unittest.SkipTest("compendium absent")
        cls.engine = RuleEngine.load("dnd5e", validate=True, strict=True)

    def test_long_rest_clears_concentration(self):
        char = _warlock_with_spells("hex")
        result = cast_spell(char, "hex", self.engine, persist_slots=True)
        self.assertIn(
            "concentration",
            get_spellcasting_state(result.updated_character),
        )
        rested, _ = apply_long_rest(result.updated_character, self.engine)
        self.assertNotIn("concentration", get_spellcasting_state(rested))

    def test_short_rest_clears_concentration(self):
        char = _warlock_with_spells("hex")
        result = cast_spell(char, "hex", self.engine, persist_slots=True)
        rested, _ = apply_short_rest(result.updated_character, self.engine, 0)
        self.assertNotIn("concentration", get_spellcasting_state(rested))


class TestConcentrationPersistence(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not Path("compendium/dnd5e").is_dir():
            raise unittest.SkipTest("compendium absent")
        cls.engine = RuleEngine.load("dnd5e", validate=True, strict=True)

    def test_concentration_survives_sqlite_reload(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "bot.db"
            init_database(db_path)
            repo = SqliteCharacterRepository(db_path)
            char = _warlock_with_spells("hex")
            char.id = "conc001"
            char.guild_id = "111"
            repo.save(char)
            result = cast_spell(char, "hex", self.engine, persist_slots=True)
            repo.save(result.updated_character)
            reloaded = repo.get_by_id("conc001")
            self.assertIsNotNone(reloaded)
            assert reloaded is not None
            conc = get_spellcasting_state(reloaded).get("concentration")
            self.assertEqual(conc["spell_id"], "hex")


class TestConcentrationDisplay(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not Path("compendium/dnd5e").is_dir():
            raise unittest.SkipTest("compendium absent")
        cls.engine = RuleEngine.load("dnd5e", validate=True, strict=True)

    def test_format_spellcasting_detail_shows_concentration(self):
        char = _warlock_with_spells("hex")
        result = cast_spell(char, "hex", self.engine, persist_slots=True)
        detail = format_spellcasting_detail(result.updated_character)
        hex_name = self.engine.get_entity("spell", "hex").get_name(
            "fr", self.engine.registry.manifest.default_locale
        )
        self.assertIn("Concentration", detail)
        self.assertIn(hex_name, detail)

    def test_format_spellcasting_detail_without_concentration(self):
        char = _warlock_with_spells("hex")
        detail = format_spellcasting_detail(char)
        self.assertNotIn("Concentration", detail)

    def test_perso_afficher_embed_shows_concentration(self):
        char = _warlock_with_spells("hex")
        result = cast_spell(char, "hex", self.engine, persist_slots=True)
        sheet = build_character_sheet(result.updated_character, self.engine)
        display = build_character_display(sheet, self.engine, locale="fr")
        incantation_fields = [
            f.value
            for f in display.embed.fields
            if f.name == "✨ Incantation"
        ]
        self.assertEqual(len(incantation_fields), 1)
        hex_name = self.engine.get_entity("spell", "hex").get_name(
            "fr", self.engine.registry.manifest.default_locale
        )
        self.assertIn("Concentration", incantation_fields[0])
        self.assertIn(hex_name, incantation_fields[0])

    def test_perso_afficher_embed_without_concentration(self):
        char = _warlock_with_spells("hex")
        sheet = build_character_sheet(char, self.engine)
        display = build_character_display(sheet, self.engine, locale="fr")
        incantation_fields = [
            f.value
            for f in display.embed.fields
            if f.name == "✨ Incantation"
        ]
        self.assertEqual(len(incantation_fields), 1)
        self.assertNotIn("Concentration", incantation_fields[0])


if __name__ == "__main__":
    unittest.main(verbosity=2)
