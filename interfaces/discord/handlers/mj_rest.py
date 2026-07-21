# interfaces/discord/handlers/mj_rest.py
"""Repos long / court — commandes MJ (/repos-long, /repos-court)."""
from __future__ import annotations

import discord

from jdr_engine.application.character_service import CharacterNotFoundError
from jdr_engine.rules.rest import RestError

from interfaces.discord.container import DiscordJdrContext
from interfaces.discord.formatters.character_embed import (
    COULEUR_ERREUR,
    COULEUR_INFO,
    COULEUR_PRINCIPALE,
    COULEUR_SUCCES,
)
from interfaces.discord.handlers.mj_delete import guild_character_autocomplete
from interfaces.discord.permissions.mj import require_mj_role

FOOTER = "JDR Bot — D&D 5e SRD 2014"


def build_long_rest_embed(result) -> discord.Embed:
    description = (
        f"**PV** : {result.hp_before} → **{result.hp_after}** / {result.hp_after}\n"
        f"**Dés de vie** : {result.hit_dice_before} → **{result.hit_dice_after}** "
        f"(+{result.hit_dice_regained})\n"
        f"**Emplacements de sorts** : {result.slots_text}"
    )
    if getattr(result, "prepared_rechoice_pending", False):
        description += (
            f"\n\n📘 **{result.character_name}** peut re-préparer ses sorts "
            f"via `/preparer-sorts`."
        )
    embed = discord.Embed(
        title=f"🌙 Repos long — {result.character_name}",
        description=description,
        color=COULEUR_SUCCES,
    )
    embed.set_footer(text=FOOTER)
    return embed


def build_short_rest_embed(result) -> discord.Embed:
    lines = [
        f"**PV** : {result.hp_before} → **{result.hp_after}**",
        f"**Dés dépensés** : {result.dice_spent} · **Restants** : {result.hit_dice_remaining}",
    ]
    if result.rolls:
        lines.append("**Jets de récupération** :")
        lines.extend(f"• {roll.label}" for roll in result.rolls)
    elif result.dice_spent == 0:
        lines.append("_Aucun dé de vie dépensé — repos court sans soin._")

    embed = discord.Embed(
        title=f"☕ Repos court — {result.character_name}",
        description="\n".join(lines),
        color=COULEUR_INFO,
    )
    embed.set_footer(text=FOOTER)
    return embed


async def mj_repos_long(
    interaction: discord.Interaction,
    ctx: DiscordJdrContext,
    personnage: str,
) -> None:
    if not await require_mj_role(interaction):
        return
    if interaction.guild is None:
        await interaction.response.send_message(
            embed=discord.Embed(
                title="❌ Serveur requis",
                description="Cette commande doit être utilisée sur un serveur.",
                color=COULEUR_ERREUR,
            ).set_footer(text=FOOTER),
            ephemeral=True,
        )
        return

    await interaction.response.defer(ephemeral=True)
    assert ctx.character_service
    guild_id = str(interaction.guild.id)

    try:
        ctx.character_service.get_on_guild(personnage.strip(), guild_id)
    except CharacterNotFoundError:
        await interaction.edit_original_response(
            embed=discord.Embed(
                title="❌ Personnage introuvable",
                description=(
                    f"Aucun personnage **`{personnage.strip()}`** sur ce serveur."
                ),
                color=COULEUR_ERREUR,
            ).set_footer(text=FOOTER),
        )
        return

    try:
        result = ctx.character_service.long_rest_on_guild(personnage.strip(), guild_id)
    except RestError as exc:
        await interaction.edit_original_response(
            embed=discord.Embed(
                title="⚠️ Repos long impossible",
                description=str(exc),
                color=COULEUR_ERREUR,
            ).set_footer(text=FOOTER),
        )
        return

    await interaction.edit_original_response(embed=build_long_rest_embed(result))


async def mj_repos_court(
    interaction: discord.Interaction,
    ctx: DiscordJdrContext,
    personnage: str,
    des: int = 1,
) -> None:
    if not await require_mj_role(interaction):
        return
    if interaction.guild is None:
        await interaction.response.send_message(
            embed=discord.Embed(
                title="❌ Serveur requis",
                description="Cette commande doit être utilisée sur un serveur.",
                color=COULEUR_ERREUR,
            ).set_footer(text=FOOTER),
            ephemeral=True,
        )
        return

    await interaction.response.defer(ephemeral=True)
    assert ctx.character_service
    guild_id = str(interaction.guild.id)

    try:
        ctx.character_service.get_on_guild(personnage.strip(), guild_id)
    except CharacterNotFoundError:
        await interaction.edit_original_response(
            embed=discord.Embed(
                title="❌ Personnage introuvable",
                description=(
                    f"Aucun personnage **`{personnage.strip()}`** sur ce serveur."
                ),
                color=COULEUR_ERREUR,
            ).set_footer(text=FOOTER),
        )
        return

    try:
        result = ctx.character_service.short_rest_on_guild(
            personnage.strip(), guild_id, max(0, des)
        )
    except RestError as exc:
        await interaction.edit_original_response(
            embed=discord.Embed(
                title="⚠️ Repos court impossible",
                description=str(exc),
                color=COULEUR_ERREUR,
            ).set_footer(text=FOOTER),
        )
        return

    await interaction.edit_original_response(embed=build_short_rest_embed(result))
