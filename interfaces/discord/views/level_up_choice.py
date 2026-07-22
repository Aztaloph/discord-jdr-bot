# interfaces/discord/views/level_up_choice.py
"""Choix lors du /monter-niveau (style, sous-classe, compétences niv. 3)."""
from __future__ import annotations

import logging

import discord

from jdr_engine.application.character_service import CharacterNotFoundError, CharacterService
from jdr_engine.domain.character.choices_schema import get_specialization_id
from jdr_engine.rules.character_progression import LevelUpError, LevelUpPending, LevelUpPendingChoice
from jdr_engine.rules.derived_stats import skill_label_fr
from jdr_engine.rules.engine import RuleEngine

from interfaces.discord.components.asi_distribution import (
    AsiConfirmCallback,
    AsiDistributionState,
    AsiDistributionView,
)

from interfaces.discord.formatters.character_embed import COULEUR_ERREUR, COULEUR_SUCCES

logger = logging.getLogger(__name__)
FOOTER = "JDR Bot — D&D 5e SRD 2014"


def build_level_up_embed(result) -> "discord.Embed":
    import discord

    embed = discord.Embed(
        title=f"⬆️ Montée de niveau — {result.character_name}",
        description=(
            f"**Niveau** : {result.old_level} → **{result.new_level}**\n"
            f"**PV** : {result.hp_before}/{result.hp_max_before} → "
            f"**{result.hp_after}/{result.hp_max_after}** (+{result.hp_gain})\n"
            f"**Dés de vie** : {result.hit_dice_before} → **{result.hit_dice_after}** "
            f"(total)\n"
            f"**Emplacements max** : {result.slots_max_before} → "
            f"**{result.slots_max_after}**"
        ),
        color=COULEUR_SUCCES,
    )
    embed.set_footer(text=FOOTER)
    return embed


def _option_label(engine: RuleEngine, option_id: str, locale: str = "fr") -> str:
    trait = engine.get_entity("trait", option_id)
    if trait is not None:
        return trait.get_name(locale, engine.registry.manifest.default_locale)
    if option_id == "bear":
        return "Esprit de l'ours"
    if option_id == "eagle":
        return "Esprit de l'aigle"
    if option_id == "wolf":
        return "Esprit du loup"
    style_trait = engine.get_entity("trait", f"fighting_style_{option_id}")
    if style_trait is not None:
        return style_trait.get_name(locale, engine.registry.manifest.default_locale)
    return option_id.replace("_", " ").title()


def _subclass_kwarg(pending: LevelUpPending) -> str | None:
    return pending.parent_subclass or get_specialization_id(pending.character.choices)


async def _edit_level_up_message(
    interaction: discord.Interaction,
    *,
    embed: discord.Embed,
    view: discord.ui.View | None = None,
) -> None:
    """Édite le message de montée de niveau (slash ou composant)."""
    if interaction.response.is_done():
        await interaction.edit_original_response(embed=embed, view=view)
    else:
        await interaction.response.edit_message(embed=embed, view=view)


async def _handle_level_up_result(
    interaction: discord.Interaction,
    *,
    engine: RuleEngine,
    character_service: CharacterService,
    guild_id: str,
    character_id: str,
    result,
) -> None:
    await _edit_level_up_message(
        interaction,
        embed=build_level_up_embed(result),
        view=None,
    )


async def _handle_level_up_pending(
    interaction: discord.Interaction,
    exc: LevelUpPendingChoice,
    *,
    engine: RuleEngine,
    character_service: CharacterService,
    guild_id: str,
    character_id: str,
) -> None:
    pending = exc.pending

    async def on_asi_confirm(
        interaction: discord.Interaction,
        _state: AsiDistributionState,
        asi_choice: dict[str, int],
    ) -> None:
        await _on_asi_distribution_confirmed(
            interaction,
            asi_choice,
            pending=pending,
            engine=engine,
            character_service=character_service,
            guild_id=guild_id,
            character_id=character_id,
        )

    view, embed = build_level_up_pending_ui(
        pending,
        engine=engine,
        character_service=character_service,
        guild_id=guild_id,
        character_id=character_id,
        on_asi_confirm=on_asi_confirm,
    )
    await _edit_level_up_message(
        interaction,
        embed=embed,
        view=view,
    )


