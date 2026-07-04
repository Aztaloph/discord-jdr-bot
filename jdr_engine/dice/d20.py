# jdr_engine/dice/d20.py
"""
Point d'entrée unique pour tous les jets de d20 (SRD 5.1 2014).

API
---

Entrée — ``D20RollRequest`` :
    roll_type            : ``attack`` | ``ability_check`` | ``saving_throw``
    ability_modifier     : modificateur de caractéristique (sans maîtrise)
    proficiency_bonus    : bonus de maîtrise du personnage
    is_proficient        : la maîtrise s'applique-t-elle ?
    ability              : id caractéristique (str, dex, …) si pertinent
    skill                : id compétence (survival, …) si pertinent
    save_versus_condition: condition ciblée (ex. ``frightened``) pour sauvegarde
    base_mode            : avantage / désavantage externe (sort, terrain, …)
    tracking             : jet de pistage (Survival) — contexte Ennemi juré
    recalling_favored_enemy_info : jet d'Intelligence pour se rappeler d'un ennemi juré
    favored_terrain_related      : jet Int/Sag lié au terrain favori

Entrée — ``D20RollContext`` :
    request  : D20RollRequest
    effects  : liste d'effets Compendium (``mechanics.effects``) actifs sur le personnage

Sortie — ``D20RollResult`` :
    rolls              : tous les d20 lancés (y compris relances Lucky)
    is_kept            : dé gardé pour chaque lancer (avantage / relance)
    kept_value         : valeur du d20 retenu avant modificateur
    mode               : mode final (normal | avantage | desavantage)
    modifier           : modificateur total appliqué
    modifier_breakdown : détail textuel (ex. ``+2 (mod DEX) +4 (maîtrise x2)``)
    total              : kept_value + modifier
    natural_20 / natural_1 : sur le d20 final retenu
    applied_effects    : piste d'audit (sources des modifications)
    rerolled           : True si Chanceux a déclenché une relance

Pipeline
--------
1. **Avant le jet** — résolution des effets ``advantage``, ``disadvantage``,
   ``double_proficiency`` ; fusion avec ``base_mode`` (5e : avantages et
   désavantages multiples s'annulent par paires).
2. **Jet** — 1d20 ou 2d20 selon le mode.
3. **Après le jet** — effets ``reroll_natural_1`` (Chanceux) sur le d20 retenu.
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Any, Callable, Literal

from jdr_engine.dice.models import DiceError

D20RollType = Literal["attack", "ability_check", "saving_throw"]
D20Mode = Literal["normal", "avantage", "desavantage"]

RollTypeFilter = Literal["attack", "ability_check", "saving_throw"]


@dataclass(frozen=True)
class D20RollRequest:
    """Paramètres d'un jet de d20."""

    roll_type: D20RollType
    ability_modifier: int = 0
    proficiency_bonus: int = 0
    is_proficient: bool = False
    ability: str | None = None
    skill: str | None = None
    save_versus_condition: str | None = None
    base_mode: D20Mode = "normal"
    tracking: bool = False
    recalling_favored_enemy_info: bool = False
    favored_terrain_related: bool = False
    # ── Contexte features Lot A (SRD 2014) ──
    rage_active: bool = False
    reckless_attack: bool = False
    target_reckless: bool = False
    visible_effect: bool = False
    ranged_weapon: bool = False
    melee_weapon: bool = False
    finesse_weapon: bool = False
    str_melee_attack: bool = False
    expertise_skills: tuple[str, ...] = ()


@dataclass
class D20RollContext:
    """Contexte complet : requête + effets actifs (traits, features de classe)."""

    request: D20RollRequest
    effects: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class D20RollResult:
    """Résultat enrichi d'un jet de d20."""

    request: D20RollRequest
    rolls: list[int]
    is_kept: list[bool]
    kept_value: int
    mode: D20Mode
    modifier: int
    modifier_breakdown: str
    total: int
    natural_20: bool
    natural_1: bool
    applied_effects: list[str] = field(default_factory=list)
    rerolled: bool = False


