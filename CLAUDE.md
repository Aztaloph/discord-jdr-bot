# CLAUDE.md — Contexte projet Discord JDR Bot

> **Fichier de référence** pour Cursor Composer. Lis ce document AVANT de commencer à coder.
> Tout changement d'architecture, de conventions ou de priorités doit être reporté ici.

---

## 📋 Présentation du projet

**Nom** : Discord JDR Bot
**Type** : Bot Discord de jeu de rôle (JDR) basé sur D&D 5e
**Plateforme cible** : Windows (PowerShell), lancé via `python main.py`
**Dossier source** : `C:\Users\aztal\Desktop\discord-jdr-bot`
**État** : En développement actif. Quelques bugs ouverts.

Le bot permet aux joueurs de :
- Lancer des dés (commande `!roll` / slash commands)
- Créer et gérer des fiches de personnages D&D 5e via des modals interactifs
- Lister, afficher, modifier et supprimer leurs personnages

---

## 🛠️ Stack technique

| Élément | Détail |
|---|---|
| Langage | Python 3.14.6 |
| Librairie Discord | `discord.py` (slash commands, modals, views) |
| Stockage | Fichier JSON (`data/characters/characters.json`) |
| Environnement | venv Windows (PowerShell) — activation : `.\venv\Scripts\activate` |
| Lancement | `python main.py` |
| Point d'entrée | `main.py` |
| Dépendances | `discord.py`, `python-dotenv` (à installer dans le venv) |

> ⚠️ **Règle critique d'import** : `python-dotenv` s'**installe** avec `pip install python-dotenv` (tiret), mais s'**importe** avec `import dotenv` (sans tiret). Beaucoup de devs calent ici.

---

## 📁 Structure du projet

```
discord-jdr-bot/
├── main.py                          # Point d'entrée, charge les cogs
├── config.example.json               # Modèle pour config.json (token)
├── config.json                      # ⚠️ Ne JAMAIS committer (token en clair s'il existe encore)
├── .env                             # ✅ Variable DISCORD_TOKEN (en cours de mise en place)
├── .gitignore                       # ✅ À créer / vérifier
├── requirements.txt                 # Dépendances Python
├── data/
│   └── characters/
│       └── characters.json         # Fichier JSON de stockage des personnages
├── bot/                             # Package principal
│   ├── __init__.py
│   ├── cogs/                        # Commandes Discord (1 cog = 1 fichier)
│   │   ├── dice.py
│   │   └── character.py              # ⚠️ Vérifier l'import models vs bot.models (voir B2)
│   └── models/
│       ├── __init__.py
│       ├── character.py              # Classe Personnage + StockagePersonnages
│       └── dice.py
└── venv/                            # Environnement virtuel Python (ignoré par git)
```

> ⚠️ **Incohérence détectée dans les imports** : certains fichiers `character.py` importent `from models.character import ...` tandis que d'autres utilisent `from bot.models.character import ...`. Le dossier s'appelle `bot/`, donc la forme correcte est `bot.models.character`. À vérifier et uniformiser lors du fix B2.

---

## 🎨 Conventions de code

### Style général
- **Indentation** : 4 espaces (pas de tabulations)
- **Encodage** : UTF-8
- **Docstrings** : en français pour la logique métier, en anglais pour les fonctions utilitaires
- **Logging** : utiliser `logging.getLogger(__name__)` — pas de `print()`

### Architecture des cogs
```
# Structure standard d'un cog
class MonCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        logger.info("MonCog initialisé.")

    @app_commands.command(name="ma-commande", description="Description")
    async def ma_commande(self, interaction: discord.Interaction):
        ...

async def setup(bot: commands.Bot):
    await bot.add_cog(MonCog(bot))
```

### Commandes et messages
- Toutes les commandes en **français**
- Erreurs → embed rouge (`COULEUR_ERREUR = 0xDC143C`) + message `ephemeral=True`
- Succès → embed vert (`COULEUR_SUCCES = 0x228B22`)
- Validation côté bot, pas de confiance côté client

### Stockage JSON
- Fichier unique `data/characters/characters.json`
- Clé principale : `"characters"` contenant un dict `{id_perso: {...}}`
- Un utilisateur Discord (owner_id) peut posséder **plusieurs** personnages
- Recherche par nom toujours filtrée par `owner_id`

### Couleurs Embed (constantes déjà définies dans character.py)
```python
COULEUR_PRINCIPALE = 0x8B4513  # Marron — ambiance D&D
COULEUR_SUCCES     = 0x228B22  # Vert forêt
COULEUR_ERREUR     = 0xDC143C  # Rouge Crimson
COULEUR_INFO       = 0x4169E1  # Bleu Royal
```

---

## 🔐 Sécurité — RÈGLES ABSOLUES

