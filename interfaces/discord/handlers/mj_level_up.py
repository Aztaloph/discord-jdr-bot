# interfaces/discord/handlers/mj_level_up.py
"""Montée de niveau — commande MJ (/monter-niveau)."""
from __future__ import annotations

import discord

from jdr_engine.application.character_service import CharacterNotFoundError
from jdr_engine.rules.character_progression import LevelUpError, LevelUpPendingChoice

from interfaces.discord.container import DiscordJdrContext
from interfaces.discord.formatters.character_embed import (
    COULEUR_ERREUR,
    COULEUR_SUCCES,
)
from interfaces.discord.permissions.mj import require_mj_role
from interfaces.discord.views.level_up_choice import LevelUpChoiceView, _pending_embed

FOOTER = "JDR Bot — D&D 5e SRD 2014"


def build_level_up_embed(result) -> discord.Embed:
    embed = discord.Embed(
        title=f"⬆️ Montée de niveau — {result.character_name}",
        description=(
            f"**Niveau** : {result.old_level} → **{result.new_level}**\n"
            f"**PV** : {result.hp_before}/{result.hp_max_before} → "
            f"**{result.hp_after}/{result.hp_max_after}** (+{result.hp_gain})\n"
            f"**Dés de vie** : {result.hit_dice_before} → **{result.hit_dice_after}** "
            f"(total)\n"
            f"**Emplacements max** : {result.slots_max_before} → "
            f"**{result.slots_max_after}**"
        ),
        color=COULEUR_SUCCES,
    )
    embed.set_footer(text=FOOTER)
    return embed


async def mj_monter_niveau(
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
    character_ref = personnage.strip()

    try:
        ctx.character_service.get_on_guild(character_ref, guild_id)
    except CharacterNotFoundError:
        await interaction.edit_original_response(
            embed=discord.Embed(
                title="❌ Personnage introuvable",
                description=(
                    f"Aucun personnage **`{character_ref}`** sur ce serveur.\n"
                    "Utilisez l'autocomplétion ou `/perso-liste`."
                ),
                color=COULEUR_ERREUR,
            ).set_footer(text=FOOTER),
        )
        return

    try:
        result = ctx.character_service.level_up_on_guild(character_ref, guild_id)
    except LevelUpPendingChoice as exc:
        await interaction.edit_original_response(
            embed=_pending_embed(exc.pending),
            view=LevelUpChoiceView(
                exc.pending,
                ctx.rule_engine,
                ctx.character_service,
                guild_id,
                character_ref,
            ),
        )
        return
    except LevelUpError as exc:
        await interaction.edit_original_response(
            embed=discord.Embed(
                title="⚠️ Montée de niveau impossible",
                description=str(exc),
                color=COULEUR_ERREUR,
            ).set_footer(text=FOOTER),
        )
        return

    await interaction.edit_original_response(embed=build_level_up_embed(result))
