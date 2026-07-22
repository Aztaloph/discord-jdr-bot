# Discord JDR Bot

**Bot Discord de jeu de rôle — Donjons & Dragons 5e (SRD 2014)**

Organisez vos parties directement sur Discord : fiches personnages, lancer de sorts, repos, montée de niveau — le moteur applique les règles SRD pour vous.

> Chaque MJ héberge **sa propre instance** du bot. Les données restent locales (SQLite), jamais partagées entre serveurs.

<p align="center">

| Tests | Classes | Sorts curated | Python |
|:-----:|:-------:|:-------------:|:------:|
| **543** ✅ | **12/12** | **28** | **3.10+** |

</p>

---

## Ce que fait le bot aujourd'hui

### Commandes joueur

| Domaine | Slash commands |
|---------|----------------|
| **Dés** | `/roll` — d20, avantage/désavantage, hooks traits raciaux |
| **Personnages** | `/creer-perso` · `/perso-afficher` · `/perso-liste` · `/perso-choisir` |
| **Sorts** | `/sort` — lancement avec autocomplete (✨ lançable · 🔒 niveau · 📘 non préparé) |
| **Préparation** | `/preparer-sorts` — re-choix après repos long (clerc, druide, paladin, **magicien**) |
| **Racial** | `/souffle` — Souffle draconique (Drakéide) |

### Commandes MJ (rôle `MJ` requis)

| Domaine | Slash commands |
|---------|----------------|
| **Repos** | `/repos-long` · `/repos-court` |
| **Progression** | `/monter-niveau` — niv. 2–3 (PV, emplacements, sorts ; SRD strict) |
| **Admin** | `/perso-supprimer` |

### Contenu SRD 2014

**9 races** — Humain · Elfe · Nain · Halfelin · Drakéide · Gnome des roches · Demi-elfe · Demi-orc · Tieffelin

**12 classes** (niv. 1–3) — Barbar · Barde · Clerc · Druide · Guerrier · Moine · Occultiste · Paladin · Rôdeur · Roublard · Ensorceleur · **Magicien**

**28 sorts** curated — cantrips, niv. 1 et niv. 2 avec métadonnées mécaniques et incantation instantanée.

---

## Philosophie

- Les **stats sont sacrées** — le joueur ne modifie jamais ses PV, emplacements ou caractéristiques à la main.
- Tout calcul passe par le **moteur de règles** (`jdr_engine`), en réaction à une action de jeu.
- Un joueur peut avoir **plusieurs personnages**, mais **un seul actif** à la fois (`/perso-choisir`).

---

## Démarrage rapide (Windows)

### Prérequis

- [Python 3.10+](https://www.python.org/downloads/) (testé en 3.14) — cocher **Add to PATH**
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

Créez un rôle Discord nommé **`MJ`**. Les commandes repos, montée de niveau et suppression personnage le requièrent.

---

## Tests

```powershell
.\venv\Scripts\activate
python -m unittest discover -s tests/unit -p "test_*.py" -q
```

**543 tests** unitaires — moteur de règles, sorts, persistance SQLite, handlers Discord.

---

## Architecture

```
discord-jdr-bot/
├── main.py                      # Point d'entrée
├── bot/cogs/                    # Slash commands Discord
├── interfaces/discord/          # Handlers, embeds, wizards UI
├── jdr_engine/
│   ├── application/             # CharacterService (use cases)
│   ├── domain/                  # Character, CharacterSheet
│   ├── rules/                   # Rule Engine (stateless, data-driven)
│   ├── persistence/             # SQLite + migrations
│   └── dice/                    # Parser et roller de dés
├── compendium/dnd5e/entries/    # Données YAML (races, classes, sorts, traits)
├── data/bot.db                  # Base locale (ignorée par git)
├── installer.bat / launcher_bot.bat
└── tests/unit/                  # Suite unitaire
```

Le **Rule Engine** charge le Compendium YAML et calcule les stats dérivées — aucune règle D&D codée en dur dans les cogs.

---

## Incantation — où on en est

| Lot | Statut | Détail |
|-----|--------|--------|
| P2a–P2d | ✅ | Taxonomie lanceurs, règles par classe, `/sort`, correctifs |
| P2e | ✅ | `/preparer-sorts` clerc / druide / paladin |
| P2f-0 | ✅ | `/preparer-sorts` magicien — pool = grimoire personnel |
| **P2f** | 🔜 | Autocomplete `/sort` strict mage (préparés + cantrips seulement) |
| P2g–P2h | 🔜 | Outils MJ grimoire + migration persos legacy |

Détail complet → [ROADMAP.md](ROADMAP.md)

**Prochaine étape majeure après la Passe 2 :** système de combat (Étape 4).

---

## Sécurité

Ne **jamais** committer :

- `.env` (token Discord)
- `config.json`
- `data/bot.db` / `venv/`

Token exposé → régénérer immédiatement sur le portail Discord.

---

## Licence contenu

Règles et textes dérivés du **SRD 5.1 (2014)** — Open Gaming License.
