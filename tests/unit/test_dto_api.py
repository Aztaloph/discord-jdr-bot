# tests/unit/test_dto_api.py
"""Lot DTO/API — conversions DTO de sortie + endpoints HTTP (interfaces/api)."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from jdr_engine.application.dto.output_serializers import (
    character_sheet_to_dict,
    long_rest_result_to_dict,
    short_rest_result_to_dict,
    spell_cast_result_to_dict,
)
from jdr_engine.domain.character.ability_scores import AbilityScores
from jdr_engine.domain.character.character import Character
from jdr_engine.persistence.database import init_database
from jdr_engine.persistence.sqlite_character_repository import (
    SqliteCharacterRepository,
)
from jdr_engine.rules import RuleEngine
from jdr_engine.rules.calculator import build_character_sheet
from jdr_engine.rules.rest import apply_long_rest, apply_short_rest
from jdr_engine.rules.spellcasting.cast import cast_spell
from jdr_engine.rules.spellcasting.state import get_slots_used, get_spellcasting_state

from interfaces.api.app import create_app

_ENGINE: RuleEngine | None = None


def _get_engine() -> RuleEngine:
    global _ENGINE
    if _ENGINE is None:
        if not Path("compendium/dnd5e").is_dir():
            raise unittest.SkipTest("compendium absent")
        _ENGINE = RuleEngine.load("dnd5e", validate=True, strict=True)
    return _ENGINE


class SequenceRng:
    def __init__(self, values: list[int]):
        self._values = list(values)
        self._index = 0

    def __call__(self, low: int, high: int) -> int:
        value = self._values[self._index]
        self._index += 1
        return value


def _scores(main_ability: str) -> AbilityScores:
    scores = dict.fromkeys(("str", "dex", "con", "int", "wis", "cha"), 10)
    scores[main_ability] = 16
    return AbilityScores(scores=scores)


def _tiefling_warlock(level: int = 3) -> Character:
    return Character(
        owner_id="1",
        name="Occultiste",
        race_id="tiefling",
        class_id="warlock",
        level=level,
        ability_scores=_scores("cha"),
        hp_current=10,
        choices={
            "spellcasting": {
                "cantrips_known": ["eldritch_blast"],
                "spells_known": ["hex"],
                "slots_used": {},
            }
        },
    )


def _cleric(level: int = 3) -> Character:
    return Character(
        owner_id="1",
        name="Clerc",
        race_id="human",
        class_id="cleric",
        level=level,
        ability_scores=_scores("wis"),
        hp_current=12,
        choices={
            "skills": ["medicine", "religion"],
            "spellcasting": {
                "cantrips_known": ["guidance"],
                "spells_prepared": ["cure_wounds"],
                "domain_spells": ["bless"],
                "slots_used": {},
            },
        },
    )


def _sorcerer(level: int = 3) -> Character:
    return Character(
        owner_id="1",
        name="Ensorceleur",
        race_id="human",
        class_id="sorcerer",
        level=level,
        ability_scores=_scores("cha"),
        hp_current=15,
        choices={
            "metamagic_options": ["quickened"],
            "spellcasting": {
                "cantrips_known": ["fire_bolt"],
                "spells_known": ["magic_missile"],
                "slots_used": {},
            },
        },
    )


def _fighter(level: int = 2) -> Character:
    return Character(
        owner_id="1",
        name="Guerrier",
        race_id="human",
        class_id="fighter",
        level=level,
        ability_scores=_scores("str"),
        hp_current=15,
        choices={},
    )


class TestCharacterSheetDto(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.engine = _get_engine()

    def test_sheet_dto_is_json_serializable(self):
        sheet = build_character_sheet(_cleric(), self.engine)
        data = character_sheet_to_dict(sheet)
        reloaded = json.loads(json.dumps(data))
        self.assertEqual(reloaded["name"], "Clerc")

    def test_sheet_dto_excludes_display_fields(self):
        sheet = build_character_sheet(_tiefling_warlock(), self.engine)
        data = character_sheet_to_dict(sheet)
        for excluded in (
            "proficient_skill_labels",
            "armor_proficiencies_text",
            "weapon_proficiencies_text",
            "spellcasting_summary",
            "class_features_lines",
            "innate_spells_text",
            "trait_ids",
            "class_display",
            "hit_dice_display",
        ):
            self.assertNotIn(excluded, data)

    def test_sheet_dto_saving_throws_structured(self):
        sheet = build_character_sheet(_cleric(), self.engine)
        data = character_sheet_to_dict(sheet)
        entries = {e["ability_id"]: e for e in data["saving_throws"]}
        self.assertEqual(len(entries), 6)
        # Clerc SRD : maîtrise SAG + CHA.
        self.assertTrue(entries["wis"]["proficient"])
        self.assertTrue(entries["cha"]["proficient"])
        self.assertFalse(entries["str"]["proficient"])
        # mod SAG +3 + maîtrise +2 = +5.
        self.assertEqual(entries["wis"]["modifier"], 5)
        self.assertIsInstance(entries["str"]["modifier"], int)

    def test_sheet_dto_proficiencies_are_ids(self):
        sheet = build_character_sheet(_cleric(), self.engine)
        data = character_sheet_to_dict(sheet)
        self.assertIn("medicine", data["proficient_skill_ids"])
        self.assertIn("religion", data["proficient_skill_ids"])
        self.assertIn("light", data["armor_proficiencies"])
        self.assertIn("simple", data["weapon_proficiencies"])

    def test_sheet_dto_spellcasting_block(self):
        char = _cleric()
        result = cast_spell(char, "bless", self.engine, persist_slots=True)
        sheet = build_character_sheet(result.updated_character, self.engine)
        data = character_sheet_to_dict(sheet)
        block = data["spellcasting"]
        self.assertEqual(block["ability"], "wis")
        self.assertFalse(block["pact_magic"])
        self.assertEqual(block["cantrips_known"], ["guidance"])
        self.assertEqual(block["spells_prepared"], ["cure_wounds"])
        self.assertEqual(block["domain_spells"], ["bless"])
        self.assertIn("1", block["slots_max"])
        self.assertEqual(
            block["slots_remaining"]["1"], block["slots_max"]["1"] - 1
        )
        self.assertEqual(block["concentration"]["spell_id"], "bless")

    def test_sheet_dto_warlock_pact_magic(self):
        sheet = build_character_sheet(_tiefling_warlock(), self.engine)
        block = character_sheet_to_dict(sheet)["spellcasting"]
        self.assertTrue(block["pact_magic"])
        self.assertEqual(block["ability"], "cha")
        self.assertIsNone(block["concentration"])

    def test_sheet_dto_innate_spells_tiefling(self):
        sheet = build_character_sheet(_tiefling_warlock(level=3), self.engine)
        data = character_sheet_to_dict(sheet)
        by_id = {e["spell_id"]: e for e in data["innate_spells"]}
        self.assertEqual(by_id["thaumaturgy"]["usage"], "at_will")
        self.assertEqual(by_id["hellish_rebuke"]["usage"], "one_per_long_rest")
        self.assertEqual(by_id["hellish_rebuke"]["min_level"], 3)
        # Niveau 3 : darkness (niv. 5+) pas encore accessible.
        self.assertNotIn("darkness", by_id)

    def test_sheet_dto_class_features_ids_and_names(self):
        sheet = build_character_sheet(_fighter(), self.engine)
        data = character_sheet_to_dict(sheet)
        feature_ids = [f["feature_id"] for f in data["class_features"]]
        self.assertIn("second_wind", feature_ids)
        self.assertIn("action_surge", feature_ids)
        for feature in data["class_features"]:
            self.assertTrue(feature["name"])

    def test_sheet_dto_non_caster(self):
        sheet = build_character_sheet(_fighter(), self.engine)
        data = character_sheet_to_dict(sheet)
        self.assertIsNone(data["spellcasting"])
        self.assertEqual(data["innate_spells"], [])
        self.assertEqual(data["damage_resistances"], [])

    def test_sheet_dto_damage_resistances_are_ids(self):
        sheet = build_character_sheet(_tiefling_warlock(), self.engine)
        data = character_sheet_to_dict(sheet)
        self.assertEqual(data["damage_resistances"], ["fire"])


class TestSpellCastResultDto(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.engine = _get_engine()

    def test_cast_dto_excludes_display_and_persistence_fields(self):
        char = _tiefling_warlock()
        result = cast_spell(char, "hex", self.engine, persist_slots=True)
        data = spell_cast_result_to_dict(result)
        self.assertNotIn("display_lines", data)
        self.assertNotIn("updated_character", data)
        json.dumps(data)

    def test_cast_dto_attack_roll_nested_d20(self):
        char = _sorcerer()
        rng = SequenceRng([12, 5])  # d20 puis 1d10 de dégâts
        result = cast_spell(
            char, "fire_bolt", self.engine, persist_slots=True, rng=rng
        )
        data = spell_cast_result_to_dict(result)
        atk = data["attack_rolls"][0]
        self.assertEqual(atk["d20"]["kept_value"], 12)
        self.assertEqual(atk["d20"]["mode"], "normal")
        self.assertNotIn("modifier_breakdown", atk["d20"])
        self.assertEqual(atk["d20"]["request"]["roll_type"], "attack")
        self.assertEqual(atk["damage_rolls"], [5])
        json.dumps(data)

    def test_cast_dto_metamagic_options_structured(self):
        char = _sorcerer()
        rng = SequenceRng([12, 5])
        result = cast_spell(
            char, "fire_bolt", self.engine, persist_slots=True, rng=rng
        )
        data = spell_cast_result_to_dict(result)
        self.assertEqual(len(data["metamagic_options"]), 1)
        option = data["metamagic_options"][0]
        self.assertEqual(option["metamagic_id"], "quickened")
        self.assertIsInstance(option["cost"], int)
        self.assertGreater(option["cost"], 0)

    def test_cast_dto_healing_fields(self):
        char = _cleric()
        char.hp_current = 5
        rng = SequenceRng([4])  # 1d8 de soins
        result = cast_spell(
            char, "cure_wounds", self.engine, persist_slots=True, rng=rng
        )
        data = spell_cast_result_to_dict(result)
        self.assertEqual(data["hp_before"], 5)
        self.assertEqual(data["healing_total"], 4 + 3)  # 1d8 + mod SAG
        self.assertEqual(data["hp_after"], data["hp_before"] + data["healing_applied"])

    def test_cast_dto_slot_keys_are_strings(self):
        char = _tiefling_warlock()
        result = cast_spell(char, "hex", self.engine, persist_slots=True)
        data = spell_cast_result_to_dict(result)
        self.assertEqual(data["slots_max"], {"2": 2})
        self.assertEqual(data["slots_remaining"], {"2": 1})
        self.assertTrue(data["concentration"])


class TestRestResultDto(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.engine = _get_engine()

    def test_short_rest_dto(self):
        char = _fighter()
        char.hp_current = 5
        updated, result = apply_short_rest(
            char, self.engine, 2, rng=SequenceRng([3, 6])
        )
        data = short_rest_result_to_dict(result)
        self.assertEqual(data["dice_spent"], 2)
        self.assertEqual(
            data["rolls"],
            [
                {"faces": 10, "con_modifier": 0, "roll_value": 3, "healing": 3},
                {"faces": 10, "con_modifier": 0, "roll_value": 6, "healing": 6},
            ],
        )
        for roll in data["rolls"]:
            self.assertNotIn("label", roll)
        json.dumps(data)

    def test_long_rest_dto_structured_slots(self):
        char = _cleric()
        cast_spell(char, "bless", self.engine, persist_slots=True)
        updated, result = apply_long_rest(char, self.engine)
        data = long_rest_result_to_dict(result)
        self.assertNotIn("slots_text", data)
        self.assertEqual(data["slots_max"], data["slots_remaining"])
        self.assertIn("1", data["slots_max"])
        self.assertEqual(data["hp_after"], updated.hp_current)
        self.assertTrue(data["prepared_rechoice_pending"])
        json.dumps(data)


class TestApiEndpoints(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.engine = _get_engine()

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.db_path = Path(self._tmp.name) / "bot.db"
        init_database(self.db_path)
        self.repo = SqliteCharacterRepository(self.db_path)
        app = create_app(engine=self.engine, db_path=self.db_path)
        self.client = TestClient(app)

    def tearDown(self):
        self.client.close()
        self._tmp.cleanup()

    def _seed(self, character: Character, char_id: str) -> Character:
        character.id = char_id
        character.guild_id = "111"
        self.repo.save(character)
        return character

    # ── GET /characters/{id}/sheet ──

    def test_get_sheet_ok(self):
        self._seed(_tiefling_warlock(), "api001")
        response = self.client.get("/characters/api001/sheet")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["name"], "Occultiste")
        self.assertEqual(data["character_id"], "api001")
        self.assertTrue(data["spellcasting"]["pact_magic"])
        self.assertNotIn("spellcasting_summary", data)

    def test_get_sheet_unknown_character_404(self):
        response = self.client.get("/characters/inconnu/sheet")
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["detail"], "Personnage introuvable.")

    # ── POST /characters/{id}/cast ──

    def test_cast_ok_and_persisted_state_matches_response(self):
        self._seed(_tiefling_warlock(), "api002")
        response = self.client.post(
            "/characters/api002/cast", json={"spell_id": "hex"}
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["spell_id"], "hex")
        self.assertEqual(data["slots_remaining"], {"2": 1})
        # L'état persisté correspond à l'état retourné.
        reloaded = self.repo.get_by_id("api002")
        self.assertEqual(get_slots_used(reloaded), {2: 1})
        conc = get_spellcasting_state(reloaded).get("concentration")
        self.assertEqual(conc["spell_id"], "hex")

    def test_cast_unknown_spell_409(self):
        self._seed(_tiefling_warlock(), "api003")
        response = self.client.post(
            "/characters/api003/cast", json={"spell_id": "sort_inexistant"}
        )
        self.assertEqual(response.status_code, 409)
        self.assertIn("Sort inconnu", response.json()["detail"])

    def test_cast_no_slots_left_409(self):
        self._seed(_tiefling_warlock(), "api004")
        for _ in range(2):
            ok = self.client.post(
                "/characters/api004/cast", json={"spell_id": "hex"}
            )
            self.assertEqual(ok.status_code, 200)
        response = self.client.post(
            "/characters/api004/cast", json={"spell_id": "hex"}
        )
        self.assertEqual(response.status_code, 409)
        self.assertIn("emplacement", response.json()["detail"].lower())

    def test_cast_unknown_character_404(self):
        response = self.client.post(
            "/characters/inconnu/cast", json={"spell_id": "hex"}
        )
        self.assertEqual(response.status_code, 404)

    def test_cast_missing_spell_id_422(self):
        self._seed(_tiefling_warlock(), "api005")
        response = self.client.post("/characters/api005/cast", json={})
        self.assertEqual(response.status_code, 422)

    # ── POST /characters/{id}/short-rest ──

    def test_short_rest_ok_and_persisted(self):
        char = _fighter()
        char.hp_current = 5
        self._seed(char, "api006")
        response = self.client.post(
            "/characters/api006/short-rest", json={"dice_to_spend": 1}
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["dice_spent"], 1)
        self.assertEqual(data["hp_before"], 5)
        self.assertEqual(len(data["rolls"]), 1)
        reloaded = self.repo.get_by_id("api006")
        self.assertEqual(reloaded.hp_current, data["hp_after"])

    def test_short_rest_not_enough_dice_409(self):
        self._seed(_fighter(), "api007")
        response = self.client.post(
            "/characters/api007/short-rest", json={"dice_to_spend": 99}
        )
        self.assertEqual(response.status_code, 409)
        self.assertIn("Dés de vie insuffisants", response.json()["detail"])

    def test_short_rest_negative_dice_422(self):
        self._seed(_fighter(), "api008")
        response = self.client.post(
            "/characters/api008/short-rest", json={"dice_to_spend": -1}
        )
        self.assertEqual(response.status_code, 422)

    # ── POST /characters/{id}/long-rest ──

    def test_long_rest_ok_and_persisted(self):
        char = _tiefling_warlock()
        char.hp_current = 3
        self._seed(char, "api009")
        cast = self.client.post(
            "/characters/api009/cast", json={"spell_id": "hex"}
        )
        self.assertEqual(cast.status_code, 200)
        response = self.client.post("/characters/api009/long-rest")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["slots_remaining"], data["slots_max"])
        self.assertGreater(data["hp_after"], data["hp_before"])
        reloaded = self.repo.get_by_id("api009")
        self.assertEqual(reloaded.hp_current, data["hp_after"])
        self.assertEqual(get_slots_used(reloaded), {})
        self.assertNotIn(
            "concentration", get_spellcasting_state(reloaded)
        )

    def test_long_rest_unknown_character_404(self):
        response = self.client.post("/characters/inconnu/long-rest")
        self.assertEqual(response.status_code, 404)


if __name__ == "__main__":
    unittest.main(verbosity=2)
