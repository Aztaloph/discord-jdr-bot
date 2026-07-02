# 🎲 Discord JDR Bot — D&D 5e

> **Boîte à outils JDR complète** pour organiser des parties de Donjons & Dragons 5e directement sur Discord.
> Les joueurs ont accès à tout ce qu'il faut (dés, fiches, combat, générateurs) sans quitter Discord.

---

## 📋 Roadmap du projet

Le bot est développé par étapes. Seule l'**Étape 1** est actuellement disponible.

| Étape | Fonctionnalité | État |
|-------|----------------|------|
| **1** | Lancer de dés (`/roll`) | ✅ **FAIT** |
| **2** | Fiches de personnage (créer, modifier, sauvegarder, afficher en MP) | 🔨 À venir |
| **3** | Système de combat (style Pokémon, lobby, sélection d'attaque) | 🔨 À venir |
| **4** | Générateur de PNJ + tables aléatoires | 🔨 À venir |

> Chaque nouvelle étape sera ajoutée au projet au fur et à mesure des tests et retours.

---

## ✅ Étape 1 — Lancer de dés (`/roll`)

### Syntaxe supportée

```
XdY+Z
```

| Exemple | Description |
|---------|-------------|
| `d20` | 1dé20, sans modificateur |
| `1d20+5` | 1dé20 + 5 |
| `3d6` | 3dés6 (carac. standard D&D) |
| `3d6+2` | 3dés6 + 2 |
| `2d8-1` | 2dés8 − 1 |
| `d6+3` | 1dé6 + 3 |
| `d20` (avantage) | 2dés20, garde le plus haut |

**Règles :**
- `X` (nombre de dés) est optionnel → `d6` = `1d6`
- `+Z` (modificateur) est optionnel
- Les espaces sont ignorées (` 2d10+3  ` fonctionne)
- Insensible à la casse (`D20+5` fonctionne)

**Limites de sécurité :**
- Nombre de dés max : **100**
- Faces max : **1000**
- Avantage/désavantage : **d20 uniquement**

### Modes de lancer

| Mode | Description |
|------|-------------|
| **Normal** (défaut) | Lancers standards |
| **🤝 Avantage** | Lance 2d20, garde le plus haut |
| **😬 Désavantage** | Lance 2d20, garde le plus bas |

> Avantage et désavantage ne fonctionnent qu'avec un `d20`. Autres dés = erreur.

### Exemples concrets

```
/roll dé:d20
/roll dé:3d6+2
/roll dé:d20 mode:avantage
/roll dé:1d20+5
/roll dé:2d8-1
```

---

## 🛠️ Prérequis

- **Python 3.10** ou supérieur
- Un **bot Discord** créé sur le [Discord Developer Portal](https://discord.com/developers/applications)
- Le **token** du bot (secret !)

> ⚠️ Ce bot utilise des **slash commands** (`/roll`). Il n'a pas besoin de l'intent *Message Content*. Assure-toi juste d'activer les intents bot normaux.

---

## 🔧 Créer le bot sur le Discord Developer Portal

### 1. Créer une application

1. Va sur [discord.com/developers/applications](https://discord.com/developers/applications)
2. Clique **"New Application"** → donne un nom (ex: `JDR Bot`)
3. Dans le menu gauche : **"Bot"**

### 2. Récupérer le token

1. Toujours dans **"Bot"** :
   - Ton nom de bot (à gauche)
   - Bouton **"Reset Token"** → confirme → copie le token
   - **Colle-le dans `config.json`** (voir section Configuration)
2. Clique sur **"Save Changes"**

### 3. Activer les intents nécessaires

Dans **"Bot"** → **"Privileged Gateway Intents"**, active :

| Intent | Description | Requis ? |
|--------|-------------|----------|
| **PRESENCE INTENT** | Voir si les gens sont en ligne | ❌ Non |
| **SERVER MEMBERS INTENT** | Voir la liste des membres | ❌ Non |
| **MESSAGE CONTENT INTENT** | Lire le contenu des messages | ❌ Non (on utilise des slash commands) |

> ✅ Les intents par défaut suffisent largement pour un bot de dés.

### 4. Générer le lien d'invitation (OAuth2)

1. Menu gauche : **"OAuth2"** → **"URL Generator"**
2. Coche les **scopes** :
   - ✅ `bot`
   - ✅ `applications.commands`
3. Dans **"Bot Permissions"**, décoche tout puis coche uniquement :
   - ✅ **Send Messages** — envoyer des messages
   - ✅ **Use Slash Commands** — utiliser les commandes slash
   - ✅ **Embed Links** — envoyer des embeds (les résultats de dés)
4. Clique **"Copy"** sur le lien généré en bas
5. Ouvre le lien dans ton navigateur → choisis le serveur Discord cible → autorise

---

## 📦 Installation

### 1. Télécharger / cloner le projet

```bash
git clone <URL_DU_REPO>
cd discord-jdr-bot
```

Ou téléverse le dossier directement dans ton espace de travail.

### 2. Créer un environnement virtuel

**Windows (PowerShell / Invite de commandes) :**
```bash
python -m venv venv
venv\Scripts\activate
```

**macOS / Linux :**
```bash
python3 -m venv venv
source venv/bin/activate
```

> 💡 Tu verras `(venv)` devant ton prompt quand l'environnement est activé.

### 3. Installer les dépendances

```bash
pip install -r requirements.txt
```

---

## ⚙️ Configuration

### 1. Créer le fichier de config

Copie le fichier d'exemple :

**Windows :**
```bash
copy config.example.json config.json
```

**macOS / Linux :**
```bash
cp config.example.json config.json
```

### 2. Modifier `config.json`

Ouvre `config.json` dans un éditeur de texte (Notepad, VS Code…) :

```json
{
  "token": "COLLE_TON_TOKEN_ICI",
  "guild_id": null
}
```

| Champ | Valeur | Description |
|-------|--------|-------------|
| `token` | Ton token bot | Copié depuis le Developer Portal |
| `guild_id` | `null` ou un ID | `null` = sync globale (lent, ~1h) / ID numérique = sync serveur unique (instantané) |

#### Comment trouver un `guild_id` ?

1. Sur Discord, active le **mode développeur** :
   - Paramètres Discord → Avancé → **Mode développeur** ✅
2. Fais un clic droit sur le nom du serveur → **"Copier l'identifiant"**
3. Colle le nombre dans `guild_id`

#### Sync rapide en développement

Quand tu modifies le code (ajout de commandes, etc.) :

- **Avec `guild_id`** : les commandes slash sont disponibles **immédiatement** sur ce serveur
- **Sans `guild_id` (null)** : Discord met jusqu'à **1 heure** à propager les commandes globales

> 💡 En dev, mets ton `guild_id` pour tester vite. Pour la prod, remets `null`.

### 3. Ne jamais partager `config.json`

Ce fichier contient ton **token secret**. Ajoute-le au `.gitignore` s'il ne l'est pas déjà (il l'est par défaut dans ce projet).

---

## ▶️ Lancer le bot

```bash
python main.py
```

Tu devrais voir quelque chose comme :

```
🎲 Bot connecté !
   Nom : JDR Bot
   ID  : 123456789012345678
```

Pour arrêter : `Ctrl+C`.

> 💡 Pour tourner en arrière-plan (24/7), voir la section **Hébergement** ci-dessous.

---

## 🔍 Dépannage

### Les slash commands n'apparaissent pas

1. **Vérifie que le bot a le droit d'utiliser les slash commands** dans le lien OAuth2 (scopes `bot` ET `applications.commands` cochés).
2. **Attend** : si `guild_id` est `null`, Discord peut mettre jusqu'à **1 heure** pour registrar les commandes globales.
3. **Redémarre le bot** — un nouveau `guild_id` dans `config.json` force un re-sync.
4. Tape `/` dans Discord — tu devrais voir la liste des commandes disponibles.

### Erreur "Invalid token"

```
Token manquant ou invalide.
Vérifie config.json.
```

- Le token dans `config.json` est vide, `"COLLE_TON_TOKEN_ICI"`, ou mal copié.
- Relève le token sur le **Discord Developer Portal** → Bot → **Token** → **Reset Token** si besoin.

### Le bot ne se connecte pas

- Vérifie ta connexion Internet.
- Vérifie que le token est bien le token du bot (pas le *Client Secret* ni l'*Application ID*).
- Désactive les VPN si Discord est bloqué.

### Erreur "Intents" au lancement

```
discord.errors.PrivilegedIntentsRequired: ...
```

- Va sur le [Developer Portal](https://discord.com/developers/applications) → Bot → **Privileged Gateway Intents**
- Active les intents nécessaires (ou utilise les intents par défaut, suffit pour ce bot).

### `config.json` non trouvé

```
Fichier config.json manquant.
Crée-le depuis config.example.json.
```

- Assure-toi que `config.json` est dans le **même dossier** que `main.py`.
- Vérifie le nom du fichier (pas `config.example.json` mais `config.json`).

---

## 📂 Arborescence du projet

```
discord-jdr-bot/
├── bot/
│   ├── __init__.py
│   ├── cogs/
│   │   ├── __init__.py
│   │   └── dice.py          ← Commande /roll
│   └── utils/
│       ├── __init__.py
│       └── dice_parser.py    ← Parser de dés (utilisable seul)
├── tests/
│   └── test_dice.py         ← Tests unitaires
├── main.py                  ← Point d'entrée
├── config.example.json      ← Template de config
├── requirements.txt         ← Dépendances
├── .gitignore               ← Fichiers ignorés par git
└── README.md                ← Ce fichier
```

---

## 🧪 Lancer les tests

```bash
python -m pytest tests/ -v
# ou
python -m unittest tests.test_dice -v
# ou
python tests/test_dice.py
```

**36 tests** couvrent le parser de dés (parsing, roulant, avantage/désavantage, limites de sécurité).

---

## 🌐 Hébergement (optionnel)

Pour faire tourner le bot **24/7 sans ton PC allumé**, plusieurs options :

| Service | Prix | Facilité | Note |
|---------|------|----------|------|
| **Railway** | Freemium | ⭐⭐⭐ | Déploiement en 1 clic depuis Git |
| **Replit** | Freemium | ⭐⭐⭐⭐ | Idéal pour débuter, inclut une IP fixe payante |
| **VPS** (Kimsufi, OVH…) | ~3€/mois | ⭐⭐ | Contrôle total, nécessite SSH |
| **Raspberry Pi** | Matériel | ⭐⭐ | Solution maison, gratuit |

> ⚠️ Ne mets **jamais** ton `config.json` dans un dépôt Git public ! Le token serait volé et ton bot piraté en quelques minutes.

---

## 🔮 Prochaines étapes

- **Fiches de personnage** — création, modification, sauvegarde auto, envoi en MP pour éviter le flood
- **Système de combat** — lobby de combat, engagement, tour par tour style Pokémon (sélection d'attaque parmis le répertoire)
- **Générateur de PNJ** — PNJ aléatoires avec lore contextuel généré

Chaque étape suivra le même cycle : développement → livraison → tests → retours → ajustements.

---

*Projet communautaire JDR D&D 5e — Discord*
