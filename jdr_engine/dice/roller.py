# jdr_engine/dice/roller.py
# Exécute un lancer de dés à partir d'une notation parsée.
import random

from jdr_engine.dice.models import DiceError, RollResult
from jdr_engine.dice.parser import parse


def roll(dice_str: str, mode: str = "normal") -> RollResult:
    """
    Parse et exécute le lancer de dés.

    mode : "normal" | "avantage" | "desavantage"
    """
    if mode not in ("normal", "avantage", "desavantage"):
        raise DiceError(
            f'Mode invalide : "{mode}". Utilise normal, avantage ou desavantage.'
        )

    count, faces, modifier, sign = parse(dice_str)

    if mode in ("avantage", "desavantage"):
        if faces != 20:
            raise DiceError(
                "L'avantage/désavantage ne s'applique qu'aux d20."
            )
        all_rolls = [random.randint(1, 20) for _ in range(2)]

        if mode == "avantage":
            best = max(all_rolls)
            best_index = all_rolls.index(best)
            kept = [i == best_index for i in range(len(all_rolls))]
            kept_label = " (meilleur gardé)"
        else:
            worst = min(all_rolls)
            worst_index = all_rolls.index(worst)
            kept = [i == worst_index for i in range(len(all_rolls))]
            kept_label = " (pire gardé)"

        kept_total = sum(r for r, k in zip(all_rolls, kept) if k)
        total = kept_total + modifier
        modifier_label = f"{sign}{abs(modifier)}" if modifier != 0 else ""

        return RollResult(
            dice_notation=f"2d20{kept_label}",
            rolls=all_rolls,
            modifier=modifier,
            modifier_label=modifier_label,
            total=total,
            is_kept=kept,
        )

    rolls = [random.randint(1, faces) for _ in range(count)]
    modifier_label = f"{sign}{abs(modifier)}" if modifier != 0 else ""
    total = sum(rolls) + modifier

    return RollResult(
        dice_notation=dice_str,
        rolls=rolls,
        modifier=modifier,
        modifier_label=modifier_label,
        total=total,
        is_kept=[True] * count,
    )
