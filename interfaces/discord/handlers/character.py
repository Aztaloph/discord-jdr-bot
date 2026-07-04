# interfaces/discord/handlers/character.py
"""Handlers v2 pour les commandes personnage Discord."""
from __future__ import annotations

import discord
from discord import app_commands

from jdr_engine.application.dto.character_commands import (
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

FOOTER = "JDR Bot — D&D 5e SRD 2014"


def _guild_id(interaction: discord.Interaction) -> str | None:
    if interaction.guild is None:
        return None
    return str(interaction.guild.id)


async def perso_liste(interaction: discord.Interaction, ctx: DiscordJdrContext) -> None:
    assert ctx.character_service
    guild_id = _guild_id(interaction)
    query = ListCharactersQuery(
        owner_id=str(interaction.user.id),
        guild_id=guild_id,
    )
    sheets = ctx.character_service.list_sheets(query, locale=ctx.locale)
    if not sheets:
        embed = discord.Embed(
            title="📋 Vos personnages",
            description="Vous n'avez pas encore de personnage.\nUtilisez `/creer-perso` !",
            color=COULEUR_INFO,
        )
        embed.set_footer(text=FOOTER)
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return

    active_id: str | None = None
    if guild_id:
        active = ctx.character_service.get_active_character(
            str(interaction.user.id), guild_id
        )
        active_id = active.id if active else None

    embed = discord.Embed(
        title=f"📋 Vos personnages ({len(sheets)})",
        description=(
            "⭐ = personnage **actif** en jeu sur ce serveur.\n"
            "Utilisez `/perso-choisir` pour changer de personnage actif."
            if guild_id
            else None
        ),
        color=COULEUR_PRINCIPALE,
    )
    for i, sheet in enumerate(sheets, 1):
        prefix = "⭐ " if active_id and sheet.character_id == active_id else ""
        embed.add_field(
            name=f"{prefix}{i}. {sheet.name}",
            value=list_entry_line(sheet),
            inline=False,
        )
    embed.set_footer(text=FOOTER)
    await interaction.response.send_message(embed=embed, ephemeral=True)


def _get_sheet_by_name(ctx: DiscordJdrContext, owner_id: int, nom: str, guild_id: str | None):
    assert ctx.character_service
    if guild_id:
        character = ctx.character_service.resolve_owned_on_guild(
            str(owner_id), guild_id, nom
        )
        return ctx.character_service.get_sheet(
            GetCharacterSheetQuery(
                character_id=character.id,
                owner_id=str(owner_id),
                locale=ctx.locale,
            )
        )
    return ctx.character_service.get_sheet(
        GetCharacterSheetQuery(
            name=nom,
            owner_id=str(owner_id),
            locale=ctx.locale,
        )
    )


async def perso_afficher(
    interaction: discord.Interaction,
    ctx: DiscordJdrContext,
    nom: str | None = None,
) -> None:
    assert ctx.character_service
    guild_id = _guild_id(interaction)
    try:
        if nom:
            sheet = _get_sheet_by_name(ctx, interaction.user.id, nom, guild_id)
        elif guild_id:
            active = ctx.character_service.get_active_character(
                str(interaction.user.id), guild_id
            )
            if active is None:
                await interaction.response.send_message(
                    embed=discord.Embed(
                        title="ℹ️ Aucun personnage actif",
                        description=(
                            "Vous n'avez pas de personnage actif sur ce serveur.\n"
                            "Utilisez `/perso-choisir` ou `/creer-perso`."
                        ),
                        color=COULEUR_INFO,
                    ).set_footer(text=FOOTER),
                    ephemeral=True,
                )
                return
            sheet = ctx.character_service.get_sheet(
                GetCharacterSheetQuery(
                    character_id=active.id,
                    owner_id=str(interaction.user.id),
                    locale=ctx.locale,
                )
            )
        else:
            await interaction.response.send_message(
                embed=discord.Embed(
                    title="❌ Serveur requis",
                    description="Précisez un nom de personnage ou utilisez la commande sur un serveur.",
                    color=COULEUR_ERREUR,
                ).set_footer(text=FOOTER),
                ephemeral=True,
            )
            return
    except CharacterNotFoundError:
        embed = discord.Embed(
            title="❌ Personnage introuvable",
            description=f"Aucun personnage « {nom} » trouvé sur ce serveur.",
            color=COULEUR_ERREUR,
        )
        embed.set_footer(text=FOOTER)
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return

    await interaction.response.defer()

    display = build_character_display(sheet, ctx.rule_engine, locale=ctx.locale)
    showing_active = nom is None and guild_id is not None
    if showing_active:
        display.embed.description = (
            f"⭐ **Personnage actif** sur ce serveur\n\n{display.embed.description or ''}"
        )
    if display.files:
        await interaction.edit_original_response(
            embed=display.embed, attachments=display.files
        )
    else:
        await interaction.edit_original_response(embed=display.embed)


async def _send_character_display_dm(
    interaction: discord.Interaction,
    display,
    sheet_name: str,
) -> None:
    """Envoie la fiche en MP puis confirme (defer déjà fait)."""
    try:
        if display.files:
            await interaction.user.send(embed=display.embed, files=display.files)
        else:
            await interaction.user.send(embed=display.embed)
        await interaction.edit_original_response(
            embed=discord.Embed(
                title="✅ Fiche envoyée",
                description=f"La fiche de **{sheet_name}** vous a été envoyée par MP.",
                color=COULEUR_SUCCES,
            ).set_footer(text=FOOTER),
        )
    except discord.Forbidden:
        await interaction.edit_original_response(
            embed=discord.Embed(
                title="❌ MP désactivés",
                description="Autorisez les MP ou utilisez `/perso-afficher`.",
                color=COULEUR_ERREUR,
            ).set_footer(text=FOOTER),
        )


async def perso_choisir(
    interaction: discord.Interaction,
    ctx: DiscordJdrContext,
    personnage: str,
) -> None:
    assert ctx.character_service
    guild_id = _guild_id(interaction)
    if guild_id is None:
        await interaction.response.send_message(
            embed=discord.Embed(
                title="❌ Serveur requis",
                description="Choisissez votre personnage actif sur un serveur Discord.",
                color=COULEUR_ERREUR,
            ).set_footer(text=FOOTER),
            ephemeral=True,
        )
        return

    try:
        character = ctx.character_service.set_active_character(
            str(interaction.user.id), guild_id, personnage
        )
    except CharacterNotFoundError:
        await interaction.response.send_message(
            embed=discord.Embed(
                title="❌ Personnage introuvable",
                description=(
                    f"Aucun personnage « **{personnage}** » trouvé parmi les vôtres "
                    f"sur ce serveur.\nUtilisez `/perso-liste` pour voir vos fiches."
                ),
                color=COULEUR_ERREUR,
            ).set_footer(text=FOOTER),
            ephemeral=True,
        )
        return

    await interaction.response.send_message(
        embed=discord.Embed(
            title="✅ Personnage actif",
            description=(
                f"**{character.name}** (`{character.id}`) est maintenant votre "
                f"personnage actif sur ce serveur.\n"
                "Les commandes `/roll` et `/sort` utiliseront cette fiche par défaut."
            ),
            color=COULEUR_SUCCES,
        ).set_footer(text=FOOTER),
        ephemeral=True,
    )


async def perso_mp(interaction: discord.Interaction, ctx: DiscordJdrContext, nom: str) -> None:
    guild_id = _guild_id(interaction)
    try:
        sheet = _get_sheet_by_name(ctx, interaction.user.id, nom, guild_id)
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

    await interaction.response.defer(ephemeral=True)
    display = build_character_display(
        sheet, ctx.rule_engine, locale=ctx.locale
    )
    await _send_character_display_dm(interaction, display, sheet.name)


async def character_name_autocomplete(
    interaction: discord.Interaction,
    current: str,
    ctx: DiscordJdrContext,
) -> list[app_commands.Choice[str]]:
    if not ctx.character_service:
        return []

    guild_id = _guild_id(interaction)
    sheets = ctx.character_service.list_sheets(
        ListCharactersQuery(
            owner_id=str(interaction.user.id),
            guild_id=guild_id,
        ),
        locale=ctx.locale,
    )
    active_id: str | None = None
    if guild_id:
        active = ctx.character_service.get_active_character(
            str(interaction.user.id), guild_id
        )
        active_id = active.id if active else None

    choices = []
    current_lower = current.lower()
    for sheet in sheets:
        label = f"{sheet.name} ({sheet.character_id})"
        if active_id and sheet.character_id == active_id:
            label = f"⭐ {label}"
        if (
            current_lower in sheet.name.lower()
            or current_lower in sheet.character_id.lower()
        ):
            choices.append(app_commands.Choice(name=label, value=sheet.name))
        if len(choices) >= 25:
            break
    return choices


async def character_id_autocomplete(
    interaction: discord.Interaction,
    current: str,
    ctx: DiscordJdrContext,
) -> list[app_commands.Choice[str]]:
    """Autocomplete par id court (valeur = character_id)."""
    if not ctx.character_service:
        return []

    guild_id = _guild_id(interaction)
    if guild_id is None:
        return []

    characters = ctx.character_service.list_by_owner(
        ListCharactersQuery(
            owner_id=str(interaction.user.id),
            guild_id=guild_id,
        )
    )
    active_id: str | None = None
    active = ctx.character_service.get_active_character(
        str(interaction.user.id), guild_id
    )
    active_id = active.id if active else None

    choices: list[app_commands.Choice[str]] = []
    current_lower = current.lower()
    for character in characters:
        label = f"{character.name} ({character.id})"
        if active_id and character.id == active_id:
            label = f"⭐ {label}"
        if (
            current_lower in character.name.lower()
            or current_lower in character.id.lower()
        ):
            choices.append(app_commands.Choice(name=label, value=character.id))
        if len(choices) >= 25:
            break
    return choices