def build_level_up_pending_ui(
    pending: LevelUpPending,
    *,
    engine: RuleEngine,
    character_service: CharacterService,
    guild_id: str,
    character_id: str,
    on_asi_confirm: AsiConfirmCallback,
) -> tuple[discord.ui.View, discord.Embed]:
    """Vue + embed pour un choix de montée de niveau en attente (testable)."""
    if pending.choice_type == "ability_score_improvement":
        state = AsiDistributionState.from_character(pending.character, engine=engine)
        owner_id = int(pending.character.owner_id)
        view: discord.ui.View = AsiDistributionView(
            pending=pending,
            engine=engine,
            character_service=character_service,
            guild_id=guild_id,
            character_id=character_id,
            state=state,
            owner_id=owner_id,
            on_confirm=on_asi_confirm,
        )
        embed = view.build_embed()
    else:
        view = LevelUpChoiceView(
            pending,
            engine,
            character_service,
            guild_id,
            character_id,
        )
        embed = _pending_embed(pending)
    return view, embed


async def _on_asi_distribution_confirmed(
    interaction: discord.Interaction,
    asi_choice: dict[str, int],
    *,
    pending: LevelUpPending,
    engine: RuleEngine,
    character_service: CharacterService,
    guild_id: str,
    character_id: str,
) -> None:
    await interaction.response.defer(ephemeral=True)
    try:
        result = character_service.complete_level_up_choice_on_guild(
            character_id,
            guild_id,
            asi_choice=asi_choice,
            base_character=pending.character,
        )
    except LevelUpPendingChoice as exc:
        await _handle_level_up_pending(
            interaction,
            exc,
            engine=engine,
            character_service=character_service,
            guild_id=guild_id,
            character_id=character_id,
        )
        return
    except LevelUpError as exc:
        await _handle_level_up_error(interaction, exc)
        return

    await _handle_level_up_result(
        interaction,
        engine=engine,
        character_service=character_service,
        guild_id=guild_id,
        character_id=character_id,
        result=result,
    )


async def _handle_level_up_error(
    interaction: discord.Interaction,
    exc: LevelUpError,
) -> None:
    await _edit_level_up_message(
        interaction,
        embed=discord.Embed(
            title="⚠️ Montée de niveau impossible",
            description=str(exc),
            color=COULEUR_ERREUR,
        ).set_footer(text=FOOTER),
        view=None,
    )


class LevelUpSubclassSelect(discord.ui.Select):
    def __init__(
        self,
        pending: LevelUpPending,
        engine: RuleEngine,
        character_service: CharacterService,
        guild_id: str,
        character_id: str,
    ):
        self.pending = pending
        self.engine = engine
        self.character_service = character_service
        self.guild_id = guild_id
        self.character_id = character_id
        options = [
            discord.SelectOption(
                label=_option_label(engine, opt)[:100],
                value=opt,
            )
            for opt in pending.options
        ]
        if pending.choice_type == "fighting_style":
            placeholder = "▼ Style de combat (niv. 2)"
        elif pending.choice_type == "subchoice":
            placeholder = "▼ Option de sous-classe"
        elif pending.choice_type == "pact_boon":
            placeholder = "▼ Faveur du pacte (niv. 3)"
        else:
            placeholder = "▼ Sous-classe (niv. 3)"
        super().__init__(
            placeholder=placeholder,
            options=options,
            min_values=1,
            max_values=1,
        )

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        choice = self.values[0]
        try:
            if self.pending.choice_type == "fighting_style":
                result = self.character_service.complete_level_up_choice_on_guild(
                    self.character_id,
                    self.guild_id,
                    fighting_style=choice,
                    base_character=self.pending.character,
                )
            elif self.pending.choice_type == "subchoice":
                kwargs: dict = {
                    "subchoice_value": choice,
                    "base_character": self.pending.character,
                }
                if self.pending.parent_subclass:
                    kwargs["subclass"] = self.pending.parent_subclass
                if self.pending.subchoice_storage_key == "totem_spirit":
                    kwargs["totem_spirit"] = choice
                result = self.character_service.complete_level_up_choice_on_guild(
                    self.character_id,
                    self.guild_id,
                    **kwargs,
                )
            elif self.pending.choice_type == "pact_boon":
                try:
                    result = self.character_service.complete_level_up_choice_on_guild(
                        self.character_id,
                        self.guild_id,
                        pact_boon=choice,
                        base_character=self.pending.character,
                    )
                except LevelUpPendingChoice as exc:
                    await _handle_level_up_pending(
                        interaction,
                        exc,
                        engine=self.engine,
                        character_service=self.character_service,
                        guild_id=self.guild_id,
                        character_id=self.character_id,
                    )
                    return
            else:
                try:
                    result = self.character_service.complete_level_up_choice_on_guild(
                        self.character_id,
                        self.guild_id,
                        subclass=choice,
                        base_character=self.pending.character,
                    )
                except LevelUpPendingChoice as exc:
                    await _handle_level_up_pending(
                        interaction,
                        exc,
                        engine=self.engine,
                        character_service=self.character_service,
                        guild_id=self.guild_id,
                        character_id=self.character_id,
                    )
                    return
        except LevelUpError as exc:
            await _handle_level_up_error(interaction, exc)
            return

        await _handle_level_up_result(
            interaction,
            engine=self.engine,
            character_service=self.character_service,
            guild_id=self.guild_id,
            character_id=self.character_id,
            result=result,
        )


