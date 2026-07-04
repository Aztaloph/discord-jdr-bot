"""
cogs/character.py
==================
Cog Discord pour la gestion des fiches de personnages D&D 5e.
Commandes en français avec assistants modals style jeu vidéo.

Auteur : Bot JDR
Version : 1.0.0
"""

import logging
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

from bot.models.character import Personnage, stockage

from interfaces.discord.handlers import character as character_v2
from interfaces.discord.handlers import mj_delete as mj_delete_handler




logger = logging.getLogger(__name__)

# =============================================================================
# CONSTANTES
# =============================================================================

COULEUR_PRINCIPALE = 0x8B4513  # Marron saddlebrown (ambiance D&D)
COULEUR_SUCCES = 0x228B22     # Vert forêt
COULEUR_ERREUR = 0xDC143C     # Rouge Crimson
COULEUR_INFO = 0x4169E1       # Bleu Royal

# Ordre des caractéristiques D&D 5e
NOMS_CARAC = ["force", "dexterite", "constitution", "intelligence", "sagesse", "charisme"]
ABBREV_CARAC = ["FOR", "DEX", "CON", "INT", "SAG", "CHA"]


# =============================================================================
# FONCTIONS UTILITAIRES
# =============================================================================

def _formater_caracs(perso: Personnage) -> str:
    """Retourne une liste formatée des 6 caractéristiques avec leurs modificateurs."""
    lignes = []
    for abbrev, nom in zip(ABBREV_CARAC, NOMS_CARAC):
        valeur = perso.caracteristiques.get(nom, 10)
        mod = Personnage.modificateur(valeur)
        mod_str = f"+{mod}" if mod >= 0 else str(mod)
        lignes.append(f"{abbrev} {valeur:2d} ({mod_str})")
    return "\n".join(lignes)


def _formater_attaques(perso: Personnage) -> str:
    """Retourne une liste formatée des attaques du personnage."""
    if not perso.attaques:
        return "*Aucune attaque enregistrée*"
    lignes = []
    for atk in perso.attaques:
        lignes.append(f"**{atk['nom']}** : +{atk['bonus_attaque']} → {atk['des_degats']}")
    return "\n".join(lignes)


def _creer_embed_fiche(perso: Personnage, couleur: int = COULEUR_PRINCIPALE, 
                       titre: str = None) -> discord.Embed:
    """
    Crée un embed riche pour afficher la fiche d'un personnage.
    Style inspiré des interfaces de jeux vidéo RPG.
    """
    titre = titre or f"📜 Fiche de {perso.nom}"
    embed = discord.Embed(title=titre, color=couleur)
    
    # Image du personnage en thumbnail
    if perso.image_url:
        embed.set_thumbnail(url=perso.image_url)
    
    # --- Bloc Identité ---
    embed.add_field(
        name="⚔️ Identité",
        value=(f"**Race :** {perso.race}\n"
               f"**Classe :** {perso.classe}\n"
               f"**Niveau :** {perso.niveau}"),
        inline=True
    )
    
    # --- Bloc Combat ---
    embed.add_field(
        name="❤️ Combat",
        value=(f"**PV :** {perso.pv_actuels}/{perso.pv_max}\n"
               f"**CA :** {perso.ca}\n"
               f"**Bonus de maîtrise :** +{perso.bonus_maitrise}"),
        inline=True
    )
    
    # --- Bloc Caractéristiques ---
    embed.add_field(
        name="📊 Caractéristiques",
        value=_formater_caracs(perso),
        inline=False
    )
    
    # --- Bloc Attaques ---
    embed.add_field(
        name="⚔️ Attaques",
        value=_formater_attaques(perso),
        inline=False
    )
    
    embed.set_footer(text=f"ID personnage : {perso.id}")
    return embed


def _formater_caracs_from_values(caracs: list[int]) -> str:
    """Formate les caractéristiques depuis une liste de valeurs brutes."""
    lignes = []
    for abbrev, val in zip(ABBREV_CARAC, caracs):
        mod = Personnage.modificateur(val)
        mod_str = f"+{mod}" if mod >= 0 else str(mod)
        lignes.append(f"{abbrev} {val:2d} ({mod_str})")
    return "\n".join(lignes)


# =============================================================================
# MODALS DE CRÉATION
# =============================================================================

