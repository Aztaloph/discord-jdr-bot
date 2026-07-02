# interfaces/discord/handlers/character.py
"""Handlers v2 pour les commandes personnage Discord."""
from __future__ import annotations

import discord
from discord import app_commands

from jdr_engine.application.dto.character_commands import (
    DeleteCharacterCommand,
    GetCharacterQuery,
    GetCharacterSheetQuery,
    ListCharactersQuery,
)
from jdr_engine.application.character_service import CharacterNotFoundError

from interfaces.discord.container import DiscordJdrContext
from interfaces.discord.formatters.character_embed import (
    COULEUR_ERREUR,
    COULEUR_INFO,
    COULEUR_PRINCIPALE,
    COULEUR_SUCCES,
    build_character_display,
    list_entry_line,
)
from interfaces.discord.views.creation_wizard import start_creation_wizard


class ConfirmDeleteViewV2(discord.ui.View):
    def __init__(self, ctx: DiscordJdrContext, owner_id: int, character_id: str, name: str):
        super().__init__(timeout=60)
        self.ctx = ctx
        self.owner_id = owner_id
        self.character_id = character_id
        self.name = name

    @discord.ui.button(label="Confirmer la suppression", style=discord.ButtonStyle.danger)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("Action non autorisée.", ephemeral=True)
            return
        assert self.ctx.character_service
        try:
            self.ctx.character_service.delete(
                DeleteCharacterCommand(
                    character_id=self.character_id,
                    owner_id=str(self.owner_id),
                )
            )
            embed = discord.Embed(
                title="✅ Personnage supprimé",
                description=f"**{self.name}** a été supprimé.",
                color=COULEUR_SUCCES,
            )
        except CharacterNotFoundError:
            embed = discord.Embed(
                title="❌ Erreur",
                description="Personnage introuvable.",
                color=COULEUR_ERREUR,
            )
        await interaction.response.edit_message(embed=embed, view=None)

    @discord.ui.button(label="Annuler", style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("Action non autorisée.", ephemeral=True)
            return
        embed = discord.Embed(
            title="ℹ️ Suppression annulée",
            description=f"**{self.name}** n'a pas été supprimé.",
            color=COULEUR_INFO,
        )
        await interaction.response.edit_message(embed=embed, view=None)


async def perso_creer(interaction: discord.Interaction, ctx: DiscordJdrContext) -> None:
    await start_creation_wizard(interaction, ctx)


async def perso_liste(interaction: discord.Interaction, ctx: DiscordJdrContext) -> None:
    assert ctx.character_service
    sheets = ctx.character_service.list_sheets(
        ListCharactersQuery(owner_id=str(interaction.user.id)),
        locale=ctx.locale,
    )
    if not sheets:
        embed = discord.Embed(
            title="📋 Vos personnages",
            description="Vous n'avez pas encore de personnage.\nUtilisez `/perso-creer` !",
            color=COULEUR_INFO,
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return

    embed = discord.Embed(
        title=f"📋 Vos personnages ({len(sheets)})",
        color=COULEUR_PRINCIPALE,
    )
    for i, sheet in enumerate(sheets, 1):
        embed.add_field(
            name=f"{i}. {sheet.name}",
            value=list_entry_line(sheet),
            inline=False,
        )
    await interaction.response.send_message(embed=embed, ephemeral=True)


def _get_sheet_by_name(ctx: DiscordJdrContext, owner_id: int, nom: str):
    assert ctx.character_service
    return ctx.character_service.get_sheet(
        GetCharacterSheetQuery(
            name=nom,
            owner_id=str(owner_id),
            locale=ctx.locale,
        )
    )


async def perso_afficher(interaction: discord.Interaction, ctx: DiscordJdrContext, nom: str) -> None:
    try:
        sheet = _get_sheet_by_name(ctx, interaction.user.id, nom)
    except CharacterNotFoundError:
        embed = discord.Embed(
            title="❌ Personnage introuvable",
            description=f"Aucun personnage nommé « {nom} » trouvé.",
            color=COULEUR_ERREUR,
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return
    display = build_character_display(
        sheet, ctx.rule_engine, locale=ctx.locale
    )
    if display.files:
        await interaction.response.send_message(
            embed=display.embed, files=display.files
        )
    else:
        await interaction.response.send_message(embed=display.embed)


async def perso_mp(interaction: discord.Interaction, ctx: DiscordJdrContext, nom: str) -> None:
    try:
        sheet = _get_sheet_by_name(ctx, interaction.user.id, nom)
    except CharacterNotFoundError:
        await interaction.response.send_message(
            embed=discord.Embed(
                title="❌ Personnage introuvable",
                description=f"Aucun personnage nommé « {nom} » trouvé.",
                color=COULEUR_ERREUR,
            ),
            ephemeral=True,
        )
        return

    try:
        display = build_character_display(
            sheet, ctx.rule_engine, locale=ctx.locale
        )
        if display.files:
            await interaction.user.send(embed=display.embed, files=display.files)
        else:
            await interaction.user.send(embed=display.embed)
        await interaction.response.send_message(
            embed=discord.Embed(
                title="✅ Fiche envoyée",
                description=f"La fiche de **{sheet.name}** vous a été envoyée par MP.",
                color=COULEUR_SUCCES,
            ),
            ephemeral=True,
        )
    except discord.Forbidden:
        await interaction.response.send_message(
            embed=discord.Embed(
                title="❌ MP désactivés",
                description="Autorisez les MP ou utilisez `/perso-afficher`.",
                color=COULEUR_ERREUR,
            ),
            ephemeral=True,
        )


async def perso_supprimer(interaction: discord.Interaction, ctx: DiscordJdrContext, nom: str) -> None:
    assert ctx.character_service
    try:
        char = ctx.character_service.get(
            GetCharacterQuery(name=nom, owner_id=str(interaction.user.id))
        )
    except CharacterNotFoundError:
        await interaction.response.send_message(
            embed=discord.Embed(
                title="❌ Personnage introuvable",
                description=f"Aucun personnage nommé « {nom} » trouvé.",
                color=COULEUR_ERREUR,
            ),
            ephemeral=True,
        )
        return

    embed = discord.Embed(
        title="⚠️ Confirmation requise",
        description=f"Supprimer **{char.name}** ? Irréversible.",
        color=COULEUR_ERREUR,
    )
    view = ConfirmDeleteViewV2(ctx, interaction.user.id, char.id, char.name)
    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


async def character_name_autocomplete(
    interaction: discord.Interaction,
    current: str,
    ctx: DiscordJdrContext,
) -> list[app_commands.Choice[str]]:
    if not ctx.character_service:
        return []

    sheets = ctx.character_service.list_sheets(
        ListCharactersQuery(owner_id=str(interaction.user.id)),
        locale=ctx.locale,
    )
    choices = []
    current_lower = current.lower()
    for sheet in sheets:
        if current_lower in sheet.name.lower():
            choices.append(app_commands.Choice(name=sheet.name, value=sheet.name))
        if len(choices) >= 25:
            break
    return choices
