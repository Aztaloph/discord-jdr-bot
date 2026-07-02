# bot/cogs/dice.py
# Cog Discord — commande slash /roll pour le lancer de dés D&D 5e.
import logging

import discord
from discord import app_commands
from discord.app_commands import Choice
from discord.ext import commands

from bot.utils.dice_parser import DiceError, MAX_DICE, MAX_FACES
from interfaces.discord.handlers.character import character_name_autocomplete
from interfaces.discord.handlers.dice import RollDisplay, execute_roll

log = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Couleurs des embeds (thème sombre style Discord)
# ─────────────────────────────────────────────────────────────────────────────

COLOR_NORMAL = discord.Color(0x7289DA)
COLOR_AVANTAGE = discord.Color(0x57F286)
COLOR_DESAVANTAGE = discord.Color(0xF44336)
COLOR_TRAITS = discord.Color(0xE6B422)
COLOR_ERROR = discord.Color(0xF44336)


def _build_dice_display(rolls: list[int], is_kept: list[bool]) -> str:
    parts = []
    for val, kept in zip(rolls, is_kept):
        if kept:
            parts.append(f"**{val}**")
        else:
            parts.append(f"~~{val}~~")
    return "  ".join(parts)


def _build_embed(result: RollDisplay) -> discord.Embed:
    """Construit l'embed Discord pour afficher le résultat du lancer."""
    mode = result.mode
    color = {
        "normal": COLOR_NORMAL,
        "avantage": COLOR_AVANTAGE,
        "desavantage": COLOR_DESAVANTAGE,
    }.get(mode, COLOR_NORMAL)
    if result.traits_active:
        color = COLOR_TRAITS

    modifier_str = f" {result.modifier_label}" if result.modifier != 0 else ""
    dice_line = _build_dice_display(result.rolls, result.is_kept)

    title = "🎲 Lancer de dés"
    if result.traits_active and result.character_name:
        title = f"🎲 Lancer de dés — {result.character_name}"

    embed = discord.Embed(title=title, color=color)
    embed.description = (
        f"**{result.dice_notation}**\n"
        f"Dés : {dice_line}{modifier_str}\n"
        f"**Total = {result.total}**"
    )

    if result.rerolled:
        embed.add_field(
            name="🍀 Chanceux",
            value="1 naturel → relance obligatoire (SRD 5.1)",
            inline=False,
        )

    effects = [
        e for e in result.applied_effects if not e.startswith("hint:")
    ]
    hints = [e.removeprefix("hint:") for e in result.applied_effects if e.startswith("hint:")]

    if effects:
        embed.add_field(
            name="✨ Traits actifs",
            value="\n".join(f"• {e}" for e in effects),
            inline=False,
        )

    if len(result.rolls) > 1 and not result.rerolled:
        sum_kept = sum(r for r, k in zip(result.rolls, result.is_kept) if k)
        detail = f"Résultat conservé : {sum_kept}"
        if result.modifier != 0:
            detail += f" {result.modifier_label} = {result.total}"
        embed.add_field(name="Détail", value=detail, inline=False)

    footer = "JDR Bot — D&D 5e"
    if hints:
        footer = f"{hints[0]} · {footer}"
    embed.set_footer(text=footer)
    return embed


def _build_error_embed(error_msg: str) -> discord.Embed:
    embed = discord.Embed(
        title="❌ Erreur de lancer",
        description=error_msg,
        color=COLOR_ERROR,
    )
    embed.add_field(
        name="💡 Aide",
        value=(
            "**Syntaxe :** `XdY+Z`\n"
            "Exemples : `4d6`, `1d20+5`, `2d8-1`, `d20`, `d6`\n\n"
            f"• Nombre de dés max : **{MAX_DICE}**\n"
            f"• Faces max : **{MAX_FACES}**\n"
            "• **Avantage** : lance 2d20, garde le plus élevé\n"
            "• **Désavantage** : lance 2d20, garde le plus faible\n"
            "• **Perso** : active les traits (ex. Chanceux halfelin) sur un `d20`"
        ),
        inline=False,
    )
    return embed


MODE_CHOICES = [
    Choice(name="Normal", value="normal"),
    Choice(name="🤝 Avantage", value="avantage"),
    Choice(name="👎 Désavantage", value="desavantage"),
]


class DiceCog(commands.Cog):
    """Cog pour le système de dés D&D 5e."""

    def __init__(self, bot):
        self.bot = bot
        log.info("Cog DiceCog chargé.")

    def _jdr(self):
        return getattr(self.bot, "jdr", None)

    async def _perso_autocomplete(
        self,
        interaction: discord.Interaction,
        current: str,
    ) -> list[app_commands.Choice[str]]:
        ctx = self._jdr()
        if ctx is None or not ctx.use_engine_v2:
            return []
        return await character_name_autocomplete(interaction, current, ctx)

    @app_commands.command(
        name="roll",
        description="Lancer un dé D&D 5e. Exemples : 3d6+2, d20, 2d8-1",
    )
    @app_commands.describe(
        dé="Notation du dé (ex : 3d6+2, d20, 2d8-1, 4d6)",
        mode="Normal, Avantage (2d20 meilleur) ou Désavantage (2d20 pire)",
        perso="Personnage dont appliquer les traits (d20 uniquement)",
    )
    @app_commands.choices(mode=MODE_CHOICES)
    @app_commands.autocomplete(perso=_perso_autocomplete)
    async def roll_command(
        self,
        interaction: discord.Interaction,
        dé: str,
        mode: str = "normal",
        perso: str | None = None,
    ):
        await interaction.response.defer(ephemeral=False)

        try:
            ctx = self._jdr()
            result = execute_roll(
                dé,
                mode,
                ctx,
                interaction.user.id,
                perso=perso,
            )
            embed = _build_embed(result)
            await interaction.followup.send(embed=embed)
        except DiceError as e:
            embed = _build_error_embed(str(e))
            await interaction.followup.send(embed=embed, ephemeral=True)
        except Exception as e:
            log.exception("Erreur inattendue dans /roll : %s", e)
            await interaction.followup.send(
                embed=_build_error_embed("Une erreur inattendue s'est produite."),
                ephemeral=True,
            )


async def setup(bot):
    await bot.add_cog(DiceCog(bot))