class AssistantCreationView(discord.ui.View):
    """
    Vue assistant pour la création de personnage.
    Présente les boutons pour ouvrir les modals Caracs et Combat.
    """
    
    def __init__(self, owner_id: int):
        super().__init__(timeout=300)
        self.owner_id = owner_id
        self.donnees = {}
        self.creation_effectuee = False
        
        # Bouton pour ouvrir le modal de caractéristiques
        bouton_caracs = discord.ui.Button(
            label="📊 Caractéristiques",
            style=discord.ButtonStyle.primary,
            custom_id="btn_caracs"
        )
        bouton_caracs.callback = self._ouvrir_caracs
        self.add_item(bouton_caracs)
        
        # Bouton pour stats de combat
        bouton_combat = discord.ui.Button(
            label="⚔️ Combat",
            style=discord.ButtonStyle.primary,
            custom_id="btn_combat"
        )
        bouton_combat.callback = self._ouvrir_combat
        self.add_item(bouton_combat)
    
    async def _ouvrir_caracs(self, interaction: discord.Interaction):
        """Ouvre le modal des caractéristiques."""
        modal = ModalCaracteristiques(self)
        await interaction.response.send_modal(modal)
    
    async def _ouvrir_combat(self, interaction: discord.Interaction):
        """Ouvre le modal de combat."""
        modal = ModalCombat(self)
        await interaction.response.send_modal(modal)


class ModalIdentite(discord.ui.Modal):
    """
    Modal 1 — Identité du personnage.
    Champs : Nom, Race, Classe, Niveau, URL image (optionnel)
    """
    
    def __init__(self, view_ref: AssistantCreationView):
        super().__init__(title="🎭 Création de personnage")
        self.view_ref = view_ref
        
        self.nom_input = discord.ui.TextInput(
            label="Nom du personnage",
            placeholder="Ex: Aldric le Brave",
            required=True,
            max_length=50
        )
        
        self.race_input = discord.ui.TextInput(
            label="Race",
            placeholder="Ex: Humain, Elfe, Nain",
            required=True,
            max_length=30
        )
        
        self.classe_input = discord.ui.TextInput(
            label="Classe",
            placeholder="Ex: Guerrier, Mage, Voleur",
            required=True,
            max_length=30
        )
        
        self.niveau_input = discord.ui.TextInput(
            label="Niveau (1-20)",
            placeholder="Ex: 1",
            required=True,
            max_length=2
        )
        
        self.image_input = discord.ui.TextInput(
            label="URL de l'image (optionnel)",
            placeholder="https://exemple.com/image.png",
            required=False,
            max_length=200
        )
        
        self.add_item(self.nom_input)
        self.add_item(self.race_input)
        self.add_item(self.classe_input)
        self.add_item(self.niveau_input)
        self.add_item(self.image_input)
    
    async def on_submit(self, interaction: discord.Interaction):
        """Valide l'identité et affiche l'assistant pour les étapes suivantes."""
        try:
            niveau = int(self.niveau_input.value)
        except ValueError:
            await interaction.response.send_message(
                "⚠️ Le niveau doit être un nombre entier.",
                ephemeral=True
            )
            return

        if not 1 <= niveau <= 20:
            await interaction.response.send_message(
                "⚠️ Le niveau doit être entre 1 et 20.",
                ephemeral=True
            )
            return

        nom = self.nom_input.value.strip()
        if stockage.nom_deja_utilise(nom, self.view_ref.owner_id):
            await interaction.response.send_message(
                f"⚠️ Vous avez déjà un personnage nommé « {nom} ».\n"
                "Choisissez un autre nom ou supprimez l'ancien personnage.",
                ephemeral=True
            )
            return
        
        # Stocker les données d'identité
        self.view_ref.donnees = {
            "nom": nom,
            "race": self.race_input.value.strip(),
            "classe": self.classe_input.value.strip(),
            "niveau": niveau,
            "image_url": self.image_input.value.strip() or None
        }
        
        # Créer l'embed de transition
        embed = discord.Embed(
            title=f"✅ Identité enregistrée : {self.view_ref.donnees['nom']}",
            description="Maintenant, remplissez les caractéristiques et les stats de combat.\n\n"
                       "Cliquez sur les boutons ci-dessous :",
            color=COULEUR_SUCCES
        )
        embed.add_field(
            name="📋 Récapitulatif",
            value=(f"**Nom :** {self.view_ref.donnees['nom']}\n"
                   f"**Race :** {self.view_ref.donnees['race']}\n"
                   f"**Classe :** {self.view_ref.donnees['classe']}\n"
                   f"**Niveau :** {self.view_ref.donnees['niveau']}"),
            inline=False
        )
        embed.add_field(
            name="📝 Prochaines étapes",
            value="1️⃣ Cliquez sur **📊 Caractéristiques** pour saisir les 6 stats\n"
                  "2️⃣ Cliquez sur **⚔️ Combat** pour les PV, CA et bonus",
            inline=False
        )
        
        await interaction.response.send_message(embed=embed, view=self.view_ref, ephemeral=True)



