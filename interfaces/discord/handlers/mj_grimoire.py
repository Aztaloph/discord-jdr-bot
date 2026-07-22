# interfaces/discord/handlers/mj_grimoire.py
"""Réinitialisation grimoire mage — commande MJ (/reset-grimoire)."""
from __future__ import annotations

import discord

from jdr_engine.application.character_service import (
    CharacterNotFoundError,
    CharacterValidationError,
)
from jdr_engine.application.dto.wizard_grimoire_reset import WizardGrimoireResetResult

from interfaces.discord.container import DiscordJdrContext
from interfaces.discord.formatters.character_embed import (
    COULEUR_ERREUR,
    COULEUR_INFO,
    COULEUR_SUCCES,
)
from interfaces.discord.handlers.mj_delete import guild_character_autocomplete
from interfaces.discord.permissions.mj import require_mj_role, user_has_mj_role

FOOTER = "JDR Bot — D&D 5e SRD 2014"


def _format_spell_list(spell_ids: tuple[str, ...]) -> str:
    if not spell_ids:
        return "_aucun_"
    return ", ".join(f"`{spell_id}`" for spell_id in spell_ids)


def build_grimoire_reset_embed(result: WizardGrimoireResetResult) -> discord.Embed:
    if result.already_clean:
        return discord.Embed(
            title="ℹ️ Grimoire déjà conforme",
            description=(
                f"**{result.character_name}** (`{result.character_id}`) — "
                f"grimoire, cantrips et sorts préparés correspondent déjà "
                f"au catalogue mage curated.\n\n"
                f"**Grimoire** : {_format_spell_list(result.spellbook_after)}"
            ),
            color=COULEUR_INFO,
        ).set_footer(text=FOOTER)

    lines = [
        f"**{result.character_name}** (`{result.character_id}`) — grimoire réinitialisé.",
        "",
        f"**Grimoire** : {_format_spell_list(result.spellbook_before)}",
        f"→ {_format_spell_list(result.spellbook_after)}",
        "",
        f"**Préparés** : {_format_spell_list(result.prepared_before)}",
        f"→ {_format_spell_list(result.prepared_after)}",
    ]
    if result.removed_from_spellbook:
        lines.append(
            f"\n**Retirés du grimoire** : {_format_spell_list(result.removed_from_spellbook)}"
        )
    if result.removed_from_prepared:
        lines.append(
            f"**Retirés des préparés** : {_format_spell_list(result.removed_from_prepared)}"
        )
    return discord.Embed(
        title="✅ Grimoire réinitialisé",
        description="\n".join(lines),
        color=COULEUR_SUCCES,
    ).set_footer(text=FOOTER)


def build_grimoire_reset_confirm_embed(
    result: WizardGrimoireResetResult,
) -> discord.Embed:
    lines = [
        f"**{result.character_name}** (`{result.character_id}`)",
        "",
        "Confirmez la réinitialisation du grimoire (cantrips + préparés inclus).",
        "",
        f"**Grimoire actuel** : {_format_spell_list(result.spellbook_before)}",
        f"**Grimoire après** : {_format_spell_list(result.spellbook_after)}",
        "",
        f"**Préparés actuels** : {_format_spell_list(result.prepared_before)}",
        f"**Préparés après** : {_format_spell_list(result.prepared_after)}",
    ]
    return discord.Embed(
        title="⚠️ Confirmation requise (MJ)",
        description="\n".join(lines),
        color=COULEUR_INFO,
    ).set_footer(text=FOOTER)


