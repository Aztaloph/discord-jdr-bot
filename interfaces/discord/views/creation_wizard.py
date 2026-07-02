# interfaces/discord/views/creation_wizard.py
"""Assistant de création v2 — selects Compendium + modal nom."""
from __future__ import annotations

import logging

import discord

from jdr_engine.application.character_service import (
    CharacterService,
    CharacterValidationError,
    CreateCharacterCommand,
)
from jdr_engine.application.dto.character_commands import GetCharacterSheetQuery
from jdr_engine.rules.engine import RuleEngine

from interfaces.discord.components.entity_select import (
    class_select_options,
    race_select_options,
)
from interfaces.discord.formatters.character_embed import COULEUR_ERREUR, COULEUR_SUCCES
from interfaces.discord.formatters.lore_text import truncate_lore

logger = logging.getLogger(__name__)


class ModalNomPersonnage(discord.ui.Modal, title="Nom du personnage"):
    def __init__(self, wizard: CreationWizardView):
        super().__init__()
        self.wizard = wizard
        self.nom_input = discord.ui.TextInput(
            label="Nom du personnage",
            placeholder="Ex: Aldric le Brave",
            required=True,
            max_length=50,
        )
        self.add_item(self.nom_input)

    async def on_submit(self, interaction: discord.Interaction):
        if interaction.user.id != self.wizard.owner_id:
            await interaction.response.send_message(
                "Cette création ne vous appartient pas.",
                ephemeral=True,
            )
            return

        if not self.wizard.race_id or not self.wizard.class_id:
            await interaction.response.send_message(
                "Sélectionnez d'abord une race et une classe.",
                ephemeral=True,
            )
            return

        try:
            character = self.wizard.character_service.create(
                CreateCharacterCommand(
                    owner_id=str(interaction.user.id),
                    name=self.nom_input.value.strip(),
                    race_id=self.wizard.race_id,
                    class_id=self.wizard.class_id,
                    level=1,
                    ruleset_id=self.wizard.rule_engine.ruleset_id,
                )
            )
        except CharacterValidationError as exc:
            await interaction.response.send_message(
                embed=discord.Embed(
                    title="❌ Création impossible",
                    description=str(exc),
                    color=COULEUR_ERREUR,
                ),
                ephemeral=True,
            )
            return

        sheet = self.wizard.character_service.get_sheet(
            GetCharacterSheetQuery(
                character_id=character.id,
                owner_id=str(interaction.user.id),
                locale=self.wizard.locale,
            )
        )

        description_lines = [
            f"**{sheet.name}** — {sheet.race_name} {sheet.class_name} niv. {sheet.level}",
            f"PV : {sheet.hp_current}/{sheet.hp_max} · CA : {sheet.ac}",
        ]
        race_lore = self.wizard.rule_engine.presenter.get_lore(
            "race", self.wizard.race_id, self.wizard.locale
        )
        if race_lore:
            description_lines.append(f"_{truncate_lore(race_lore, 220)}_")

        embed = discord.Embed(
            title="🎉 Personnage créé !",
            description="\n".join(description_lines),
            color=COULEUR_SUCCES,
        )
        embed.set_footer(text="Utilisez /perso-afficher pour la fiche complète.")
        self.wizard.creation_done = True
        await interaction.response.send_message(embed=embed, ephemeral=True)


class RaceSelect(discord.ui.Select):
    def __init__(self, wizard: CreationWizardView):
        self.wizard = wizard
        super().__init__(
            placeholder="▼ Choisissez une race",
            options=race_select_options(wizard.rule_engine, wizard.locale),
            min_values=1,
            max_values=1,
            row=0,
        )

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.wizard.owner_id:
            await interaction.response.send_message("Action non autorisée.", ephemeral=True)
            return
        self.wizard.race_id = self.values[0]
        race_name = self.wizard.rule_engine.get_display_name(
            "race", self.wizard.race_id, self.wizard.locale
        )
        await interaction.response.send_message(
            f"Race sélectionnée : **{race_name}**",
            ephemeral=True,
        )


class ClassSelect(discord.ui.Select):
    def __init__(self, wizard: CreationWizardView):
        self.wizard = wizard
        super().__init__(
            placeholder="▼ Choisissez une classe",
            options=class_select_options(wizard.rule_engine, wizard.locale),
            min_values=1,
            max_values=1,
            row=1,
        )

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.wizard.owner_id:
            await interaction.response.send_message("Action non autorisée.", ephemeral=True)
            return
        self.wizard.class_id = self.values[0]
        class_name = self.wizard.rule_engine.get_display_name(
            "class", self.wizard.class_id, self.wizard.locale
        )
        await interaction.response.send_message(
            f"Classe sélectionnée : **{class_name}**",
            ephemeral=True,
        )


class ConfirmCreationButton(discord.ui.Button):
    def __init__(self, wizard: CreationWizardView):
        super().__init__(
            label="Continuer → Nom du personnage",
            style=discord.ButtonStyle.success,
            row=2,
        )
        self.wizard = wizard

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.wizard.owner_id:
            await interaction.response.send_message("Action non autorisée.", ephemeral=True)
            return
        if self.wizard.creation_done:
            await interaction.response.send_message(
                "Création déjà terminée.", ephemeral=True
            )
            return
        if not self.wizard.race_id or not self.wizard.class_id:
            await interaction.response.send_message(
                embed=discord.Embed(
                    title="⚠️ Sélection incomplète",
                    description="Choisissez une **race** et une **classe** dans les menus.",
                    color=COULEUR_ERREUR,
                ),
                ephemeral=True,
            )
            return
        await interaction.response.send_modal(ModalNomPersonnage(self.wizard))


class CreationWizardView(discord.ui.View):
    def __init__(
        self,
        owner_id: int,
        rule_engine: RuleEngine,
        character_service: CharacterService,
        locale: str = "fr",
    ):
        super().__init__(timeout=300)
        self.owner_id = owner_id
        self.rule_engine = rule_engine
        self.character_service = character_service
        self.locale = locale
        self.race_id: str | None = None
        self.class_id: str | None = None
        self.creation_done = False

        self.add_item(RaceSelect(self))
        self.add_item(ClassSelect(self))
        self.add_item(ConfirmCreationButton(self))


async def start_creation_wizard(interaction: discord.Interaction, ctx) -> None:
    """Point d'entrée /perso-creer v2."""
    assert ctx.rule_engine and ctx.character_service

    embed = discord.Embed(
        title="🎭 Création de personnage",
        description=(
            "1️⃣ Choisissez votre **race** dans le premier menu\n"
            "2️⃣ Choisissez votre **classe** dans le second menu\n"
            "3️⃣ Cliquez sur **Continuer** pour saisir le nom\n\n"
            "*Les listes proviennent du Compendium — toute nouvelle race y apparaît automatiquement.*"
        ),
        color=0x8B4513,
    )

    view = CreationWizardView(
        owner_id=interaction.user.id,
        rule_engine=ctx.rule_engine,
        character_service=ctx.character_service,
        locale=ctx.locale,
    )
    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
