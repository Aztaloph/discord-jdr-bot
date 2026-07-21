# interfaces/discord/handlers/prepare_spells.py
"""Handler /preparer-sorts — re-préparation après repos long."""
from __future__ import annotations

import discord

from jdr_engine.rules.spellcasting.prepared_choice import (
    build_prepared_choice_context,
    is_prepared_rechoice_pending,
    requires_prepared_rechoice_class,
)

from interfaces.discord.container import DiscordJdrContext
from interfaces.discord.formatters.character_embed import COULEUR_ERREUR
from interfaces.discord.views.prepared_spells_choice import (
    PreparedSpellsChoiceView,
    build_prepared_spells_embed,
)

FOOTER = "JDR Bot — D&D 5e SRD 2014"


async def player_preparer_sorts(
    interaction: discord.Interaction,
    ctx: DiscordJdrContext,
) -> None:
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
    assert ctx.rule_engine
    guild_id = str(interaction.guild.id)
    owner_id = str(interaction.user.id)

    character = ctx.character_service.get_active_character(owner_id, guild_id)
    if character is None:
        await interaction.response.send_message(
            embed=discord.Embed(
                title="❌ Aucun personnage actif",
                description="Utilisez `/perso-choisir` pour sélectionner votre personnage.",
                color=COULEUR_ERREUR,
            ).set_footer(text=FOOTER),
            ephemeral=True,
        )
        return

    if str(character.owner_id) != owner_id:
        await interaction.response.send_message(
            embed=discord.Embed(
                title="❌ Accès refusé",
                description="Ce personnage ne vous appartient pas.",
                color=COULEUR_ERREUR,
            ).set_footer(text=FOOTER),
            ephemeral=True,
        )
        return

    if not requires_prepared_rechoice_class(character.class_id):
        await interaction.response.send_message(
            embed=discord.Embed(
                title="ℹ️ Classe non concernée",
                description=(
                    "Seuls le **clerc**, le **druide** et le **paladin** "
                    "re-préparent leurs sorts après un repos long."
                ),
                color=COULEUR_ERREUR,
            ).set_footer(text=FOOTER),
            ephemeral=True,
        )
        return

    if not is_prepared_rechoice_pending(character):
        await interaction.response.send_message(
            embed=discord.Embed(
                title="ℹ️ Re-préparation non disponible",
                description=(
                    "Vous pouvez re-choisir vos sorts préparés **uniquement après "
                    "un repos long** déclaré par le MJ (`/repos-long`)."
                ),
                color=COULEUR_ERREUR,
            ).set_footer(text=FOOTER),
            ephemeral=True,
        )
        return

    choice_ctx = build_prepared_choice_context(character, engine=ctx.rule_engine)
    if not choice_ctx.pool:
        await interaction.response.send_message(
            embed=discord.Embed(
                title="⚠️ Aucun sort disponible",
                description="Aucun sort de votre liste de classe n'est accessible à ce niveau.",
                color=COULEUR_ERREUR,
            ).set_footer(text=FOOTER),
            ephemeral=True,
        )
        return

    await interaction.response.send_message(
        embed=build_prepared_spells_embed(choice_ctx, engine=ctx.rule_engine),
        view=PreparedSpellsChoiceView(
            choice_ctx,
            ctx.rule_engine,
            ctx.character_service,
            guild_id,
            owner_id,
        ),
        ephemeral=True,
    )
