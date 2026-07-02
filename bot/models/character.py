"""
Module models/character.py
===========================
Modèle de données pour les personnages D&D 5e et helper de stockage JSON.

Un utilisateur Discord peut posséder PLUSIEURS personnages.
Tous les personnages sont stockés dans un seul fichier JSON global :
data/characters/characters.json
"""

import json
import logging
import uuid
from dataclasses import dataclass, field, asdict
from pathlib import Path

from typing import Optional

logger = logging.getLogger(__name__)

# =============================================================================
# CHEMIN DU FICHIER JSON
# =============================================================================

def _get_data_dir() -> Path:
    """Retourne le chemin du dossier data/characters/ (à la racine du projet)."""
    return Path(__file__).resolve().parent.parent.parent / "data" / "characters"

def _get_json_path() -> Path:
    """Retourne le chemin complet du fichier JSON des personnages."""
    data_dir = _get_data_dir()
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir / "characters.json"

# =============================================================================
# CLASSE DE DONNÉES : Personnage
# =============================================================================

@dataclass
class Personnage:
    """
    Représente un personnage D&D 5e.
    
    Attributs :
        - id          : identifiant unique (court, formaté depuis uuid4)
        - owner_id    : ID Discord du propriétaire du personnage
        - nom         : nom du personnage
        - race        : race (Humain, Elfe, Nain, etc.)
        - classe      : classe (Guerrier, Mage, Voleur, etc.)
        - niveau      : niveau du personnage (1-20)
        - image_url   : URL optionnelle de l'image du personnage
        
        - caracteristiques : dictionnaire des 6 caractéristiques D&D 5e
          { "force": int, "dexterite": int, "constitution": int,
            "intelligence": int, "sagesse": int, "charisme": int }
          
        - pv_max      : points de vie maximum
        - pv_actuels  : points de vie actuels
        - ca          : classe d'armure
        - bonus_maitrise : bonus de maîtrise (dépend du niveau)
        
        - attaques    : liste d'attaques, chaque attaque est un dict :
          { "nom": str, "bonus_attaque": str, "des_degats": str }
          Exemple : { "nom": "Épée longue", "bonus_attaque": "+5", "des_degats": "1d8+3" }
    """
    
    owner_id: int
    nom: str
    race: str
    classe: str
    niveau: int
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    image_url: Optional[str] = None
    
    # Caractéristiques D&D 5e (valeurs brutes, 1-30 typiquement)
    caracteristiques: dict = field(default_factory=lambda: {
        "force": 10,
        "dexterite": 10,
        "constitution": 10,
        "intelligence": 10,
        "sagesse": 10,
        "charisme": 10
    })
    
    # Stats combat
    pv_max: int = 10
    pv_actuels: int = 10
    ca: int = 10
    bonus_maitrise: int = 2
    
    # Liste des attaques du personnage
    attaques: list = field(default_factory=list)
    
    # -------------------------------------------------------------------------
    # Méthodes de calcul
    # -------------------------------------------------------------------------
    
    @staticmethod
    def modificateur(valeur: int) -> int:
        """
        Calcule le modificateur D&D 5e pour une valeur de caractéristique.
        
        Formule standard : (valeur - 10) // 2
        
        Exemples :
            10 -> 0  ("+0")
            15 -> 2  ("+2")
            8  -> -1 ("-1")
            1  -> -5 ("-5")
        
        Args:
            valeur: valeur brute de la caractéristique (1 à 30+)
            
        Returns:
            Modificateur signé (peut être négatif)
        """
        return (valeur - 10) // 2
    
    def _formater_mod(self, carac: str) -> str:
        """Retourne le modificateur formaté pour une caractéristique (ex: '+2')."""
        mod = self.modificateur(self.caracteristiques.get(carac, 10))
        if mod >= 0:
            return f"+{mod}"
        else:
            return str(mod)
    
    @property
    def mod_force(self) -> str:
        """Modificateur de Force formaté (+X ou -X)."""
        return self._formater_mod("force")
    
    @property
    def mod_dexterite(self) -> str:
        """Modificateur de Dextérité formaté (+X ou -X)."""
        return self._formater_mod("dexterite")
    
    @property
    def mod_constitution(self) -> str:
        """Modificateur de Constitution formaté (+X ou -X)."""
        return self._formater_mod("constitution")
    
    @property
    def mod_intelligence(self) -> str:
        """Modificateur d'Intelligence formaté (+X ou -X)."""
        return self._formater_mod("intelligence")
    
    @property
    def mod_sagesse(self) -> str:
        """Modificateur de Sagesse formaté (+X ou -X)."""
        return self._formater_mod("sagesse")
    
    @property
    def mod_charisme(self) -> str:
        """Modificateur de Charisme formaté (+X ou -X)."""
        return self._formater_mod("charisme")
    
    # -------------------------------------------------------------------------
    # Sérialisation JSON
    # -------------------------------------------------------------------------
    
    def to_dict(self) -> dict:
        """
        Convertit le personnage en dictionnaire pour la sérialisation JSON.
        
        Returns:
            dict : représentation JSON du personnage
        """
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: dict) -> "Personnage":
        """
        Crée un objet Personnage à partir d'un dictionnaire (désérialisation JSON).
        
        Args:
            data: dictionnaire contenant les données du personnage
            
        Returns:
            Personnage : instance de la classe
        """
        # On filtre pour ne garder que les champs du dataclass
        valid_fields = {f.name for f in cls.__dataclass_fields__.values()}
        filtered_data = {k: v for k, v in data.items() if k in valid_fields}
        return cls(**filtered_data)


