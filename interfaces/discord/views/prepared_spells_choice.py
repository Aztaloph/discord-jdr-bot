# interfaces/discord/views/prepared_spells_choice.py
"""Re-préparation des sorts — clerc, druide, paladin, magicien (après repos long)."""
from __future__ import annotations

import logging

import discord

from jdr_engine.application.character_service import (
    CharacterNotFoundError,
    CharacterService,
    CharacterValidationError,
)
from jdr_engine.rules.engine import RuleEngine
from jdr_engine.rules.spellcasting.prepared_choice import PreparedChoiceContext

from interfaces.discord.formatters.character_embed import COULEUR_ERREUR, COULEUR_SUCCES

logger = logging.getLogger(__name__)
FOOTER = "JDR Bot — D&D 5e SRD 2014"


def _spell_label(engine: RuleEngine, spell_id: str) -> str:
    return (
        engine.get_display_name("spell", spell_id, locale="fr")
        or spell_id.replace("_", " ").title()
    )


def build_prepared_spells_embed(
    ctx: PreparedChoiceContext,
    *,
    engine: RuleEngine,
    selected: list[str] | None = None,
) -> discord.Embed:
    class_labels = {
        "cleric": "Clerc",
        "druid": "Druide",
        "paladin": "Paladin",
        "wizard": "Magicien",
    }
    title = f"📘 Préparation — {ctx.character_name}"
    pool_label = (
        "votre **grimoire**"
        if ctx.class_id == "wizard"
        else "la liste SRD"
    )
    description = (
        f"**{class_labels.get(ctx.class_id, ctx.class_id.title())}** niv. {ctx.level}\n\n"
        f"Choisissez **{ctx.quota}** sort(s) préparé(s) parmi {pool_label}, "
        f"puis appuyez sur **Confirmer**."
    )
    if ctx.domain_spells:
        domain_names = [_spell_label(engine, s) for s in ctx.domain_spells]
        description += (
            f"\n\n**Domaine (toujours préparés, hors choix)** : "
            f"{', '.join(domain_names)}"
        )
    if selected:
        labels = [_spell_label(engine, s) for s in selected]
        description += (
            f"\n\n**Sélection ({len(selected)}/{ctx.quota})** : {', '.join(labels)}"
        )
    if ctx.paladin_no_slots_notice:
        description += f"\n\nℹ️ {ctx.paladin_no_slots_notice}"
    return discord.Embed(
        title=title,
        description=description,
        color=COULEUR_SUCCES,
    ).set_footer(text=FOOTER)


class PreparedSpellsMultiSelect(discord.ui.Select):
    def __init__(self, view: "PreparedSpellsChoiceView"):
        self.prep_view = view
        ctx = view.choice_ctx
        options = [
            discord.SelectOption(
                label=_spell_label(view.engine, spell_id)[:100],
                value=spell_id,
            )
            for spell_id in ctx.pool[:25]
        ]
        super().__init__(
            placeholder=f"▼ Sorts préparés — choisir {ctx.quota}",
            options=options,
            min_values=ctx.quota,
            max_values=ctx.quota,
            row=0,
        )

    async def callback(self, interaction: discord.Interaction):
        selected = list(self.values)
        new_view = PreparedSpellsChoiceView(
            self.prep_view.choice_ctx,
            self.prep_view.engine,
            self.prep_view.character_service,
            self.prep_view.guild_id,
            self.prep_view.owner_id,
            selected_values=selected,
        )
        await interaction.response.edit_message(
            embed=build_prepared_spells_embed(
                new_view.choice_ctx,
                engine=new_view.engine,
                selected=selected,
            ),
            view=new_view,
        )


class PreparedSpellsConfirmButton(discord.ui.Button):
    def __init__(self, view: "PreparedSpellsChoiceView"):
        quota = view.choice_ctx.quota
        super().__init__(
            label="Confirmer →",
            style=discord.ButtonStyle.success,
            row=1,
            disabled=len(view.selected_values) != quota,
        )
        self.prep_view = view

    async def callback(self, interaction: discord.Interaction):
        quota = self.prep_view.choice_ctx.quota
        selected = list(self.prep_view.selected_values)
        if len(selected) != quota:
            await interaction.response.send_message(
                embed=discord.Embed(
                    title="⚠️ Sélection incomplète",
                    description=f"Choisissez exactement **{quota}** sort(s).",
                    color=COULEUR_ERREUR,
                ).set_footer(text=FOOTER),
                ephemeral=True,
            )
            return

        await interaction.response.defer(ephemeral=True)
        try:
            updated, ctx = self.prep_view.character_service.prepare_spells_for_active_character(
                self.prep_view.owner_id,
                self.prep_view.guild_id,
                selected,
            )
        except (CharacterValidationError, CharacterNotFoundError) as exc:
            await interaction.edit_original_response(
                embed=discord.Embed(
                    title="⚠️ Préparation impossible",
                    description=str(exc),
                    color=COULEUR_ERREUR,
                ).set_footer(text=FOOTER),
                view=None,
            )
            return

        description = (
            f"**{updated.name}** — sorts préparés mis à jour.\n\n"
            f"**Préparés** : {', '.join(_spell_label(self.prep_view.engine, s) for s in selected)}"
        )
        if ctx.domain_spells:
            domain_labels = [
                _spell_label(self.prep_view.engine, s) for s in ctx.domain_spells
            ]
            description += f"\n**Domaine** : {', '.join(domain_labels)}"
        notice = ctx.paladin_no_slots_notice
        if notice:
            description += f"\n\nℹ️ {notice}"

        await interaction.edit_original_response(
            embed=discord.Embed(
                title="✅ Sorts préparés",
                description=description,
                color=COULEUR_SUCCES,
            ).set_footer(text=FOOTER),
            view=None,
        )
        logger.info(
            "Préparation sorts : %s (%s) — %s",
            updated.name,
            updated.class_id,
            ", ".join(selected),
        )


class PreparedSpellsChoiceView(discord.ui.View):
    def __init__(
        self,
        choice_ctx: PreparedChoiceContext,
        engine: RuleEngine,
        character_service: CharacterService,
        guild_id: str,
        owner_id: str,
        *,
        selected_values: list[str] | None = None,
    ):
        super().__init__(timeout=600)
        self.choice_ctx = choice_ctx
        self.engine = engine
        self.character_service = character_service
        self.guild_id = guild_id
        self.owner_id = owner_id
        self.selected_values: list[str] = list(selected_values or [])
        self.add_item(PreparedSpellsMultiSelect(self))
        self.add_item(PreparedSpellsConfirmButton(self))
