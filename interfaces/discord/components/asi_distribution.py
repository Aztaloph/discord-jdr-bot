# interfaces/discord/components/asi_distribution.py
"""Distribution ASI (+/−) — montée de niveau niv. 4+."""
from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field

import discord

from jdr_engine.domain.character.ability_scores import (
    DEFAULT_ABILITY_IDS,
    ability_modifier,
    format_modifier,
)
from jdr_engine.domain.character.effective_scores import compute_effective_ability_scores
from jdr_engine.rules.character_progression.asi import (
    ASI_POINT_BUDGET,
    can_decrease_asi,
    can_increase_asi,
    is_asi_pending_complete,
    asi_points_remaining,
)
from jdr_engine.rules.character_progression.level_up import LevelUpPending
from jdr_engine.rules.racial.resolve import get_racial_ability_bonuses

from interfaces.discord.formatters.character_embed import (
    ABILITY_ABBREV,
    COULEUR_ERREUR,
    COULEUR_SUCCES,
)

FOOTER = "JDR Bot — D&D 5e SRD 2014"
_ACTION_ROW = 4


@dataclass
class AsiDistributionState:
    """État UI — bases persistées + répartition ASI en cours (+/−)."""

    original_base: dict[str, int]
    racial_bonuses: dict[str, int]
    pending_bonuses: dict[str, int] = field(
        default_factory=lambda: dict.fromkeys(DEFAULT_ABILITY_IDS, 0)
    )

    @classmethod
    def from_character(cls, character, *, engine) -> AsiDistributionState:
        original_base = character.ability_scores.with_defaults(
            list(DEFAULT_ABILITY_IDS)
        ).scores
        return cls(
            original_base=dict(original_base),
            racial_bonuses=get_racial_ability_bonuses(character, engine),
        )

    def pending_dict(self) -> dict[str, int]:
        return {aid: int(self.pending_bonuses.get(aid, 0)) for aid in DEFAULT_ABILITY_IDS}


def _effective_after_pending(state: AsiDistributionState) -> dict[str, int]:
    trial_base = dict(state.original_base)
    for aid in DEFAULT_ABILITY_IDS:
        delta = int(state.pending_bonuses.get(aid, 0))
        if delta:
            trial_base[aid] = trial_base.get(aid, 10) + delta
    return compute_effective_ability_scores(trial_base, state.racial_bonuses)


def build_asi_scores_block(state: AsiDistributionState) -> str:
    """Lignes par stat ; format détaillé pour les stats touchées."""
    effective = _effective_after_pending(state)
    lines: list[str] = []
    for aid in DEFAULT_ABILITY_IDS:
        abbrev = ABILITY_ABBREV.get(aid, aid.upper())
        base = state.original_base.get(aid, 10)
        pending = int(state.pending_bonuses.get(aid, 0))
        eff = effective.get(aid, 10)
        mod = format_modifier(ability_modifier(eff))
        if pending > 0:
            new_base = base + pending
            lines.append(f"**{abbrev}** {base}→{new_base} (eff. {eff} ({mod}))")
        else:
            lines.append(f"**{abbrev}** {base} (eff. {eff} ({mod}))")
    return "\n".join(lines)


def build_asi_embed(
    *,
    pending: LevelUpPending,
    state: AsiDistributionState,
) -> discord.Embed:
    remaining = asi_points_remaining(state.pending_dict())
    return discord.Embed(
        title=f"⬆️ Amélioration de caractéristiques — {pending.character.name}",
        description=(
            f"**{pending.character.name}** passe au **niveau {pending.target_level}**.\n\n"
            f"{pending.message}\n\n"
            f"Budget ASI : **{ASI_POINT_BUDGET} pts** · Restants : **{remaining}**\n"
            "Les **+**/**−** modifient la **base** ; l'effectif inclut le racial.\n\n"
            + build_asi_scores_block(state)
        ),
        color=COULEUR_SUCCES,
    ).set_footer(text=FOOTER)


AsiConfirmCallback = Callable[
    [discord.Interaction, AsiDistributionState, dict[str, int]],
    Awaitable[None],
]


