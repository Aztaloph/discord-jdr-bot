# tests/unit/test_cog_loading.py
"""Vérifie que tous les cogs Discord se chargent (signatures autocomplete, etc.)."""
from __future__ import annotations

import asyncio
import logging
import unittest

import discord
from discord.ext import commands

from interfaces.discord.startup import init_discord_jdr
from main import COGS


class TestCogLoading(unittest.TestCase):
    def test_all_cogs_load_without_error(self):
        asyncio.run(self._load_all_cogs())

    async def _load_all_cogs(self) -> None:
        intents = discord.Intents.default()
        bot = commands.Bot(command_prefix="!", intents=intents)
        bot.jdr = init_discord_jdr({})

        loaded: list[str] = []
        for cog_path in COGS:
            await bot.load_extension(cog_path)
            loaded.append(cog_path)

        self.assertEqual(loaded, list(COGS))
        self.assertIn("bot.cogs.spell", loaded)
        self.assertIn("bot.cogs.rest", loaded)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    unittest.main(verbosity=2)
