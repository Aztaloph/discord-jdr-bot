# main.py — Point d'entrée du bot Discord JDR D&D 5e.
# Étape 1 : socle propre + lancer de dés (dice.py)
# Étapes à venir : fiches perso, combat Pokémon, générateur de PNJ.
import json
import logging
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
import discord
from discord.ext import commands

from interfaces.discord.startup import init_discord_jdr

# ─────────────────────────────────────────────────────────────────────────────
# Configuration du logging
# ─────────────────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s : %(message)s",
    datefmt="%H:%M:%S",
    handlers=[logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Chargement de la configuration
# ─────────────────────────────────────────────────────────────────────────────

def load_token() -> str:
    """
    Charge le token Discord depuis le fichier .env (variable DISCORD_TOKEN).
    Affiche un message clair en français si le token est manquant.
    """
    load_dotenv()
    token = os.getenv("DISCORD_TOKEN", "").strip()

    if not token or token == "collez_votre_token_ici":
        print(
            "\n╔══════════════════════════════════════════════════════════╗\n"
            "║  ERREUR : Token Discord manquant !                        ║\n"
            "║                                                          ║\n"
            "║  1. Copie .env.example → .env                             ║\n"
            "║  2. Va sur https://discord.com/developers/applications   ║\n"
            "║  3. Menu : Bot → Copie le TOKEN                           ║\n"
            "║  4. Colle-le dans .env : DISCORD_TOKEN=...                ║\n"
            "║  5. Relance python main.py                               ║\n"
            "╚══════════════════════════════════════════════════════════╝\n"
        )
        sys.exit(1)

    return token


def load_config() -> dict:
    """
    Charge config.json (optionnel) pour les paramètres non sensibles
    (ex. guild_id pour sync rapide des slash commands en dev).
    """
    config_path = Path(__file__).parent / "config.json"

    if not config_path.exists():
        log.info(
            "config.json absent — sync globale des commandes. "
            "Copie config.example.json → config.json pour un sync par serveur."
        )
        return {}

    with open(config_path, "r", encoding="utf-8") as f:
        return json.load(f)


# ─────────────────────────────────────────────────────────────────────────────
# Liste des cogs à charger automatiquement
# ─────────────────────────────────────────────────────────────────────────────

COGS = [
    "bot.cogs.dice",
    "bot.cogs.character",
    "bot.cogs.spell",
    "bot.cogs.creation",
    "bot.cogs.rest",
    "bot.cogs.racial",
    # "bot.cogs.fiches",      # ← Étape 2
    # "bot.cogs.combat",      # ← Étape 3
    # "bot.cogs.npc",         # ← Étape 4
]


# ─────────────────────────────────────────────────────────────────────────────
# Point d'entrée
# ─────────────────────────────────────────────────────────────────────────────

def main():
    """Point d'entrée principal."""
    token = load_token()
    config = load_config()

    intents = discord.Intents.default()
    # intents.message_content = True

    bot = commands.Bot(
        command_prefix="!",
        intents=intents,
        description="Bot JDR D&D 5e — Lanceur de dés et boîte à outils JDR",
    )

    # ── setup_hook : appelé UNE fois avant la connexion ─────────────────────
    async def setup_hook():
        bot.jdr = init_discord_jdr(config)
        if bot.jdr.use_engine_v2:
            log.info("Interface Discord → moteur v2 activée")
        else:
            log.info("Interface Discord → mode legacy v1")

        for cog_path in COGS:
            try:
                await bot.load_extension(cog_path)
                log.info("✅ Cog chargé : %s", cog_path)
            except Exception as e:
                log.error("❌ Erreur chargement de %s : %s", cog_path, e)
                raise

        guild_id = config.get("guild_id")
        if guild_id:
            guild = discord.Object(id=guild_id)
            bot.tree.copy_global_to(guild=guild)
            synced = await bot.tree.sync(guild=guild)
            log.info(
                "✅ Slash commands sync (guild) : %s — %d commande(s)",
                guild_id, len(synced),
            )
        else:
            synced = await bot.tree.sync()
            log.info("✅ Slash commands sync (globale) — %d commande(s)", len(synced))

    bot.setup_hook = setup_hook

    @bot.event
    async def on_ready():
        log.info(
            "🎲 Bot connecté !\n"
            "   Nom : %s\n"
            "   ID  : %s",
            bot.user.name,
            bot.user.id,
        )
        guilds = bot.guilds
        if guilds:
            names = ", ".join(g.name for g in guilds[:5])
            log.info("   Serveurs (%d) : %s", len(guilds), names)

    log.info("🔌 Connexion en cours...")
    bot.run(token, log_handler=None)


if __name__ == "__main__":
    main()