class MjConfirmGrimoireResetView(discord.ui.View):
    def __init__(
        self,
        ctx: DiscordJdrContext,
        mj_user_id: int,
        character_id: str,
        guild_id: str,
    ):
        super().__init__(timeout=60)
        self.ctx = ctx
        self.mj_user_id = mj_user_id
        self.character_id = character_id
        self.guild_id = guild_id

    @discord.ui.button(label="Confirmer la réinitialisation", style=discord.ButtonStyle.danger)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.mj_user_id or not user_has_mj_role(
            interaction.user if isinstance(interaction.user, discord.Member) else None
        ):
            await interaction.response.send_message("Action réservée au MJ.", ephemeral=True)
            return
        assert self.ctx.character_service
        try:
            result = self.ctx.character_service.reset_wizard_grimoire_on_guild(
                self.character_id,
                self.guild_id,
            )
        except CharacterNotFoundError:
            embed = discord.Embed(
                title="❌ Erreur",
                description="Personnage introuvable sur ce serveur.",
                color=COULEUR_ERREUR,
            )
        except CharacterValidationError as exc:
            embed = discord.Embed(
                title="ℹ️ Classe non concernée",
                description=str(exc),
                color=COULEUR_ERREUR,
            )
        else:
            embed = build_grimoire_reset_embed(result)
        embed.set_footer(text=FOOTER)
        await interaction.response.edit_message(embed=embed, view=None)

    @discord.ui.button(label="Annuler", style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.mj_user_id:
            await interaction.response.send_message("Action réservée au MJ.", ephemeral=True)
            return
        embed = discord.Embed(
            title="ℹ️ Réinitialisation annulée",
            description="Le grimoire n'a pas été modifié.",
            color=COULEUR_INFO,
        )
        embed.set_footer(text=FOOTER)
        await interaction.response.edit_message(embed=embed, view=None)


async def mj_reset_grimoire(
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

    from jdr_engine.rules.spellcasting.preparation import (
        is_wizard_spellcasting_canonical,
        project_wizard_spellcasting_reset,
    )
    from jdr_engine.rules.spellcasting.state import (
        get_cantrips_known,
        get_spellbook,
        get_spells_prepared_list,
    )

    try:
        character = ctx.character_service.get_on_guild(character_id, guild_id)
    except CharacterNotFoundError:
        await interaction.response.send_message(
            embed=discord.Embed(
                title="❌ Personnage introuvable",
                description=f"Aucun personnage **`{character_id}`** sur ce serveur.",
                color=COULEUR_ERREUR,
            ).set_footer(text=FOOTER),
            ephemeral=True,
        )
        return

    if character.class_id != "wizard":
        await interaction.response.send_message(
            embed=discord.Embed(
                title="ℹ️ Classe non concernée",
                description="Seuls les **magiciens** possèdent un grimoire réinitialisable.",
                color=COULEUR_ERREUR,
            ).set_footer(text=FOOTER),
            ephemeral=True,
        )
        return

    cantrips_before = tuple(get_cantrips_known(character))
    spellbook_before = tuple(get_spellbook(character))
    prepared_before = tuple(get_spells_prepared_list(character))

    if is_wizard_spellcasting_canonical(character):
        result = WizardGrimoireResetResult(
            character_id=character.id,
            character_name=character.name,
            already_clean=True,
            cantrips_before=cantrips_before,
            cantrips_after=cantrips_before,
            spellbook_before=spellbook_before,
            spellbook_after=spellbook_before,
            prepared_before=prepared_before,
            prepared_after=prepared_before,
        )
        await interaction.response.send_message(
            embed=build_grimoire_reset_embed(result),
            ephemeral=True,
        )
        return

    projected = project_wizard_spellcasting_reset(character)
    preview = WizardGrimoireResetResult(
        character_id=character.id,
        character_name=character.name,
        already_clean=False,
        cantrips_before=cantrips_before,
        cantrips_after=tuple(get_cantrips_known(projected)),
        spellbook_before=spellbook_before,
        spellbook_after=tuple(get_spellbook(projected)),
        prepared_before=prepared_before,
        prepared_after=tuple(get_spells_prepared_list(projected)),
    )

    await interaction.response.send_message(
        embed=build_grimoire_reset_confirm_embed(preview),
        view=MjConfirmGrimoireResetView(
            ctx,
            mj_user_id=interaction.user.id,
            character_id=character.id,
            guild_id=guild_id,
        ),
        ephemeral=True,
    )


__all__ = ["guild_character_autocomplete", "mj_reset_grimoire"]
