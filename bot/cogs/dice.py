# bot/cogs/dice.py
# Cog Discord — commande slash /roll pour le lancer de dés D&D 5e.
import logging

import discord
from discord import app_commands
from discord.app_commands import Choice
from discord.ext import commands

from bot.utils.dice_parser import roll, DiceError, MAX_DICE, MAX_FACES

log = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Couleurs des embeds (thème sombre style Discord)
# ─────────────────────────────────────────────────────────────────────────────

COLOR_NORMAL      = discord.Color(0x7289da)   # gris-bleu Discord
COLOR_AVANTAGE    = discord.Color(0x57F286)   # vert succès
COLOR_DESAVANTAGE = discord.Color(0xF44336)  # rouge danger
COLOR_ERROR      = discord.Color(0xF44336)


# ─────────────────────────────────────────────────────────────────────────────
# Fonction de formatage pour l'embed
# ─────────────────────────────────────────────────────────────────────────────

def _build_dice_display(rolls: list[int], is_kept: list[bool]) -> str:
    """
    Renvoie une chaîne stylisée pour les dés individuels.
    - Dés gardés : engras (discord Bold)
    - Dés jetés (non gardés en adv/disadv) : barrés (~~strike~~)
    """
    parts = []
    for val, kept in zip(rolls, is_kept):
        if kept:
            parts.append(f"**{val}**")
        else:
            parts.append(f"~~{val}~~")
    return "  ".join(parts)


def _build_embed(result, mode: str) -> discord.Embed:
    """Construit l'embed Discord pour afficher le résultat du lancer."""
    color = {
        "normal":      COLOR_NORMAL,
        "avantage":    COLOR_AVANTAGE,
        "desavantage": COLOR_DESAVANTAGE,
    }.get(mode, COLOR_NORMAL)

    modifier_str = f" {result.modifier_label}" if result.modifier != 0 else ""

    embed = discord.Embed(
        title="🎲 Lancer de dés",
        color=color,
    )

    dice_line = _build_dice_display(result.rolls, result.is_kept)
    embed.description = (
        f"**{result.dice_notation}**\n"
        f"Dés : {dice_line}{modifier_str}\n"
        f"**Total = {result.total}**"
    )

    # Champ détail pour les lancers multiples
    if len(result.rolls) > 1:
        sum_kept = sum(r for r, k in zip(result.rolls, result.is_kept) if k)
        detail = f"Résultat conservé : {sum_kept}"
        if result.modifier != 0:
            detail += f" + {result.modifier_label} = {result.total}"
        embed.add_field(name="Détail", value=detail, inline=False)

    embed.set_footer(text="JDR Bot — D&D 5e")
    return embed


def _build_error_embed(error_msg: str) -> discord.Embed:
    """Embed d'erreur rouge avec conseils de syntaxe."""
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
            "• **Désavantage** : lance 2d20, garde le plus faible"
        ),
        inline=False,
    )
    return embed


# ─────────────────────────────────────────────────────────────────────────────
# Choices pour le paramètre mode
# ─────────────────────────────────────────────────────────────────────────────

MODE_CHOICES = [
    Choice(name="Normal",         value="normal"),
    Choice(name="🤝 Avantage",     value="avantage"),
    Choice(name="👎 Désavantage",  value="desavantage"),
]


# ─────────────────────────────────────────────────────────────────────────────
# Cog
# ─────────────────────────────────────────────────────────────────────────────

class DiceCog(commands.Cog):
    """Cog pour le système de dés D&D 5e."""

    def __init__(self, bot):
        self.bot = bot
        log.info("Cog DiceCog chargé.")

    # ── Commande slash /roll ────────────────────────────────────────────────

    @app_commands.command(
        name="roll",
        description="Lancer un dé D&D 5e. Exemples : 3d6+2, d20, 2d8-1",
    )
    @app_commands.describe(
        dé="Notation du dé (ex : 3d6+2, d20, 2d8-1, 4d6)",
        mode="Normal, Avantage (2d20 meilleur) ou Désavantage (2d20 pire)",
    )
    @app_commands.choices(mode=MODE_CHOICES)
    async def roll_command(
        self,
        interaction: discord.Interaction,
        dé: str,
        mode: str = "normal",
    ):
        """Lance un dé D&D. Affiche le détail de chaque dé et le total."""
        await interaction.response.defer(ephemeral=False)

        try:
            result = roll(dé, mode=mode)
            embed = _build_embed(result, mode)
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

    # @roll_command.error
    # async def on_roll_error(self, interaction: discord.Interaction, error):
    #     """Gestionnaire d'erreur générique."""
    #     log.error("Erreur dans /roll : %s", error)
    #     try:
    #         await interaction.followup.send(
    #             embed=_build_error_embed(
    #                 "Une erreur inattendue s'est produite."
    #             ),
    #             ephemeral=True,
    #         )
    #     except Exception:
    #         pass


# ─────────────────────────────────────────────────────────────────────────────
# Setup — chargée dynamiquement par main.py via await bot.add_cog()
# ─────────────────────────────────────────────────────────────────────────────

async def setup(bot):
    """Appelée par main.py pour charger ce cog."""
    await bot.add_cog(DiceCog(bot))