# jdr_engine/rules/racial/features.py
"""Features raciales avec état persistant (Endurance implacable, etc.)."""
from __future__ import annotations

from jdr_engine.domain.character.character import Character


def get_feature_state(character: Character) -> dict:
    raw = (character.choices or {}).get("feature_state")
    return dict(raw) if isinstance(raw, dict) else {}


def relentless_endurance_available(character: Character) -> bool:
    """True si le Demi-orc peut encore utiliser Endurance implacable."""
    if character.race_id != "half_orc":
        return False
    state = get_feature_state(character)
    return not bool(state.get("relentless_endurance_used"))


def apply_relentless_endurance(character: Character) -> Character:
    """
    Marque Endurance implacable comme utilisée (1×/repos long).

    À appeler quand les PV tomberaient à 0 — remet hp_current à 1.
    """
    choices = dict(character.choices or {})
    state = get_feature_state(character)
    state["relentless_endurance_used"] = True
    choices["feature_state"] = state
    character.choices = choices
    character.hp_current = 1
    return character


def reset_racial_features_on_long_rest(character: Character) -> Character:
    """Réinitialise les usages raciaux après repos long."""
    choices = dict(character.choices or {})
    state = get_feature_state(character)
    state.pop("relentless_endurance_used", None)
    if state:
        choices["feature_state"] = state
    elif "feature_state" in choices:
        choices.pop("feature_state")

    innate = choices.get("innate_spells")
    if isinstance(innate, dict):
        innate = dict(innate)
        innate["uses"] = {}
        choices["innate_spells"] = innate

    character.choices = choices
    return character
