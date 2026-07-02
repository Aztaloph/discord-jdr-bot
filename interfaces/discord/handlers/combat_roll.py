# interfaces/discord/handlers/combat_roll.py
"""Flags combat /roll Discord → modules Lot A + affichage Traits actifs (Phase 4.8)."""
from __future__ import annotations

from dataclasses import dataclass

from jdr_engine.domain.character.character import Character
from jdr_engine.rules.class_features.barbarian import (
    rage_active as persisted_rage_active,
    rage_damage_bonus,
    rage_resistances,
)
from jdr_engine.rules.class_features.rogue import sneak_attack_dice_count
from jdr_engine.rules.engine import RuleEngine


@dataclass(frozen=True)
class CombatRollFlags:
    """Contexte combat optionnel sur ``/roll`` (d20 + perso)."""

    ranged_weapon: bool = False
    rage_active: bool = False
    reckless: bool = False
    sneak_attack_eligible: bool = False

    @property
    def is_combat_roll(self) -> bool:
        return any(
            (
                self.ranged_weapon,
                self.rage_active,
                self.reckless,
                self.sneak_attack_eligible,
            )
        )


def _has_feature(engine: RuleEngine, character: Character, feature_id: str) -> bool:
    return any(
        t.entry_id == feature_id
        for t in engine.get_class_features(character.class_id, character.level)
    )


def _effective_rage(character: Character, flags: CombatRollFlags) -> bool:
    choices = character.choices or {}
    return flags.rage_active or persisted_rage_active(choices)


def _has_archery(character: Character) -> bool:
    choices = character.choices or {}
    return (
        character.class_id == "fighter"
        and choices.get("fighting_style") == "archery"
    )


def _humanize_hook_line(line: str) -> str | None:
    """Convertit une piste d'audit du hook d20 en libellé joueur."""
    if line.startswith("hint:"):
        return None
    if "relance nat. 1" in line:
        suffix = line.split("→", 1)[-1].strip() if "→" in line else line
        return f"Chanceux → relance nat. 1 {suffix}"
    if "fighting_style_archery" in line or "attack_roll_bonus" in line:
        return None  # remplacé par libellé Archerie
    if "reckless_attack_melee_str" in line:
        return "Attaque impétueuse → avantage (FOR mêlée)"
    if "target_is_reckless" in line:
        return "Cible impétueuse → avantage sur l'attaque"
    if "avantage (frightened)" in line or "versus" in line:
        return line.replace("avantage (", "Brave → avantage (")
    if line.startswith("avantage (") or line.startswith("maîtrise"):
        return line
    if line.startswith("+") and "jet d'attaque" in line:
        return None
    return line


def build_trait_display_lines(
    character: Character,
    flags: CombatRollFlags,
    raw_effects: list[str],
    *,
    roll_mode: str,
    engine: RuleEngine,
) -> list[str]:
    """
    Libellés « Traits actifs » pour l'embed Discord.

    Réutilise les modules Lot A pour les effets hors hook (Rage, Attaque sournoise).
    """
    lines: list[str] = []
    seen: set[str] = set()

    def add(line: str) -> None:
        if line not in seen:
            seen.add(line)
            lines.append(line)

    for raw in raw_effects:
        human = _humanize_hook_line(raw)
        if human:
            add(human)

    # ── Archerie (hook + module style de combat) ──
    if flags.ranged_weapon and _has_archery(character):
        add("Archerie → +2 au toucher")

    # ── Rage (module barbare — dégâts + résistances ; hook pour FOR) ──
    if _effective_rage(character, flags) and _has_feature(engine, character, "rage"):
        bonus = rage_damage_bonus(character.level)
        resist = ", ".join(sorted(rage_resistances()))
        add(f"Rage → +{bonus} dégâts mêlée FOR, résistance {resist}")
        if any("rage_active" in r for r in raw_effects):
            add("Rage → avantage sur tests et sauvegardes de FOR")

    # ── Attaque impétueuse (hook d20) ──
    if flags.reckless and _has_feature(engine, character, "reckless_attack"):
        if roll_mode == "avantage":
            add("Attaque impétueuse → avantage (FOR mêlée)")
        else:
            add("Attaque impétueuse → avantage FOR mêlée (si attaque au corps à corps)")

    # ── Attaque sournoise (module roublard — dégâts si touché) ──
    if flags.sneak_attack_eligible and _has_feature(engine, character, "sneak_attack"):
        dice = sneak_attack_dice_count(character.level)
        add(f"Attaque sournoise → +{dice}d6 si touché (SRD 2014)")

    return lines