RandInt = Callable[[int, int], int]


def _default_randint(a: int, b: int) -> int:
    return random.randint(a, b)


def _roll_context_label(roll_type: D20RollType) -> str:
    return {
        "attack": "attack",
        "ability_check": "ability_check",
        "saving_throw": "saving_throw",
    }[roll_type]


def _effect_matches(
    effect: dict[str, Any],
    request: D20RollRequest,
) -> bool:
    """Vérifie si un effet Compendium s'applique à cette requête."""
    effect_type = effect.get("type")
    context = effect.get("context")

    if effect_type == "advantage":
        if context == "saving_throw":
            if request.roll_type != "saving_throw":
                return False
            when = effect.get("when")
            if when == "rage_active":
                return request.rage_active and request.ability == effect.get("ability")
            if when == "danger_sense_visible":
                return request.visible_effect and request.ability == "dex"
            versus = effect.get("versus")
            if versus == "magic":
                return (
                    request.save_versus_condition == "magic"
                    or getattr(request, "save_versus_magic", False)
                )
            abilities = effect.get("abilities") or []
            if abilities and request.ability not in abilities:
                return False
            return (
                versus is not None
                and request.save_versus_condition == versus
            )
        if context == "attack":
            when = effect.get("when")
            if when == "reckless_attack_melee_str":
                return (
                    request.reckless_attack
                    and request.str_melee_attack
                )
            if when == "target_is_reckless":
                return request.target_reckless
            return False
        if context == "ability_check":
            when = effect.get("when")
            if when == "rage_active":
                return request.rage_active and request.ability == effect.get("ability")
            if when == "tracking_favored_enemy":
                return (
                    request.roll_type == "ability_check"
                    and request.skill == "survival"
                    and request.tracking
                )
            if when == "recalling_favored_enemy":
                return (
                    request.roll_type == "ability_check"
                    and request.ability == "int"
                    and request.recalling_favored_enemy_info
                )
            skill = effect.get("skill")
            ability = effect.get("ability")
            if skill and request.skill != skill:
                return False
            if ability and request.ability != ability:
                return False
            return request.roll_type == "ability_check"
        return False

    if effect_type == "attack_roll_bonus":
        if request.roll_type != "attack":
            return False
        when = effect.get("when")
        if when == "ranged_weapon" and not request.ranged_weapon:
            return False
        return True

    if effect_type == "reroll_natural_1":
        contexts = effect.get("contexts") or effect.get("roll_types") or []
        return request.roll_type in contexts

    if effect_type == "double_proficiency":
        if request.roll_type != "ability_check":
            return False
        if effect.get("requires_proficiency") and not request.is_proficient:
            return False
        when = effect.get("when")
        if when == "favored_terrain_related" and not request.favored_terrain_related:
            return False
        if when == "expertise_skill":
            return (
                request.skill is not None
                and request.skill in request.expertise_skills
            )
        abilities = effect.get("abilities") or []
        if abilities and request.ability not in abilities:
            return False
        return True

    return False


def _resolve_mode(
    base_mode: D20Mode,
    effects: list[dict[str, Any]],
    request: D20RollRequest,
    applied: list[str],
) -> D20Mode:
    """Fusionne avantages / désavantages (règle 5e : annulation par paires)."""
    advantage_count = 1 if base_mode == "avantage" else 0
    disadvantage_count = 1 if base_mode == "desavantage" else 0

    for effect in effects:
        if effect.get("type") != "advantage":
            continue
        if not _effect_matches(effect, request):
            continue
        advantage_count += 1
        source = effect.get("source_id") or effect.get("when") or effect.get("versus")
        applied.append(f"avantage ({source})")

    if advantage_count > disadvantage_count:
        return "avantage"
    if disadvantage_count > advantage_count:
        return "desavantage"
    return "normal"


