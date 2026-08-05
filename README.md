# 🎲 JDR Engine

**Moteur de jeu de rôle D&D 5e (SRD 2014) — auto-hébergeable, data-driven**

**JDR Engine** avec client Discord **vivant** pour jouer aujourd'hui, moteur **`jdr_engine`** pensé pour demain : client Web, API et combat moteur pur. Les stats ne se trichent pas — PV, emplacements et caractéristiques sont **calculés** par le moteur, jamais saisis à la main.

> 🏠 Chaque MJ héberge **sa propre instance**. Données locales (SQLite), jamais partagées entre serveurs.

<p align="center">

| 🧪 Tests | ⚔️ Classes | ✨ Sorts | 🐍 Python |
|:--------:|:----------:|:-------:|:---------:|
| **835** ✅ | **12/12** | **42** | **3.12** |

</p>

<p align="center">
  <a href="VISION.md"><strong>Vision</strong></a> ·
  <a href="ROADMAP.md"><strong>Roadmap</strong></a> ·
  <a href="docs/API_LOCAL.md"><strong>API locale</strong></a> ·
  <a href="docs/ARCHITECTURE.md"><strong>Architecture</strong></a>
</p>

---

## 🧭 Où va le projet

La **cible** est une plateforme JDR complète : moteur de règles indépendant, **client Web** comme interface de jeu principale, **Discord** réduit au social et aux notifications. Le détail stratégique est dans [`VISION.md`](VISION.md).

| Priorité | Focus |
|:--------:|-------|
| 🔧 **Maintenant** | Extension **B4** (effets de sorts via registre), dettes combat mineures, API banc de test |
| 🛡️ **Discord** | Commandes existantes **maintenues**, pas de nouvelles features joueur |
| ⚔️ **Combat moteur** | Boucle **livrée** (C0–C7, ADR-004/005/006) — API pure, sans rendu UI |
| 🌐 **Ensuite** | Client Web (fiche, sorts, HUD de combat, écran MJ) |

---

## ✅ Ce que le bot fait aujourd'hui

### 👤 Commandes joueur

| Domaine | Slash commands |
|---------|----------------|
| 🎯 **Dés** | `/roll` — d20, avantage/désavantage, hooks traits raciaux |
| 📋 **Personnages** | `/creer-perso` · `/perso-afficher` · `/perso-liste` · `/perso-choisir` |
| ✨ **Sorts** | `/sort` — lancement avec autocomplete (✨ lançable · 🔒 niveau · 📘 non préparé) |
| 📖 **Préparation** | `/preparer-sorts` — re-choix après repos long (clerc, druide, paladin, magicien) |
| 🐉 **Racial** | `/souffle` — Souffle draconique (Drakéide) |

### 🎭 Commandes MJ (rôle `MJ` requis)

| Domaine | Slash commands |
|---------|----------------|
| 😴 **Repos** | `/repos-long` · `/repos-court` |
| 📈 **Progression** | `/monter-niveau` — niv. 2–20 (PV, emplacements, sorts, ASI 4/8/12/16/19) |
| 🔧 **Admin** | `/perso-supprimer` · `/reset-grimoire` · `/migrer-grimoires` |

### 📚 Contenu SRD 2014

**9 races** — Humain · Elfe · Nain · Halfelin · Drakéide · Gnome des roches · Demi-elfe · Demi-orc · Tieffelin

**12 classes** (niv. 1–20, full casters) — Barbar · Barde · Clerc · Druide · Guerrier · Moine · Occultiste · Paladin · Rôdeur · Roublard · Ensorceleur · **Magicien**

**42 sorts** curated — schéma v2.0 (`effects[]`, pools dérivés du compendium YAML), incantation instantanée avec métadonnées mécaniques.

**Magicien (pool curated)** — 4 cantrips · 18 sorts au grimoire (quota SRD niv. 7).

---

## ⚔️ Combat Engine (moteur pur)

Le **Combat Engine** vit dans `jdr_engine/game/` et `jdr_engine/domain/combat/` — **aucun rendu Discord ni Web** : fonctions déterministes + **EventBus** (ADR-003).

| Livré | Détail |
|-------|--------|
| Cycle de vie | Création, initiative, tours, rounds, clôture (ADR-005) |
| Règles | Attaque vs CA, dégâts, sorts (attaque / sauvegarde), économie d'actions |
| Concentration | Rupture sur dégâts (save CON), nettoyage des buffs liés |
| Effets actifs | Registre `ActiveEffect`, horloge combat, persistance blob (ADR-006) |
| Buffs mécaniques | `bless` (+1d4), `hunters_mark` (+1d6) via registre |

Persistance SQLite (`CombatState` JSON, version blob **2**). Décisions actées : [`docs/adr/`](docs/adr/).

---

## 🔌 API HTTP — banc de test

Une **API FastAPI** permet d'observer un personnage **hors Discord** : fiche calculée, lancer un sort, repos court/long. Couche de sérialisation **données uniquement** (pas de texte pré-formaté Discord).

```powershell
venv\Scripts\python.exe -m pip install -r requirements.txt
venv\Scripts\python.exe -m uvicorn --factory interfaces.api.app:create_app
```

→ Documentation complète : [`docs/API_LOCAL.md`](docs/API_LOCAL.md) · Swagger : `http://127.0.0.1:8000/docs`

