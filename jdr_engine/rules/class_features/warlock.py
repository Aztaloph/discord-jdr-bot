# jdr_engine/rules/class_features/warlock.py
"""Occultiste — SRD 5.1 2014, niveaux 1-3."""
from __future__ import annotations

from jdr_engine.domain.character.ability_scores import ability_modifier

INVOCATION_LABELS_FR: dict[str, str] = {
    "eldritch_sight": "Vision occulte",
    "devils_sight": "Vision du diable",
    "eldritch_spear": "Regard des lunes",
    "agonizing_blast": "Agonisant",
    "armor_of_shadows": "Armure d'ombres",
}

INVOCATION_EFFECTS_FR: dict[str, str] = {
    "eldritch_sight": "Détection de la magie à volonté (effet manuel).",
    "devils_sight": "Vision normale dans les ténèbres magiques et non magiques.",
    "eldritch_spear": "Portée de Salve occulte ×2 (affichage).",
    "agonizing_blast": "+mod CHA aux dégâts de Salve occulte.",
    "armor_of_shadows": "Armure du mage à volonté (effet manuel).",
}

PACT_BOON_LABELS_FR: dict[str, str] = {
    "pact_of_the_chain": "Pacte de la Chaîne",
    "pact_of_the_blade": "Pacte de la Lame",
    "pact_of_the_tome": "Pacte du Grimoire",
}

PACT_BOON_EFFECTS_FR: dict[str, str] = {
    "pact_of_the_chain": "Familier amélioré (affichage ; automatisation reportée).",
    "pact_of_the_blade": "Arme de pacte (affichage ; automatisation reportée).",
    "pact_of_the_tome": "Grimoire + 3 tours de magie (affichage ; automatisation reportée).",
}

FIEND_EXPANDED_SPELLS: dict[int, tuple[str, ...]] = {
    1: ("burning_hands", "hellish_rebuke"),
    3: ("darkness",),
}


def get_eldritch_invocations(choices: dict) -> tuple[str, ...]:
    raw = (choices or {}).get("eldritch_invocations") or []
    if isinstance(raw, list):
        return tuple(str(x) for x in raw if x)
    return ()


def get_pact_boon(choices: dict) -> str | None:
    raw = (choices or {}).get("pact_boon")
    return str(raw).strip() if raw else None


def format_invocations_display(choices: dict) -> str:
    options = get_eldritch_invocations(choices)
    if not options:
        return ""
    parts = []
    for opt in options:
        label = INVOCATION_LABELS_FR.get(opt, opt.replace("_", " ").title())
        effect = INVOCATION_EFFECTS_FR.get(opt, "")
        if effect:
            parts.append(f"{label} ({effect})")
        else:
            parts.append(label)
    return "; ".join(parts)


def format_pact_boon_display(choices: dict) -> str:
    boon = get_pact_boon(choices)
    if not boon:
        return ""
    label = PACT_BOON_LABELS_FR.get(boon, boon.replace("_", " ").title())
    effect = PACT_BOON_EFFECTS_FR.get(boon, "")
    return f"{label} — {effect}" if effect else label


def fiend_expanded_spells_display(level: int) -> str:
    spells: list[str] = []
    for req_level, ids in sorted(FIEND_EXPANDED_SPELLS.items()):
        if level >= req_level:
            for spell_id in ids:
                if spell_id not in spells:
                    spells.append(spell_id)
    return ", ".join(spells)


def get_fiend_expanded_spell_ids(level: int) -> tuple[str, ...]:
    """Sorts élargis du patron Fiélon — toujours préparés (SRD 2014)."""
    spells: list[str] = []
    for req_level, ids in sorted(FIEND_EXPANDED_SPELLS.items()):
        if level >= req_level:
            for spell_id in ids:
                if spell_id not in spells:
                    spells.append(spell_id)
    return tuple(spells)


def get_warlock_expanded_spell_ids(choices: dict, *, level: int) -> tuple[str, ...]:
    """Sorts de liste élargie selon le patron (occultiste niv. 1–3)."""
    from jdr_engine.domain.character.choices_schema import get_specialization_id

    if get_specialization_id(choices) == "fiend":
        return get_fiend_expanded_spell_ids(level)
    return ()


def has_agonizing_blast(choices: dict) -> bool:
    return "agonizing_blast" in get_eldritch_invocations(choices)


def agonizing_blast_bonus(cha_score: int) -> int:
    return ability_modifier(cha_score)


def dark_ones_blessing_temp_hp(cha_score: int, level: int) -> int:
    """PV temporaires SRD — mod CHA + niveau d'occultiste."""
    return max(0, ability_modifier(cha_score) + level)
