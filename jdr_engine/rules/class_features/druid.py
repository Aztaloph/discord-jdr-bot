# jdr_engine/rules/class_features/druid.py
"""Druide — SRD 5.1 2014, niveaux 1-3."""
from __future__ import annotations

from jdr_engine.rules.class_features.common import feature_state, set_feature_state
from jdr_engine.rules.class_features.ranger import favored_terrain_label

WILD_SHAPE_USES_BY_LEVEL: dict[int, int] = {2: 2, 3: 2}


def wild_shape_uses_max(level: int) -> int:
    return WILD_SHAPE_USES_BY_LEVEL.get(level, 0)


def wild_shape_uses_remaining(choices: dict, *, level: int) -> int:
    state = feature_state(choices)
    maximum = wild_shape_uses_max(level)
    if maximum <= 0:
        return 0
    if "wild_shape_uses_remaining" not in state:
        return maximum
    return max(0, min(int(state["wild_shape_uses_remaining"]), maximum))


def wild_shape_cr_max(level: int) -> str:
    """CR max affiché selon niveau SRD (niv. 1-3 : 1/4 au niv. 2+)."""
    if level < 2:
        return "—"
    return "1/4"


def wild_shape_restrictions(level: int) -> str:
    if level < 2:
        return ""
    if level < 4:
        return "sans nage ni vol"
    return ""


def get_druid_land_terrain(choices: dict) -> str | None:
    raw = (choices or {}).get("druid_land_terrain")
    return str(raw).strip() if raw else None


def land_terrain_label(terrain: str) -> str:
    return favored_terrain_label(terrain)


def natural_recovery_pool(level: int) -> int:
    """Demi-niveau de druide arrondi au supérieur (SRD 2014)."""
    if level < 2:
        return 0
    return (level + 1) // 2


def natural_recovery_available(choices: dict) -> bool:
    state = feature_state(choices)
    return bool(state.get("natural_recovery_available", True))


def init_druid_features(choices: dict, *, level: int) -> dict:
    state = feature_state(choices)
    max_ws = wild_shape_uses_max(level)
    if max_ws > 0:
        state.setdefault("wild_shape_uses_remaining", max_ws)
    if level >= 2:
        state.setdefault("natural_recovery_available", True)
    return set_feature_state(choices, state)


def reset_wild_shape_on_short_or_long_rest(choices: dict, *, level: int) -> dict:
    state = feature_state(choices)
    maximum = wild_shape_uses_max(level)
    if maximum > 0:
        state["wild_shape_uses_remaining"] = maximum
    return set_feature_state(choices, state)


def reset_natural_recovery_on_long_rest(choices: dict, *, level: int) -> dict:
    state = feature_state(choices)
    if level >= 2:
        state["natural_recovery_available"] = True
    return set_feature_state(choices, state)
