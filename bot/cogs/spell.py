# bot/cogs/spell.py
"""Cog Discord — commande slash /sort (Magicien & Clerc)."""
from __future__ import annotations

import logging

import discord
from discord import app_commands
from discord.ext import commands

from jdr_engine.dice import DiceError
from interfaces.discord.handlers.character import character_name_autocomplete
from interfaces.discord.handlers.spell import (
    SpellDisplay,
    build_spell_autocomplete_choices,
    execute_spell_cast,
    resolve_character_for_spell,
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
        if ctx is None or not ctx.use_engine_v2 or ctx.rule_engine is None:
            return []
        class_id: str | None = None
        perso_value = getattr(interaction.namespace, "perso", None)
        if perso_value:
            try:
                character = resolve_character_for_spell(
                    ctx, interaction.user.id, str(perso_value)
                )
                class_id = character.class_id
            except DiceError:
                pass
        return build_spell_autocomplete_choices(
            ctx.rule_engine,
            current,
            locale=ctx.locale,
            class_id=class_id,
        )

    @app_commands.command(
        name="sort",
        description="Lance un sort (Magicien ou Clerc niv. 1-3, SRD 2014)",
    )
    @app_commands.describe(
        perso="Nom de votre personnage lanceur de sorts",
        sort="Identifiant du sort (ex. fire_bolt, sacred_flame)",
    )
    @app_commands.autocomplete(perso=_perso_autocomplete, sort=_sort_autocomplete)
    async def sort_cmd(
        self,
        interaction: discord.Interaction,
        perso: str,
        sort: str,
    ):
        await interaction.response.defer(thinking=True)
        ctx = self.bot.jdr  # type: ignore[attr-defined]
        try:
            display = execute_spell_cast(
                ctx,
                owner_id=interaction.user.id,
                perso=perso,
                spell_id=sort.strip().lower(),
            )
        except DiceError as exc:
            await interaction.followup.send(embed=_build_error_embed(str(exc)), ephemeral=True)
            return
        await interaction.followup.send(embed=_build_spell_embed(display))


async def setup(bot: commands.Bot):
    await bot.add_cog(SpellCog(bot))
