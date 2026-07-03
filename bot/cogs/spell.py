# bot/cogs/spell.py
"""Cog Discord — commande slash /sort (Magicien Lot B)."""
from __future__ import annotations

import logging

import discord
from discord import app_commands
from discord.ext import commands

from jdr_engine.dice import DiceError
from interfaces.discord.handlers.character import character_name_autocomplete
from interfaces.discord.handlers.spell import (
    SpellDisplay,
    execute_spell_cast,
    list_available_spells,
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
    embed.set_footer(text="JDR Bot — D&D 5e SRD 2014 · Magicien")
    return embed


def _build_error_embed(message: str) -> discord.Embed:
    return discord.Embed(
        title="❌ Erreur d'incantation",
        description=message,
        color=COLOR_ERROR,
    )


async def spell_name_autocomplete(
    interaction: discord.Interaction,
    current: str,
) -> list[app_commands.Choice[str]]:
    ctx = interaction.client.jdr  # type: ignore[attr-defined]
    if not ctx.use_engine_v2 or ctx.character_service is None:
        return []
    perso_values = interaction.namespace.perso if hasattr(interaction.namespace, "perso") else None
    if not perso_values:
        return []
    try:
        character = resolve_character_for_spell(ctx, interaction.user.id, str(perso_values))
    except DiceError:
        return []
    spells = list_available_spells(character)
    current_lower = (current or "").lower()
    choices: list[app_commands.Choice[str]] = []
    engine = ctx.rule_engine
    for spell_id in spells:
        if current_lower and current_lower not in spell_id.replace("_", " "):
            if engine:
                name = engine.get_display_name("spell", spell_id, locale=ctx.locale)
                if not name or current_lower not in name.lower():
                    continue
        label = engine.get_display_name("spell", spell_id, locale=ctx.locale) if engine else spell_id
        choices.append(app_commands.Choice(name=label or spell_id, value=spell_id))
        if len(choices) >= 25:
            break
    return choices


class SpellCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        log.info("SpellCog initialisé.")

    @app_commands.command(
        name="sort",
        description="Lance un sort (Magicien niv. 1-3, SRD 2014)",
    )
    @app_commands.describe(
        perso="Nom de votre personnage magicien",
        sort="Identifiant du sort (ex. fire_bolt)",
    )
    @app_commands.autocomplete(perso=character_name_autocomplete, sort=spell_name_autocomplete)
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
