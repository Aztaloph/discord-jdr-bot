# jdr_engine/rules/rest/state.py
"""État persistant repos — character.choices.rest (dés de vie)."""
from __future__ import annotations

from jdr_engine.domain.character.character import Character


def get_rest_state(character: Character) -> dict:
    raw = (character.choices or {}).get("rest")
    return dict(raw) if isinstance(raw, dict) else {}


def init_rest_state(character: Character) -> dict:
    total = max(1, int(character.level))
    return {
        "hit_dice_total": total,
        "hit_dice_remaining": total,
    }


def ensure_rest_state(character: Character) -> Character:
    """Initialise choices.rest si absent (persos créés avant cette feature)."""
    state = get_rest_state(character)
    state.pop("last_long_rest_at", None)
    if state.get("hit_dice_total") is not None:
        total = max(1, int(state["hit_dice_total"]))
        remaining = int(state.get("hit_dice_remaining", total))
        state["hit_dice_total"] = total
        state["hit_dice_remaining"] = max(0, min(remaining, total))
    else:
        state = init_rest_state(character)
    choices = dict(character.choices or {})
    choices["rest"] = state
    character.choices = choices
    return character


def sync_hit_dice_total(character: Character) -> Character:
    """Aligne le total de dés sur le niveau actuel (montée de niveau future)."""
    character = ensure_rest_state(character)
    state = get_rest_state(character)
    new_total = max(1, int(character.level))
    old_total = int(state.get("hit_dice_total", new_total))
    remaining = int(state.get("hit_dice_remaining", new_total))
    if new_total > old_total:
        remaining += new_total - old_total
    state["hit_dice_total"] = new_total
    state["hit_dice_remaining"] = max(0, min(remaining, new_total))
    state.pop("last_long_rest_at", None)
    choices = dict(character.choices or {})
    choices["rest"] = state
    character.choices = choices
    return character


def hit_dice_remaining(character: Character) -> int:
    return int(get_rest_state(character).get("hit_dice_remaining", 0))


def hit_dice_total(character: Character) -> int:
    return int(get_rest_state(character).get("hit_dice_total", 0))


def hit_dice_regain_amount(total: int) -> int:
    """SRD 2014 : moitié du total, arrondi à l'inférieur, minimum 1."""
    return max(1, total // 2)