class AsiAdjustButton(discord.ui.Button):
    def __init__(
        self,
        state: AsiDistributionState,
        owner_id: int,
        ability_id: str,
        delta: int,
        row: int,
        *,
        view_ref: "AsiDistributionView",
    ):
        abbrev = ABILITY_ABBREV.get(ability_id, ability_id.upper())
        label = f"{abbrev} {'+' if delta > 0 else '−'}"
        disabled = False
        pending = state.pending_dict()
        if delta > 0:
            disabled = not can_increase_asi(
                state.original_base,
                state.racial_bonuses,
                pending,
                ability_id,
            )
        else:
            disabled = not can_decrease_asi(pending, ability_id)
        super().__init__(
            label=label,
            style=discord.ButtonStyle.secondary,
            row=row,
            disabled=disabled,
        )
        self.state = state
        self.owner_id = owner_id
        self.ability_id = ability_id
        self.delta = delta
        self.view_ref = view_ref

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("Action non autorisée.", ephemeral=True)
            return
        pending = self.state.pending_dict()
        if self.delta > 0 and can_increase_asi(
            self.state.original_base,
            self.state.racial_bonuses,
            pending,
            self.ability_id,
        ):
            self.state.pending_bonuses[self.ability_id] = (
                int(self.state.pending_bonuses.get(self.ability_id, 0)) + 1
            )
        elif self.delta < 0 and can_decrease_asi(pending, self.ability_id):
            self.state.pending_bonuses[self.ability_id] = (
                int(self.state.pending_bonuses.get(self.ability_id, 0)) - 1
            )
        await interaction.response.edit_message(
            embed=self.view_ref.build_embed(),
            view=AsiDistributionView(
                pending=self.view_ref.pending,
                engine=self.view_ref.engine,
                character_service=self.view_ref.character_service,
                guild_id=self.view_ref.guild_id,
                character_id=self.view_ref.character_id,
                state=self.state,
                owner_id=self.owner_id,
                on_confirm=self.view_ref.on_confirm,
            ),
        )


class AsiConfirmButton(discord.ui.Button):
    def __init__(
        self,
        state: AsiDistributionState,
        owner_id: int,
        on_confirm: AsiConfirmCallback,
        *,
        row: int = _ACTION_ROW,
    ):
        super().__init__(
            label="Confirmer ASI →",
            style=discord.ButtonStyle.success,
            row=row,
            disabled=not is_asi_pending_complete(state.pending_dict()),
        )
        self.state = state
        self.owner_id = owner_id
        self.on_confirm = on_confirm

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("Action non autorisée.", ephemeral=True)
            return
        pending = self.state.pending_dict()
        if not is_asi_pending_complete(pending):
            await interaction.response.send_message(
                embed=discord.Embed(
                    title="⚠️ ASI incomplet",
                    description=(
                        f"Dépensez exactement **{ASI_POINT_BUDGET}** points "
                        f"(restants : **{asi_points_remaining(pending)}**)."
                    ),
                    color=COULEUR_ERREUR,
                ).set_footer(text=FOOTER),
                ephemeral=True,
            )
            return
        asi_choice = {
            aid: int(value)
            for aid, value in pending.items()
            if int(value) > 0
        }
        await self.on_confirm(interaction, self.state, asi_choice)


class AsiDistributionView(discord.ui.View):
    """Vue +/- ASI — même grille que le point buy création."""

    def __init__(
        self,
        *,
        pending: LevelUpPending,
        engine,
        character_service,
        guild_id: str,
        character_id: str,
        state: AsiDistributionState,
        owner_id: int,
        on_confirm: AsiConfirmCallback,
    ):
        super().__init__(timeout=600)
        self.pending = pending
        self.engine = engine
        self.character_service = character_service
        self.guild_id = guild_id
        self.character_id = character_id
        self.state = state
        self.owner_id = owner_id
        self.on_confirm = on_confirm

        layout: list[tuple[str, int, int]] = [
            ("str", -1, 0),
            ("str", 1, 0),
            ("dex", -1, 0),
            ("dex", 1, 0),
            ("con", -1, 1),
            ("con", 1, 1),
            ("int", -1, 1),
            ("int", 1, 1),
            ("wis", -1, 2),
            ("wis", 1, 2),
            ("cha", -1, 2),
            ("cha", 1, 2),
        ]
        for aid, delta, row in layout:
            self.add_item(
                AsiAdjustButton(
                    state, owner_id, aid, delta, row, view_ref=self
                )
            )
        self.add_item(
            AsiConfirmButton(state, owner_id, self.on_confirm, row=_ACTION_ROW)
        )

    def build_embed(self) -> discord.Embed:
        return build_asi_embed(pending=self.pending, state=self.state)

    async def on_timeout(self) -> None:
        for item in self.children:
            if isinstance(item, discord.ui.Item):
                item.disabled = True
