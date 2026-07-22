# interfaces/discord/handlers/mj_grimoire_migration.py
"""Migration batch grimoires mage — commande MJ (/migrer-grimoires)."""
from __future__ import annotations

import math

import discord

from jdr_engine.application.dto.wizard_grimoire_migration import (
    WizardGrimoireMigrationEntry,
    WizardGrimoireMigrationReport,
    WizardGrimoireMigrationStatus,
)

from interfaces.discord.container import DiscordJdrContext
from interfaces.discord.formatters.character_embed import (
    COULEUR_ERREUR,
    COULEUR_INFO,
    COULEUR_SUCCES,
)
from interfaces.discord.permissions.mj import require_mj_role, user_has_mj_role

FOOTER = "JDR Bot — D&D 5e SRD 2014"
PAGE_SIZE = 8


def format_migration_entry_line(entry: WizardGrimoireMigrationEntry) -> str:
    if entry.status == WizardGrimoireMigrationStatus.SKIP:
        return (
            f"✅ **{entry.character_name}** (`{entry.character_id}`) — déjà conforme"
        )
    if entry.status == WizardGrimoireMigrationStatus.WILL_MODIFY and entry.result:
        return _format_modify_line(entry)
    if entry.status == WizardGrimoireMigrationStatus.MODIFIED and entry.result:
        return _format_modify_line(entry, prefix="✅")
    if entry.status == WizardGrimoireMigrationStatus.ERROR:
        return (
            f"❌ **{entry.character_name}** (`{entry.character_id}`) — "
            f"{entry.error or 'Erreur inconnue'}"
        )
    return f"**{entry.character_name}** (`{entry.character_id}`)"


def _format_modify_line(
    entry: WizardGrimoireMigrationEntry,
    *,
    prefix: str = "🔄",
) -> str:
    assert entry.result is not None
    parts: list[str] = []
    if entry.result.removed_from_spellbook:
        removed = ", ".join(f"-{spell_id}" for spell_id in entry.result.removed_from_spellbook)
        parts.append(f"grimoire : {removed}")
    if entry.result.removed_from_prepared:
        removed = ", ".join(f"-{spell_id}" for spell_id in entry.result.removed_from_prepared)
        parts.append(f"préparés : {removed}")
    detail = " | ".join(parts) if parts else "normalisation cantrips/préparés"
    return f"{prefix} **{entry.character_name}** (`{entry.character_id}`) — {detail}"


def _summary_lines(report: WizardGrimoireMigrationReport) -> list[str]:
    lines = [
        f"Magiciens sur ce serveur : **{report.total_wizards}**",
    ]
    if report.dry_run:
        lines.extend(
            [
                f"🔄 Seront modifiés : **{report.to_modify}**",
                f"✅ Déjà conformes (skip) : **{report.skipped}**",
                f"❌ Erreurs : **{report.failed}**",
            ]
        )
    else:
        lines.extend(
            [
                f"✅ Modifiés : **{report.modified}**",
                f"✅ Ignorés (déjà propres) : **{report.skipped}**",
                f"❌ Échecs : **{report.failed}**",
            ]
        )
    return lines


def build_migration_preview_embed(
    report: WizardGrimoireMigrationReport,
    *,
    page: int = 0,
) -> discord.Embed:
    total_pages = max(1, math.ceil(len(report.entries) / PAGE_SIZE)) if report.entries else 1
    page = max(0, min(page, total_pages - 1))
    start = page * PAGE_SIZE
    page_entries = report.entries[start : start + PAGE_SIZE]

    lines = _summary_lines(report)
    lines.append("")
    if report.total_wizards == 0:
        lines.append("_Aucun magicien sur ce serveur._")
    elif report.to_modify == 0 and report.failed == 0:
        lines.append("_Tous les grimoires sont déjà conformes._")
    else:
        lines.append("**Détail :**")
        lines.extend(format_migration_entry_line(entry) for entry in page_entries)
        if total_pages > 1:
            lines.append("")
            lines.append(f"_Page {page + 1}/{total_pages}_")

    title = "ℹ️ Migration grimoires — aperçu (dry-run)"
    if report.to_modify > 0:
        title = "⚠️ Migration grimoires — confirmation requise (MJ)"

    return discord.Embed(
        title=title,
        description="\n".join(lines),
        color=COULEUR_INFO if report.to_modify > 0 else COULEUR_SUCCES,
    ).set_footer(text=FOOTER)


