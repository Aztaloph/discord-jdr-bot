# interfaces/discord/components/point_buy_distribution.py
"""
Distribution point buy SRD 2014 — composant réutilisable (création, montée de niveau Lot 2).

Budget 27 pts, scores 8–15 avant bonus raciaux.
"""
from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field

import discord

from jdr_engine.domain.character.ability_scores import DEFAULT_ABILITY_IDS
from jdr_engine.rules.character_creation.point_buy import (
    POINT_BUY_BUDGET,
    can_decrease_score,
    can_increase_score,
    points_remaining,
    validate_point_buy_scores,
)

from interfaces.discord.formatters.character_embed import (
    ABILITY_ABBREV,
    COULEUR_ERREUR,
    COULEUR_PRINCIPALE,
)

FOOTER = "JDR Bot — D&D 5e SRD 2014"
_ACTION_ROW = 4


@dataclass
class PointBuyState:
    """Scores de base 8–15 — réutilisable hors flux création."""

    base_scores: dict[str, int] = field(
        default_factory=lambda: dict.fromkeys(DEFAULT_ABILITY_IDS, 8)
    )

    @classmethod
    def fresh(cls) -> PointBuyState:
        return cls(base_scores=dict.fromkeys(DEFAULT_ABILITY_IDS, 8))


def scores_block(state: PointBuyState) -> str:
    lines = []
    for aid in DEFAULT_ABILITY_IDS:
        abbrev = ABILITY_ABBREV.get(aid, aid.upper())
        lines.append(f"**{abbrev}** {state.base_scores.get(aid, 8)}")
    return "\n".join(lines)


def build_point_buy_embed(
    *,
    title: str,
    step_description: str,
    state: PointBuyState,
) -> discord.Embed:
    remaining = points_remaining(state.base_scores)
    return discord.Embed(
        title=title,
        description=(
            f"{step_description}\n"
            f"Budget : **{POINT_BUY_BUDGET} pts** · Restants : **{remaining}**\n"
            "Scores **8–15** avant bonus raciaux.\n\n"
            + scores_block(state)
        ),
        color=COULEUR_PRINCIPALE,
    ).set_footer(text=FOOTER)


ConfirmCallback = Callable[[discord.Interaction, PointBuyState], Awaitable[None]]


class AbilityAdjustButton(discord.ui.Button):
    def __init__(
        self,
        state: PointBuyState,
        owner_id: int,
        ability_id: str,
        delta: int,
        row: int,
        *,
        view_ref: PointBuyDistributionView,
    ):
        abbrev = ABILITY_ABBREV.get(ability_id, ability_id.upper())
        label = f"{abbrev} {'+' if delta > 0 else '−'}"
        super().__init__(label=label, style=discord.ButtonStyle.secondary, row=row)
        self.state = state
        self.owner_id = owner_id
        self.ability_id = ability_id
        self.delta = delta
        self.view_ref = view_ref

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("Action non autorisée.", ephemeral=True)
            return
        scores = self.state.base_scores
        if self.delta > 0 and can_increase_score(scores, self.ability_id):
            scores[self.ability_id] += 1
        elif self.delta < 0 and can_decrease_score(scores, self.ability_id):
            scores[self.ability_id] -= 1
        await interaction.response.edit_message(
            embed=self.view_ref.build_embed(),
            view=self.view_ref,
        )


class PointBuyConfirmButton(discord.ui.Button):
    def __init__(
        self,
        state: PointBuyState,
        owner_id: int,
        on_confirm: ConfirmCallback,
        *,
        row: int = _ACTION_ROW,
    ):
        super().__init__(
            label="Valider les caractéristiques →",
            style=discord.ButtonStyle.success,
            row=row,
        )
        self.state = state
        self.owner_id = owner_id
        self.on_confirm = on_confirm

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("Action non autorisée.", ephemeral=True)
            return
        try:
            validate_point_buy_scores(self.state.base_scores)
        except ValueError as exc:
            await interaction.response.send_message(
                embed=discord.Embed(
                    title="❌ Point buy invalide",
                    description=str(exc),
                    color=COULEUR_ERREUR,
                ).set_footer(text=FOOTER),
                ephemeral=True,
            )
            return
        if points_remaining(self.state.base_scores) != 0:
            await interaction.response.send_message(
                embed=discord.Embed(
                    title="⚠️ Points non dépensés",
                    description=(
                        f"Il reste **{points_remaining(self.state.base_scores)}** "
                        f"point(s) sur {POINT_BUY_BUDGET}."
                    ),
                    color=COULEUR_ERREUR,
                ).set_footer(text=FOOTER),
                ephemeral=True,
            )
            return
        await self.on_confirm(interaction, self.state)


class PointBuyDistributionView(discord.ui.View):
    """Vue +/- point buy — réutilisable dans d'autres flux (Lot 2)."""

    def __init__(
        self,
        *,
        state: PointBuyState,
        owner_id: int,
        title: str,
        step_description: str,
        on_confirm: ConfirmCallback,
    ):
        super().__init__(timeout=600)
        self.state = state
        self.owner_id = owner_id
        self.title = title
        self.step_description = step_description
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
                AbilityAdjustButton(
                    state, owner_id, aid, delta, row, view_ref=self
                )
            )
        self.add_item(
            PointBuyConfirmButton(state, owner_id, on_confirm, row=_ACTION_ROW)
        )

    def build_embed(self) -> discord.Embed:
        return build_point_buy_embed(
            title=self.title,
            step_description=self.step_description,
            state=self.state,
        )

    async def on_timeout(self) -> None:
        for item in self.children:
            if isinstance(item, discord.ui.Item):
                item.disabled = True
