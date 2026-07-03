# interfaces/discord/handlers/spell.py
"""Handler /sort Discord — lanceur de sorts Magicien (Lot B)."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field

from jdr_engine.application.dto.character_commands import GetCharacterQuery
from jdr_engine.application.character_service import CharacterNotFoundError
from jdr_engine.dice import DiceError
from jdr_engine.domain.character.character import Character
from jdr_engine.rules.spellcasting.cast import SpellCastError, SpellCastResult, cast_spell
from jdr_engine.rules.spellcasting.state import get_cantrips_known, get_spells_prepared

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
    """Ids de sorts lançables (tours de magie + préparés)."""
    return get_cantrips_known(character) + get_spells_prepared(character)


def resolve_character_for_spell(
    ctx: DiscordJdrContext,
    owner_id: int,
    perso: str,
) -> Character:
    if not ctx.use_engine_v2 or ctx.character_service is None:
        raise DiceError("Moteur v2 requis pour lancer des sorts.")
    try:
        return ctx.character_service.get(
            GetCharacterQuery(owner_id=str(owner_id), name=perso.strip())
        )
    except CharacterNotFoundError:
        raise DiceError(f"Aucun personnage nommé « {perso.strip()} » trouvé.") from None


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
    perso: str,
    spell_id: str,
) -> SpellDisplay:
    character = resolve_character_for_spell(ctx, owner_id, perso)
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