class LevelUpMultiSelect(discord.ui.Select):
    """Multi-select avec confirmation — même principe que la création de perso."""

    def __init__(self, view: "LevelUpChoiceView"):
        self.level_view = view
        pending = view.pending
        count = pending.required_count
        if pending.choice_type == "lore_bonus_skills":
            placeholder = f"▼ Compétences bonus — {count} choix"
            options = [
                discord.SelectOption(
                    label=skill_label_fr(skill_id)[:100],
                    value=skill_id,
                )
                for skill_id in pending.options[:25]
            ]
        elif pending.choice_type == "metamagic_options":
            from jdr_engine.rules.class_features.sorcerer import METAMAGIC_LABELS_FR

            placeholder = f"▼ Métamagie — choisir {count}"
            options = [
                discord.SelectOption(
                    label=METAMAGIC_LABELS_FR.get(opt_id, opt_id)[:100],
                    value=opt_id,
                )
                for opt_id in pending.options[:25]
            ]
        elif pending.choice_type == "eldritch_invocations":
            from jdr_engine.rules.class_features.warlock import INVOCATION_LABELS_FR

            placeholder = f"▼ Manifestations occultes — choisir {count}"
            options = [
                discord.SelectOption(
                    label=INVOCATION_LABELS_FR.get(opt_id, opt_id)[:100],
                    value=opt_id,
                )
                for opt_id in pending.options[:25]
            ]
        else:
            placeholder = f"▼ Expertise — choisir {count}"
            options = [
                discord.SelectOption(
                    label=skill_label_fr(skill_id)[:100],
                    value=skill_id,
                )
                for skill_id in pending.options[:25]
            ]
        super().__init__(
            placeholder=placeholder,
            options=options,
            min_values=count,
            max_values=count,
            row=0,
        )

    async def callback(self, interaction: discord.Interaction):
        selected = list(self.values)
        new_view = LevelUpChoiceView(
            self.level_view.pending,
            self.level_view.engine,
            self.level_view.character_service,
            self.level_view.guild_id,
            self.level_view.character_id,
            selected_values=selected,
        )
        await interaction.response.edit_message(
            embed=_pending_embed(new_view.pending, selected),
            view=new_view,
        )


class LevelUpMultiConfirmButton(discord.ui.Button):
    def __init__(self, view: "LevelUpChoiceView"):
        required = view.pending.required_count
        super().__init__(
            label="Confirmer →",
            style=discord.ButtonStyle.success,
            row=1,
            disabled=len(view.selected_values) != required,
        )
        self.level_view = view

    async def callback(self, interaction: discord.Interaction):
        pending = self.level_view.pending
        required = pending.required_count
        selected = list(self.level_view.selected_values)

        if len(selected) != required:
            await interaction.response.send_message(
                embed=discord.Embed(
                    title="⚠️ Sélection incomplète",
                    description=f"Choisissez exactement **{required}** option(s).",
                    color=COULEUR_ERREUR,
                ).set_footer(text=FOOTER),
                ephemeral=True,
            )
            return

        await interaction.response.defer(ephemeral=True)
        subclass = _subclass_kwarg(pending)
        base = pending.character
        try:
            if pending.choice_type == "lore_bonus_skills":
                try:
                    result = self.level_view.character_service.complete_level_up_choice_on_guild(
                        self.level_view.character_id,
                        self.level_view.guild_id,
                        subclass=subclass,
                        lore_bonus_skills=selected,
                        base_character=base,
                    )
                except LevelUpPendingChoice as exc:
                    await _handle_level_up_pending(
                        interaction,
                        exc,
                        engine=self.level_view.engine,
                        character_service=self.level_view.character_service,
                        guild_id=self.level_view.guild_id,
                        character_id=self.level_view.character_id,
                    )
                    return
            else:
                lore_bonus = (base.choices or {}).get("lore_bonus_skills")
                kwargs: dict = {
                    "subclass": subclass,
                    "lore_bonus_skills": lore_bonus,
                    "base_character": base,
                }
                if pending.choice_type == "metamagic_options":
                    kwargs["metamagic_options"] = selected
                elif pending.choice_type == "eldritch_invocations":
                    kwargs["eldritch_invocations"] = selected
                else:
                    kwargs["expertise_skills"] = selected
                result = self.level_view.character_service.complete_level_up_choice_on_guild(
                    self.level_view.character_id,
                    self.level_view.guild_id,
                    **kwargs,
                )
        except LevelUpError as exc:
            await _handle_level_up_error(interaction, exc)
            return
        except CharacterNotFoundError as exc:
            logger.exception("Confirmer montée de niveau — personnage introuvable")
            await _handle_level_up_error(interaction, LevelUpError(str(exc)))
            return
        except Exception:
            logger.exception(
                "Confirmer montée de niveau — erreur (%s, perso=%s)",
                pending.choice_type,
                self.level_view.character_id,
            )
            await _handle_level_up_error(
                interaction,
                LevelUpError("Erreur interne lors de la finalisation. Réessayez."),
            )
            return

        logger.info(
            "Montée de niveau finalisée (%s) : %s → niv. %s",
            pending.choice_type,
            base.name,
            result.new_level,
        )
        await _handle_level_up_result(
            interaction,
            engine=self.level_view.engine,
            character_service=self.level_view.character_service,
            guild_id=self.level_view.guild_id,
            character_id=self.level_view.character_id,
            result=result,
        )


