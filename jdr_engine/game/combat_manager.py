# jdr_engine/game/combat_manager.py
"""Orchestration de rencontre — lots C1–C2 (cycle de vie) et C3a (attaque)."""
from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, replace
from typing import TYPE_CHECKING, Callable

from jdr_engine.core.events.bus import EventBus
from jdr_engine.core.events.combat_events import (
    AttackRollResolved,
    CombatEnded,
    CombatStarted,
    DamageDealt,
    InitiativeRolled,
    RoundStarted,
    SavingThrowResolved,
    SpellCast,
    TurnEnded,
    TurnStarted,
)
from jdr_engine.dice.d20 import D20Mode, D20RollRequest, D20RollResult, RandInt
from jdr_engine.domain.combat.combat_state import (
    COMBAT_STATE_VERSION,
    CombatState,
    sql_status_from_combat,
    utc_now_iso,
)
from jdr_engine.domain.combat.combatant import Combatant
from jdr_engine.persistence.combat_repository import (
    CombatNotFoundError,
    CombatRecord,
    OpenCombatExistsError,
    SqliteCombatRepository,
)
from jdr_engine.persistence.sqlite_character_repository import (
    SqliteCharacterRepository,
)
from jdr_engine.rules.calculator import build_character_sheet
from jdr_engine.rules.combat.attack_roll import AttackHitOutcome, resolve_attack_hit
from jdr_engine.rules.combat.damage import (
    DamageApplicationResult,
    DamageRollResult,
    apply_damage_to_hp,
    roll_damage,
)
from jdr_engine.rules.combat.initiative import (
    InitiativeRollResult,
    next_active_turn_index,
    roll_initiative,
    sort_initiative_order,
)
from jdr_engine.rules.engine import RuleEngine
from jdr_engine.rules.combat.saving_throw import (
    damage_after_save,
    save_succeeded,
)
from jdr_engine.rules.combat.spell_resolution import (
    CombatSpellEffect,
    build_save_request,
    build_spell_attack_request,
    compute_spell_save_dc,
    half_on_save_for_spell,
    load_combat_spell,
    resolve_spell_damage_notation,
    save_ability_for_spell,
)
from jdr_engine.rules.roll_effects import roll_d20_for_character
from jdr_engine.rules.spellcasting.cast import SpellCastError, _set_concentration

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

# Alias rétrocompatibilité.
ActiveCombatExistsError = OpenCombatExistsError


class CombatCharacterNotFoundError(Exception):
    """Personnage requis pour le combat introuvable."""


class CombatStatusError(Exception):
    """Opération interdite pour le statut courant du combat."""


class InsufficientCombatantsError(Exception):
    """Nombre de combattants insuffisant pour l'opération."""


class NoActiveCombatantsError(Exception):
    """Aucun combattant actif dans la séquence d'initiative."""


class CombatantNotFoundError(Exception):
    """Combattant introuvable dans la rencontre."""


@dataclass(frozen=True)
class AttackRollResolution:
    """Résultat complet d'un jet d'attaque (sans application des dégâts)."""

    d20: D20RollResult
    outcome: AttackHitOutcome


@dataclass(frozen=True)
class DamageResolution:
    """Résultat d'un jet et d'une application de dégâts."""

    roll: DamageRollResult | None
    application: DamageApplicationResult


@dataclass(frozen=True)
class SpellAttackOutcome:
    """Attaque de sort — jet et dégâts éventuels."""

    spell: CombatSpellEffect
    attack: AttackRollResolution
    damage: DamageResolution | None = None


@dataclass(frozen=True)
class SpellSaveOutcome:
    """Sort à sauvegarde — jet DD, dégâts ajustés."""

    spell: CombatSpellEffect
    save_dc: int
    save_total: int
    succeeded: bool
    damage_roll: DamageRollResult
    damage: DamageResolution