def build_migration_result_embed(
    report: WizardGrimoireMigrationReport,
    *,
    page: int = 0,
) -> discord.Embed:
    total_pages = max(1, math.ceil(len(report.entries) / PAGE_SIZE)) if report.entries else 1
    page = max(0, min(page, total_pages - 1))
    start = page * PAGE_SIZE
    page_entries = report.entries[start : start + PAGE_SIZE]

    lines = _summary_lines(report)
    lines.append("")
    if report.entries:
        lines.append("**Détail :**")
        lines.extend(format_migration_entry_line(entry) for entry in page_entries)
        if total_pages > 1:
            lines.append("")
            lines.append(f"_Page {page + 1}/{total_pages}_")

    color = COULEUR_SUCCES
    title = "✅ Migration grimoires terminée"
    if report.failed:
        color = COULEUR_ERREUR
        title = "⚠️ Migration grimoires terminée avec erreurs"

    return discord.Embed(
        title=title,
        description="\n".join(lines),
        color=color,
    ).set_footer(text=FOOTER)


class MjMigrationPreviewView(discord.ui.View):
    """Preview paginé + confirmation. Ne mémorise pas le rapport (re-scan à la confirmation)."""

    def __init__(
        self,
        ctx: DiscordJdrContext,
        mj_user_id: int,
        guild_id: str,
        report: WizardGrimoireMigrationReport,
        *,
        page: int = 0,
    ):
        super().__init__(timeout=120)
        self.ctx = ctx
        self.mj_user_id = mj_user_id
        self.guild_id = guild_id
        self.report = report
        self.page = page
        self._refresh_buttons()

    @property
    def total_pages(self) -> int:
        if not self.report.entries:
            return 1
        return max(1, math.ceil(len(self.report.entries) / PAGE_SIZE))

    def _refresh_buttons(self) -> None:
        self.clear_items()
        if self.total_pages > 1:
            prev = discord.ui.Button(label="◀ Précédent", style=discord.ButtonStyle.secondary)
            nxt = discord.ui.Button(label="Suivant ▶", style=discord.ButtonStyle.secondary)

            @prev.callback
            async def prev_cb(interaction: discord.Interaction):
                await self._change_page(interaction, self.page - 1)

            @nxt.callback
            async def next_cb(interaction: discord.Interaction):
                await self._change_page(interaction, self.page + 1)

            prev.disabled = self.page <= 0
            nxt.disabled = self.page >= self.total_pages - 1
            self.add_item(prev)
            self.add_item(nxt)

        confirm = discord.ui.Button(
            label=f"Confirmer la migration ({self.report.to_modify} perso(s))",
            style=discord.ButtonStyle.danger,
        )
        cancel = discord.ui.Button(label="Annuler", style=discord.ButtonStyle.secondary)

        @confirm.callback
        async def confirm_cb(interaction: discord.Interaction):
            await self._confirm(interaction)

        @cancel.callback
        async def cancel_cb(interaction: discord.Interaction):
            await self._cancel(interaction)

        self.add_item(confirm)
        self.add_item(cancel)

    async def _change_page(self, interaction: discord.Interaction, new_page: int) -> None:
        if interaction.user.id != self.mj_user_id:
            await interaction.response.send_message("Action réservée au MJ.", ephemeral=True)
            return
        self.page = max(0, min(new_page, self.total_pages - 1))
        self._refresh_buttons()
        embed = build_migration_preview_embed(self.report, page=self.page)
        await interaction.response.edit_message(embed=embed, view=self)

    async def _confirm(self, interaction: discord.Interaction) -> None:
        if interaction.user.id != self.mj_user_id or not user_has_mj_role(
            interaction.user if isinstance(interaction.user, discord.Member) else None
        ):
            await interaction.response.send_message("Action réservée au MJ.", ephemeral=True)
            return
        assert self.ctx.character_service
        result = self.ctx.character_service.migrate_wizard_grimoires_on_guild(
            self.guild_id,
            dry_run=False,
        )
        embed = build_migration_result_embed(result, page=0)
        await interaction.response.edit_message(embed=embed, view=None)

    async def _cancel(self, interaction: discord.Interaction) -> None:
        if interaction.user.id != self.mj_user_id:
            await interaction.response.send_message("Action réservée au MJ.", ephemeral=True)
            return
        embed = discord.Embed(
            title="ℹ️ Migration annulée",
            description="Aucun grimoire n'a été modifié.",
            color=COULEUR_INFO,
        ).set_footer(text=FOOTER)
        await interaction.response.edit_message(embed=embed, view=None)


async def mj_migrer_grimoires(
    interaction: discord.Interaction,
    ctx: DiscordJdrContext,
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
    report = ctx.character_service.migrate_wizard_grimoires_on_guild(guild_id, dry_run=True)
    embed = build_migration_preview_embed(report, page=0)

    if report.to_modify > 0:
        view: discord.ui.View | None = MjMigrationPreviewView(
            ctx,
            mj_user_id=interaction.user.id,
            guild_id=guild_id,
            report=report,
        )
    else:
        view = None

    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


__all__ = ["mj_migrer_grimoires"]
