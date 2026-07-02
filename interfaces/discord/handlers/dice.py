# interfaces/discord/handlers/dice.py
"""Handler /roll Discord — branchement moteur d20 + traits personnage (Phase 4.6+)."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Callable

from jdr_engine.application.dto.character_commands import (
    GetCharacterQuery,
    ListCharactersQuery,
)
from jdr_engine.application.character_service import CharacterNotFoundError
from jdr_engine.dice import DiceError, D20RollRequest, parse, roll
from jdr_engine.dice.d20 import D20RollResult
from jdr_engine.domain.character.character import Character
from jdr_engine.rules.roll_effects import roll_d20_for_character

from interfaces.discord.container import DiscordJdrContext
from interfaces.discord.handlers.combat_roll import (
    CombatRollFlags,
    build_trait_display_lines,
)

log = logging.getLogger(__name__)

RandInt = Callable[[int, int], int]


@dataclass
class RollDisplay:
    """Résultat normalisé pour l'embed Discord."""

    dice_notation: str
    rolls: list[int]
    is_kept: list[bool]
    modifier: int
    modifier_label: str
    total: int
    mode: str
    character_name: str | None = None
    applied_effects: list[str] = field(default_factory=list)
    rerolled: bool = False
    traits_active: bool = False


def is_single_d20(dice_str: str) -> bool:
    """True si la notation est un unique d20 (éventuellement + modificateur)."""
    count, faces, _, _ = parse(dice_str)
    return count == 1 and faces == 20


def resolve_character_for_roll(
    ctx: DiscordJdrContext,
    owner_id: int,
    perso: str | None,
) -> Character | None:
    """
    Retourne le personnage dont appliquer les traits.

    - ``perso`` renseigné → ce personnage (obligatoire s'il existe).
    - Sinon → auto si l'utilisateur n'a qu'un seul personnage.
    """
    if not ctx.use_engine_v2 or ctx.character_service is None:
        return None

    owner = str(owner_id)
    service = ctx.character_service

    if perso:
        try:
            return service.get(GetCharacterQuery(owner_id=owner, name=perso.strip()))
        except CharacterNotFoundError:
            raise DiceError(f"Aucun personnage nommé « {perso.strip()} » trouvé.") from None

    characters = service.list_by_owner(ListCharactersQuery(owner_id=owner))
    if len(characters) == 1:
        return characters[0]
    return None


def _modifier_label(modifier: int, sign: str) -> str:
    if modifier == 0:
        return ""
    return f" {sign}{abs(modifier)}"


def _d20_notation(mode: str, modifier: int, sign: str) -> str:
    mod = _modifier_label(modifier, sign)
    if mode == "avantage":
        return f"2d20 (meilleur gardé){mod}"
    if mode == "desavantage":
        return f"2d20 (pire gardé){mod}"
    return f"d20{mod}"


def _from_legacy_roll(result, mode: str) -> RollDisplay:
    return RollDisplay(
        dice_notation=result.dice_notation,
        rolls=result.rolls,
        is_kept=result.is_kept,
        modifier=result.modifier,
        modifier_label=result.modifier_label,
        total=result.total,
        mode=mode,
    )


def _build_d20_request(
    *,
    modifier: int,
    mode: str,
    combat: CombatRollFlags,
) -> D20RollRequest:
    roll_type = "attack" if combat.is_combat_roll else "ability_check"
    return D20RollRequest(
        roll_type=roll_type,
        ability_modifier=modifier,
        base_mode=mode,  # type: ignore[arg-type]
        ranged_weapon=combat.ranged_weapon,
        rage_active=combat.rage_active,
        reckless_attack=combat.reckless,
        str_melee_attack=combat.reckless,
    )


def _from_d20_result(
    result: D20RollResult,
    *,
    sign: str,
    character_name: str,
    display_effects: list[str],
) -> RollDisplay:
    mod = result.modifier
    mod_label = f"{sign}{abs(mod)}" if mod != 0 else ""
    return RollDisplay(
        dice_notation=_d20_notation(result.mode, mod, sign if mod >= 0 else "-"),
        rolls=result.rolls,
        is_kept=result.is_kept,
        modifier=mod,
        modifier_label=mod_label,
        total=result.total,
        mode=result.mode,
        character_name=character_name,
        applied_effects=display_effects,
        rerolled=result.rerolled,
        traits_active=True,
    )


def execute_roll(
    dice_str: str,
    mode: str,
    ctx: DiscordJdrContext | None,
    owner_id: int,
    perso: str | None = None,
    *,
    combat: CombatRollFlags | None = None,
    rng: RandInt | None = None,
) -> RollDisplay:
    """
    Exécute un lancer Discord.

    d20 + personnage résolu → hook ``roll_d20_for_character`` (traits actifs).
    Sinon → ``roll()`` classique.
    """
    if mode not in ("normal", "avantage", "desavantage"):
        raise DiceError(
            f'Mode invalide : "{mode}". Utilise normal, avantage ou desavantage.'
        )

    combat_flags = combat or CombatRollFlags()
    _, _, modifier, sign = parse(dice_str)

    character: Character | None = None
    if ctx is not None and is_single_d20(dice_str):
        character = resolve_character_for_roll(ctx, owner_id, perso)

    if character is not None and ctx is not None and ctx.rule_engine is not None:
        request = _build_d20_request(
            modifier=modifier,
            mode=mode,
            combat=combat_flags,
        )
        result = roll_d20_for_character(
            request,
            character,
            ctx.rule_engine,
            rng=rng,
        )
        display_lines = build_trait_display_lines(
            character,
            combat_flags,
            result.applied_effects,
            roll_mode=result.mode,
            engine=ctx.rule_engine,
        )
        log.info(
            "Roll d20 traits : %s (%s) total=%s effects=%s display=%s",
            character.name,
            character.class_id,
            result.total,
            result.applied_effects,
            display_lines,
        )
        return _from_d20_result(
            result,
            sign=sign,
            character_name=character.name,
            display_effects=display_lines,
        )

    legacy = roll(dice_str, mode=mode)
    display = _from_legacy_roll(legacy, mode)
    if is_single_d20(dice_str) and ctx is not None and ctx.use_engine_v2 and not perso:
        chars = []
        if ctx.character_service:
            chars = ctx.character_service.list_by_owner(
                ListCharactersQuery(owner_id=str(owner_id))
            )
        if len(chars) > 1:
            display.applied_effects.append(
                "hint:plusieurs_persos — précisez le paramètre `perso` pour vos traits"
            )
    return display
