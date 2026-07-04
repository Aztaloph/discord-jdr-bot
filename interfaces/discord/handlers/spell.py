# interfaces/discord/handlers/spell.py
"""Handler /sort Discord — lanceurs de sorts Magicien & Clerc."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field

from jdr_engine.application.character_service import CharacterNotFoundError
from jdr_engine.dice import DiceError
from jdr_engine.domain.character.character import Character
from discord import app_commands

from jdr_engine.rules.engine import RuleEngine
from jdr_engine.rules.spellcasting.cast import SpellCastError, SpellCastResult, cast_spell
from jdr_engine.rules.spellcasting.spells_catalog import (
    all_spellcasting_spell_ids,
    get_spell_ids_for_class,
)
from jdr_engine.rules.spellcasting.state import list_castable_spell_ids

from interfaces.discord.container import DiscordJdrContext

log = logging.getLogger(__name__)


@dataclass
class SpellDisplay:
    """Résultat normalisé pour l'embed Discord /sort."""

    spell_name: str
    character_name: str
    spell_level: int
    school: str
    casting_time: str
    range_text: str
    duration: str
    display_lines: list[str] = field(default_factory=list)
    effect_type: str = ""
    total_attack: int | None = None
    save_dc: int | None = None
    damage_total: int | None = None
    slots_remaining_text: str = ""


def list_available_spells(character: Character) -> list[str]:
    """Ids de sorts lançables (tours de magie + sorts connus niv. 1+)."""
    return list_castable_spell_ids(character)


def _spell_matches_query(spell_id: str, label: str, query: str) -> bool:
    if not query:
        return True
    haystack = " ".join(
        (
            spell_id,
            spell_id.replace("_", " "),
            spell_id.replace("_", ""),
            label,
        )
    ).lower()
    return query in haystack


def build_spell_autocomplete_choices(
    engine: RuleEngine,
    current: str,
    *,
    locale: str = "fr",
    class_id: str | None = None,
    known_spell_ids: list[str] | None = None,
) -> list[app_commands.Choice[str]]:
    """
    Propose les sorts filtrés pour l'autocomplete /sort.

    Si ``known_spell_ids`` est fourni (y compris liste vide), seuls ces sorts
    apparaissent — même source de vérité que ``cast_spell`` / ``spell_is_known``.
    Sinon repli catalogue classe ou global (tests / rétrocompat).
    """
    query = (current or "").strip().lower()
    if known_spell_ids is not None:
        spell_ids = tuple(known_spell_ids)
    elif class_id:
        spell_ids = get_spell_ids_for_class(class_id)
    else:
        spell_ids = all_spellcasting_spell_ids()
    choices: list[app_commands.Choice[str]] = []
    for spell_id in spell_ids:
        if engine.get_entity("spell", spell_id) is None:
            continue
        label = engine.get_display_name("spell", spell_id, locale=locale) or spell_id
        if not _spell_matches_query(spell_id, label, query):
            continue
        choices.append(
            app_commands.Choice(name=f"{label} ({spell_id})", value=spell_id)
        )
    return choices[:25]


def build_sort_autocomplete_choices(
    ctx: DiscordJdrContext,
    *,
    owner_id: int,
    perso: str | None,
    guild_id: str | None,
    current: str,
) -> list[app_commands.Choice[str]]:
    """
    Autocomplete /sort : sorts lançables du personnage actif uniquement.

    Retourne ``[]`` sans lever d'exception si perso introuvable, sans sorts, ou erreur.
    """
    if ctx.rule_engine is None:
        return []
    known_spell_ids: list[str] = []
    try:
        character = resolve_character_for_spell(
            ctx, owner_id, perso, guild_id=guild_id
        )
        known_spell_ids = list_available_spells(character)
    except DiceError:
        pass
    except Exception:
        log.exception("Autocomplete /sort — échec inattendu")
        return []
    return build_spell_autocomplete_choices(
        ctx.rule_engine,
        current,
        locale=ctx.locale,
        known_spell_ids=known_spell_ids,
    )


def build_lot_b_spell_autocomplete_choices(
    engine: RuleEngine,
    current: str,
    *,
    locale: str = "fr",
) -> list[app_commands.Choice[str]]:
    """Alias rétrocompat — tous les sorts lanceurs."""
    return build_spell_autocomplete_choices(engine, current, locale=locale)


def resolve_character_for_spell(
    ctx: DiscordJdrContext,
    owner_id: int,
    perso: str | None,
    guild_id: str | None = None,
) -> Character:
    if not ctx.use_engine_v2 or ctx.character_service is None:
        raise DiceError("Moteur v2 requis pour lancer des sorts.")
    if guild_id is None:
        raise DiceError("Cette commande doit être utilisée sur un serveur.")
    try:
        return ctx.character_service.resolve_for_game(
            str(owner_id), guild_id, perso
        )
    except CharacterNotFoundError as exc:
        raise DiceError(str(exc)) from exc


def _slots_remaining_text(result: SpellCastResult) -> str:
    if not result.slots_remaining:
        return "Aucun emplacement"
    parts = [
        f"niv.{lvl}: {rem}/{result.slots_max.get(lvl, rem)}"
        for lvl, rem in sorted(result.slots_remaining.items())
    ]
    return ", ".join(parts)


def _to_display(result: SpellCastResult, character_name: str) -> SpellDisplay:
    total_attack = None
    if result.attack_rolls:
        total_attack = result.attack_rolls[0].d20_result.total
    return SpellDisplay(
        spell_name=result.spell_name,
        character_name=character_name,
        spell_level=result.spell_level,
        school=result.school,
        casting_time=result.casting_time,
        range_text=result.range_text,
        duration=result.duration,
        display_lines=list(result.display_lines),
        effect_type=result.effect_type,
        total_attack=total_attack,
        save_dc=result.save_dc,
        damage_total=result.damage_total,
        slots_remaining_text=_slots_remaining_text(result),
    )


def execute_spell_cast(
    ctx: DiscordJdrContext,
    *,
    owner_id: int,
    perso: str | None,
    spell_id: str,
    guild_id: str | None = None,
) -> SpellDisplay:
    character = resolve_character_for_spell(ctx, owner_id, perso, guild_id=guild_id)
    engine = ctx.rule_engine
    if engine is None:
        raise DiceError("Moteur de règles indisponible.")

    try:
        result = cast_spell(
            character,
            spell_id,
            engine,
            locale=ctx.locale,
            persist_slots=True,
        )
    except SpellCastError as exc:
        raise DiceError(str(exc)) from exc

    if result.updated_character is not None and ctx.character_service is not None:
        ctx.character_service.save(result.updated_character)

    return _to_display(result, character.name)
