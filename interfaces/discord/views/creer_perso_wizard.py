# interfaces/discord/views/creer_perso_wizard.py
"""Assistant interactif /creer-perso — Lot 1 (point buy, compétences, domaine clerc)."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field

import discord

from jdr_engine.application.character_service import (
    CharacterService,
    CharacterValidationError,
)
from jdr_engine.application.dto.character_commands import GetCharacterSheetQuery
from jdr_engine.rules.character_creation.class_choices import (
    get_cleric_domain_options,
    get_skill_choice_config,
    requires_domain_at_creation,
)
from jdr_engine.rules.character_creation.race_choices import (
    get_dragonborn_ancestry_options,
    race_needs_creation_step,
)
from jdr_engine.rules.derived_stats import SKILL_LABELS_FR, skill_label_fr
from jdr_engine.rules.racial.draconic_ancestry import get_draconic_ancestry
from jdr_engine.rules.racial.resolve import HALF_ELF_FLEXIBLE_ABILITIES
from jdr_engine.rules.engine import RuleEngine

from interfaces.discord.components.playable_select import (
    playable_class_select_options,
    playable_race_select_options,
)
from interfaces.discord.components.point_buy_distribution import (
    PointBuyDistributionView,
    PointBuyState,
)
from interfaces.discord.formatters.character_embed import (
    COULEUR_ERREUR,
    COULEUR_PRINCIPALE,
    COULEUR_SUCCES,
    build_character_display,
)

logger = logging.getLogger(__name__)

FOOTER = "JDR Bot — D&D 5e SRD 2014"


@dataclass
class CreerPersoState:
    owner_id: int
    guild_id: str
    name: str
    locale: str = "fr"
    race_id: str | None = None
    class_id: str | None = None
    point_buy: PointBuyState = field(default_factory=PointBuyState.fresh)
    selected_skills: list[str] = field(default_factory=list)
    specialization: str | None = None
    draconic_ancestry: str | None = None
    racial_ability_bonuses: list[str] = field(default_factory=list)
    racial_skills: list[str] = field(default_factory=list)
    done: bool = False


def _owner_check(interaction: discord.Interaction, owner_id: int) -> bool:
    return interaction.user.id == owner_id


class ModalNomCreerPerso(discord.ui.Modal, title="Nom du personnage"):
    nom_input = discord.ui.TextInput(
        label="Nom du personnage",
        placeholder="Ex : Aldric le Sage",
        required=True,
        max_length=50,
    )

    def __init__(self, wizard: CreerPersoWizard):
        super().__init__()
        self.wizard = wizard

    async def on_submit(self, interaction: discord.Interaction):
        if not _owner_check(interaction, self.wizard.state.owner_id):
            await interaction.response.send_message("Action non autorisée.", ephemeral=True)
            return
        self.wizard.state.name = self.nom_input.value.strip()
        await interaction.response.send_message(
            embed=self.wizard.build_identity_embed(),
            view=IdentityStepView(self.wizard),
            ephemeral=True,
        )


class PlayableRaceSelect(discord.ui.Select):
    def __init__(self, wizard: CreerPersoWizard):
        self.wizard = wizard
        super().__init__(
            placeholder="▼ Race",
            options=playable_race_select_options(wizard.engine, wizard.state.locale),
            min_values=1,
            max_values=1,
            row=0,
        )

    async def callback(self, interaction: discord.Interaction):
        if not _owner_check(interaction, self.wizard.state.owner_id):
            await interaction.response.send_message("Action non autorisée.", ephemeral=True)
            return
        self.wizard.state.race_id = self.values[0]
        await interaction.response.edit_message(
            embed=self.wizard.build_identity_embed(),
            view=IdentityStepView(self.wizard),
        )


class PlayableClassSelect(discord.ui.Select):
    def __init__(self, wizard: CreerPersoWizard):
        self.wizard = wizard
        super().__init__(
            placeholder="▼ Classe (Magicien ou Clerc)",
            options=playable_class_select_options(wizard.engine, wizard.state.locale),
            min_values=1,
            max_values=1,
            row=1,
        )

    async def callback(self, interaction: discord.Interaction):
        if not _owner_check(interaction, self.wizard.state.owner_id):
            await interaction.response.send_message("Action non autorisée.", ephemeral=True)
            return
        self.wizard.state.class_id = self.values[0]
        self.wizard.state.selected_skills = []
        self.wizard.state.specialization = None
        await interaction.response.edit_message(
            embed=self.wizard.build_identity_embed(),
            view=IdentityStepView(self.wizard),
        )


class IdentityContinueButton(discord.ui.Button):
    def __init__(self, wizard: CreerPersoWizard):
        super().__init__(
            label="Continuer → Caractéristiques",
            style=discord.ButtonStyle.success,
            row=2,
        )
        self.wizard = wizard

    async def callback(self, interaction: discord.Interaction):
        if not _owner_check(interaction, self.wizard.state.owner_id):
            await interaction.response.send_message("Action non autorisée.", ephemeral=True)
            return
        if not self.wizard.state.race_id or not self.wizard.state.class_id:
            await interaction.response.send_message(
                embed=discord.Embed(
                    title="⚠️ Sélection incomplète",
                    description="Choisissez une **race** et une **classe**.",
                    color=COULEUR_ERREUR,
                ).set_footer(text=FOOTER),
                ephemeral=True,
            )
            return
        self.wizard.state.point_buy = PointBuyState.fresh()
        view = self.wizard.build_point_buy_view()
        await interaction.response.edit_message(
            embed=view.build_embed(),
            view=view,
        )


class IdentityStepView(discord.ui.View):
    def __init__(self, wizard: CreerPersoWizard):
        super().__init__(timeout=600)
        self.wizard = wizard
        self.add_item(PlayableRaceSelect(wizard))
        self.add_item(PlayableClassSelect(wizard))
        self.add_item(IdentityContinueButton(wizard))


class SkillMultiSelect(discord.ui.Select):
    def __init__(self, wizard: CreerPersoWizard, config):
        self.wizard = wizard
        options = [
            discord.SelectOption(
                label=skill_label_fr(skill_id)[:100],
                value=skill_id,
            )
            for skill_id in config.options
        ]
        super().__init__(
            placeholder=f"▼ Choisir {config.count} compétence(s)",
            options=options,
            min_values=config.count,
            max_values=config.count,
            row=0,
        )

    async def callback(self, interaction: discord.Interaction):
        if not _owner_check(interaction, self.wizard.state.owner_id):
            await interaction.response.send_message("Action non autorisée.", ephemeral=True)
            return
        self.wizard.state.selected_skills = list(self.values)
        await interaction.response.edit_message(
            embed=self.wizard.build_skills_embed(),
            view=SkillsStepView(self.wizard),
        )


class SkillsContinueButton(discord.ui.Button):
    def __init__(self, wizard: CreerPersoWizard):
        config = get_skill_choice_config(wizard.engine, wizard.state.class_id or "")
        disabled = config is not None and len(wizard.state.selected_skills) != config.count
        super().__init__(
            label="Continuer →",
            style=discord.ButtonStyle.success,
            row=1,
            disabled=disabled,
        )
        self.wizard = wizard

    async def callback(self, interaction: discord.Interaction):
        if not _owner_check(interaction, self.wizard.state.owner_id):
            await interaction.response.send_message("Action non autorisée.", ephemeral=True)
            return
        config = get_skill_choice_config(
            self.wizard.engine, self.wizard.state.class_id or ""
        )
        if config and len(self.wizard.state.selected_skills) != config.count:
            await interaction.response.send_message(
                embed=discord.Embed(
                    title="⚠️ Compétences incomplètes",
                    description=f"Sélectionnez **{config.count}** compétence(s).",
                    color=COULEUR_ERREUR,
                ).set_footer(text=FOOTER),
                ephemeral=True,
            )
            return
        if requires_domain_at_creation(
            self.wizard.engine, self.wizard.state.class_id or ""
        ):
            view = DomainStepView(self.wizard)
            await interaction.response.edit_message(
                embed=self.wizard.build_domain_embed(),
                view=view,
            )
        else:
            await self.wizard.finalize(interaction)


class SkillsStepView(discord.ui.View):
    def __init__(self, wizard: CreerPersoWizard):
        super().__init__(timeout=600)
        self.wizard = wizard
        config = get_skill_choice_config(wizard.engine, wizard.state.class_id or "")
        if config:
            self.add_item(SkillMultiSelect(wizard, config))
        self.add_item(SkillsContinueButton(wizard))


class DraconicAncestrySelect(discord.ui.Select):
    def __init__(self, wizard: CreerPersoWizard):
        self.wizard = wizard
        options: list[discord.SelectOption] = []
        for color_id in get_dragonborn_ancestry_options():
            anc = get_draconic_ancestry(color_id)
            label = anc.label_fr if anc else color_id.title()
            options.append(discord.SelectOption(label=label[:100], value=color_id))
        super().__init__(
            placeholder="▼ Ascendance draconique",
            options=options,
            min_values=1,
            max_values=1,
            row=0,
        )

    async def callback(self, interaction: discord.Interaction):
        if not _owner_check(interaction, self.wizard.state.owner_id):
            await interaction.response.send_message("Action non autorisée.", ephemeral=True)
            return
        self.wizard.state.draconic_ancestry = self.values[0]
        await interaction.response.edit_message(
            embed=self.wizard.build_race_choices_embed(),
            view=RaceChoicesStepView(self.wizard),
        )


class HalfElfAbilitySelect(discord.ui.Select):
    def __init__(self, wizard: CreerPersoWizard):
        self.wizard = wizard
        ability_labels = {
            "str": "FOR", "dex": "DEX", "con": "CON", "int": "INT", "wis": "SAG",
        }
        options = [
            discord.SelectOption(label=ability_labels[a], value=a)
            for a in HALF_ELF_FLEXIBLE_ABILITIES
        ]
        super().__init__(
            placeholder="▼ +1 à 2 caractéristiques (hors CHA)",
            options=options,
            min_values=2,
            max_values=2,
            row=0,
        )

    async def callback(self, interaction: discord.Interaction):
        if not _owner_check(interaction, self.wizard.state.owner_id):
            await interaction.response.send_message("Action non autorisée.", ephemeral=True)
            return
        self.wizard.state.racial_ability_bonuses = list(self.values)
        await interaction.response.edit_message(
            embed=self.wizard.build_race_choices_embed(),
            view=RaceChoicesStepView(self.wizard),
        )


class HalfElfSkillSelect(discord.ui.Select):
    def __init__(self, wizard: CreerPersoWizard):
        self.wizard = wizard
        options = [
            discord.SelectOption(label=skill_label_fr(s)[:100], value=s)
            for s in SKILL_LABELS_FR
        ]
        super().__init__(
            placeholder="▼ 2 compétences au choix",
            options=options,
            min_values=2,
            max_values=2,
            row=1,
        )

    async def callback(self, interaction: discord.Interaction):
        if not _owner_check(interaction, self.wizard.state.owner_id):
            await interaction.response.send_message("Action non autorisée.", ephemeral=True)
            return
        self.wizard.state.racial_skills = list(self.values)
        await interaction.response.edit_message(
            embed=self.wizard.build_race_choices_embed(),
            view=RaceChoicesStepView(self.wizard),
        )


class RaceChoicesContinueButton(discord.ui.Button):
    def __init__(self, wizard: CreerPersoWizard):
        race_id = wizard.state.race_id or ""
        ready = True
        if race_id == "dragonborn":
            ready = wizard.state.draconic_ancestry is not None
        elif race_id == "half_elf":
            ready = (
                len(wizard.state.racial_ability_bonuses) == 2
                and len(wizard.state.racial_skills) == 2
            )
        super().__init__(
            label="Continuer → Compétences de classe",
            style=discord.ButtonStyle.success,
            row=2,
            disabled=not ready,
        )
        self.wizard = wizard

    async def callback(self, interaction: discord.Interaction):
        if not _owner_check(interaction, self.wizard.state.owner_id):
            await interaction.response.send_message("Action non autorisée.", ephemeral=True)
            return
        race_id = self.wizard.state.race_id or ""
        if race_id == "dragonborn" and not self.wizard.state.draconic_ancestry:
            await interaction.response.send_message(
                embed=discord.Embed(
                    title="⚠️ Ascendance requise",
                    description="Choisissez une **ascendance draconique**.",
                    color=COULEUR_ERREUR,
                ).set_footer(text=FOOTER),
                ephemeral=True,
            )
            return
        if race_id == "half_elf" and (
            len(self.wizard.state.racial_ability_bonuses) != 2
            or len(self.wizard.state.racial_skills) != 2
        ):
            await interaction.response.send_message(
                embed=discord.Embed(
                    title="⚠️ Choix incomplets",
                    description="Sélectionnez **2 caractéristiques** et **2 compétences**.",
                    color=COULEUR_ERREUR,
                ).set_footer(text=FOOTER),
                ephemeral=True,
            )
            return
        await interaction.response.edit_message(
            embed=self.wizard.build_skills_embed(),
            view=SkillsStepView(self.wizard),
        )


class RaceChoicesStepView(discord.ui.View):
    def __init__(self, wizard: CreerPersoWizard):
        super().__init__(timeout=600)
        self.wizard = wizard
        race_id = wizard.state.race_id or ""
        if race_id == "dragonborn":
            self.add_item(DraconicAncestrySelect(wizard))
        elif race_id == "half_elf":
            self.add_item(HalfElfAbilitySelect(wizard))
            self.add_item(HalfElfSkillSelect(wizard))
        self.add_item(RaceChoicesContinueButton(wizard))


class DomainSelect(discord.ui.Select):
    def __init__(self, wizard: CreerPersoWizard):
        self.wizard = wizard
        options: list[discord.SelectOption] = []
        for domain_id in get_cleric_domain_options(wizard.engine):
            trait = wizard.engine.get_entity("trait", f"{domain_id}_domain")
            label = (
                trait.get_name(wizard.state.locale, wizard.engine.registry.manifest.default_locale)
                if trait
                else domain_id.replace("_", " ").title()
            )
            options.append(
                discord.SelectOption(label=label[:100], value=domain_id)
            )
        super().__init__(
            placeholder="▼ Domaine divin",
            options=options,
            min_values=1,
            max_values=1,
            row=0,
        )

    async def callback(self, interaction: discord.Interaction):
        if not _owner_check(interaction, self.wizard.state.owner_id):
            await interaction.response.send_message("Action non autorisée.", ephemeral=True)
            return
        self.wizard.state.specialization = self.values[0]
        await interaction.response.edit_message(
            embed=self.wizard.build_domain_embed(),
            view=DomainStepView(self.wizard),
        )


class DomainConfirmButton(discord.ui.Button):
    def __init__(self, wizard: CreerPersoWizard):
        super().__init__(
            label="Finaliser le personnage →",
            style=discord.ButtonStyle.success,
            row=1,
            disabled=wizard.state.specialization is None,
        )
        self.wizard = wizard

    async def callback(self, interaction: discord.Interaction):
        if not _owner_check(interaction, self.wizard.state.owner_id):
            await interaction.response.send_message("Action non autorisée.", ephemeral=True)
            return
        if not self.wizard.state.specialization:
            await interaction.response.send_message(
                embed=discord.Embed(
                    title="⚠️ Domaine requis",
                    description="Choisissez un **domaine divin**.",
                    color=COULEUR_ERREUR,
                ).set_footer(text=FOOTER),
                ephemeral=True,
            )
            return
        await self.wizard.finalize(interaction)


class DomainStepView(discord.ui.View):
    def __init__(self, wizard: CreerPersoWizard):
        super().__init__(timeout=600)
        self.wizard = wizard
        if get_cleric_domain_options(wizard.engine):
            self.add_item(DomainSelect(wizard))
        self.add_item(DomainConfirmButton(wizard))


class CreerPersoWizard:
    def __init__(
        self,
        *,
        state: CreerPersoState,
        engine: RuleEngine,
        character_service: CharacterService,
    ):
        self.state = state
        self.engine = engine
        self.character_service = character_service

    def build_identity_embed(self) -> discord.Embed:
        race = (
            self.engine.get_display_name("race", self.state.race_id, self.state.locale)
            if self.state.race_id
            else "—"
        )
        classe = (
            self.engine.get_display_name("class", self.state.class_id, self.state.locale)
            if self.state.class_id
            else "—"
        )
        return discord.Embed(
            title=f"🎭 Création — {self.state.name}",
            description=(
                "**Étape 1 — Identité**\n"
                f"Race : **{race}**\n"
                f"Classe : **{classe}**\n\n"
                "Seuls le **Magicien** et le **Clerc** sont jouables (niv. 1)."
            ),
            color=COULEUR_PRINCIPALE,
        ).set_footer(text=FOOTER)

    def build_point_buy_view(self) -> PointBuyDistributionView:
        return PointBuyDistributionView(
            state=self.state.point_buy,
            owner_id=self.state.owner_id,
            title=f"🎭 Création — {self.state.name}",
            step_description="**Étape 2 — 📊 Répartir les points (SRD 2014)**",
            on_confirm=self._on_point_buy_confirmed,
        )

    async def _on_point_buy_confirmed(
        self, interaction: discord.Interaction, _state: PointBuyState
    ) -> None:
        if race_needs_creation_step(self.state.race_id or ""):
            await interaction.response.edit_message(
                embed=self.build_race_choices_embed(),
                view=RaceChoicesStepView(self),
            )
        else:
            await interaction.response.edit_message(
                embed=self.build_skills_embed(),
                view=SkillsStepView(self),
            )

    def build_race_choices_embed(self) -> discord.Embed:
        race_id = self.state.race_id or ""
        if race_id == "dragonborn":
            label = "—"
            if self.state.draconic_ancestry:
                anc = get_draconic_ancestry(self.state.draconic_ancestry)
                label = anc.label_fr if anc else self.state.draconic_ancestry
            description = (
                "**Étape 2b — 🐉 Ascendance draconique**\n"
                "Choisissez la couleur de votre ascendance (souffle + résistance).\n\n"
                f"Ascendance : **{label}**"
            )
        elif race_id == "half_elf":
            ability_labels = (
                ", ".join(a.upper() for a in self.state.racial_ability_bonuses)
                if self.state.racial_ability_bonuses
                else "—"
            )
            skill_labels = (
                ", ".join(skill_label_fr(s) for s in self.state.racial_skills)
                if self.state.racial_skills
                else "—"
            )
            description = (
                "**Étape 2b — 🌿 Choix Demi-elfe**\n"
                "+1 à **2 caractéristiques** (hors CHA) et **2 compétences** au choix.\n\n"
                f"Caractéristiques : **{ability_labels}**\n"
                f"Compétences : **{skill_labels}**"
            )
        else:
            description = "**Étape 2b — Choix raciaux**"
        return discord.Embed(
            title=f"🎭 Création — {self.state.name}",
            description=description,
            color=COULEUR_PRINCIPALE,
        ).set_footer(text=FOOTER)

    def build_skills_embed(self) -> discord.Embed:
        config = get_skill_choice_config(self.engine, self.state.class_id or "")
        count = config.count if config else 0
        selected = self.state.selected_skills
        if selected:
            labels = ", ".join(skill_label_fr(s) for s in selected)
        else:
            labels = "—"
        return discord.Embed(
            title=f"🎭 Création — {self.state.name}",
            description=(
                "**Étape 3 — 🎯 Compétences maîtrisées**\n"
                f"Choisissez **{count}** compétence(s) parmi la liste SRD.\n\n"
                f"Sélection : **{labels}**"
            ),
            color=COULEUR_PRINCIPALE,
        ).set_footer(text=FOOTER)

    def build_domain_embed(self) -> discord.Embed:
        domain_label = "—"
        if self.state.specialization:
            trait = self.engine.get_entity(
                "trait", f"{self.state.specialization}_domain"
            )
            if trait:
                domain_label = trait.get_name(
                    self.state.locale,
                    self.engine.registry.manifest.default_locale,
                )
            else:
                domain_label = self.state.specialization
        return discord.Embed(
            title=f"🎭 Création — {self.state.name}",
            description=(
                "**Étape 4 — ✨ Domaine divin (Clerc)**\n"
                "SRD 2014 : choisissez votre domaine (capacités = plus tard).\n\n"
                f"Domaine : **{domain_label}**"
            ),
            color=COULEUR_PRINCIPALE,
        ).set_footer(text=FOOTER)

    async def finalize(self, interaction: discord.Interaction) -> None:
        if self.state.done:
            await interaction.response.send_message(
                "Création déjà terminée.", ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=True)

        try:
            character = self.character_service.create_from_wizard(
                owner_id=str(self.state.owner_id),
                guild_id=self.state.guild_id,
                name=self.state.name,
                race_id=self.state.race_id or "human",
                class_id=self.state.class_id or "wizard",
                base_scores=dict(self.state.point_buy.base_scores),
                skills=self.state.selected_skills,
                specialization=self.state.specialization,
                draconic_ancestry=self.state.draconic_ancestry,
                racial_ability_bonuses=self.state.racial_ability_bonuses,
                racial_skills=self.state.racial_skills,
                locale=self.state.locale,
            )
        except CharacterValidationError as exc:
            await interaction.edit_original_response(
                embed=discord.Embed(
                    title="❌ Création impossible",
                    description=str(exc),
                    color=COULEUR_ERREUR,
                ).set_footer(text=FOOTER),
                view=None,
            )
            return

        self.state.done = True
        sheet = self.character_service.get_sheet(
            GetCharacterSheetQuery(
                character_id=character.id,
                owner_id=str(self.state.owner_id),
                locale=self.state.locale,
            )
        )
        display = build_character_display(sheet, self.engine, locale=self.state.locale)
        display.embed.title = f"🎉 {self.state.name} — prêt à l'aventure !"
        display.embed.color = discord.Color(COULEUR_SUCCES)
        desc = display.embed.description or ""
        display.embed.description = (
            f"{desc}\n\n"
            "**Finalisation**\n"
            "Votre personnage est enregistré. Utilisez `/perso-afficher` et `/sort`."
        )
        display.embed.set_footer(text=FOOTER)

        if display.files:
            await interaction.edit_original_response(
                embed=display.embed,
                attachments=display.files,
                view=None,
            )
        else:
            await interaction.edit_original_response(
                embed=display.embed,
                view=None,
            )


async def start_creer_perso_wizard(interaction: discord.Interaction, ctx) -> None:
    """Point d'entrée /creer-perso."""
    assert ctx.rule_engine and ctx.character_service

    if interaction.guild is None:
        await interaction.response.send_message(
            embed=discord.Embed(
                title="❌ Serveur requis",
                description="Créez votre personnage sur un serveur Discord (pas en MP).",
                color=COULEUR_ERREUR,
            ).set_footer(text=FOOTER),
            ephemeral=True,
        )
        return

    state = CreerPersoState(
        owner_id=interaction.user.id,
        guild_id=str(interaction.guild.id),
        name="",
    )
    wizard = CreerPersoWizard(
        state=state,
        engine=ctx.rule_engine,
        character_service=ctx.character_service,
    )
    await interaction.response.send_modal(ModalNomCreerPerso(wizard))
