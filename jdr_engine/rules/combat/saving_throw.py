# jdr_engine/rules/combat/saving_throw.py
"""
Jets de sauvegarde en combat — lot C3b.

La moitié de dégâts sur sauvegarde réussie s'applique au **total** obtenu,
pas aux dés individuellement (SRD 5.1).
"""
from __future__ import annotations


def save_succeeded(save_total: int, save_dc: int) -> bool:
    """Réussite si total du jet >= DD (SRD 5.1 2014)."""
    return save_total >= save_dc


def damage_after_save(
    full_total: int,
    *,
    save_succeeded_flag: bool,
    half_on_save: bool,
) -> int:
    """
    Dégâts finaux après sauvegarde.

    Si ``half_on_save`` et sauvegarde réussie : moitié du total, arrondi inférieur.
    """
    if save_succeeded_flag and half_on_save:
        return full_total // 2
    return full_total
