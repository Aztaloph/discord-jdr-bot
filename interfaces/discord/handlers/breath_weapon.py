# interfaces/discord/handlers/breath_weapon.py
"""Handler /souffle — souffle draconique Drakéide."""
from __future__ import annotations

import discord

from jdr_engine.application.character_service import CharacterNotFoundError
from jdr_engine.dice import DiceError
from jdr_engine.rules.racial.breath_weapon import BreathWeaponError, use_breath_weapon

from interfaces.discord.container import DiscordJdrContext
from interfaces.discord.formatters.character_embed import COULEUR_ERREUR

FOOTER = "JDR Bot — D&D 5e SRD 2014"
COLOR_BREATH = discord.Color(0xE67E22)


def build_breath_embed(result) -> discord.Embed:
    embed = discord.Embed(
        title=f"🐉 Souffle draconique — {result.character_name}",
        description=(
            f"**Ascendance {result.ancestry_label}** · {result.shape} "
            f"{result.area_ft} ft\n"
            f"**Dégâts** : {result.damage_total} ({result.damage_dice} "
            f"{result.damage_type_label})\n"
            f"**DD de sauvegarde** : {result.save_dc} "
            f"(8 + {result.con_modifier} CON + maîtrise)\n\n"
            "_Les cibles qui réussissent leur sauvegarde de Constitution "
            "subissent la moitié des dégâts._"
        ),
        color=COLOR_BREATH,
    )
    embed.set_footer(text=f"{FOOTER} · Action raciale")
    return embed


def execute_breath_weapon(
    ctx: DiscordJdrContext,
    *,
    owner_id: int,
    perso: str | None,
    guild_id: str | None,
):
    if not ctx.use_engine_v2 or ctx.character_service is None:
        raise DiceError("Moteur v2 requis.")
    if guild_id is None:
        raise DiceError("Cette commande doit être utilisée sur un serveur.")
    try:
        character = ctx.character_service.resolve_for_game(
            str(owner_id), guild_id, perso
        )
    except CharacterNotFoundError as exc:
        raise DiceError(str(exc)) from exc
    if ctx.rule_engine is None:
        raise DiceError("Moteur de règles indisponible.")
    try:
        return use_breath_weapon(character, ctx.rule_engine)
    except BreathWeaponError as exc:
        raise DiceError(str(exc)) from exc