def _resolve_modifier(
    request: D20RollRequest,
    effects: list[dict[str, Any]],
    applied: list[str],
) -> tuple[int, str]:
    """Calcule le modificateur total (maîtrise doublée incluse)."""
    prof_multiplier = 1
    for effect in effects:
        if effect.get("type") != "double_proficiency":
            continue
        if not _effect_matches(effect, request):
            continue
        prof_multiplier = max(prof_multiplier, int(effect.get("multiplier", 2)))
        source = effect.get("source_id") or "double_proficiency"
        applied.append(f"maîtrise x{prof_multiplier} ({source})")

    prof = request.proficiency_bonus * prof_multiplier if request.is_proficient else 0
    modifier = request.ability_modifier + prof

    for effect in effects:
        if effect.get("type") != "attack_roll_bonus":
            continue
        if not _effect_matches(effect, request):
            continue
        bonus = int(effect.get("value", 0))
        modifier += bonus
        source = effect.get("source_id") or "attack_roll_bonus"
        applied.append(f"+{bonus} jet d'attaque ({source})")

    parts: list[str] = []
    if request.ability_modifier:
        sign = "+" if request.ability_modifier >= 0 else ""
        parts.append(f"{sign}{request.ability_modifier} (mod)")
    if prof:
        parts.append(f"+{prof} (maîtrise{' x2' if prof_multiplier > 1 else ''})")
    breakdown = " ".join(parts) if parts else "+0"
    return modifier, breakdown


def _roll_d20_values(mode: D20Mode, rng: RandInt) -> tuple[list[int], list[bool], int]:
    """Lance le ou les d20 et retourne (rolls, is_kept, kept_value)."""
    if mode == "avantage":
        rolls = [rng(1, 20), rng(1, 20)]
        best = max(rolls)
        best_index = rolls.index(best)
        kept = [i == best_index for i in range(2)]
        return rolls, kept, best

    if mode == "desavantage":
        rolls = [rng(1, 20), rng(1, 20)]
        worst = min(rolls)
        worst_index = rolls.index(worst)
        kept = [i == worst_index for i in range(2)]
        return rolls, kept, worst

    value = rng(1, 20)
    return [value], [True], value


def roll_d20(
    context: D20RollContext,
    *,
    rng: RandInt | None = None,
) -> D20RollResult:
    """
    Point d'entrée unique pour un jet de d20 avec hooks avant / après.

    Les effets Compendium dans ``context.effects`` sont appliqués automatiquement.
    """
    randint = rng or _default_randint
    request = context.request
    applied: list[str] = []

    if request.base_mode not in ("normal", "avantage", "desavantage"):
        raise DiceError(
            f'Mode de base invalide : "{request.base_mode}". '
            "Utilise normal, avantage ou desavantage."
        )

    mode = _resolve_mode(request.base_mode, context.effects, request, applied)
    modifier, breakdown = _resolve_modifier(request, context.effects, applied)

    rolls, is_kept, kept_value = _roll_d20_values(mode, randint)
    rerolled = False

    for effect in context.effects:
        if effect.get("type") != "reroll_natural_1":
            continue
        if not _effect_matches(effect, request):
            continue
        if kept_value != 1:
            continue
        new_value = randint(1, 20)
        rolls.append(new_value)
        is_kept.append(True)
        for i in range(len(is_kept) - 1):
            is_kept[i] = False
        kept_value = new_value
        rerolled = True
        source = effect.get("source_id") or "lucky"
        applied.append(f"relance nat. 1 ({source}) → {new_value}")

    total = kept_value + modifier
    return D20RollResult(
        request=request,
        rolls=rolls,
        is_kept=is_kept,
        kept_value=kept_value,
        mode=mode,
        modifier=modifier,
        modifier_breakdown=breakdown,
        total=total,
        natural_20=kept_value == 20,
        natural_1=kept_value == 1,
        applied_effects=applied,
        rerolled=rerolled,
    )