class ModalCaracteristiques(discord.ui.Modal):
    """
    Modal 2 — Caractéristiques.
    Un seul champ texte pour les 6 valeurs (FOR DEX CON INT SAG CHA).
    """
    
    def __init__(self, view_ref: AssistantCreationView):
        super().__init__(title="📊 Caractéristiques")
        self.view_ref = view_ref
        
        self.carac_input = discord.ui.TextInput(
            label="6 caractéristiques (FOR DEX CON INT SAG CHA)",
            placeholder="Ex: 15 14 13 12 10 8",
            required=True,
            max_length=50
        )
        self.add_item(self.carac_input)
    
    async def on_submit(self, interaction: discord.Interaction):
        """Valide et parse les 6 caractéristiques."""
        parties = self.carac_input.value.strip().split()
        
        if len(parties) != 6:
            await interaction.response.send_message(
                f"⚠️ Vous devez fournir exactement 6 valeurs. "
                f"Vous en avez fourni {len(parties)}.",
                ephemeral=True
            )
            return
        
        try:
            caracs = [int(v.strip()) for v in parties]
        except ValueError:
            await interaction.response.send_message(
                "⚠️ Les 6 valeurs doivent être des nombres entiers.",
                ephemeral=True
            )
            return
        
        # Stocker les caractéristiques
        self.view_ref.donnees["caracteristiques"] = dict(zip(NOMS_CARAC, caracs))
        
        # Afficher le récapitulatif formaté
        embed = discord.Embed(
            title="✅ Caractéristiques enregistrées",
            description=_formater_caracs_from_values(caracs),
            color=COULEUR_SUCCES
        )
        
        await interaction.response.send_message(embed=embed, view=self.view_ref, ephemeral=True)



