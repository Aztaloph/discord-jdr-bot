# jdr_engine/rules/combat/concentration_save.py
"""Save CON pour maintenir la concentration après des dégâts — lot C5 (SRD 5.1)."""
from __future__ import annotations


def concentration_save_dc(damage_dealt: int) -> int:
    """
    DD du jet de sauvegarde CON pour conserver la concentration.

    SRD 5.1 : ``max(10, dégâts ÷ 2)`` (division entière).
    """
    if damage_dealt <= 0:
        return 0
    return max(10, damage_dealt // 2)
