# Vision produit — Discord JDR Bot

> Document fondateur du projet. Il définit la **cible à plusieurs années**, les décisions structurantes arrêtées et la manière dont elles s'articulent avec l'état réel du code.
>
> Pour l'avancement détaillé et les lots en cours, voir [`ROADMAP.md`](ROADMAP.md). Pour l'architecture technique de référence, voir [`docs/ARCHITECTURE_V2.md`](docs/ARCHITECTURE_V2.md) et les [ADR](docs/adr/).

---

## 1. Vision finale du projet

### Le « pourquoi »

Faire tourner une table de jeu de rôle Donjons & Dragons 5e demande aujourd'hui de jongler entre un logiciel de fiche, un lanceur de dés, une VTT payante et un salon vocal. Les outils existants sont soit **fermés et payants**, soit **auto-hébergeables mais austères**, soit **enfermés dans Discord** avec des fiches illisibles.

**Discord JDR Bot** part d'un principe simple, déjà inscrit dans le code : **le joueur ne triche jamais avec ses chiffres**. Les PV, emplacements de sorts et caractéristiques sont **dérivés** par un moteur de règles ; ils ne sont jamais saisis à la main (voir *Principe d'intégrité des stats*, `ROADMAP.md`). Autour de ce moteur, on construit un outil de jeu complet, **libre, auto-hébergeable et jouable de bout en bout gratuitement**.

### La cible

Une **plateforme de JDR en ligne** structurée autour d'un moteur de règles indépendant de toute interface :