class ModalCombat(discord.ui.Modal):
    """
    Modal 3 — Stats de combat.
    Champs : PV max, PV actuels, CA, Bonus de maîtrise
    """
    
    def __init__(self, view_ref: AssistantCreationView):
        super().__init__(title="⚔️ Statistiques de combat")
        self.view_ref = view_ref
        
        self.pv_max_input = discord.ui.TextInput(
            label="PV maximum",
            placeholder="Ex: 30",
            required=True,
            max_length=3
        )
        
        self.pv_actuels_input = discord.ui.TextInput(
            label="PV actuels (par défaut = PV max)",
            placeholder="Ex: 30",
            required=False,
            max_length=3
        )
        
        self.ca_input = discord.ui.TextInput(
            label="Classe d'armure (CA)",
            placeholder="Ex: 16",
            required=True,
            max_length=2
        )
        
        self.bonus_input = discord.ui.TextInput(
            label="Bonus de maîtrise",
            placeholder="Ex: 2",
            required=True,
            max_length=2
        )
        
        self.add_item(self.pv_max_input)
        self.add_item(self.pv_actuels_input)
        self.add_item(self.ca_input)
        self.add_item(self.bonus_input)
    
    async def on_submit(self, interaction: discord.Interaction):
        if self.view_ref.creation_effectuee:
            await interaction.response.send_message(
                "ℹ️ Ce personnage a déjà été créé. Utilisez `/perso-afficher` pour le consulter.",
                ephemeral=True,
            )
            return

        manquantes = [
            cle for cle in CLES_CREATION_REQUISES
            if cle not in self.view_ref.donnees
        ]
        if manquantes:
            await interaction.response.send_message(
                embed=discord.Embed(
                    title="⚠️ Étapes manquantes",
                    description=(
                        "Remplissez d'abord **📊 Caractéristiques** avant **⚔️ Combat**.\n\n"
                        f"Données manquantes : {', '.join(manquantes)}"
                    ),
                    color=COULEUR_ERREUR,
                ),
                ephemeral=True,
            )
            return

        logger.info("on_submit Combat — clés : %s", list(self.view_ref.donnees.keys()))
        try:
            pv_max = int(self.pv_max_input.value)
            pv_actuels_str = self.pv_actuels_input.value.strip()
            pv_actuels = int(pv_actuels_str) if pv_actuels_str else pv_max
            ca = int(self.ca_input.value)
            bonus = int(self.bonus_input.value)
        except ValueError:
            await interaction.response.send_message(
                "⚠️ Tous les champs doivent contenir des nombres entiers.",
                ephemeral=True
            )
            return
        
        if pv_actuels > pv_max:
            pv_actuels = pv_max  # Auto-corriger si PV actuels > PV max
        
        # Stocker les données de combat
        self.view_ref.donnees["pv_max"] = pv_max
        self.view_ref.donnees["pv_actuels"] = pv_actuels
        self.view_ref.donnees["ca"] = ca
        self.view_ref.donnees["bonus_maitrise"] = bonus
        
        # Créer le personnage (la création en base est isolée de l'affichage)
        try:
            perso = Personnage(
                owner_id=self.view_ref.owner_id,
                nom=self.view_ref.donnees["nom"],
                race=self.view_ref.donnees["race"],
                classe=self.view_ref.donnees["classe"],
                niveau=self.view_ref.donnees["niveau"],
                image_url=self.view_ref.donnees.get("image_url"),
                caracteristiques=self.view_ref.donnees["caracteristiques"],
                pv_max=pv_max,
                pv_actuels=pv_actuels,
                ca=ca,
                bonus_maitrise=bonus,
                attaques=[]
            )
            stockage.ajouter(perso)
            self.view_ref.creation_effectuee = True
        except ValueError as e:
            logger.warning("Création refusée (validation) : %s", e)
            await interaction.response.send_message(
                embed=discord.Embed(
                    title="❌ Création impossible",
                    description=str(e),
                    color=COULEUR_ERREUR,
                ),
                ephemeral=True,
            )
            return
        except Exception as e:
            logger.error(f"Erreur lors de la création du personnage : {e}")
            await interaction.response.send_message(
                embed=discord.Embed(
                    title="❌ Erreur",
                    description=f"Une erreur est survenue lors de la création : {e}",
                    color=COULEUR_ERREUR,
                ),
                ephemeral=True,
            )
            return

        # ── Création réussie ────────────────────────────────────────────────
        # On répond TOUJOURS via send_message ephemeral (jamais edit_message :
        # un modal n'a pas de message parent à éditer → erreur 404).
        # L'affichage est isolé : si l'envoi échoue, le perso reste créé et on
        # ne relance pas la création (évite les doublons au retry).
        embed = discord.Embed(
            title="🎉 Personnage créé avec succès !",
            color=COULEUR_SUCCES,
        )
        embed.set_footer(
            text="Votre fiche est prête. Utilisez /perso-afficher pour la consulter."
        )
        try:
            await interaction.response.send_message(embed=embed, ephemeral=True)
        except Exception as e:
            logger.error(f"🔴 Affichage du succès échoué (perso déjà créé) : {e}")



# =============================================================================
# VUES DE CONFIRMATION
# =============================================================================

class ConfirmDeleteView(discord.ui.View):
    """Vue de confirmation pour la suppression d'un personnage."""
    
    def __init__(self, owner_id: int, nom_personnage: str):
        super().__init__(timeout=60)
        self.owner_id = owner_id
        self.nom_personnage = nom_personnage
        self.resultat = None
        
        bouton_confirmer = discord.ui.Button(
            label="✅ Confirmer la suppression",
            style=discord.ButtonStyle.danger,
            custom_id="btn_confirmer_suppression"
        )
        bouton_confirmer.callback = self._confirmer
        self.add_item(bouton_confirmer)
        
        bouton_annuler = discord.ui.Button(
            label="❌ Annuler",
            style=discord.ButtonStyle.secondary,
            custom_id="btn_annuler_suppression"
        )
        bouton_annuler.callback = self._annuler
        self.add_item(bouton_annuler)
    
    async def _confirmer(self, interaction: discord.Interaction):
        """Confirme la suppression."""
        if stockage.supprimer(self.nom_personnage, self.owner_id):
            embed = discord.Embed(
                title="✅ Personnage supprimé",
                description=f"**{self.nom_personnage}** a été supprimé avec succès.",
                color=COULEUR_SUCCES
            )
        else:
            embed = discord.Embed(
                title="❌ Erreur",
                description="Le personnage n'a pas pu être supprimé.",
                color=COULEUR_ERREUR
            )
        
        self.resultat = True
        await interaction.response.edit_message(embed=embed, view=None)
    
    async def _annuler(self, interaction: discord.Interaction):
        """Annule la suppression."""
        embed = discord.Embed(
            title="ℹ️ Suppression annulée",
            description=f"**{self.nom_personnage}** n'a pas été supprimé.",
            color=COULEUR_INFO
        )
        self.resultat = False
        await interaction.response.edit_message(embed=embed, view=None)


