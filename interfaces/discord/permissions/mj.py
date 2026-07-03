# interfaces/discord/permissions/mj.py
"""Vérification du rôle Discord « MJ » — réutilisable pour commandes réservées."""
from __future__ import annotations

import discord

MJ_ROLE_NAME = "MJ"

COLOR_MJ_DENIED = discord.Color(0xF44336)


def build_mj_denied_embed() -> discord.Embed:
    return discord.Embed(
        title="🔒 Réservé au Maître du Jeu",
        description=(
            "Cette action est réservée aux membres ayant le rôle **MJ** sur ce serveur.\n"
            "Demandez à votre MJ si vous pensez avoir besoin de cette commande."
        ),
        color=COLOR_MJ_DENIED,
    ).set_footer(text="JDR Bot — D&D 5e SRD 2014")


def user_has_mj_role(member: discord.Member | None) -> bool:
    """True si le membre possède le rôle Discord nommé « MJ »."""
    if member is None:
        return False
    return any(role.name == MJ_ROLE_NAME for role in member.roles)


async def require_mj_role(interaction: discord.Interaction) -> bool:
    """
    Vérifie le rôle MJ. En cas d'échec, envoie un embed poli (ephemeral).

    Usage dans une commande slash ::
        if not await require_mj_role(interaction):
            return
    """
    if not isinstance(interaction.user, discord.Member):
        await interaction.response.send_message(
            embed=build_mj_denied_embed(),
            ephemeral=True,
        )
        return False
    if user_has_mj_role(interaction.user):
        return True
    if interaction.response.is_done():
        await interaction.followup.send(
            embed=build_mj_denied_embed(),
            ephemeral=True,
        )
    else:
        await interaction.response.send_message(
            embed=build_mj_denied_embed(),
            ephemeral=True,
        )
    return False
