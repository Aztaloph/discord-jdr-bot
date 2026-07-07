# tests/unit/test_embed_fields.py
"""Limites embed Discord — découpage fields et garde-fous."""
from __future__ import annotations

import unittest

import discord

from interfaces.discord.formatters.embed_fields import (
    DISCORD_FIELD_VALUE_MAX,
    add_field_chunked,
    chunk_field_value,
    enforce_embed_limits,
)
from interfaces.discord.formatters.character_embed import build_character_display
from jdr_engine.domain.character.character_sheet import CharacterSheet


class TestChunkFieldValue(unittest.TestCase):
    def test_short_value_single_chunk(self):
        self.assertEqual(chunk_field_value("hello"), ["hello"])

    def test_splits_between_lines_not_mid_line(self):
        lines = [f"Ligne {i} — texte aptitudes de classe" for i in range(40)]
        value = "\n".join(lines)
        self.assertGreater(len(value), DISCORD_FIELD_VALUE_MAX)
        chunks = chunk_field_value(value)
        self.assertGreater(len(chunks), 1)
        for chunk in chunks:
            self.assertLessEqual(len(chunk), DISCORD_FIELD_VALUE_MAX)
            self.assertNotIn("\n\n\n", chunk)
        self.assertEqual("\n".join(chunks), value)

    def test_empty_value_placeholder(self):
        self.assertEqual(chunk_field_value(""), ["_—_"])


class TestAddFieldChunked(unittest.TestCase):
    def test_creates_suite_fields(self):
        embed = discord.Embed(title="Test")
        long_value = "\n".join(
            f"**Aptitude {i}** — description SRD 2014 détaillée." for i in range(50)
        )
        count = add_field_chunked(
            embed,
            name="⚔️ Aptitudes de classe",
            value=long_value,
        )
        self.assertGreater(count, 1)
        names = [f.name for f in embed.fields]
        self.assertIn("⚔️ Aptitudes de classe", names)
        self.assertTrue(any("(suite)" in n for n in names))
        for field in embed.fields:
            self.assertLessEqual(len(field.value), DISCORD_FIELD_VALUE_MAX)


class TestCharacterEmbedChunking(unittest.TestCase):
    def test_oversized_class_features_valid_embed(self):
        lines = tuple(
            f"**Aptitude {i}** — " + ("x" * 80) for i in range(30)
        )
        sheet = CharacterSheet(
            character_id="abc12345",
            name="LongPaladin",
            owner_id="1",
            ruleset_id="dnd5e",
            race_id="human",
            race_name="Humain",
            class_id="paladin",
            class_name="Paladin",
            level=3,
            ability_scores_base={"str": 10, "dex": 10, "con": 10, "int": 10, "wis": 10, "cha": 14},
            ability_scores={"str": 10, "dex": 10, "con": 10, "int": 10, "wis": 10, "cha": 14},
            ability_modifiers={"str": 0, "dex": 0, "con": 0, "int": 0, "wis": 0, "cha": 2},
            proficiency_bonus=2,
            hit_die="d10",
            hp_max=24,
            hp_current=24,
            ac=18,
            speed=30,
            class_features_lines=lines,
        )
        display = build_character_display(sheet, None, include_lore=False)
        embed = display.embed
        for field in embed.fields:
            self.assertLessEqual(len(field.value), DISCORD_FIELD_VALUE_MAX)
        aptitude_fields = [f for f in embed.fields if "Aptitudes" in f.name]
        self.assertGreaterEqual(len(aptitude_fields), 2)


class TestEnforceEmbedLimits(unittest.TestCase):
    def test_truncates_when_too_many_fields(self):
        embed = discord.Embed(title="T", description="D")
        for i in range(30):
            embed.add_field(name=f"F{i}", value="v", inline=False)
        enforce_embed_limits(embed)
        self.assertLessEqual(len(embed.fields), 25)


if __name__ == "__main__":
    unittest.main(verbosity=2)