# =============================================================================
# HELPER DE STOCKAGE JSON
# =============================================================================

class StockagePersonnages:
    """
    Gestionnaire de stockage pour les personnages dans un fichier JSON global.
    
    Structure du fichier JSON :
    {
        "characters": {
            "<id_perso>": { ... données du personnage ... }
        }
    }
    
    Un utilisateur peut posséder PLUSIEURS personnages.
    La recherche par nom est limitée au propriétaire (owner_id).
    """
    
    def __init__(self, json_path: Optional[Path] = None):
        """
        Initialise le gestionnaire de stockage.
        
        Args:
            json_path: chemin optionnel vers le fichier JSON (par défaut : automatique)
        """
        self.json_path = json_path or _get_json_path()
        self.json_path.parent.mkdir(parents=True, exist_ok=True)
    
    def _charger(self) -> dict:
        """Charge le contenu du fichier JSON. Retourne un dict vide si le fichier n'existe pas."""
        if not self.json_path.exists():
            return {"characters": {}}
        try:
            with open(self.json_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            logger.error(f"Erreur lecture JSON {self.json_path}: {e}")
            return {"characters": {}}
    
    def _sauvegarder(self, data: dict) -> None:
        """Sauvegarde le contenu dans le fichier JSON (écrasement complet)."""
        try:
            with open(self.json_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except IOError as e:
            logger.error(f"Erreur écriture JSON {self.json_path}: {e}")
            raise
    
    # -------------------------------------------------------------------------
    # Opérations CRUD
    # -------------------------------------------------------------------------
    
    def lister(self, owner_id: int) -> list[Personnage]:
        """
        Liste tous les personnages d'un utilisateur.
        
        Args:
            owner_id: ID Discord du propriétaire
            
        Returns:
            list[Personnage]: liste des personnages de l'utilisateur
        """
        data = self._charger()
        personnages = []
        for char_data in data.get("characters", {}).values():
            if char_data.get("owner_id") == owner_id:
                personnages.append(Personnage.from_dict(char_data))
        return personnages
    
    def obtenir(self, identifiant: str, owner_id: int) -> Optional[Personnage]:
        """
        Obtient un personnage par son ID ou son nom (limité au propriétaire).
        
        Args:
            identifiant: ID ou nom du personnage
            owner_id: ID Discord du propriétaire (pour limiter la recherche)
            
        Returns:
            Personnage ou None si non trouvé
        """
        data = self._charger()
        chars = data.get("characters", {})
        
        # Recherche par ID
        if identifiant in chars:
            char_data = chars[identifiant]
            if char_data.get("owner_id") == owner_id:
                return Personnage.from_dict(char_data)
        
        # Recherche par nom (insensible à la casse, limité au propriétaire)
        for char_data in chars.values():
            if (char_data.get("owner_id") == owner_id and 
                char_data.get("nom", "").lower() == identifiant.lower()):
                return Personnage.from_dict(char_data)
        
        return None

    def nom_deja_utilise(
        self,
        nom: str,
        owner_id: int,
        exclure_id: Optional[str] = None,
    ) -> bool:
        """
        Vérifie si un personnage avec ce nom existe déjà pour l'utilisateur.

        Args:
            nom: nom à vérifier (insensible à la casse)
            owner_id: ID Discord du propriétaire
            exclure_id: ID à ignorer (utile lors d'une modification de nom)
        """
        nom_lower = nom.strip().lower()
        data = self._charger()
        for char_data in data.get("characters", {}).values():
            if char_data.get("owner_id") != owner_id:
                continue
            if exclure_id and char_data.get("id") == exclure_id:
                continue
            if char_data.get("nom", "").lower() == nom_lower:
                return True
        return False
    
    def ajouter(self, personnage: Personnage) -> None:
        """
        Ajoute un nouveau personnage au stockage.
        
        Args:
            personnage: objet Personnage à sauvegarder
            
        Raises:
            ValueError: si un personnage avec le même ID ou le même nom existe déjà
        """
        logger.debug(
            "ajouter() — nom=%r, id=%s, owner_id=%s",
            personnage.nom,
            personnage.id,
            personnage.owner_id,
        )
        data = self._charger()
        chars = data.setdefault("characters", {})
        nb_avant = len(chars)

        if personnage.id in chars:
            logger.warning(
                "Doublon ID refusé — id=%s, nom=%r, owner_id=%s",
                personnage.id,
                personnage.nom,
                personnage.owner_id,
            )
            raise ValueError(f"Un personnage avec l'ID {personnage.id} existe déjà.")

        if self.nom_deja_utilise(personnage.nom, personnage.owner_id):
            logger.warning(
                "Doublon nom refusé — nom=%r, owner_id=%s (total persos: %d)",
                personnage.nom,
                personnage.owner_id,
                nb_avant,
            )
            raise ValueError(
                f"Vous avez déjà un personnage nommé « {personnage.nom} »."
            )

        chars[personnage.id] = personnage.to_dict()
        self._sauvegarder(data)
        logger.info(
            "Personnage '%s' (ID: %s) ajouté pour owner %s (%d → %d perso(s))",
            personnage.nom,
            personnage.id,
            personnage.owner_id,
            nb_avant,
            len(chars),
        )
    
    def mettre_a_jour(self, personnage: Personnage) -> None:
        """
        Met à jour un personnage existant.
        
        Args:
            personnage: objet Personnage avec les nouvelles données
            
        Raises:
            KeyError: si le personnage n'existe pas
            ValueError: si le nouveau nom est déjà pris par un autre personnage
        """
        data = self._charger()
        chars = data.get("characters", {})

        if personnage.id not in chars:
            raise KeyError(f"Aucun personnage avec l'ID {personnage.id}.")

        if self.nom_deja_utilise(
            personnage.nom,
            personnage.owner_id,
            exclure_id=personnage.id,
        ):
            raise ValueError(
                f"Vous avez déjà un personnage nommé « {personnage.nom} »."
            )

        chars[personnage.id] = personnage.to_dict()
        self._sauvegarder(data)
        logger.info(f"Personnage '{personnage.nom}' (ID: {personnage.id}) mis à jour")
    
    def supprimer(self, identifiant: str, owner_id: int) -> bool:
        """
        Supprime un personnage par son ID ou son nom.
        
        Args:
            identifiant: ID ou nom du personnage
            owner_id: ID Discord du propriétaire
            
        Returns:
            True si supprimé, False si non trouvé
        """
        personnage = self.obtenir(identifiant, owner_id)
        if not personnage:
            return False
        
        data = self._charger()
        chars = data.get("characters", {})
        
        if personnage.id in chars:
            del chars[personnage.id]
            self._sauvegarder(data)
            logger.info(f"Personnage '{personnage.nom}' (ID: {personnage.id}) supprimé")
            return True
        
        return False


# Instance globale pour удобство (convenience)
stockage = StockagePersonnages()
