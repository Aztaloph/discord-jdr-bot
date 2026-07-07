# jdr_engine/rules/class_features/display.py
"""Affichage fiche — aptitudes de classe et ressources (Lot 1)."""
from __future__ import annotations

from jdr_engine.domain.character.character import Character
from jdr_engine.domain.character.choices_schema import (
    get_expertise_skills,
    get_fighting_style_id,
    get_specialization_id,
)
from jdr_engine.rules.class_features.barbarian import (
    rage_active,
    rage_uses_max,
    rage_uses_remaining,
)
from jdr_engine.rules.class_features.fighter import (
    action_surge_available,
    improved_critical_range,
    second_wind_available,
)
from jdr_engine.rules.class_features.monk import (
    ki_points_max,
    ki_points_remaining,
    martial_arts_die,
)
from jdr_engine.rules.class_features.rogue import sneak_attack_dice_count
from jdr_engine.rules.class_features.resolve import collect_subclass_traits
from jdr_engine.rules.derived_stats import skill_label_fr
from jdr_engine.rules.engine import RuleEngine

# Aptitudes déjà rendues avec compteurs / détail dans un bloc classe dédié.
_CLASS_LOOP_SKIP: dict[str, frozenset[str]] = {
    "paladin": frozenset(
        {
            "divine_sense",
            "lay_on_hands",
            "divine_smite",
            "divine_health",
            "channel_divinity",
        }
    ),
    "rogue": frozenset({"sneak_attack", "expertise"}),
    "monk": frozenset({"martial_arts", "ki", "unarmored_movement"}),
    "barbarian": frozenset({"rage"}),
    "fighter": frozenset({"second_wind", "action_surge"}),
    "bard": frozenset(
        {
            "bardic_inspiration",
            "jack_of_all_trades",
            "song_of_rest",
            "expertise",
        }
    ),
    "cleric": frozenset(
        {
            "channel_divinity",
            "divine_domain",
        }
    ),
    "wizard": frozenset({"arcane_recovery", "spellcasting", "arcane_tradition"}),
    "sorcerer": frozenset(
        {"spellcasting", "sorcerous_origin", "font_of_magic", "metamagic"}
    ),
    "druid": frozenset(
        {"spellcasting", "wild_shape", "druid_circle", "natural_recovery"}
    ),
    "warlock": frozenset(
        {
            "pact_magic",
            "otherworldly_patron",
            "eldritch_invocations",
            "pact_boon",
            "dark_ones_blessing",
        }
    ),
}

_SUBCLASS_CHOICE_TRAITS = frozenset(
    {
        "fighting_style",
        "martial_archetype",
        "primal_path",
        "roguish_archetype",
        "monastic_tradition",
        "ranger_conclave",
        "sacred_oath",
        "bard_college",
        "divine_domain",
        "arcane_tradition",
        "sorcerous_origin",
        "druid_circle",
        "otherworldly_patron",
    }
)


def _feature_label(engine: RuleEngine, trait_id: str, locale: str = "fr") -> str:
    entry = engine.get_entity("trait", trait_id)
    if entry is None:
        return trait_id.replace("_", " ").title()
    return entry.get_name(locale, engine.registry.manifest.default_locale)


def _resource_line(label: str, remaining: int, maximum: int, recharge: str) -> str:
    return f"**{label}** : {remaining}/{maximum} ({recharge})"


def _format_trait_line(
    engine: RuleEngine,
    trait_id: str,
    *,
    locale: str = "fr",
) -> str:
    label = _feature_label(engine, trait_id, locale)
    entry = engine.get_entity("trait", trait_id)
    desc = ""
    if entry is not None:
        raw = entry.definition.mechanics.get("description_fr")
        if isinstance(raw, str) and raw.strip():
            desc = raw.strip()
    if desc:
        return f"**{label}** — {desc}"
    return f"**{label}**"


def _append_unique(
    lines: list[str],
    seen_ids: set[str],
    trait_id: str,
    text: str,
) -> None:
    if trait_id in seen_ids:
        return
    seen_ids.add(trait_id)
    lines.append(text)