class ModalAjoutAttaque(discord.ui.Modal):
    """Modal pour ajouter une attaque à un personnage."""
    
    def __init__(self, owner_id: int, nom_personnage: str):
        super().__init__(title="⚔️ Ajouter une attaque")
        self.owner_id = owner_id
        self.nom_personnage = nom_personnage
        
        self.nom_attaque = discord.ui.TextInput(
            label="Nom de l'attaque",
            placeholder="Ex: Épée longue",
            required=True,
            max_length=50
        )
        
        self.bonus_attaque = discord.ui.TextInput(
            label="Bonus à l'attaque",
            placeholder="Ex: +5",
            required=True,
            max_length=5
        )
        
        self.des_degats = discord.ui.TextInput(
            label="Dés de dégâts",
            placeholder="Ex: 1d8+3",
            required=True,
            max_length=20
        )
        
        self.add_item(self.nom_attaque)
        self.add_item(self.bonus_attaque)
        self.add_item(self.des_degats)
    
    async def on_submit(self, interaction: discord.Interaction):
        """Ajoute l'attaque au personnage."""
        perso = stockage.obtenir(self.nom_personnage, self.owner_id)
        if not perso:
            await interaction.response.send_message(
                "❌ Personnage introuvable.",
                ephemeral=True
            )
            return
        
        nouvelle_attaque = {
            "nom": self.nom_attaque.value.strip(),
            "bonus_attaque": self.bonus_attaque.value.strip(),
            "des_degats": self.des_degats.value.strip()
        }
        
        perso.attaques.append(nouvelle_attaque)
        stockage.mettre_a_jour(perso)
        
        embed = discord.Embed(
            title="✅ Attaque ajoutée !",
            description=f"**{perso.nom}** peut maintenant utiliser :",
            color=COULEUR_SUCCES
        )
        embed.add_field(
            name=nouvelle_attaque["nom"],
            value=f"**Bonus :** {nouvelle_attaque['bonus_attaque']} | **Dégâts :** {nouvelle_attaque['des_degats']}",
            inline=False
        )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)


# =============================================================================
# COG PRINCIPAL
# =============================================================================