- un **moteur (`jdr_engine`)** qui applique les règles SRD 2014 et, à terme, d'autres rulesets ;
- un **client Web** riche qui devient **l'interface de jeu principale** (fiche, sorts, combat, carte, écran MJ) ;
- **Discord** réduit à un rôle de **liant social et de notifications**, pas d'interface de jeu ;
- une **API** qui expose le moteur à toutes les interfaces (Web d'abord, puis mobile/VTT si pertinent).

Le succès se mesure à une chose : **n'importe qui peut héberger le projet, inviter ses amis et jouer une campagne entière sans payer**.

### Décision structurante — l'avenir est le client Web

> **L'interface de jeu du futur est le client Web. Discord cesse d'être l'interface de jeu.**

C'est la décision qui prime sur toutes les autres et sur toute réflexion antérieure. Elle est justifiée par trois constats :

1. **Les limites de Discord sont un plafond de verre** — 4096 caractères par embed, composants restreints, pas de vraie mise en page. Reproduire une fiche de RPG dans un embed produit une « fiche Excel » illisible.
2. **Le combat a besoin d'un vrai HUD** — carte, jetons, ressources par tour, animations : impossible à rendre correctement dans Discord.
3. **Le moteur est déjà découplé** — l'architecture (`RuleEngine`, `EventBus`, `Application Services`) a été pensée dès le départ pour servir plusieurs interfaces. Le Web n'est pas une réécriture, c'est **la deuxième interface** que l'architecture attendait.

**Conséquence directe : aucune nouvelle fonctionnalité joueur n'est développée pour Discord.** L'effort d'interface va au client Web.

---

## 2. Architecture cible

L'architecture de référence est décrite dans `docs/ARCHITECTURE_V2.md`. Ce document en rappelle le principe fondateur et la répartition des responsabilités sous l'angle de la vision produit.

### Principe fondateur

> **Le moteur ne connaît ni Discord, ni le Web, ni D&D par son nom. Il connaît des mécanismes et des identifiants.**

Toute interface est un **adaptateur** interchangeable branché sur le même moteur.

### Vue d'ensemble

```
┌──────────────────────────────────────────────────────────────┐
│                        INTERFACES                             │
│   Web (jeu)   ·   Discord (social)   ·   CLI / VTT (futurs)   │
└───────────────────────────┬──────────────────────────────────┘
                            │  API (REST + WebSocket)  ↑↓ Events
┌───────────────────────────▼──────────────────────────────────┐
│                     APPLICATION LAYER                         │
│      Services (use cases)  +  EventBus (publish/subscribe)    │
└──────┬────────────────┬────────────────┬─────────────────────┘
       │                │                │
┌──────▼──────┐  ┌──────▼──────┐  ┌──────▼──────┐  ┌───────────┐
│ GAME ENGINE │  │ RULE ENGINE │  │ PERSISTENCE │  │  PLUGINS  │
│   (état)    │  │  (calcul)   │  │    (I/O)    │  │(extensions)│
└──────┬──────┘  └──────┬──────┘  └─────────────┘  └───────────┘
       └────────┬───────┘
                │
┌───────────────▼──────────────────────────────────────────────┐
│                        COMPENDIUM                             │
│    definition.yaml · lore · i18n · assets · meta · homebrew   │
└───────────────────────────────────────────────────────────────┘
```

### Séparation des responsabilités

| Couche | Package | Responsabilité | Connaît l'UI ? |
|---|---|---|---|
| **Rule Engine** | `jdr_engine/rules/` | Validation, résolution, calcul des stats dérivées — **sans état** | ❌ |
| **Game Engine** | `jdr_engine/game/` | Transitions d'état, machines à états (combat, session) | ❌ |
| **Application** | `jdr_engine/application/` | Use cases (`CharacterService`, `CombatService`, `CompendiumService`) | ❌ |
| **EventBus** | `jdr_engine/core/events/` | Diffusion des événements métier (pub/sub in-process, typé) | ❌ |
| **Compendium** | `compendium/` | Données de jeu YAML + lore + assets, par ruleset | ❌ |
| **Persistence** | `jdr_engine/persistence/` | Repositories, migrations versionnées | I/O |
| **API** | `interfaces/api/` | Expose les services au monde extérieur (REST + WebSocket) | Contrat |
| **Interfaces** | `interfaces/web`, `interfaces/discord` | Adaptateurs de présentation | ✅ |

**Règle d'or de dépendance :** `interfaces/* → application → game → domain`. Le domaine ne dépend de **rien**. Une interface ne parle **jamais** directement au Game Engine : elle passe par les Services et **réagit aux événements** de l'EventBus.

### Le rôle central de l'EventBus

L'EventBus (ADR-003) est la clé qui rend le multi-interface possible **sans toucher au moteur** :

- Le Game Engine et les Services **publient** des événements (`AttackResolved`, `SpellCast`, `CharacterLevelUp`…) sans connaître aucun abonné.
- Chaque interface **s'abonne** et traduit l'événement dans son propre langage : le Web pousse une mise à jour WebSocket, Discord envoie une notification, un plugin joue un son.
- Ajouter le client Web = **ajouter des abonnés**, pas modifier la logique de jeu.

---

## 3. Rôle de Discord dans l'écosystème

Discord reste dans l'écosystème, mais **change de nature** : de plateforme de jeu, il devient un **liant social et un canal de notification**.

### Ce que Discord fait (périmètre minimal, gelé)

| Fonction | Détail |
|---|---|
| **Chat & voix** | Le salon reste le lieu de la table (rôleplay, voix). C'est le rôle natif de Discord. |
| **Lancement de partie** | Commandes légères pour ouvrir/rejoindre une session. |
| **`/personnage`** | Renvoie vers le **client Web** (lien profond vers la fiche/la session), ne rend plus la fiche dans un embed. |
| **Notifications** | « C'est ton tour », « repos long effectué », « la partie commence » — poussées via l'EventBus. |

### Ce que Discord ne fait plus (et ne fera pas)

- ❌ Pas de nouvelle fiche riche, de tableau de bord, d'onglets ni de menus de sorts dans Discord.
- ❌ **Aucun HUD de combat Discord.** Le combat se joue sur le Web.
- ❌ Aucune nouvelle fonctionnalité joueur ajoutée aux cogs Discord.

Les commandes joueur existantes (`/creer-perso`, `/perso-afficher`, `/sort`, `/preparer-sorts`…) sont **maintenues telles quelles** tant qu'elles servent, puis progressivement **redirigées vers le Web**. Elles ne sont plus une cible d'investissement.

> **Justification.** Concentrer l'effort d'interface sur un seul front (le Web) évite de maintenir deux UI concurrentes et permet enfin une expérience « jeu » que Discord ne peut techniquement pas offrir. Discord garde ce qu'il fait le mieux : réunir les gens.

---

## 4. Vision du client Web

Le client Web est **l'interface de jeu principale**. Il consomme l'API et se met à jour en temps réel via WebSocket (événements du moteur). Il incarne la sensation de « **jouer dans une vraie interface de RPG** », pas d'enchaîner des commandes.

> **Note importante.** Les maquettes ci-dessous proviennent d'une réflexion initialement formulée pour Discord. Elles sont ici **reclassées comme spécification UX du client Web**. Aucune n'est une cible Discord.

### 4.1 Principe : tableau de bord, pas « fiche Excel »

On n'affiche **jamais tout d'un coup**. La fiche principale ne montre que ce qui sert 90 % du temps ; le reste est accessible par onglets et menus déroulants.

**Fiche principale (hors combat)** — identité, PV/CA, caractéristiques, valeurs dérivées clés (attaque, DD des sorts, initiative, vitesse), conditions actives. Navigation par onglets persistants :

```
🧙 Aria — Elfe Magicien niv. 4
❤️ 26 / 31    🛡️ 15    🎲 Inspiration

FOR 8 (-1)   DEX 16 (+3)   CON 14 (+2)
INT 18 (+4)  SAG 12 (+1)   CHA 10 (+0)

⚔️ Attaque +6   ✨ DD sorts 15   🎯 Init +3   🚶 9 m

[ Infos ] [ Combat ] [ Magie ] [ Sac ] [ Capacités ] [ Journal ]
```

### 4.2 Navigation par onglets et détail progressif

- **Santé** — PV, PV temporaires, dés de vie, résistances/immunités/vulnérabilités.
- **Magie** — sorts groupés par niveau (menu déroulant) ; un clic ouvre le **détail d'un sort** (portée, durée, effet). On ne liste jamais 20 sorts à plat.
- **Sac (inventaire)** — objets par catégorie ; un clic ouvre quantité, effet, poids ; actions jeter/vendre.
- **Capacités** — traits, aptitudes de classe, maîtrises.
- **Statistiques détaillées** — sauvegardes et compétences, consultées à la demande (jamais toutes affichées en permanence).

Les onglets restent **au même endroit** ; seul le panneau central change. Le joueur a l'impression d'être dans un menu de jeu.

### 4.3 Vue de combat dédiée (HUD)

Pendant le combat, l'interface bascule sur un **HUD compact** mis à jour automatiquement à chaque tour :

```
🧙 Aria — Ton tour
❤️ 26/31   🛡️ 15   🚶 9 m
Action ✔   Bonus ✔   Réaction ❌
Concentration : Hâte
Conditions : Aucune
[ ⚔ Attaque ]  [ ✨ Sort ]  [ 🎒 Objet ]  [ Examiner ]
```

Le joueur consulte rarement sa fiche complète pendant un combat, mais il a constamment besoin de ses PV, sa CA, ses ressources et ses actions restantes. **Deux vues distinctes** (fiche complète ↔ HUD de combat) pour deux usages distincts.

### 4.4 Écran Maître du Jeu

Le MJ dispose d'une vue dédiée : suivi d'initiative, PV/états des PNJ et monstres, contrôle de la carte, déclenchement d'événements. C'est l'écran qui orchestre la session ; les joueurs n'en voient que les effets.

### 4.5 Carte & VTT (horizon long)

Une carte dynamique avec jetons, brouillard de guerre et déplacements. Le Compendium prévoit déjà des assets `token.png` par entité. Cette brique est **loin dans la roadmap**, mais les **formats** (assets, positions) sont conçus pour ne pas la bloquer.

### 4.6 Confidentialité par défaut

Ce qui était « message éphémère » sur Discord devient la **norme Web** : chaque joueur voit **ses** PV, **son** inventaire, **ses** sorts préparés. La table ne voit que ce qui est public. Le MJ voit tout.

---

## 5. Système de combat — une API moteur pure

Le combat est le **gros chantier** identifié dans `ROADMAP.md` (**ÉTAPE 4 — Système de combat complet**). La décision structurante en fixe la nature.

> **Le Combat Engine est une API moteur pure : des fonctions déterministes et des événements. Il ne construit jamais d'interface — ni Discord, ni Web.**

### Ce que le Combat Engine fait

- Gère l'**état de combat** (`Game Engine`) : initiative, ordre des tours, actions/bonus/réactions disponibles, concentration, conditions, PV des participants.
- Expose des **use cases** via `CombatService` : démarrer un combat, résoudre une attaque, lancer un sort en combat, appliquer des dégâts/soins, passer au tour suivant.
- **Publie des événements** métier : `CombatStarted`, `InitiativeRolled`, `TurnStarted`, `AttackDeclared`, `AttackResolved`, `DamageDealt`, `ConditionApplied`… (déjà anticipés dans ADR-003).
- Retourne des **résultats de calcul purs** (Rule Engine) : jets, dégâts, réussite/échec de sauvegarde.

### Ce que le Combat Engine ne fait jamais

- ❌ Aucun embed, bouton, ou message Discord.
- ❌ Aucun composant Web.
- ❌ Aucune supposition sur la manière dont le combat sera affiché.

### Comment les interfaces s'y branchent

```
CombatService.attack(cmd)
  → CombatManager.resolve_attack()        (Game Engine, état)
  → RuleEngine résout jet + dégâts        (calcul pur)
  → publish(AttackResolved(...))          (EventBus)
        ├─ Web  →  push WebSocket → HUD mis à jour, animation
        ├─ Discord  →  notification « Aria attaque le gobelin »
        └─ AutoSaveHandler  →  persistance de l'état de combat
```

Concrètement, **chaque interface s'abonne au boot** aux événements de combat qui l'intéressent (`event_bus.subscribe(AttackResolved, handler)`), puis les traduit dans son propre langage. Le moteur ne sait pas qui l'écoute ; il se contente de publier.

| Abonné | Écoute | Ce qu'il en fait |
|---|---|---|
| **Client Web (joueur)** | `TurnStarted`, `AttackResolved`, `DamageDealt`, `ConditionApplied`… | Pousse une mise à jour **WebSocket** au HUD de combat (§4.3) : PV, ressources du tour, animation de l'attaque. C'est **le seul à rendre le combat**. |
| **Client Web (écran MJ)** | Les mêmes, plus l'état complet | Met à jour le suivi d'initiative, les PV/états des PNJ et monstres (§4.4). |
| **Discord** | `CombatStarted`, `TurnStarted` (surtout) | Envoie une **notification texte** dans le salon (« C'est au tour d'Aria », « Aria attaque le gobelin »). **Aucun rendu de combat**, aucun embed de HUD. |
| **AutoSaveHandler** (moteur) | `AttackResolved`, `TurnStarted`… | Persiste l'état de combat, sans interface. |
| **Plugins** (optionnels) | Événements souscrits | Réactions custom (son de coup critique, succès…), no-op si l'interface concernée est absente. |

La règle de partage est nette : **le Web affiche et joue le combat, Discord se contente de notifier, le moteur persiste.** Le HUD de combat décrit en §4.3 n'est donc qu'un **consommateur** de ces événements, développé côté Web. Le moteur, lui, reste réutilisable par n'importe quelle interface sans aucune modification — c'est précisément ce que garantit l'EventBus.

> **Justification.** Écrire le combat comme moteur pur permet de le **tester intégralement sans interface** (la suite unitaire actuelle compte déjà 645 tests), de le brancher au Web sans réécriture, et d'éviter le piège d'un combat « ficelé » à Discord qu'il faudrait défaire ensuite. Les prérequis règles sont déjà partiellement documentés dans `docs/COMBAT_ROLL_PREREQUISITES.md`.

---

## 6. Principes UX / UI

Ces principes s'appliquent au client Web (interface de jeu) ; Discord n'est plus concerné.

1. **Détail progressif.** Montrer l'essentiel, révéler le reste à la demande. Jamais de « mur d'informations ».
2. **Contexte avant tout.** L'interface s'adapte à la situation : exploration ≠ combat. Les actions proposées sont celles qui ont du sens ici et maintenant.
3. **Deux vues pour deux usages.** Fiche complète pour consulter, HUD compact pour agir en combat.
4. **Intégrité des stats visible.** L'UI ne propose que des **choix encadrés** (création, montée de niveau) ; jamais d'édition libre d'une valeur dérivée. Ce principe moteur devient une garantie ressentie par le joueur.
5. **Confidentialité par défaut.** Chacun voit ses informations ; la table ne voit que le public ; le MJ voit tout.
6. **Sensation de jeu.** Navigation stable (onglets fixes), retours immédiats, animations sobres au service de la lisibilité — pas de gadget.
7. **Le moteur est la source de vérité.** L'UI n'implémente **aucune règle** : elle affiche des résultats calculés et envoie des intentions. Aucune règle D&D en dur dans le front.

---

## 7. Architecture d'hébergement hybride

Le projet doit être **100 % auto-hébergeable gratuitement**, tout en laissant la place à des services managés optionnels.

### Auto-hébergement (gratuit, par défaut)

```bash
docker compose up
```

Tout tourne chez l'utilisateur : moteur, API, client Web, base locale (SQLite). Aucune dépendance à un service tiers, aucune donnée envoyée à l'extérieur. C'est le mode de référence — **chaque MJ héberge sa propre instance avec ses propres données**, principe déjà posé dans `ROADMAP.md`.

### Services managés (optionnels, payants)

Pour ceux qui ne veulent pas héberger, une **offre cloud** propose exactement le même moteur, opéré et sauvegardé. Le passage de l'un à l'autre ne change **ni les règles, ni les fonctionnalités de jeu** — uniquement le confort d'exploitation.

| | Auto-hébergé | Cloud managé |
|---|---|---|
| Moteur & règles | Identiques | Identiques |
| Fonctionnalités de jeu | Toutes | Toutes |
| Sauvegardes | À la charge de l'hôte | Automatiques |
| Mises à jour | Manuelles (`git pull` / image) | Gérées |
| Coût | Gratuit | Abonnement (confort) |

> **Justification.** Le modèle Home Assistant : gratuit et complet en local, l'abonnement finance l'infrastructure et le confort, jamais les fonctionnalités.

---

## 8. Philosophie open source et modèle premium

### La règle qui ne changera jamais

> **Tout ce qui est nécessaire pour jouer une campagne complète reste gratuit et auto-hébergeable. Tout ce qui demande une infrastructure, une création de contenu professionnelle ou un service continu peut devenir premium.**

Le **moteur** et les **fonctionnalités de base** ne sont **jamais** payants. Gratuitement, tout le monde doit pouvoir : héberger son serveur, inviter ses amis, jouer une campagne entière, utiliser toutes les règles SRD, créer ses cartes, importer ses assets, écrire ses scénarios.

### Ce qui reste gratuit (non négociable)

- ✅ Le moteur, les règles SRD, la progression, les sorts.
- ✅ Le système de combat, la carte, le brouillard de guerre, les animations.
- ✅ Le système de campagnes et l'import d'assets personnels (PNG, MP3, OGG…).
- ✅ L'auto-hébergement complet.

### Ce que le premium peut vendre — du confort et du contenu, pas des possibilités

Sur le modèle **VS Code / GitLab / Bitwarden** : le cœur est libre, la valeur ajoutée est autour.

| Offre | Contenu | Nature |
|---|---|---|
| **Cloud** (abonnement) | Sauvegarde cloud, synchronisation multi-appareils, bibliothèque personnelle synchronisée | Service continu |
| **Campagnes officielles** | Aventures clé en main produites/validées par l'équipe (contenu long, illustrations, musiques, éventuellement voix) | Création professionnelle |
| **Packs premium** | Packs graphiques et sonores conçus spécialement, jetons HD, portraits | Création professionnelle |
| **Génération assistée (horizon IA)** | Génération de donjons/PNJ à la demande ; l'abonnement finance les coûts d'appels IA | Service continu |

### Marketplace communautaire (horizon long)

Si les **formats de campagnes et de packs** sont propres dès le départ, une marketplace type *Steam Workshop* devient naturelle : contenus gratuits partagés par la communauté, contenus payants créés par des auteurs (partage de revenus). Cette possibilité **n'est pas une priorité**, mais l'architecture (Compendium, packs, homebrew déjà prévus dans `ARCHITECTURE_V2.md`) est conçue pour ne pas la fermer.

### Le contrat moral

> « Je paie parce que je veux soutenir un super projet, pas parce qu'on m'empêche de jouer. »

C'est le seul indicateur qui compte pour valider une future offre premium. Toute idée qui donnerait l'impression d'une version libre « bridée » est écartée par principe.

---

## 9. Roadmap actualisée

Cette roadmap **prolonge** `ROADMAP.md` sans le contredire : les étapes et axes existants sont conservés, et le virage Web y est inséré à sa place logique. La règle d'ordonnancement est : **finir le moteur avant de bâtir le Web**, car le Web consomme le moteur.

### Séquencement

Les libellés **ÉTAPE** sont ceux de `ROADMAP.md` (numéros canoniques : ÉTAPE 4 = combat, ÉTAPE 5 = portage 2024 en toute fin). Comme les nouvelles étapes Web s'intercalent **avant** l'ÉTAPE 5, la numérotation seule n'est plus séquentielle : la colonne **Ordre d'exécution** donne l'enchaînement réel.

| Ordre d'exécution | Phase (`ROADMAP.md`) | Contenu | Interface visée | Statut |
|:---:|---|---|---|---|
| **1** | **ÉTAPE 3** | Compléter les classes (Passe 3 aptitudes, Passe 4 UI/libellés), **Axe A** (progression) et **Axe B** (sorts + moteur d'effets B4) | Discord (existant, maintenu) | 🚧 En cours |
| **2** | **ÉTAPE 4** | **Système de combat comme API moteur pure** : `CombatService`, `CombatManager`, événements combat (ADR-003), aucun rendu d'interface | Aucune (moteur + events) | ⏭️ Prochain gros chantier |
| **3** | **ÉTAPE 6 — API** | `interfaces/api/` : REST + WebSocket exposant `CharacterService`, `CombatService`, `CompendiumService` ; push des événements EventBus | Contrat API | 🔜 Nouveau |
| **4** | **ÉTAPE 7 — Client Web** | Fiche/tableau de bord, onglets, magie, inventaire, **HUD de combat**, écran MJ (§4) | **Web (interface de jeu principale)** | 🔜 Nouveau |
| **5** | **ÉTAPE 8 — Discord minimal** | Réduction de Discord à chat / lancement de partie / `/personnage` → Web / notifications (§3) | Discord (social) | 🔜 Nouveau |
| **6** | **ÉTAPE 9 — Contenu & carte** | Campagnes, packs d'assets, carte/VTT, marketplace (horizon long) | Web | 🔭 Long terme |
| **7** | **ÉTAPE 5** | Portage / fix version 2024 (armes, dégâts, actions bonus, sous-classes) | Transverse | ⏸️ Après le combat, comme prévu |

> **Note.** L'`ÉTAPE 5` (portage 2024) conserve son numéro de `ROADMAP.md` mais s'exécute **en dernier** (ordre 7), **volontairement en fin de parcours**, après la stabilisation du combat et du Web. Les étapes 6 à 9 sont de **nouvelles étapes** introduites par cette vision, numérotées à la suite de l'existant.

### Jalons produit (MVP → v1.0)

| Jalon | Définition | Contenu clé |
|---|---|---|
| **MVP** | Jouable en combat via une interface moderne | ÉTAPE 4 (combat moteur) + ÉTAPE 6 (API) + ÉTAPE 7 réduit à fiche + HUD combat |
| **Alpha** | Une campagne complète jouable sur le Web | Client Web complet (§4), Discord minimal (ÉTAPE 8) |
| **Beta** | Confort et contenu | Cloud optionnel, campagnes officielles, packs, écran MJ abouti |
| **v1.0** | Plateforme ouverte | Carte/VTT, formats de packs stabilisés, base marketplace |

### Où s'arrêter côté Discord — réponse tranchée

**On ne pousse plus Discord au-delà du moteur.** Les lots Discord en cours (Passe 3/4, Axes A/B) qui **enrichissent le moteur** sont utiles et se terminent normalement — ils bénéficieront directement au Web. Mais **aucune nouvelle brique d'interface joueur Discord** n'est engagée. Dès l'ÉTAPE 4 (combat moteur pur), l'effort d'interface bascule vers l'API puis le Web.

---

## 10. Décisions et arbitrages

Traçabilité des choix arrêtés et, surtout, des **pistes écartées**, afin que la décision reste documentée.

### Décisions arrêtées

| # | Décision | Justification courte |
|---|---|---|
| D1 | **Le client Web est l'interface de jeu du futur.** | Les limites de Discord empêchent une vraie UI de RPG ; le moteur est déjà découplé. |
| D2 | **Discord est réduit au social/notifications.** | Concentrer l'effort sur une seule UI ; garder Discord pour ce qu'il fait le mieux. |
| D3 | **Le Combat Engine est une API moteur pure (fonctions + events).** | Testable sans UI, réutilisable par toute interface, jamais à défaire. |
| D4 | **Le moteur ne connaît aucune interface** ; tout passe par Services + EventBus. | Multi-interface sans modifier le moteur (ADR-003). |
| D5 | **Moteur et fonctionnalités de jeu 100 % gratuits et auto-hébergeables.** | Confiance de la communauté ; éviter l'image « open source bridé ». |
| D6 | **Le premium vend du confort et du contenu, pas des possibilités.** | Modèle VS Code / Home Assistant ; financement sain. |
| D7 | **Finir le moteur avant de bâtir le Web ; portage 2024 en dernier.** | Le Web consomme le moteur ; éviter de porter des règles instables. |
| D8 | **Les maquettes (tableau de bord, onglets, HUD) sont des specs UX du client Web.** | Elles décrivent la bonne UX, sur la bonne plateforme. |

### Pistes écartées

| Piste écartée | Raison |
|---|---|
| **UI Discord riche** (tableau de bord, onglets, menus de sorts imbriqués dans des embeds) | Décision D1/D2 : obsolète. Techniquement plafonné par Discord, et concurrence inutilement le Web. Reclassée comme **spec UX du client Web** (§4). |
| **HUD de combat dans Discord** | Le combat se joue sur le Web (D1/D3). Discord ne reçoit que des **notifications**. |
| **Nouvelles fonctionnalités joueur ajoutées aux cogs Discord** | Aucun investissement d'interface joueur supplémentaire sur Discord (D2). |
| **Combat couplé à une interface** (rendu Discord/Web dans le moteur) | Violerait D3/D4 ; imposerait une réécriture au moment du Web. |
| **Rendre payantes des fonctionnalités de base** (combat, carte, fog, campagnes, animations) | Contraire à D5 ; casserait la confiance de la communauté. |
| **Event sourcing complet** pour l'état de jeu | Rejeté dans ADR-003 : complexité disproportionnée ; le pub/sub suffit, persistance sélective possible. |
| **Message broker externe (Redis/RabbitMQ) dès la v1** | Rejeté dans ADR-003 : infrastructure superflue ; l'EventBus in-process expose une interface compatible avec un adaptateur distribué ultérieur. |

---

*Document de vision produit — maintenu au niveau projet. Toute évolution structurante doit rester cohérente avec les ADR (`docs/adr/`) et se refléter dans `ROADMAP.md`.*
