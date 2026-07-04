# Discord JDR Bot — D&D 5e SRD 2014

Bot Discord de jeu de rôle (JDR) pour organiser des parties **Donjons & Dragons 5e** (SRD 2014) directement sur Discord : dés, fiches personnages, sorts, repos et montée de niveau.

> Chaque MJ héberge **sa propre instance** du bot avec ses propres données (SQLite locale).

---

## Fonctionnalités actuelles

| Domaine | Commandes / contenu |
|---------|---------------------|
| **Dés** | `/roll` — jets d20 avec avantage/désavantage, hooks traits raciaux |
| **Personnages** | `/creer-perso`, `/perso-afficher`, `/perso-liste`, `/perso-choisir`, `/perso-supprimer` (MJ) |
| **Sorts** | `/sort` — Magicien & Clerc niv. 1–3 (autocomplete sur sorts possédés) |
| **Repos (MJ)** | `/repos-long`, `/repos-court` |
| **Niveau (MJ)** | `/monter-niveau` — niv. 2–3 (PV, emplacements, dés de vie ; SRD strict, pas d'ASI) |
| **Racial** | `/souffle` — Drakéide (souffle draconique) |

### Races jouables (SRD 2014)

Humain, Elfe, Nain, Halfelin, **Drakéide**, **Gnome des roches**, **Demi-elfe**, **Demi-orc**, **Tieffelin**.

### Classes jouables (niv. 1–3)

**Magicien**, **Clerc** — création avec point buy (27 pts), choix de compétences, domaine clerc (Vie).

---

## Prérequis

- **Python 3.10+** (testé en 3.14)
- Un bot Discord sur le [portail développeur](https://discord.com/developers/applications)
- Token dans `.env` (jamais commité)

---

## Installation

```powershell
# Cloner le dépôt
git clone https://github.com/Aztaloph/discord-jdr-bot.git
cd discord-jdr-bot

# Environnement virtuel
python -m venv venv
.\venv\Scripts\activate

# Dépendances
pip install -r requirements.txt

# Configuration
copy .env.example .env
# Éditer .env : DISCORD_TOKEN=votre_token_ici

# (Optionnel) sync slash commands sur un serveur de dev
copy config.example.json config.json
# Renseigner guild_id dans config.json
```

---

## Lancement

```powershell
.\venv\Scripts\activate
python main.py
```

Sortie attendue : `Bot connecté !` + chargement des cogs.

### Rôle MJ

Créez un rôle Discord nommé **`MJ`** sur votre serveur. Les commandes `[MJ]` (`/repos-long`, `/repos-court`, `/monter-niveau`, `/perso-supprimer`) le requièrent.

---

## Tests

```powershell
.\venv\Scripts\activate
python -m unittest discover -s tests -p "test_*.py" -q
```

---

## Structure du projet

```
discord-jdr-bot/
├── main.py                 # Point d'entrée
├── bot/cogs/               # Commandes slash Discord
├── jdr_engine/             # Moteur de règles (domaine, persistance, sorts, repos…)
├── interfaces/discord/     # Handlers, embeds, wizard création
├── compendium/dnd5e/       # Données SRD (races, classes, sorts, traits)
├── data/                   # SQLite locale (ignorée par git sauf structure)
└── tests/                  # Suite unitaire (~300 tests)
```

---

## Sécurité

- **Ne jamais** committer `.env`, `config.json`, `data/bot.db` ni le dossier `venv/`.
- Régénérez le token sur le portail Discord si exposé.

---

## Feuille de route

Voir [ROADMAP.md](ROADMAP.md) pour le détail des lots (classes, combat, etc.).

**Prochaine étape majeure :** système de combat complet (Étape 4).

---

## Licence contenu

Règles et textes dérivés du **SRD 5.1 (2014)** sous licence Open Gaming License.
