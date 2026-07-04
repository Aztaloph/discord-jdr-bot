# interfaces/discord/handlers/mj_delete.py
"""Suppression de personnage par le MJ — /perso-supprimer."""
from __future__ import annotations

import discord
from discord import app_commands

from jdr_engine.application.character_service import CharacterNotFoundError

from interfaces.discord.container import DiscordJdrContext
from interfaces.discord.formatters.character_embed import COULEUR_ERREUR, COULEUR_INFO, COULEUR_SUCCES
from interfaces.discord.permissions.mj import require_mj_role, user_has_mj_role

FOOTER = "JDR Bot — D&D 5e SRD 2014"


class MjConfirmDeleteView(discord.ui.View):
    def __init__(
        self,
        ctx: DiscordJdrContext,
        mj_user_id: int,
        character_id: str,
        character_name: str,
        guild_id: str,
    ):
        super().__init__(timeout=60)
        self.ctx = ctx
        self.mj_user_id = mj_user_id
        self.character_id = character_id
        self.character_name = character_name
        self.guild_id = guild_id

    @discord.ui.button(label="Confirmer la suppression", style=discord.ButtonStyle.danger)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.mj_user_id or not user_has_mj_role(
            interaction.user if isinstance(interaction.user, discord.Member) else None
        ):
            await interaction.response.send_message("Action réservée au MJ.", ephemeral=True)
            return
        assert self.ctx.character_service
        try:
            self.ctx.character_service.delete_on_guild(self.character_id, self.guild_id)
            embed = discord.Embed(
                title="✅ Personnage supprimé",
                description=(
                    f"**{self.character_name}** (`{self.character_id}`) "
                    f"a été supprimé définitivement de ce serveur."
                ),
                color=COULEUR_SUCCES,
            )
        except CharacterNotFoundError:
            embed = discord.Embed(
                title="❌ Erreur",
                description="Personnage introuvable sur ce serveur.",
                color=COULEUR_ERREUR,
            )
        embed.set_footer(text=FOOTER)
        await interaction.response.edit_message(embed=embed, view=None)

    @discord.ui.button(label="Annuler", style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.mj_user_id:
            await interaction.response.send_message("Action réservée au MJ.", ephemeral=True)
            return
        embed = discord.Embed(
            title="ℹ️ Suppression annulée",
            description=f"**{self.character_name}** n'a pas été supprimé.",
            color=COULEUR_INFO,
        )
        embed.set_footer(text=FOOTER)
        await interaction.response.edit_message(embed=embed, view=None)


async def guild_character_autocomplete(
    interaction: discord.Interaction,
    current: str,
    ctx: DiscordJdrContext,
) -> list[app_commands.Choice[str]]:
    if not ctx.character_service or interaction.guild is None:
        return []

    guild_id = str(interaction.guild.id)
    characters = ctx.character_service.list_by_guild(guild_id)
    choices: list[app_commands.Choice[str]] = []
    current_lower = current.lower()
    for character in characters:
        label = f"{character.name} ({character.id})"
        if (
            current_lower in character.name.lower()
            or current_lower in character.id.lower()
        ):
            choices.append(app_commands.Choice(name=label, value=character.id))
        if len(choices) >= 25:
            break
    return choices


async def mj_perso_supprimer(
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

    assert ctx.character_service
    guild_id = str(interaction.guild.id)
    character_id = personnage.strip()

    try:
        character = ctx.character_service.get_on_guild(character_id, guild_id)
    except CharacterNotFoundError:
        await interaction.response.send_message(
            embed=discord.Embed(
                title="❌ Personnage introuvable",
                description=(
                    f"Aucun personnage avec l'identifiant **`{character_id}`** "
                    f"sur ce serveur.\n"
                    "Utilisez `/perso-liste` pour voir les identifiants disponibles."
                ),
                color=COULEUR_ERREUR,
            ).set_footer(text=FOOTER),
            ephemeral=True,
        )
        return

    embed = discord.Embed(
        title="⚠️ Confirmation requise (MJ)",
        description=(
            f"Supprimer le personnage **{character.name}** "
            f"(id : `{character.id}`) sur ce serveur ?\n"
            "Cette action est **irréversible**."
        ),
        color=COULEUR_ERREUR,
    )
    embed.set_footer(text=FOOTER)
    view = MjConfirmDeleteView(
        ctx,
        mj_user_id=interaction.user.id,
        character_id=character.id,
        character_name=character.name,
        guild_id=guild_id,
    )
    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