class LevelUpChoiceView(discord.ui.View):
    def __init__(
        self,
        pending: LevelUpPending,
        engine: RuleEngine,
        character_service: CharacterService,
        guild_id: str,
        character_id: str,
        *,
        selected_values: list[str] | None = None,
    ):
        super().__init__(timeout=600)
        self.pending = pending
        self.engine = engine
        self.character_service = character_service
        self.guild_id = guild_id
        self.character_id = character_id
        self.selected_values: list[str] = list(selected_values or [])

        if pending.choice_type == "ability_score_improvement":
            raise ValueError(
                "ASI : utiliser AsiDistributionView via build_level_up_pending_ui(), "
                "pas LevelUpChoiceView."
            )

        if pending.choice_type in (
            "lore_bonus_skills",
            "expertise_skills",
            "metamagic_options",
            "eldritch_invocations",
        ):
            self.add_item(LevelUpMultiSelect(self))
            self.add_item(LevelUpMultiConfirmButton(self))
        else:
            self.add_item(
                LevelUpSubclassSelect(
                    pending,
                    engine,
                    character_service,
                    guild_id,
                    character_id,
                )
            )


def _pending_embed(
    pending: LevelUpPending,
    selected: list[str] | None = None,
) -> discord.Embed:
    if pending.choice_type == "fighting_style":
        title = f"⬆️ Style de combat — {pending.character.name}"
    elif pending.choice_type == "subchoice":
        title = f"⬆️ Choix de sous-classe — {pending.character.name}"
    elif pending.choice_type == "lore_bonus_skills":
        title = f"⬆️ Compétences bonus — {pending.character.name}"
    elif pending.choice_type == "expertise_skills":
        title = f"⬆️ Expertise — {pending.character.name}"
    elif pending.choice_type == "metamagic_options":
        title = f"⬆️ Métamagie — {pending.character.name}"
    elif pending.choice_type == "eldritch_invocations":
        title = f"⬆️ Manifestations occultes — {pending.character.name}"
    elif pending.choice_type == "pact_boon":
        title = f"⬆️ Faveur du pacte — {pending.character.name}"
    elif pending.choice_type == "ability_score_improvement":
        title = f"⬆️ Amélioration de caractéristiques — {pending.character.name}"
    else:
        title = f"⬆️ Choix requis — {pending.character.name}"
    confirm_hint = (
        "Utilisez les boutons **+**/**−** pour répartir **2 points ASI**, puis **Confirmer ASI**."
        if pending.choice_type == "ability_score_improvement"
        else "Sélectionnez vos choix puis appuyez sur **Confirmer**."
    )
    description = (
        f"**{pending.character.name}** passe au **niveau {pending.target_level}**.\n\n"
        f"{pending.message}\n\n"
        f"{confirm_hint}"
    )
    if selected:
        if pending.choice_type == "ability_score_improvement":
            labels = [ABILITY_LABELS_FR.get(v, v) for v in selected]
        elif pending.choice_type == "metamagic_options":
            from jdr_engine.rules.class_features.sorcerer import METAMAGIC_LABELS_FR

            labels = [METAMAGIC_LABELS_FR.get(v, v) for v in selected]
        elif pending.choice_type == "eldritch_invocations":
            from jdr_engine.rules.class_features.warlock import INVOCATION_LABELS_FR

            labels = [INVOCATION_LABELS_FR.get(v, v) for v in selected]
        else:
            labels = [skill_label_fr(v) for v in selected]
        description += f"\n\n**Sélection ({len(selected)}/{pending.required_count})** : {', '.join(labels)}"
    return discord.Embed(
        title=title,
        description=description,
        color=COULEUR_SUCCES,
    ).set_footer(text=FOOTER)
