# bot/cogs/spell.py
"""Cog Discord — commande slash /sort (Magicien & Clerc)."""
from __future__ import annotations

import logging

import discord
from discord import app_commands
from discord.ext import commands

from jdr_engine.dice import DiceError
from interfaces.discord.handlers.character import character_name_autocomplete
from interfaces.discord.handlers.prepare_spells import player_preparer_sorts
from interfaces.discord.handlers.spell import (
    SpellDisplay,
    build_sort_autocomplete_choices,
    execute_spell_cast,
)

log = logging.getLogger(__name__)

COLOR_SPELL = discord.Color(0x9B59B6)
COLOR_ERROR = discord.Color(0xF44336)


def _build_spell_embed(display: SpellDisplay) -> discord.Embed:
    level_label = (
        "Tour de magie" if display.spell_level == 0 else f"Sort niv. {display.spell_level}"
    )
    embed = discord.Embed(
        title=f"✨ {display.spell_name} — {display.character_name}",
        color=COLOR_SPELL,
    )
    embed.description = (
        f"**{level_label}** · {display.school}\n"
        f"⏱ {display.casting_time} · 📏 {display.range_text} · ⌛ {display.duration}"
    )
    if display.display_lines:
        embed.add_field(
            name="✨ Incantation",
            value="\n".join(f"• {line}" for line in display.display_lines),
            inline=False,
        )
    embed.set_footer(text="JDR Bot — D&D 5e SRD 2014 · Lanceur de sorts")
    return embed


def _build_error_embed(message: str) -> discord.Embed:
    return discord.Embed(
        title="❌ Erreur d'incantation",
        description=message,
        color=COLOR_ERROR,
    )


class SpellCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        log.info("SpellCog initialisé.")

    async def _perso_autocomplete(
        self,
        interaction: discord.Interaction,
        current: str,
    ) -> list[app_commands.Choice[str]]:
        ctx = getattr(self.bot, "jdr", None)
        if ctx is None or not ctx.use_engine_v2:
            return []
        return await character_name_autocomplete(interaction, current, ctx)

    async def _sort_autocomplete(
        self,
        interaction: discord.Interaction,
        current: str,
    ) -> list[app_commands.Choice[str]]:
        ctx = getattr(self.bot, "jdr", None)
        if ctx is None or not ctx.use_engine_v2:
            return []
        perso_value = getattr(interaction.namespace, "perso", None)
        guild_id = str(interaction.guild.id) if interaction.guild else None
        return build_sort_autocomplete_choices(
            ctx,
            owner_id=interaction.user.id,
            perso=perso_value,
            guild_id=guild_id,
            current=current,
        )

    @app_commands.command(
        name="sort",
        description="Lance un sort du personnage actif (lanceurs SRD, niv. 1–3)",
    )
    @app_commands.describe(
        perso="Personnage (optionnel — utilise le perso actif par défaut)",
        sort="Identifiant du sort (ex. fire_bolt, sacred_flame)",
    )
    @app_commands.autocomplete(perso=_perso_autocomplete, sort=_sort_autocomplete)
    async def sort_cmd(
        self,
        interaction: discord.Interaction,
        sort: str,
        perso: str | None = None,
    ):
        await interaction.response.defer(thinking=True)
        ctx = self.bot.jdr  # type: ignore[attr-defined]
        guild_id = str(interaction.guild.id) if interaction.guild else None
        try:
            display = execute_spell_cast(
                ctx,
                owner_id=interaction.user.id,
                perso=perso,
                spell_id=sort.strip().lower(),
                guild_id=guild_id,
            )
        except DiceError as exc:
            await interaction.followup.send(embed=_build_error_embed(str(exc)), ephemeral=True)
            return
        await interaction.followup.send(embed=_build_spell_embed(display))


    @app_commands.command(
        name="preparer-sorts",
        description="Re-choisir vos sorts préparés (après repos long — clerc, druide, paladin)",
    )
    async def preparer_sorts_cmd(self, interaction: discord.Interaction):
        ctx = getattr(self.bot, "jdr", None)
        if ctx is None or not ctx.use_engine_v2:
            await interaction.response.send_message(
                "Moteur v2 requis.", ephemeral=True
            )
            return
        await player_preparer_sorts(interaction, ctx)


async def setup(bot: commands.Bot):
    await bot.add_cog(SpellCog(bot))
