# interfaces/discord/formatters/character_embed.py
"""CharacterSheet → embed Discord enrichi (lore + portraits)."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import discord

from jdr_engine.core.assets import AssetResolver
from jdr_engine.domain.character.ability_scores import format_modifier
from jdr_engine.domain.character.character_sheet import CharacterSheet
from jdr_engine.rules.engine import RuleEngine

from interfaces.discord.formatters.lore_text import combine_lore_sections

COULEUR_PRINCIPALE = 0x8B4513
COULEUR_SUCCES = 0x228B22
COULEUR_ERREUR = 0xDC143C
COULEUR_INFO = 0x4169E1

FOOTER = "JDR Bot — D&D 5e SRD 2014"

ABILITY_ORDER = ("str", "dex", "con", "int", "wis", "cha")
ABILITY_ABBREV = {
    "str": "FOR",
    "dex": "DEX",
    "con": "CON",
    "int": "INT",
    "wis": "SAG",
    "cha": "CHA",
}

PORTRAIT_ATTACHMENT = "portrait.png"


@dataclass
class CharacterDisplay:
    """Embed Discord + pièces jointes optionnelles (portrait local)."""

    embed: discord.Embed
    files: list[discord.File] = field(default_factory=list)


def _format_caracs(sheet: CharacterSheet) -> str:
    lines = []
    for ability_id in ABILITY_ORDER:
        abbrev = ABILITY_ABBREV.get(ability_id, ability_id.upper())
        score = sheet.ability_scores.get(ability_id, 10)
        mod_str = sheet.format_modifier(ability_id)
        lines.append(f"{abbrev} {score:2d} ({mod_str})")
    return "\n".join(lines)


def _format_saving_throws(sheet: CharacterSheet) -> str:
    if not sheet.saving_throws:
        return "_Non calculés_"
    return " · ".join(sheet.saving_throws)


def _format_skills(sheet: CharacterSheet) -> str:
    if not sheet.proficient_skill_labels:
        return "_Aucune compétence enregistrée_"
    return ", ".join(sheet.proficient_skill_labels)


def _resolve_portrait_path(
    sheet: CharacterSheet,
    resolver: AssetResolver | None,
) -> Path | None:
    if resolver is None:
        return None
    return resolver.resolve_portrait("race", sheet.race_id) or resolver.resolve_portrait(
        "class", sheet.class_id
    )


def _attach_portrait(
    embed: discord.Embed,
    portrait_path: Path | None,
    *,
    image_url: str | None,
) -> list[discord.File]:
    if portrait_path is not None:
        embed.set_thumbnail(url=f"attachment://{PORTRAIT_ATTACHMENT}")
        return [discord.File(str(portrait_path), filename=PORTRAIT_ATTACHMENT)]
    if image_url:
        embed.set_thumbnail(url=image_url)
    return []


def sheet_to_embed(
    sheet: CharacterSheet,
    *,
    couleur: int = COULEUR_PRINCIPALE,
    titre: str | None = None,
) -> discord.Embed:
    """Embed de base sans lore Compendium (compatibilité)."""
    return _base_embed(sheet, couleur=couleur, titre=titre)


def _base_embed(
    sheet: CharacterSheet,
    *,
    couleur: int = COULEUR_PRINCIPALE,
    titre: str | None = None,
    description: str | None = None,
) -> discord.Embed:
    titre = titre or f"📜 Fiche de {sheet.name}"
    embed = discord.Embed(title=titre, color=couleur, description=description)

    identity_lines = [
        f"**Race :** {sheet.race_name}",
        f"**Classe :** {sheet.class_display}",
        f"**Niveau :** {sheet.level}",
    ]
    if sheet.fighting_style_label:
        identity_lines.append(f"**Style de combat :** {sheet.fighting_style_label}")

    embed.add_field(
        name="⚔️ Identité",
        value="\n".join(identity_lines),
        inline=True,
    )

    init_mod = format_modifier(sheet.initiative)
    embed.add_field(
        name="❤️ Combat",
        value=(
            f"**PV :** {sheet.hp_current}/{sheet.hp_max}\n"
            f"**CA :** {sheet.ac}\n"
            f"**Initiative :** {init_mod}\n"
            f"**Vitesse :** {sheet.speed} ft\n"
            f"**Maîtrise :** +{sheet.proficiency_bonus}\n"
            f"**Dés de vie :** {sheet.hit_dice_display}"
        ),
        inline=True,
    )

    embed.add_field(
        name="📊 Caractéristiques",
        value=_format_caracs(sheet),
        inline=False,
    )

    embed.add_field(
        name="🛡️ Jets de sauvegarde",
        value=_format_saving_throws(sheet) + "\n_● = maîtrise de classe_",
        inline=False,
    )

    embed.add_field(
        name="🎯 Compétences maîtrisées",
        value=_format_skills(sheet),
        inline=False,
    )

    if sheet.trait_names:
        traits = ", ".join(sheet.trait_names)
        embed.add_field(name="✨ Traits raciaux", value=traits, inline=False)

    if sheet.damage_resistances:
        embed.add_field(
            name="🛡️ Résistances aux dégâts",
            value=sheet.damage_resistances,
            inline=False,
        )

    if sheet.innate_spells_text:
        embed.add_field(
            name="🔮 Sorts innés",
            value=sheet.innate_spells_text,
            inline=False,
        )

    embed.add_field(
        name="⚔️ Attaques",
        value="*Aucune attaque enregistrée*",
        inline=False,
    )

    embed.set_footer(text=f"{FOOTER} · ID : {sheet.character_id}")
    return embed


def build_character_display(
    sheet: CharacterSheet,
    engine: RuleEngine | None = None,
    *,
    locale: str = "fr",
    couleur: int = COULEUR_PRINCIPALE,
    titre: str | None = None,
    include_lore: bool = True,
) -> CharacterDisplay:
    """
    Fiche enrichie : lore race/classe dans la description, portrait Compendium si présent.
    """
    presenter = engine.presenter if engine else None
    resolver = AssetResolver(presenter) if presenter else None

    lore_description: str | None = None
    if include_lore and presenter is not None:
        sections: list[tuple[str, str]] = []
        race_lore = presenter.get_lore("race", sheet.race_id, locale)
        if race_lore:
            sections.append((sheet.race_name, race_lore))
        class_lore = presenter.get_lore("class", sheet.class_id, locale)
        if class_lore:
            sections.append((sheet.class_name, class_lore))
        lore_description = combine_lore_sections(sections)

    embed = _base_embed(
        sheet,
        couleur=couleur,
        titre=titre,
        description=lore_description,
    )

    portrait_path = _resolve_portrait_path(sheet, resolver)
    files = _attach_portrait(
        embed,
        portrait_path,
        image_url=sheet.image_url,
    )

    return CharacterDisplay(embed=embed, files=files)


def list_entry_line(sheet: CharacterSheet) -> str:
    return (
        f"**Race :** {sheet.race_name} | **Classe :** {sheet.class_display}\n"
        f"**Niveau :** {sheet.level} | **PV :** {sheet.hp_current}/{sheet.hp_max} | "
        f"**CA :** {sheet.ac}\n"
        f"__{sheet.character_id}__"
    )