### Ne JAMAIS committer
- `.env` (contient `DISCORD_TOKEN`)
- `config.json` (token en clair s'il existe encore)
- `venv/` et tout sous-dossier `.venv`
- Fichiers `.pyc`, `__pycache__/`
- Logs, tokens, secrets de toute nature

### Le fichier `.gitignore` doit contenir au minimum
```
.env
config.json
venv/
__pycache__/
*.pyc
*.log
data/characters/characters.json
```

### Workflow sécurisé pour le token Discord
1. Régénérer le token sur le [portail Discord](https://discord.com/developers/applications) (section Bot → Reset Token)
2. Le copier dans `.env` : `DISCORD_TOKEN=le_nouveau_token`
3. **Ne JAMAIS** le coller ailleurs dans le code
4. Si le token a été exposé (lu dans un log, partagé, pushé sur Git) → **régénérer immédiatement**

---

## 🤝 Méthode de collaboration (IMPORTANT)

### Profil de l'utilisateur
- **Débutant en programmation**, mais méthodique et prudent
- Préférence forte pour les **petites étapes validées une par une**
- Pose beaucoup de questions "pourquoi ?" — toujours expliquer le raisonnement
- Utilise Cursor Composer 2.5 pour orchestrer les modifications

### Protocole attendu
1. **Un problème à la fois** — ne pas tout corriger d'un coup
2. **Étapes numérotées** avec commande exacte à copier-coller (PowerShell/Windows)
3. **Validation entre chaque étape** — attendre le retour de l'utilisateur avant de continuer
4. **Expliquer le pourquoi**, pas seulement le quoi
5. En cas de doute, demander confirmation avant de modifier

### Si Cursor doit modifier plusieurs fichiers
- Lister clairement chaque fichier concerné
- Indiquer la ligne ou la section exacte modifiée
- Prévoir une commande de test après chaque modification importante

---

## 📊 État actuel du projet

### ✅ Déjà fait
- Point d'entrée `main.py` fonctionnel avec chargement dynamique des cogs
- Système de dés (`dice.py`) opérationnel
- Système de fiches personnages complet (création, listing, affichage, modification, suppression, attaques)
- Interface modals+views style jeu vidéo
- Stockage JSON des personnages
- **Sécurité (B1)** : token régénéré sur le portail Discord

### 🔄 En cours
- **Sécurité (B1)** : migration `.env` — `.gitignore` à finaliser + validation

### ❌ Bugs ouverts (priorisés)

#### 🟡 B1 — Sécurité (quasi-terminé)
- Migrer le token de `config.json` → `.env` via `python-dotenv`
- Créer / vérifier le `.gitignore`
- S'assurer que `python-dotenv` est installé dans le venv

#### 🔴 B2 — Bug de création de personnage + doublons (PRIORITÉ HAUTE)
- **Description** : Lors de la création d'un personnage, des erreurs 404 peuvent survenir. Des doublons de personnages peuvent apparaître.
- **Cause suspectée** : Incohérence dans les imports Python (`models.character` vs `bot.models.character`). Le dossier s'appelle `bot/`, donc tous les imports dans les cogs doivent utiliser `from bot.models.character import ...`.
- **Action requise** :
  1. Uniformiser tous les imports dans `bot/cogs/character.py` → `from bot.models.character import ...`
  2. Vérifier que `bot/models/character.py` exporte bien `stockage` (instance globale de `StockagePersonnages`)
  3. Vérifier que `bot/models/__init__.py` expose correctement les symboles
  4. Ajouter des logs de debug dans `stockage.ajouter()` pour tracer les doublons
  5. Vérifier la sérialisation JSON (`to_dict` / `from_dict`)

#### ⬜ B3 — Intent message content Discord (optionnel)
- L'intent `message_content` est commenté dans `main.py`. À activer sur le portail Discord si nécessaire pour les commandes préfixées (`!`).

---

## 🗂️ Tâches restantes (ordre de priorité)

| # | Tâche | Description | Fichier(s) |
|---|---|---|---|
| 1 | Valider B1 | `.gitignore` correct + `.env` chargé + `python-dotenv` installé | `.env`, `.gitignore`, `main.py` |
| 2 | Fix B2 | Uniformiser imports + corriger doublons | `bot/cogs/character.py`, `bot/models/character.py`, `bot/models/__init__.py` |
| 3 | Tester `/perso-creer` | Créer un personnage complet, vérifier que l'enregistrement JSON est correct | `data/characters/characters.json` |
| 4 | B3 (optionnel) | Activer intent message content si besoin | `main.py`, portail Discord |

---

## 📌 Notes techniques pour Cursor

### Logs Discord.py — pas de panique
Les warnings de type `PyNaCl` ou `voice` lors du lancement sont **sans gravité** si le bot se connecte correctement. Ils concernent des fonctionnalités optionnelles (voix) non utilisées par ce bot.

### Test de connexion minimal
```powershell
# 1. Activer le venv
.\venv\Scripts\activate

# 2. Vérifier que python-dotenv est installé
pip show python-dotenv

# 3. Lancer le bot
python main.py
```

Sortie attendue : `🎲 Bot connecté !` suivi du nom du bot et du nombre de serveurs.

### Sur les doublons de personnages
- Chaque personnage a un UUID court (8 caractères) comme identifiant unique (`id`)
- La recherche se fait par `nom + owner_id` (un utilisateur ne peut pas avoir deux personnages avec le même nom)
- Vérifier `stockage.lister(owner_id)` pour confirmer que les doublons ne sont qu'en affichage

---

*Document généré automatiquement. Mis à jour le 2 juillet 2026.*