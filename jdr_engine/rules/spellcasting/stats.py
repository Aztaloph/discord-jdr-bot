# jdr_engine/rules/spellcasting/stats.py
"""Statistiques d'incantation SRD 2014."""


def spell_save_dc(proficiency_bonus: int, ability_modifier: int) -> int:
    """DD de sauvegarde = 8 + maîtrise + mod caractéristique d'incantation."""
    return 8 + proficiency_bonus + ability_modifier


def spell_attack_bonus(proficiency_bonus: int, ability_modifier: int) -> int:
    """Bonus d'attaque de sort = maîtrise + mod caractéristique d'incantation."""
    return proficiency_bonus + ability_modifier