| Méthode | Route | Effet |
|:-------:|-------|-------|
| `GET` | `/characters/{id}/sheet` | Fiche calculée (DTO JSON) |
| `POST` | `/characters/{id}/cast` | Lance un sort, persiste l'état |
| `POST` | `/characters/{id}/short-rest` | Repos court |
| `POST` | `/characters/{id}/long-rest` | Repos long |

---

## 💡 Philosophie

- 🔒 **Stats sacrées** — le joueur ne modifie jamais PV, emplacements ou caractéristiques à la main.
- ⚙️ **Moteur d'abord** — tout calcul passe par `jdr_engine`, en réaction à une action de jeu.
- 👥 **Un actif à la fois** — plusieurs personnages possibles, un seul actif par défaut (`/perso-choisir`).
- 📦 **Compendium = source de vérité** — races, classes, sorts en YAML ; pools dérivés, jamais codés en dur.

---

## 🚀 Démarrage rapide (Windows)

### Prérequis

- [Python 3.12](https://www.python.org/downloads/) recommandé (minimum 3.11) — cocher **Add to PATH**
- Un bot sur le [portail Discord Developer](https://discord.com/developers/applications)

### Installation

```powershell
git clone https://github.com/Aztaloph/discord-jdr-bot.git
cd discord-jdr-bot

# Double-clic ou terminal :
.\installer.bat
```

`installer.bat` crée le venv, installe les dépendances et vérifie Python.

### Configuration

```powershell
copy .env.example .env
# Éditer .env → DISCORD_TOKEN=votre_token

# (Optionnel) sync slash commands sur un serveur de dev
copy config.example.json config.json
# Renseigner guild_id
```

### Lancement

```powershell
.\launcher_bot.bat
```

Sortie attendue : `Bot connecté !` + chargement des cogs.

### Rôle MJ

Créez un rôle Discord nommé **`MJ`**. Repos, montée de niveau et suppression personnage le requièrent.

---

## 🧪 Tests

```powershell
.\venv\Scripts\activate
python -m unittest discover -s tests -p "test_*.py" -q
```

**835 tests** — moteur de règles, sorts, combat (C0–C7), effets actifs (ADR-006), concentration, DTO/API, persistance SQLite.

Validation compendium :

```powershell
python tools/validate_compendium.py dnd5e
```

---

## 🏗️ Architecture

```
discord-jdr-bot/
├── main.py                          # Point d'entrée bot Discord
├── bot/cogs/                        # Slash commands (couche fine)
├── interfaces/
│   ├── discord/                     # Handlers, embeds, wizards UI
│   └── api/                         # API FastAPI (banc de test)
├── jdr_engine/                      # Moteur pur — zéro import Discord
│   ├── application/                 # CharacterService, CombatService, DTO
│   ├── core/events/                 # EventBus, événements domaine
│   ├── domain/                      # Character, CombatState, ActiveEffect
│   ├── game/                        # CombatManager (orchestration)
│   ├── rules/                       # Rule Engine (stateless, data-driven)
│   │   ├── effects/                 # Registre effets actifs (ADR-006)
│   │   └── spellcasting/            # Pools, préparation, cast
│   ├── persistence/                 # SQLite
│   └── dice/                        # Parser et roller de dés
├── compendium/dnd5e/entries/        # Données YAML (races, classes, sorts)
├── docs/                            # Schémas sorts, API locale, ADR, architecture
├── data/bot.db                      # Base locale (ignorée par git)
└── tests/unit/                      # Suite unitaire
```

Le **Rule Engine** charge le Compendium YAML et calcule les stats dérivées — aucune règle D&D dans les cogs ni dans `interfaces/`.

---

## 📍 Où on en est

| Axe | Statut | Détail |
|-----|:------:|--------|
| **Passe 2 sorts** | ✅ | Préparés / grimoire / autocomplete mage, outils MJ migration |
| **Level-up 4+ (ASI)** | ✅ | Cap niv. 20, ASI 5 paliers, full casters 1–20 |
| **Axe B — Schéma v2.0** | ✅ | 42 sorts curated, pools dérivés YAML |
| **Concentration (hors combat)** | ✅ | Pose, remplacement, repos, affichage fiche (13 sorts) |
| **DTO + API HTTP** | ✅ | `output_serializers`, endpoints personnage, banc de test |
| **Étape 4 — Combat moteur** | ✅ | C0–C7, ADR-004/005, persistance blob, journal événementiel |
| **B4 — Effets de sorts** | 🚧 | `bless` / `hunters_mark` via registre (ADR-006) ; suite catalogue à venir |
| **Client Web** | 🔜 | Interface de jeu principale (après stabilisation combat) |

Documentation sorts → [`docs/SPELLS_INVENTORY.md`](docs/SPELLS_INVENTORY.md) · [`docs/SPELL_SCHEMA.md`](docs/SPELL_SCHEMA.md)

Feuille de route complète → [`ROADMAP.md`](ROADMAP.md)

---

## 🔐 Sécurité

Ne **jamais** committer :

- `.env` (token Discord)
- `config.json`
- `data/bot.db` / `venv/`

Token exposé → régénérer immédiatement sur le portail Discord.

---

## 📜 Licence contenu

Règles et textes dérivés du **SRD 5.1 (2014)** — Open Gaming License.