class CombatManager:
    """
    Machine de cycle de vie combat — création, initiative, tours, attaque (C3a).

    Publie les événements de cycle sur l'EventBus injecté.
    """

    def __init__(
        self,
        event_bus: EventBus,
        combat_repository: SqliteCombatRepository,
        character_repository: SqliteCharacterRepository,
        engine: RuleEngine,
    ) -> None:
        self._bus = event_bus
        self._combats = combat_repository
        self._characters = character_repository
        self._engine = engine

    def create_combat(
        self,
        guild_id: str,
        channel_id: str,
        character_ids: list[str] | None = None,
    ) -> CombatState:
        """Ouvre un combat en ``preparing`` ; publie ``CombatStarted``."""
        combatants: dict[str, Combatant] = {}
        resolved_character_ids: list[str] = []

        for character_id in character_ids or []:
            combatant = self._build_combatant(character_id)
            combatants[combatant.combatant_id] = combatant
            resolved_character_ids.append(character_id)

        state = CombatState(
            schema_version=COMBAT_STATE_VERSION,
            ruleset_id=self._engine.ruleset_id,
            round_number=0,
            turn_index=0,
            initiative_order=(),
            combatants=combatants,
            status="preparing",
            started_at=utc_now_iso(),
            guild_id=str(guild_id),
            channel_id=str(channel_id),
        )

        combat_id = self._combats.insert(guild_id, channel_id, state)
        state.combat_id = str(combat_id)

        self._bus.publish(
            CombatStarted(
                ruleset_id=state.ruleset_id,
                combat_id=state.combat_id,
                guild_id=str(guild_id),
                channel_id=str(channel_id),
                character_ids=tuple(resolved_character_ids),
            )
        )
        return state

    def add_combatant(self, combat_id: int, character_id: str) -> CombatState:
        """Ajoute un PJ pendant ``preparing`` uniquement."""
        state = self._require_state(combat_id)
        if state.status != "preparing":
            raise CombatStatusError(
                "Les combattants ne peuvent être ajoutés qu'en préparation."
            )
        combatant = self._build_combatant(character_id)
        state.combatants[combatant.combatant_id] = combatant
        self._persist(state)
        return state

    def activate_combat(
        self,
        combat_id: int,
        *,
        rng: Callable[[], int] | None = None,
    ) -> CombatState:
        """
        Passe en ``active``, calcule l'initiative (ordre figé), démarre le tour 1.

        Requiert au moins deux combattants actifs.
        """
        state = self._require_state(combat_id)
        if state.status != "preparing":
            raise CombatStatusError(
                "Seul un combat en préparation peut être activé."
            )
        active = [c for c in state.combatants.values() if c.is_active]
        if len(active) < 2:
            raise InsufficientCombatantsError(
                "Au moins deux combattants sont requis pour activer le combat."
            )

        rolls = self._roll_initiative_for_combatants(active, rng=rng)
        order = sort_initiative_order(rolls)
        roll_by_id = {r.combatant_id: r for r in rolls}

        updated_combatants = dict(state.combatants)
        for combatant_id, roll in roll_by_id.items():
            old = updated_combatants[combatant_id]
            updated_combatants[combatant_id] = replace(
                old, initiative_total=roll.total
            )

        state.combatants = updated_combatants
        state.initiative_order = order
        state.status = "active"
        state.round_number = 1
        state.turn_index = 0
        self._persist(state)

        record = self._combats.get_by_id(combat_id)
        assert record is not None
        self._publish_initiative_events(record, rolls, order)
        self._publish_turn_started(state)
        return state

    def advance_turn(self, combat_id: int) -> CombatState:
        """Termine le tour courant et démarre le suivant (combattants inactifs ignorés)."""
        state = self._require_state(combat_id)
        if state.status != "active":
            raise CombatStatusError(
                "L'avancement de tour n'est possible qu'en combat actif."
            )
        if not state.initiative_order:
            raise CombatStatusError("Aucune séquence d'initiative établie.")

        current_id = state.initiative_order[state.turn_index]
        self._bus.publish(
            TurnEnded(
                ruleset_id=state.ruleset_id,
                combat_id=state.combat_id or str(combat_id),
                guild_id=state.guild_id or "",
                channel_id=state.channel_id or "",
                combatant_id=current_id,
                round_number=state.round_number,
                turn_index=state.turn_index,
            )
        )

        def _is_active(combatant_id: str) -> bool:
            return state.combatants[combatant_id].is_active

        result = next_active_turn_index(
            state.initiative_order,
            state.turn_index,
            is_active=_is_active,
        )
        if result is None:
            raise NoActiveCombatantsError(
                "Aucun combattant actif — fin de combat non tranchée (ambiguïté C2)."
            )

        new_index, delta_round = result
        if delta_round:
            state.round_number += 1
            self._bus.publish(
                RoundStarted(
                    ruleset_id=state.ruleset_id,
                    combat_id=state.combat_id or str(combat_id),
                    guild_id=state.guild_id or "",
                    channel_id=state.channel_id or "",
                    round_number=state.round_number,
                )
            )
        state.turn_index = new_index
        self._persist(state)
        self._publish_turn_started(state)
        return state

    def remove_combatant(self, combat_id: int, combatant_id: str) -> CombatState:
        """Marque un combattant inactif ; conserve sa place dans l'initiative."""
        state = self._require_state(combat_id)
        if state.status == "ended":
            raise CombatStatusError("Combat déjà terminé.")
        if combatant_id not in state.combatants:
            raise ValueError(f"Combattant introuvable : {combatant_id!r}.")
        old = state.combatants[combatant_id]
        state.combatants[combatant_id] = replace(old, is_active=False)
        self._persist(state)
        return state

    def resolve_attack_roll(
        self,
        combat_id: int,
        attacker_id: str,
        target_id: str,
        request: D20RollRequest,
        *,
        rng: RandInt | None = None,
    ) -> AttackRollResolution:
        """
        Résout un jet d'attaque vs la CA cible — sans modifier les PV.

        Délègue le d20 à ``roll_d20_for_character`` (moteur de jets existant).
        Publie ``AttackRollResolved``.
        """
        state = self._require_state(combat_id)
        if state.status != "active":
            raise CombatStatusError(
                "Les attaques ne sont possibles qu'en combat actif."
            )
        attacker = self._require_combatant(state, attacker_id)
        target = self._require_combatant(state, target_id)
        character = self._characters.get_by_id(attacker.character_id)
        if character is None:
            raise CombatCharacterNotFoundError(
                f"Personnage introuvable : {attacker.character_id!r}."
            )

        if request.roll_type != "attack":
            raise ValueError("roll_type doit être 'attack' pour un jet d'attaque.")

        d20 = roll_d20_for_character(request, character, self._engine, rng=rng)
        outcome = resolve_attack_hit(d20, target.ac)

        self._bus.publish(
            AttackRollResolved(
                ruleset_id=state.ruleset_id,
                combat_id=state.combat_id or str(combat_id),
                guild_id=state.guild_id or "",
                channel_id=state.channel_id or "",
                attacker_id=attacker_id,
                target_id=target_id,
                target_ac=target.ac,
                hit=outcome.hit,
                critical=outcome.critical,
                automatic_miss=outcome.automatic_miss,
                attack_total=d20.total,
                kept_d20=d20.kept_value,
            )
        )
        return AttackRollResolution(d20=d20, outcome=outcome)

    def apply_damage(
        self,
        combat_id: int,
        target_id: str,
        damage_notation: str = "",
        *,
        damage_amount: int | None = None,
        critical: bool = False,
        source_id: str | None = None,
        rng: RandInt | None = None,
        dice_notation_label: str | None = None,
    ) -> tuple[CombatState, DamageResolution]:
        """
        Applique des dégâts aux PV du combattant (overlay).

        Soit ``damage_notation`` (jet de dés), soit ``damage_amount`` (montant fixe).
        Publie ``DamageDealt``. Persiste l'état combat.
        """
        state = self._require_state(combat_id)
        if state.status != "active":
            raise CombatStatusError(
                "Les dégâts ne s'appliquent qu'en combat actif."
            )
        target = self._require_combatant(state, target_id)
        if source_id is not None:
            self._require_combatant(state, source_id)

        if damage_amount is not None:
            if damage_amount < 0:
                raise ValueError("Les dégâts ne peuvent pas être négatifs.")
            damage_roll = None
            amount = damage_amount
            notation = dice_notation_label or str(damage_amount)
        else:
            if not damage_notation:
                raise ValueError(
                    "damage_notation ou damage_amount requis pour apply_damage."
                )
            damage_roll = roll_damage(damage_notation, critical=critical, rng=rng)
            amount = damage_roll.total
            notation = damage_roll.dice_notation

        application = apply_damage_to_hp(target.hp_current, amount)

        state.combatants[target_id] = target.with_hp(application.hp_after)
        self._persist(state)

        self._bus.publish(
            DamageDealt(
                ruleset_id=state.ruleset_id,
                combat_id=state.combat_id or str(combat_id),
                guild_id=state.guild_id or "",
                channel_id=state.channel_id or "",
                source_id=source_id,
                target_id=target_id,
                damage=application.damage_dealt,
                hp_before=application.hp_before,
                hp_after=application.hp_after,
                critical=critical,
                dice_notation=notation,
            )
        )
        return state, DamageResolution(roll=damage_roll, application=application)

    def cast_spell_attack(
        self,
        combat_id: int,
        caster_id: str,
        target_id: str,
        spell_id: str,
        *,
        base_mode: D20Mode = "normal",
        rng: RandInt | None = None,
        locale: str = "fr",
    ) -> tuple[CombatState, SpellAttackOutcome]:
        """Attaque de sort — réutilise ``resolve_attack_hit`` et ``apply_damage``."""
        state = self._require_state(combat_id)
        if state.status != "active":
            raise CombatStatusError("Les sorts ne sont lançables qu'en combat actif.")

        caster = self._require_combatant(state, caster_id)
        self._require_combatant(state, target_id)
        caster_char = self._require_character(caster.character_id)

        spell = load_combat_spell(self._engine, spell_id, locale=locale)
        if spell.effect_type != "spell_attack":
            raise SpellCastError(f"{spell_id!r} n'est pas une attaque de sort.")

        self._publish_spell_cast(state, caster_id, spell, (target_id,))

        request = build_spell_attack_request(
            caster_char, self._engine, base_mode=base_mode
        )
        attack = self.resolve_attack_roll(
            combat_id, caster_id, target_id, request, rng=rng
        )

        damage_resolution = None
        state = self._require_state(combat_id)
        if attack.outcome.hit:
            notation = resolve_spell_damage_notation(spell, caster_char)
            state, damage_resolution = self.apply_damage(
                combat_id,
                target_id,
                notation,
                critical=attack.outcome.critical,
                source_id=caster_id,
                rng=rng,
            )

        return state, SpellAttackOutcome(
            spell=spell,
            attack=attack,
            damage=damage_resolution,
        )

    def cast_spell_save(
        self,
        combat_id: int,
        caster_id: str,
        target_id: str,
        spell_id: str,
        *,
        rng: RandInt | None = None,
        locale: str = "fr",
    ) -> tuple[CombatState, SpellSaveOutcome]:
        """Sort à sauvegarde — DD calculé, moitié des dégâts si réussite."""
        state = self._require_state(combat_id)
        if state.status != "active":
            raise CombatStatusError("Les sorts ne sont lançables qu'en combat actif.")

        caster = self._require_combatant(state, caster_id)
        target = self._require_combatant(state, target_id)
        caster_char = self._require_character(caster.character_id)
        target_char = self._require_character(target.character_id)

        spell = load_combat_spell(self._engine, spell_id, locale=locale)
        if spell.effect_type != "saving_throw":
            raise SpellCastError(f"{spell_id!r} n'est pas un sort à sauvegarde.")

        self._publish_spell_cast(state, caster_id, spell, (target_id,))

        notation = resolve_spell_damage_notation(spell, caster_char)
        damage_roll = roll_damage(notation, rng=rng)
        save_dc = compute_spell_save_dc(caster_char, self._engine)
        save_ability = save_ability_for_spell(spell)
        save_request = build_save_request(
            target_char, self._engine, save_ability
        )
        d20 = roll_d20_for_character(
            save_request, target_char, self._engine, rng=rng
        )
        succeeded = save_succeeded(d20.total, save_dc)
        half = half_on_save_for_spell(spell)
        final_damage = damage_after_save(
            damage_roll.total,
            save_succeeded_flag=succeeded,
            half_on_save=half,
        )

        state = self._require_state(combat_id)
        self._bus.publish(
            SavingThrowResolved(
                ruleset_id=state.ruleset_id,
                combat_id=state.combat_id or str(combat_id),
                guild_id=state.guild_id or "",
                channel_id=state.channel_id or "",
                caster_id=caster_id,
                target_id=target_id,
                spell_id=spell_id,
                save_ability=save_ability,
                save_dc=save_dc,
                save_total=d20.total,
                succeeded=succeeded,
                damage_before_save=damage_roll.total,
                damage_applied=final_damage,
            )
        )

        state, damage_resolution = self.apply_damage(
            combat_id,
            target_id,
            damage_amount=final_damage,
            source_id=caster_id,
            dice_notation_label=f"{notation} → {final_damage}",
        )

        return state, SpellSaveOutcome(
            spell=spell,
            save_dc=save_dc,
            save_total=d20.total,
            succeeded=succeeded,
            damage_roll=damage_roll,
            damage=damage_resolution,
        )

    def cast_hunters_mark(
        self,
        combat_id: int,
        caster_id: str,
        target_id: str,
        *,
        locale: str = "fr",
    ) -> CombatState:
        """Pose la concentration et marque la cible (overlay combat)."""
        state = self._require_state(combat_id)
        if state.status != "active":
            raise CombatStatusError("Les sorts ne sont lançables qu'en combat actif.")

        caster = self._require_combatant(state, caster_id)
        self._require_combatant(state, target_id)
        caster_char = self._require_character(caster.character_id)

        spell = load_combat_spell(self._engine, "hunters_mark", locale=locale)
        self._publish_spell_cast(state, caster_id, spell, (target_id,))

        updated_char, _interrupted = _set_concentration(
            caster_char, spell.spell_id, spell.spell_name
        )
        self._characters.save(updated_char)

        state.combatants[caster_id] = caster.with_concentration(
            spell.spell_id, spell.spell_name
        )
        state.combatants[target_id] = state.combatants[target_id].with_hunters_mark(
            caster_id
        )
        self._persist(state)
        return state

    def cast_bless(
        self,
        combat_id: int,
        caster_id: str,
        target_ids: list[str],
        *,
        locale: str = "fr",
    ) -> CombatState:
        """Bénédiction — concentration + buff overlay sur jusqu'à 3 cibles."""
        if len(target_ids) > 3:
            raise ValueError("Bénédiction : maximum 3 cibles (SRD 2014).")

        state = self._require_state(combat_id)
        if state.status != "active":
            raise CombatStatusError("Les sorts ne sont lançables qu'en combat actif.")

        caster = self._require_combatant(state, caster_id)
        for target_id in target_ids:
            self._require_combatant(state, target_id)
        caster_char = self._require_character(caster.character_id)

        spell = load_combat_spell(self._engine, "bless", locale=locale)
        self._publish_spell_cast(
            state, caster_id, spell, tuple(target_ids)
        )

        updated_char, _interrupted = _set_concentration(
            caster_char, spell.spell_id, spell.spell_name
        )
        self._characters.save(updated_char)

        state.combatants[caster_id] = caster.with_concentration(
            spell.spell_id, spell.spell_name
        )
        for target_id in target_ids:
            state.combatants[target_id] = state.combatants[target_id].with_blessed(
                True
            )
        self._persist(state)
        return state

    def load_combat(self, combat_id: int) -> CombatState:
        """Charge un combat par identifiant SQL."""
        record = self._combats.get_by_id(combat_id)
        if record is None:
            raise CombatNotFoundError(f"Combat introuvable : id={combat_id}.")
        return record.state

    def load_open_combat(
        self,
        guild_id: str,
        channel_id: str,
    ) -> CombatState | None:
        """Retourne le combat ouvert (preparing ou active) du salon, ou ``None``."""
        record = self._combats.get_open_by_channel(guild_id, channel_id)
        if record is None:
            return None
        return record.state

    def load_active_combat(
        self,
        guild_id: str,
        channel_id: str,
    ) -> CombatState | None:
        """Alias C1 — combat ouvert (preparing ou active)."""
        return self.load_open_combat(guild_id, channel_id)

    def save_combat(self, state: CombatState) -> None:
        """Persiste l'état complet du combat (blob JSON)."""
        if state.combat_id is None:
            raise ValueError("combat_id requis pour sauvegarder.")
        combat_id = int(state.combat_id)
        record = self._combats.get_by_id(combat_id)
        if record is None:
            raise CombatNotFoundError(f"Combat introuvable : id={combat_id}.")
        sql_status = sql_status_from_combat(state.status)
        self._combats.save(
            CombatRecord(
                combat_id=combat_id,
                guild_id=record.guild_id,
                channel_id=record.channel_id,
                sql_status=sql_status,
                state=state,
            )
        )

    def close_combat(self, combat_id: int, *, reason: str = "closed") -> CombatState:
        """Clôture un combat ouvert ; publie ``CombatEnded``."""
        record = self._combats.get_by_id(combat_id)
        if record is None:
            raise CombatNotFoundError(f"Combat introuvable : id={combat_id}.")
        if record.state.status == "ended":
            return record.state

        state = record.state
        state.status = "ended"
        state.ended_at = utc_now_iso()

        self._combats.save(
            CombatRecord(
                combat_id=record.combat_id,
                guild_id=record.guild_id,
                channel_id=record.channel_id,
                sql_status="ended",
                state=state,
            )
        )

        self._bus.publish(
            CombatEnded(
                ruleset_id=state.ruleset_id,
                combat_id=str(combat_id),
                guild_id=record.guild_id,
                channel_id=record.channel_id,
                reason=reason,
            )
        )
        return state

    def _build_combatant(self, character_id: str) -> Combatant:
        character = self._characters.get_by_id(character_id)
        if character is None:
            raise CombatCharacterNotFoundError(
                f"Personnage introuvable pour le combat : {character_id!r}."
            )
        sheet = build_character_sheet(character, self._engine)
        combatant_id = str(uuid.uuid4())[:8]
        return Combatant(
            combatant_id=combatant_id,
            display_name=sheet.name,
            kind="player_character",
            character_id=character_id,
            hp_current=sheet.hp_current,
            hp_max=sheet.hp_max,
            ac=sheet.ac,
        )

    def _require_character(self, character_id: str):
        character = self._characters.get_by_id(character_id)
        if character is None:
            raise CombatCharacterNotFoundError(
                f"Personnage introuvable : {character_id!r}."
            )
        return character

    def _publish_spell_cast(
        self,
        state: CombatState,
        caster_id: str,
        spell: CombatSpellEffect,
        target_ids: tuple[str, ...],
    ) -> None:
        self._bus.publish(
            SpellCast(
                ruleset_id=state.ruleset_id,
                combat_id=state.combat_id or "",
                guild_id=state.guild_id or "",
                channel_id=state.channel_id or "",
                caster_id=caster_id,
                spell_id=spell.spell_id,
                spell_name=spell.spell_name,
                effect_type=spell.effect_type,
                target_ids=target_ids,
            )
        )

    def _require_combatant(self, state: CombatState, combatant_id: str) -> Combatant:
        combatant = state.combatants.get(combatant_id)
        if combatant is None:
            raise CombatantNotFoundError(
                f"Combattant introuvable dans la rencontre : {combatant_id!r}."
            )
        return combatant

    def _roll_initiative_for_combatants(
        self,
        combatants: list[Combatant],
        *,
        rng: Callable[[], int] | None,
    ) -> list[InitiativeRollResult]:
        rolls: list[InitiativeRollResult] = []
        for combatant in combatants:
            character = self._characters.get_by_id(combatant.character_id)
            if character is None:
                raise CombatCharacterNotFoundError(
                    f"Personnage introuvable : {combatant.character_id!r}."
                )
            sheet = build_character_sheet(character, self._engine)
            rolls.append(
                roll_initiative(combatant.combatant_id, sheet.initiative, rng=rng)
            )
        return rolls

    def _require_state(self, combat_id: int) -> CombatState:
        record = self._combats.get_by_id(combat_id)
        if record is None:
            raise CombatNotFoundError(f"Combat introuvable : id={combat_id}.")
        return record.state

    def _persist(self, state: CombatState) -> None:
        if state.combat_id is None:
            raise ValueError("combat_id requis pour persister.")
        combat_id = int(state.combat_id)
        record = self._combats.get_by_id(combat_id)
        if record is None:
            raise CombatNotFoundError(f"Combat introuvable : id={combat_id}.")
        self._combats.save(
            CombatRecord(
                combat_id=combat_id,
                guild_id=record.guild_id,
                channel_id=record.channel_id,
                sql_status=sql_status_from_combat(state.status),
                state=state,
            )
        )

    def _publish_initiative_events(
        self,
        record: CombatRecord,
        rolls: list[InitiativeRollResult],
        order: tuple[str, ...],
    ) -> None:
        state = record.state
        roll_payload = tuple(
            (r.combatant_id, r.d20, r.modifier, r.total) for r in rolls
        )
        self._bus.publish(
            InitiativeRolled(
                ruleset_id=state.ruleset_id,
                combat_id=state.combat_id or str(record.combat_id),
                guild_id=record.guild_id,
                channel_id=record.channel_id,
                initiative_order=order,
                rolls=roll_payload,
            )
        )

    def _publish_turn_started(self, state: CombatState) -> None:
        combatant_id = state.initiative_order[state.turn_index]
        self._bus.publish(
            TurnStarted(
                ruleset_id=state.ruleset_id,
                combat_id=state.combat_id or "",
                guild_id=state.guild_id or "",
                channel_id=state.channel_id or "",
                combatant_id=combatant_id,
                round_number=state.round_number,
                turn_index=state.turn_index,
            )
        )