def build_class_features_display(
    character: Character,
    engine: RuleEngine,
    *,
    locale: str = "fr",
) -> tuple[str, ...]:
    """Lignes « Aptitudes de classe » pour /perso-afficher."""
    lines: list[str] = []
    seen_ids: set[str] = set()
    choices = character.choices or {}
    level = character.level
    class_id = character.class_id

    for feature in engine.get_class_features(class_id, level):
        fid = feature.entry_id
        if fid in _SUBCLASS_CHOICE_TRAITS:
            continue
        if fid in _CLASS_LOOP_SKIP.get(class_id, frozenset()):
            continue
        _append_unique(
            lines,
            seen_ids,
            fid,
            _format_trait_line(engine, fid, locale=locale),
        )

    if class_id == "barbarian" and level >= 1:
        max_r = rage_uses_max(level)
        rem = rage_uses_remaining(choices, level=level)
        active = " (active)" if rage_active(choices) else ""
        _append_unique(
            lines,
            seen_ids,
            "rage_uses",
            _resource_line("Rage", rem, max_r, "recharge repos long") + active,
        )

    if class_id == "fighter":
        if level >= 1 and second_wind_available(choices):
            _append_unique(
                lines,
                seen_ids,
                "second_wind_state",
                "**Second souffle** : disponible (repos court ou long)",
            )
        elif level >= 1:
            _append_unique(
                lines,
                seen_ids,
                "second_wind_state",
                "**Second souffle** : utilisé (repos court ou long)",
            )
        if level >= 2 and action_surge_available(choices):
            _append_unique(
                lines,
                seen_ids,
                "action_surge_state",
                "**Fougue** : disponible (repos court ou long)",
            )
        elif level >= 2:
            _append_unique(
                lines,
                seen_ids,
                "action_surge_state",
                "**Fougue** : utilisée (repos court ou long)",
            )

    spec = get_specialization_id(choices)
    if class_id == "warlock":
        min_subclass_level = 1
    elif class_id == "druid":
        min_subclass_level = 2
    else:
        min_subclass_level = 3
    if spec and level >= min_subclass_level:
        for trait in collect_subclass_traits(character, engine):
            tid = trait.entry_id
            if tid in seen_ids:
                continue
            label = trait.get_name(locale, engine.registry.manifest.default_locale)
            desc = trait.definition.mechanics.get("description_fr")
            if isinstance(desc, str) and desc.strip():
                _append_unique(lines, seen_ids, tid, f"**{label}** — {desc.strip()}")
            else:
                _append_unique(lines, seen_ids, tid, f"**{label}**")
        crit_min, crit_max = improved_critical_range(choices, level=level)
        if spec == "champion" and crit_min < 20:
            _append_unique(
                lines,
                seen_ids,
                "improved_critical",
                f"**Critique amélioré** : {crit_min}-{crit_max}",
            )

    style = get_fighting_style_id(choices)
    if style and class_id in ("fighter", "ranger", "paladin"):
        from jdr_engine.rules.derived_stats import resolve_fighting_style_label

        _, style_label = resolve_fighting_style_label(choices, engine, locale=locale)
        if style == "defense":
            line = f"**{style_label}** — +1 CA en armure"
        elif style == "dueling":
            line = f"**{style_label}** — +2 dégâts (mêlée à une main)"
        elif style == "archery":
            line = f"**{style_label}** — +2 attaque à distance"
        else:
            line = f"**{style_label}**"
        _append_unique(lines, seen_ids, f"fighting_style_{style}", line)

    if class_id == "ranger":
        enemy = choices.get("favored_enemy_type")
        terrain = choices.get("favored_terrain")
        if enemy:
            from jdr_engine.rules.class_features.ranger import favored_enemy_label

            _append_unique(
                lines,
                seen_ids,
                "favored_enemy_choice",
                f"**Ennemi juré** : {favored_enemy_label(str(enemy))}",
            )
        if terrain:
            from jdr_engine.rules.class_features.ranger import favored_terrain_label

            _append_unique(
                lines,
                seen_ids,
                "favored_terrain_choice",
                f"**Terrain favori** : {favored_terrain_label(str(terrain))}",
            )
        prey = choices.get("hunter_prey")
        if prey and level >= 3:
            from jdr_engine.rules.class_features.ranger import hunter_prey_label

            _append_unique(
                lines,
                seen_ids,
                "hunter_prey_choice",
                f"**Option de proie** : {hunter_prey_label(str(prey))}",
            )

    if class_id == "paladin":
        from jdr_engine.rules.class_features.paladin import (
            channel_divinity_remaining,
            channel_divinity_uses_max,
            divine_sense_remaining,
            divine_sense_uses_max,
            lay_on_hands_pool_max,
            lay_on_hands_remaining,
        )

        cha_score = character.ability_scores.with_defaults(
            ["str", "dex", "con", "int", "wis", "cha"]
        ).scores.get("cha", 10)
        if level >= 1:
            max_ds = divine_sense_uses_max(cha_score)
            rem_ds = divine_sense_remaining(choices, cha_score=cha_score)
            _append_unique(
                lines,
                seen_ids,
                "divine_sense",
                _resource_line("Sens divin", rem_ds, max_ds, "recharge repos long"),
            )
            max_loh = lay_on_hands_pool_max(level)
            rem_loh = lay_on_hands_remaining(choices, level=level)
            _append_unique(
                lines,
                seen_ids,
                "lay_on_hands",
                f"**Imposition des mains** : {rem_loh}/{max_loh} PV (recharge repos long)",
            )
        if level >= 2:
            _append_unique(
                lines,
                seen_ids,
                "divine_smite",
                "**Châtiment divin** — consomme un emplacement (+2d8 radiants, niv.1)",
            )
        if level >= 3:
            _append_unique(
                lines,
                seen_ids,
                "divine_health",
                "**Santé divine** — immunité aux maladies",
            )
            max_cd = channel_divinity_uses_max(level)
            if max_cd > 0:
                rem_cd = channel_divinity_remaining(choices, level=level)
                _append_unique(
                    lines,
                    seen_ids,
                    "channel_divinity",
                    _resource_line(
                        "Canalisation d'énergie divine",
                        rem_cd,
                        max_cd,
                        "recharge repos court ou long",
                    ),
                )

    if class_id == "rogue":
        expertise = get_expertise_skills(choices)
        if expertise:
            labels = ", ".join(skill_label_fr(s) for s in expertise)
            _append_unique(
                lines,
                seen_ids,
                "expertise",
                f"**Expertise** : {labels} (maîtrise ×2)",
            )
        if level >= 1:
            dice = sneak_attack_dice_count(level)
            _append_unique(
                lines,
                seen_ids,
                "sneak_attack",
                f"**Attaque sournoise** : +{dice}d6 (si conditions SRD)",
            )

    if class_id == "bard":
        from jdr_engine.rules.class_features.bard import (
            bardic_inspiration_die,
            bardic_inspiration_remaining,
            bardic_inspiration_uses_max,
            song_of_rest_die,
        )

        cha_score = character.ability_scores.with_defaults(
            ["str", "dex", "con", "int", "wis", "cha"]
        ).scores.get("cha", 10)
        if level >= 1:
            max_insp = bardic_inspiration_uses_max(cha_score)
            rem_insp = bardic_inspiration_remaining(choices, cha_score=cha_score)
            die = bardic_inspiration_die(level)
            _append_unique(
                lines,
                seen_ids,
                "bardic_inspiration",
                _resource_line(
                    f"Inspiration bardique (d{die})",
                    rem_insp,
                    max_insp,
                    "recharge repos long",
                ),
            )
        if level >= 2:
            _append_unique(
                lines,
                seen_ids,
                "jack_of_all_trades",
                "**Touche-à-tout** — +½ maîtrise aux jets non maîtrisés",
            )
            rest_die = song_of_rest_die(level)
            if rest_die:
                _append_unique(
                    lines,
                    seen_ids,
                    "song_of_rest",
                    f"**Chant de repos** — +d{rest_die} soins bonus (repos court)",
                )
        if level >= 3:
            expertise = get_expertise_skills(choices)
            if expertise:
                labels = ", ".join(skill_label_fr(s) for s in expertise)
                _append_unique(
                    lines,
                    seen_ids,
                    "expertise",
                    f"**Expertise** : {labels} (maîtrise ×2)",
                )
            lore_skills = choices.get("lore_bonus_skills") or []
            if lore_skills:
                labels = ", ".join(skill_label_fr(str(s)) for s in lore_skills)
                _append_unique(
                    lines,
                    seen_ids,
                    "lore_bonus_skills",
                    f"**Maîtrises bonus (Savoir)** : {labels}",
                )

    if class_id == "cleric":
        from jdr_engine.rules.class_features.cleric import (
            channel_divinity_remaining,
            channel_divinity_uses_max,
            preserve_life_pool,
            preserve_life_remaining,
        )

        domain = get_specialization_id(choices)
        if domain == "life" and level >= 1:
            _append_unique(
                lines,
                seen_ids,
                "disciple_of_life",
                "**Disciple de la vie** — soins +2 + niveau du sort",
            )
        if level >= 2:
            max_cd = channel_divinity_uses_max(level)
            if max_cd > 0:
                rem_cd = channel_divinity_remaining(choices, level=level)
                _append_unique(
                    lines,
                    seen_ids,
                    "channel_divinity",
                    _resource_line(
                        "Canalisation d'énergie divine",
                        rem_cd,
                        max_cd,
                        "recharge repos court ou long",
                    ),
                )
            _append_unique(
                lines,
                seen_ids,
                "turn_undead",
                "**Renvoi des morts-vivants** — via canalisation",
            )
            if domain == "life":
                pool = preserve_life_pool(level)
                rem_pl = preserve_life_remaining(choices, level=level)
                _append_unique(
                    lines,
                    seen_ids,
                    "preserve_life",
                    f"**Préservation de la vie** : {rem_pl}/{pool} PV (recharge repos long)",
                )

    if class_id == "wizard":
        from jdr_engine.rules.class_features.wizard import (
            arcane_recovery_available,
            arcane_recovery_pool,
        )

        if level >= 1:
            pool = arcane_recovery_pool(level)
            if arcane_recovery_available(choices):
                _append_unique(
                    lines,
                    seen_ids,
                    "arcane_recovery",
                    f"**Récupération arcanique** : disponible (jusqu'à {pool} niv. d'emplacements, repos court)",
                )
            else:
                _append_unique(
                    lines,
                    seen_ids,
                    "arcane_recovery",
                    f"**Récupération arcanique** : utilisée (repos long)",
                )

    if class_id == "sorcerer":
        from jdr_engine.rules.class_features.sorcerer import (
            format_metamagic_display,
            get_lineage_damage_type,
            sorcery_points_max,
            sorcery_points_remaining,
        )
        from jdr_engine.rules.racial.draconic_ancestry import get_draconic_ancestry

        if level >= 2:
            max_sp = sorcery_points_max(level)
            rem_sp = sorcery_points_remaining(choices, level=level)
            _append_unique(
                lines,
                seen_ids,
                "sorcery_points",
                f"**Points de sorcellerie** : {rem_sp}/{max_sp} (recharge repos long)",
            )
        if level >= 3:
            meta = format_metamagic_display(choices)
            if meta:
                _append_unique(
                    lines,
                    seen_ids,
                    "metamagic_options",
                    f"**Métamagie** : {meta}",
                )
        dragon = (choices or {}).get("sorcerer_dragon_type")
        if get_specialization_id(choices) == "draconic" and dragon:
            ancestry = get_draconic_ancestry(str(dragon))
            if ancestry:
                _append_unique(
                    lines,
                    seen_ids,
                    "draconic_lineage",
                    f"**Lignée** : {ancestry.label_fr} ({ancestry.damage_type})",
                )

    if class_id == "druid":
        from jdr_engine.rules.class_features.druid import (
            get_druid_land_terrain,
            land_terrain_label,
            natural_recovery_available,
            natural_recovery_pool,
            wild_shape_cr_max,
            wild_shape_restrictions,
            wild_shape_uses_max,
            wild_shape_uses_remaining,
        )

        if level >= 2:
            max_ws = wild_shape_uses_max(level)
            rem_ws = wild_shape_uses_remaining(choices, level=level)
            cr = wild_shape_cr_max(level)
            restrictions = wild_shape_restrictions(level)
            restriction_text = f", {restrictions}" if restrictions else ""
            _append_unique(
                lines,
                seen_ids,
                "wild_shape",
                _resource_line("Forme sauvage", rem_ws, max_ws, "repos court ou long")
                + f" — CR max {cr}{restriction_text}",
            )
        terrain = get_druid_land_terrain(choices)
        if get_specialization_id(choices) == "land" and terrain:
            _append_unique(
                lines,
                seen_ids,
                "druid_land_terrain",
                f"**Terrain de cercle** : {land_terrain_label(terrain)}",
            )
        if level >= 2 and get_specialization_id(choices) == "land":
            pool = natural_recovery_pool(level)
            if natural_recovery_available(choices):
                _append_unique(
                    lines,
                    seen_ids,
                    "natural_recovery",
                    f"**Récupération naturelle** : disponible (jusqu'à {pool} niv. d'emplacements, repos long)",
                )
            else:
                _append_unique(
                    lines,
                    seen_ids,
                    "natural_recovery",
                    "**Récupération naturelle** : utilisée (repos long)",
                )

    if class_id == "warlock":
        from jdr_engine.rules.class_features.warlock import (
            dark_ones_blessing_temp_hp,
            fiend_expanded_spells_display,
            format_invocations_display,
            format_pact_boon_display,
        )

        if get_specialization_id(choices) == "fiend" and level >= 1:
            cha_score = character.ability_scores.with_defaults(
                ["str", "dex", "con", "int", "wis", "cha"]
            ).scores.get("cha", 10)
            temp_hp = dark_ones_blessing_temp_hp(cha_score, level)
            _append_unique(
                lines,
                seen_ids,
                "dark_ones_blessing",
                f"**Bénédiction du Ténébreux** — +{temp_hp} PV temporaires (ennemi à 0 PV)",
            )
            expanded = fiend_expanded_spells_display(level)
            if expanded:
                _append_unique(
                    lines,
                    seen_ids,
                    "fiend_expanded_spells",
                    f"**Sorts étendus (Fiélon)** : {expanded}",
                )
        if level >= 2:
            invocations = format_invocations_display(choices)
            if invocations:
                _append_unique(
                    lines,
                    seen_ids,
                    "eldritch_invocations",
                    f"**Manifestations occultes** : {invocations}",
                )
        if level >= 3:
            boon = format_pact_boon_display(choices)
            if boon:
                _append_unique(
                    lines,
                    seen_ids,
                    "pact_boon",
                    f"**Faveur du pacte** : {boon}",
                )

    if class_id == "monk":
        if level >= 1:
            die = martial_arts_die(level)
            _append_unique(
                lines,
                seen_ids,
                "martial_arts",
                f"**Arts martiaux** : d{die} (mains nues / armes de moine)",
            )
        if level >= 2:
            max_ki = ki_points_max(level)
            rem = ki_points_remaining(choices, level=level)
            _append_unique(
                lines,
                seen_ids,
                "ki",
                _resource_line("Ki", rem, max_ki, "recharge repos court ou long"),
            )
            _append_unique(
                lines,
                seen_ids,
                "unarmored_movement",
                "**Déplacement sans armure** : +10 ft (inclus dans la vitesse)",
            )

    return tuple(lines)