class CharacterCog(commands.Cog):
    """
    Cog pour la gestion des fiches de personnages D&D 5e.
    
    Commandes disponibles (toutes en français) :
    - /creer-perso           : Création de personnage (voir cog creation)
    - /perso-liste          : Liste les personnages de l'utilisateur (éphémère)
    - /perso-choisir        : Choisit le personnage actif en jeu sur ce serveur
    - /perso-afficher [nom] : Affiche la fiche (perso actif si omis)
    - /perso-mp [nom]       : Envoie la fiche par MP
    - /perso-modifier [nom] : Modifie un personnage existant
    - /perso-supprimer [personnage] : [MJ] Supprime un personnage par son identifiant
    - /perso-attaque-ajouter [nom] : Ajoute une attaque
    """
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        logger.info("Cog CharacterCog initialisé.")

    @property
    def _jdr(self):
        return getattr(self.bot, "jdr", None)

    def _use_v2(self) -> bool:
        ctx = self._jdr
        return ctx is not None and ctx.use_engine_v2

    async def _v2_unavailable(self, interaction: discord.Interaction, feature: str) -> None:
        embed = discord.Embed(
            title="ℹ️ Non disponible (moteur v2)",
            description=(
                f"**{feature}** n'est pas encore disponible avec le moteur v2.\n"
                "Désactivez `USE_ENGINE_V2=false` pour le mode legacy, "
                "ou attendez une phase ultérieure."
            ),
            color=COULEUR_INFO,
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    async def _nom_autocomplete(
        self, interaction: discord.Interaction, current: str
    ) -> list[app_commands.Choice[str]]:
        if self._use_v2():
            return await character_v2.character_name_autocomplete(
                interaction, current, self._jdr
            )
        personnages = stockage.lister(interaction.user.id)
        choices = []
        current_lower = current.lower()
        for perso in personnages:
            if current_lower in perso.nom.lower():
                choices.append(app_commands.Choice(name=perso.nom, value=perso.nom))
            if len(choices) >= 25:
                break
        return choices

    async def _perso_id_autocomplete(
        self, interaction: discord.Interaction, current: str
    ) -> list[app_commands.Choice[str]]:
        if not self._use_v2():
            return []
        return await character_v2.character_id_autocomplete(
            interaction, current, self._jdr
        )

    async def _perso_guild_autocomplete(
        self, interaction: discord.Interaction, current: str
    ) -> list[app_commands.Choice[str]]:
        if not self._use_v2():
            return []
        return await mj_delete_handler.guild_character_autocomplete(
            interaction, current, self._jdr
        )
    
    # =========================================================================
    # COMMANDE : /perso-liste
    # =========================================================================
    
    @app_commands.command(name="perso-liste", description="Liste vos personnages (visible uniquement par vous)")
    async def perso_liste(self, interaction: discord.Interaction):
        """Affiche la liste des personnages de l'utilisateur (éphémère)."""
        if self._use_v2():
            await character_v2.perso_liste(interaction, self._jdr)
            return
        personnages = stockage.lister(interaction.user.id)
        
        if not personnages:
            embed = discord.Embed(
                title="📋 Vos personnages",
                description="Vous n'avez pas encore de personnage.\n"
                           "Utilisez `/creer-perso` pour créer votre premier personnage !",
                color=COULEUR_INFO
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        # Construire l'embed de listing
        embed = discord.Embed(
            title=f"📋 Vos personnages ({len(personnages)})",
            color=COULEUR_PRINCIPALE
        )
        
        for i, perso in enumerate(personnages, 1):
            embed.add_field(
                name=f"{i}. {perso.nom}",
                value=(f"**Race :** {perso.race} | **Classe :** {perso.classe}\n"
                       f"**Niveau :** {perso.niveau} | **PV :** {perso.pv_actuels}/{perso.pv_max}\n"
                       f"__{perso.id}__"),
                inline=False
            )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @app_commands.command(
        name="perso-choisir",
        description="Choisit votre personnage actif en jeu sur ce serveur",
    )
    @app_commands.describe(
        personnage="Votre personnage (nom ou id court, ex. marie001)",
    )
    @app_commands.autocomplete(personnage=_perso_id_autocomplete)
    async def perso_choisir(self, interaction: discord.Interaction, personnage: str):
        """Définit le personnage actif pour /roll, /sort, etc."""
        if self._use_v2():
            await character_v2.perso_choisir(interaction, self._jdr, personnage)
            return
        await self._v2_unavailable(interaction, "Choix du personnage actif")

    # =========================================================================
    # COMMANDE : /perso-afficher
    # =========================================================================

    @app_commands.command(
        name="perso-afficher",
        description="Affiche la fiche complète d'un personnage (actif si omis)",
    )
    @app_commands.describe(nom="Nom du personnage (optionnel — utilise le perso actif)")
    @app_commands.autocomplete(nom=_nom_autocomplete)
    async def perso_afficher(self, interaction: discord.Interaction, nom: str | None = None):
        """Affiche la fiche complète du personnage dans le canal."""
        if self._use_v2():
            await character_v2.perso_afficher(interaction, self._jdr, nom)
            return
        if not nom:
            await self._v2_unavailable(interaction, "Affichage du personnage actif")
            return
        perso = stockage.obtenir(nom, interaction.user.id)
        
        if not perso:
            embed = discord.Embed(
                title="❌ Personnage introuvable",
                description=f"Aucun personnage nommé « {nom} » trouvé.\n"
                           "Vérifiez l'orthographe ou utilisez `/perso-liste`.",
                color=COULEUR_ERREUR
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        embed = _creer_embed_fiche(perso)
        await interaction.response.send_message(embed=embed)
    
    # =========================================================================
    # COMMANDE : /perso-mp
    # =========================================================================
    
    @app_commands.command(name="perso-mp", description="Envoie votre fiche par message privé")
    @app_commands.describe(nom="Nom du personnage")
    @app_commands.autocomplete(nom=_nom_autocomplete)
    async def perso_mp(self, interaction: discord.Interaction, nom: str):
        """Envoie la fiche du personnage par MP à l'utilisateur."""
        if self._use_v2():
            await character_v2.perso_mp(interaction, self._jdr, nom)
            return
        perso = stockage.obtenir(nom, interaction.user.id)
        
        if not perso:
            embed = discord.Embed(
                title="❌ Personnage introuvable",
                description=f"Aucun personnage nommé « {nom} » trouvé.",
                color=COULEUR_ERREUR
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        embed = _creer_embed_fiche(perso)
        
        try:
            # Envoyer par MP
            await interaction.user.send(embed=embed)
            
            # Confirmation éphémère
            confirmation = discord.Embed(
                title="✅ Fiche envoyée",
                description=f"La fiche de **{perso.nom}** vous a été envoyée par MP.",
                color=COULEUR_SUCCES
            )
            await interaction.response.send_message(embed=confirmation, ephemeral=True)
            
        except discord.Forbidden:
            # MP désactivés
            embed_erreur = discord.Embed(
                title="❌ MP désactivés",
                description="Le bot ne peut pas vous envoyer la fiche par MP.\n"
                           "Veuillez autoriser les messages privés depuis les serveurs inconnus, "
                           "ou utilisez `/perso-afficher {nom}` dans un canal à la place.",
                color=COULEUR_ERREUR
            )
            await interaction.response.send_message(embed=embed_erreur, ephemeral=True)
    
    # =========================================================================
    # COMMANDE : /perso-modifier
    # =========================================================================
    
    @app_commands.command(name="perso-modifier", description="Modifier un personnage existant")
    @app_commands.describe(nom="Nom du personnage à modifier")
    @app_commands.autocomplete(nom=_nom_autocomplete)
    async def perso_modifier(self, interaction: discord.Interaction, nom: str):
        """Réouvre les modals pré-remplis pour modifier un personnage."""
        if self._use_v2():
            await self._v2_unavailable(interaction, "Modification de personnage")
            return
        perso = stockage.obtenir(nom, interaction.user.id)
        
        if not perso:
            embed = discord.Embed(
                title="❌ Personnage introuvable",
                description=f"Aucun personnage nommé « {nom} » trouvé.",
                color=COULEUR_ERREUR
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        # Afficher le récapitulatif et inviter à utiliser les commandes de modification
        embed = discord.Embed(
            title=f"✏️ Modifier : {perso.nom}",
            description="Utilisez les commandes suivantes pour modifier le personnage :\n\n"
                       "• `/perso-modifier-identite {nom}` - Modifier nom, race, classe, niveau\n"
                       "• `/perso-modifier-caracs {nom}` - Modifier les caractéristiques\n"
                       "• `/perso-modifier-combat {nom}` - Modifier PV, CA, bonus\n"
                       "• `/perso-attaque-ajouter {nom}` - Ajouter une attaque",
            color=COULEUR_INFO
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    # =========================================================================
    # COMMANDE : /perso-supprimer
    # =========================================================================
    
    @app_commands.command(
        name="perso-supprimer",
        description="[MJ] Supprime un personnage de ce serveur par son identifiant",
    )
    @app_commands.describe(
        personnage="Identifiant du personnage (ex. 7fcf37cd, marie001)",
    )
    @app_commands.autocomplete(personnage=_perso_guild_autocomplete)
    async def perso_supprimer(self, interaction: discord.Interaction, personnage: str):
        """Supprime un personnage par son id (MJ uniquement)."""
        if self._use_v2():
            await mj_delete_handler.mj_perso_supprimer(interaction, self._jdr, personnage)
            return
        await self._v2_unavailable(interaction, "Suppression de personnage par le MJ")
    
    # =========================================================================
    # COMMANDE : /perso-attaque-ajouter
    # =========================================================================
    
    @app_commands.command(name="perso-attaque-ajouter", 
                         description="Ajouter une attaque au répertoire d'un personnage")
    @app_commands.describe(nom="Nom du personnage")
    @app_commands.autocomplete(nom=_nom_autocomplete)
    async def perso_attaque_ajouter(self, interaction: discord.Interaction, nom: str):
        """Ouvre un modal pour ajouter une attaque au personnage."""
        if self._use_v2():
            await self._v2_unavailable(interaction, "Ajout d'attaque")
            return
        perso = stockage.obtenir(nom, interaction.user.id)
        
        if not perso:
            embed = discord.Embed(
                title="❌ Personnage introuvable",
                description=f"Aucun personnage nommé « {nom} » trouvé.",
                color=COULEUR_ERREUR
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        modal = ModalAjoutAttaque(interaction.user.id, nom)
        await interaction.response.send_modal(modal)
    
    # =========================================================================
    # COMMANDES DE MODIFICATION DÉTAILLÉE
    # =========================================================================
    
    @app_commands.command(name="perso-modifier-identite", 
                         description="Modifier l'identité d'un personnage")
    @app_commands.describe(nom="Nom du personnage")
    @app_commands.autocomplete(nom=_nom_autocomplete)
    async def perso_modifier_identite(self, interaction: discord.Interaction, nom: str):
        """Modifie l'identité (nom, race, classe, niveau, image)."""
        if self._use_v2():
            await self._v2_unavailable(interaction, "Modification d'identité")
            return
        perso = stockage.obtenir(nom, interaction.user.id)
        
        if not perso:
            await interaction.response.send_message(
                f"❌ Aucun personnage nommé « {nom} » trouvé.",
                ephemeral=True
            )
            return
        
        view = AssistantModificationView(interaction.user.id, perso)
        embed = discord.Embed(
            title=f"✏️ Modifier : {perso.nom}",
            description="Cliquez sur le bouton pour modifier l'identité.",
            color=COULEUR_INFO
        )
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


class AssistantModificationView(discord.ui.View):
    """Vue pour la modification d'un personnage existant."""
    
    def __init__(self, owner_id: int, personnage: Personnage):
        super().__init__(timeout=300)
        self.owner_id = owner_id
        self.personnage = personnage
        self.donnees = {}
        
        # Bouton pour modifier l'identité
        bouton = discord.ui.Button(
            label="✏️ Modifier l'identité",
            style=discord.ButtonStyle.primary,
            custom_id="btn_modif_identite"
        )
        bouton.callback = self._ouvrir_identite
        self.add_item(bouton)
    
    async def _ouvrir_identite(self, interaction: discord.Interaction):
        """Ouvre le modal de modification de l'identité."""
        modal = ModalModificationIdentite(self)
        await interaction.response.send_modal(modal)


class ModalModificationIdentite(discord.ui.Modal):
    """Modal de modification de l'identité (pré-rempli)."""
    
    def __init__(self, view_ref: AssistantModificationView):
        super().__init__(title="✏️ Modifier l'identité")
        self.view_ref = view_ref
        perso = view_ref.personnage
        
        self.nom_input = discord.ui.TextInput(
            label="Nom du personnage",
            default_value=perso.nom,
            required=True,
            max_length=50
        )
        
        self.race_input = discord.ui.TextInput(
            label="Race",
            default_value=perso.race,
            required=True,
            max_length=30
        )
        
        self.classe_input = discord.ui.TextInput(
            label="Classe",
            default_value=perso.classe,
            required=True,
            max_length=30
        )
        
        self.niveau_input = discord.ui.TextInput(
            label="Niveau (1-20)",
            default_value=str(perso.niveau),
            required=True,
            max_length=2
        )
        
        self.image_input = discord.ui.TextInput(
            label="URL de l'image (optionnel)",
            default_value=perso.image_url or "",
            required=False,
            max_length=200
        )
        
        self.add_item(self.nom_input)
        self.add_item(self.race_input)
        self.add_item(self.classe_input)
        self.add_item(self.niveau_input)
        self.add_item(self.image_input)
    
    async def callback(self, interaction: discord.Interaction):
        """Valide et sauvegarde les modifications d'identité."""
        try:
            niveau = int(self.niveau_input.value)
        except ValueError:
            await interaction.response.send_message(
                "⚠️ Le niveau doit être un nombre entier.",
                ephemeral=True
            )
            return

        if not 1 <= niveau <= 20:
            await interaction.response.send_message(
                "⚠️ Le niveau doit être entre 1 et 20.",
                ephemeral=True
            )
            return
        
        perso = self.view_ref.personnage
        nouveau_nom = self.nom_input.value.strip()
        perso.nom = nouveau_nom
        perso.race = self.race_input.value.strip()
        perso.classe = self.classe_input.value.strip()
        perso.niveau = niveau
        perso.image_url = self.image_input.value.strip() or None

        try:
            stockage.mettre_a_jour(perso)
        except ValueError as e:
            await interaction.response.send_message(
                embed=discord.Embed(
                    title="❌ Modification impossible",
                    description=str(e),
                    color=COULEUR_ERREUR,
                ),
                ephemeral=True,
            )
            return
        
        embed = discord.Embed(
            title="✅ Identité mise à jour !",
            description=f"**{perso.nom}** a été modifié avec succès.",
            color=COULEUR_SUCCES
        )
        await interaction.response.edit_message(embed=embed, view=None)


# =============================================================================
# FONCTION D'ENREGISTREMENT DU COG
# =============================================================================

async def setup(bot: commands.Bot):
    """
    Fonction d'enregistrement du cog (appelée depuis le bot principal).
    
    Pour enregistrer ce cog, ajoutez dans votre fichier bot principal :
    
        await bot.add_cog(CharacterCog(bot))
    
    Ou avec la fonction helper :
    
        async def setup(bot):
            await CharacterCog.setup(bot)
    """
    await bot.add_cog(CharacterCog(bot))
    logger.info("Cog CharacterCog chargé.")
