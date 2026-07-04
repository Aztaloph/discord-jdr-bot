# jdr_engine/rules/rest/__init__.py
from jdr_engine.rules.rest.errors import RestError
from jdr_engine.rules.rest.long_rest import LongRestResult, apply_long_rest
from jdr_engine.rules.rest.short_rest import HitDieRoll, ShortRestResult, apply_short_rest
from jdr_engine.rules.rest.state import ensure_rest_state, hit_dice_remaining, hit_dice_total

__all__ = [
    "RestError",
    "LongRestResult",
    "ShortRestResult",
    "HitDieRoll",
    "apply_long_rest",
    "apply_short_rest",
    "ensure_rest_state",
    "hit_dice_remaining",
    "hit_dice_total",
]
