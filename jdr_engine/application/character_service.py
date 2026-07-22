# jdr_engine/application/character_service.py
"""Use cases CRUD personnages v2 + fiche calculée."""
from __future__ import annotations

import logging

from jdr_engine.application.dto.character_commands import (
    CreateCharacterCommand,
    DeleteCharacterCommand,
    GetCharacterQuery,
    GetCharacterSheetQuery,
    ListCharactersQuery,
)
from jdr_engine.domain.character.ability_scores import AbilityScores
from jdr_engine.domain.character.character import Character
from jdr_engine.domain.character.character_sheet import CharacterSheet
from jdr_engine.persistence.character_repository import CharacterRepository
from jdr_engine.rules.calculator import build_character_sheet
from jdr_engine.rules.engine import RuleEngine

logger = logging.getLogger(__name__)


class CharacterServiceError(Exception):
    """Erreur métier CharacterService."""


class CharacterNotFoundError(CharacterServiceError):
    pass


class CharacterValidationError(CharacterServiceError):
    pass


class CharacterService:
    """Orchestre persistance + Rule Engine pour les personnages."""

    def __init__(
        self,
        repository: CharacterRepository,
        rule_engine: RuleEngine,
    ):
        self._repo = repository
        self._engine = rule_engine

    def create(self, cmd: CreateCharacterCommand) -> Character:
        name = cmd.name.strip()
        if not name:
            raise CharacterValidationError("Le nom du personnage est obligatoire.")
        if not 1 <= cmd.level <= 20:
            raise CharacterValidationError("Le niveau doit être entre 1 et 20.")

        if cmd.ruleset_id != self._engine.ruleset_id:
            raise CharacterValidationError(
                f"Ruleset {cmd.ruleset_id!r} non chargé dans le moteur."
            )
        if not self._engine.entity_exists("race", cmd.race_id):
            raise CharacterValidationError(f"Race inconnue : {cmd.race_id!r}")
        if not self._engine.entity_exists("class", cmd.class_id):
            raise CharacterValidationError(f"Classe inconnue : {cmd.class_id!r}")

        owner = str(cmd.owner_id)
        guild_id = str(cmd.guild_id or "0")

        if self._repo.name_exists(name, owner, guild_id=guild_id):
            raise CharacterValidationError(
                f"Vous avez déjà un personnage nommé « {name} »."
            )

        character = Character(
            owner_id=owner,
            guild_id=guild_id,
            name=name,
            race_id=cmd.race_id,
            class_id=cmd.class_id,
            level=cmd.level,
            ruleset_id=cmd.ruleset_id,
            ruleset_version=self._engine.ruleset_version,
            ability_scores=cmd.ability_scores or AbilityScores(),
            hp_current=cmd.hp_current,
            image_url=cmd.image_url,
        )
        self._repo.save(character)
        logger.info("Personnage créé : %s (%s)", character.name, character.id)
        self._ensure_active_if_none(owner, guild_id, character.id)
        return character

    def _resolve_character(self, query: GetCharacterQuery) -> Character:
        owner = str(query.owner_id)
        character: Character | None = None

        if query.character_id:
            character = self._repo.get_by_id(query.character_id)
        elif query.name:
            character = self._repo.get_by_name(query.name, owner)
        else:
            raise CharacterValidationError("character_id ou name requis.")

        if character is None or character.owner_id != owner:
            raise CharacterNotFoundError("Personnage introuvable.")
        return character

    def get(self, query: GetCharacterQuery) -> Character:
        return self._resolve_character(query)

    def get_sheet(self, query: GetCharacterSheetQuery) -> CharacterSheet:
        char_query = GetCharacterQuery(
            character_id=query.character_id,
            name=query.name,
            owner_id=query.owner_id,
        )
        character = self._resolve_character(char_query)
        return build_character_sheet(
            character,
            self._engine,
            locale=query.locale,
        )

    def list_by_owner(self, query: ListCharactersQuery) -> list[Character]:
        return self._repo.list_by_owner(
            str(query.owner_id),
            guild_id=query.guild_id,
        )

    def list_by_guild(self, guild_id: str) -> list[Character]:
        return self._repo.list_by_guild(str(guild_id))

    def get_on_guild(self, character_id: str, guild_id: str) -> Character:
        character = self._repo.get_by_id(character_id)
        if character is None or str(character.guild_id) != str(guild_id):
            raise CharacterNotFoundError("Personnage introuvable sur ce serveur.")
        return character

    def delete_on_guild(self, character_id: str, guild_id: str) -> bool:
        character = self.get_on_guild(character_id, guild_id)
        return self._repo.delete(character.id)

    def list_sheets(
        self,
        query: ListCharactersQuery,
        *,
        locale: str = "fr",
    ) -> list[CharacterSheet]:
        return [
            build_character_sheet(c, self._engine, locale=locale)
            for c in self.list_by_owner(query)
        ]

    def delete(self, cmd: DeleteCharacterCommand) -> bool:
        character = self._repo.get_by_id(cmd.character_id)
        if character is None or character.owner_id != str(cmd.owner_id):
            raise CharacterNotFoundError("Personnage introuvable.")
        deleted = self._repo.delete(cmd.character_id)
        return deleted

    def resolve_owned_on_guild(
        self,
        owner_id: str,
        guild_id: str,
        character_ref: str,
    ) -> Character:
        """Résout un personnage par id court ou nom sur un serveur."""
        owner = str(owner_id)
        guild = str(guild_id)
        ref = character_ref.strip()
        by_id = self._repo.get_by_id(ref)
        if (
            by_id is not None
            and by_id.owner_id == owner
            and str(by_id.guild_id) == guild
        ):
            return by_id
        by_name = self._repo.get_by_name(ref, owner, guild_id=guild)
        if by_name is not None:
            return by_name
        raise CharacterNotFoundError("Personnage introuvable sur ce serveur.")

    def get_active_character(self, owner_id: str, guild_id: str) -> Character | None:
        active_id = self._repo.get_active_character_id(str(owner_id), str(guild_id))
        if not active_id:
            return None
        character = self._repo.get_by_id(active_id)
        if character is None or character.owner_id != str(owner_id):
            self._repo.clear_active_for_character(active_id)
            return None
        if str(character.guild_id) != str(guild_id):
            return None
        return character

    def set_active_character(
        self, owner_id: str, guild_id: str, character_ref: str
    ) -> Character:
        character = self.resolve_owned_on_guild(owner_id, guild_id, character_ref)
        self._repo.set_active_character_id(str(owner_id), str(guild_id), character.id)
        logger.info(
            "Perso actif : %s (%s) owner=%s guild=%s",
            character.name,
            character.id,
            owner_id,
            guild_id,
        )
        return character

    def resolve_for_game(
        self,
        owner_id: str,
        guild_id: str,
        character_ref: str | None,
    ) -> Character:
        """Personnage pour /roll, /sort, etc. — actif par défaut."""
        if character_ref and character_ref.strip():
            return self.resolve_owned_on_guild(owner_id, guild_id, character_ref)
        active = self.get_active_character(owner_id, guild_id)
        if active is not None:
            return active
        raise CharacterNotFoundError(
            "Aucun personnage actif. Utilisez `/perso-choisir` ou précisez le paramètre `perso`."
        )

    def _ensure_active_if_none(
        self, owner_id: str, guild_id: str, character_id: str
    ) -> None:
        if self._repo.get_active_character_id(str(owner_id), str(guild_id)):
            return
        self._repo.set_active_character_id(str(owner_id), str(guild_id), character_id)

    def create_from_wizard(
        self,
        *,
        owner_id: str,
        guild_id: str,
        name: str,
        race_id: str,
        class_id: str,
        base_scores: dict[str, int],
        level: int = 1,
        skills: list[str] | tuple[str, ...] | None = None,
        expertise_skills: list[str] | tuple[str, ...] | None = None,
        specialization: str | None = None,
        fighting_style: str | None = None,
        totem_spirit: str | None = None,
        favored_enemy_type: str | None = None,
        favored_terrain: str | None = None,
        lore_bonus_skills: list[str] | tuple[str, ...] | None = None,
        sorcerer_dragon_type: str | None = None,
        druid_land_terrain: str | None = None,
        metamagic_options: list[str] | tuple[str, ...] | None = None,
        eldritch_invocations: list[str] | tuple[str, ...] | None = None,
        pact_boon: str | None = None,
        draconic_ancestry: str | None = None,
        racial_ability_bonuses: list[str] | tuple[str, ...] | None = None,
        racial_skills: list[str] | tuple[str, ...] | None = None,
        locale: str = "fr",
    ) -> Character:
        """Création guidée — stats, compétences, domaine (clerc), grimoire initial."""
        from jdr_engine.rules.character_creation.finalize import finalize_new_character

        if self._repo.name_exists(name, str(owner_id), guild_id=str(guild_id)):
            raise CharacterValidationError(
                f"Vous avez déjà un personnage nommé « {name} » sur ce serveur."
            )

        try:
            character = finalize_new_character(
                name=name,
                race_id=race_id,
                class_id=class_id,
                owner_id=str(owner_id),
                guild_id=str(guild_id),
                base_scores=base_scores,
                engine=self._engine,
                level=level,
                skills=skills,
                expertise_skills=expertise_skills,
                specialization=specialization,
                fighting_style=fighting_style,
                totem_spirit=totem_spirit,
                favored_enemy_type=favored_enemy_type,
                favored_terrain=favored_terrain,
                lore_bonus_skills=lore_bonus_skills,
                sorcerer_dragon_type=sorcerer_dragon_type,
                druid_land_terrain=druid_land_terrain,
                metamagic_options=metamagic_options,
                eldritch_invocations=eldritch_invocations,
                pact_boon=pact_boon,
                draconic_ancestry=draconic_ancestry,
                racial_ability_bonuses=racial_ability_bonuses,
                racial_skills=racial_skills,
            )
        except ValueError as exc:
            raise CharacterValidationError(str(exc)) from exc

        self._repo.save(character)
        logger.info(
            "Personnage créé (wizard) : %s (%s) guild=%s",
            character.name,
            character.id,
            guild_id,
        )
        self._ensure_active_if_none(str(owner_id), str(guild_id), character.id)
        return character

    def save(self, character: Character) -> Character:
        """Persiste l'état d'un personnage existant (ex. emplacements de sorts)."""
        existing = self._repo.get_by_id(character.id)
        if existing is None:
            raise CharacterNotFoundError("Personnage introuvable.")
        self._repo.save(character)
        return character

    def long_rest_on_guild(self, character_id: str, guild_id: str):
        """Repos long SRD — persiste le personnage mis à jour."""
        from jdr_engine.rules.rest import RestError, apply_long_rest

        character = self.get_on_guild(character_id, guild_id)
        try:
            updated, result = apply_long_rest(character, self._engine)
        except RestError:
            raise
        self._repo.save(updated)
        return result

    def prepare_spells_for_active_character(
        self,
        owner_id: str,
        guild_id: str,
        prepared_spells: list[str] | tuple[str, ...],
    ):
        """Re-préparation sorts — perso actif, propriétaire, après repos long."""
        from jdr_engine.rules.spellcasting.prepared_choice import (
            PreparedChoiceError,
            apply_prepared_selection,
            build_prepared_choice_context,
            is_prepared_rechoice_pending,
            requires_prepared_rechoice_class,
        )

        character = self.get_active_character(str(owner_id), str(guild_id))
        if character is None:
            raise CharacterNotFoundError(
                "Aucun personnage actif. Utilisez `/perso-choisir`."
            )
        if str(character.owner_id) != str(owner_id):
            raise CharacterValidationError("Ce personnage ne vous appartient pas.")

        if not requires_prepared_rechoice_class(character.class_id):
            raise CharacterValidationError(
                "Cette classe ne prépare pas ses sorts de cette manière."
            )
        if not is_prepared_rechoice_pending(character):
            raise CharacterValidationError(
                "Re-préparation disponible uniquement après un **repos long**."
            )

        try:
            updated = apply_prepared_selection(
                character,
                self._engine,
                prepared_spells,
                require_pending=True,
            )
        except PreparedChoiceError as exc:
            raise CharacterValidationError(str(exc)) from exc

        self._repo.save(updated)
        ctx = build_prepared_choice_context(updated, engine=self._engine)
        return updated, ctx

    def short_rest_on_guild(
        self,
        character_id: str,
        guild_id: str,
        dice_to_spend: int,
        *,
        rng=None,
    ):
        """Repos court SRD — persiste le personnage mis à jour."""
        from jdr_engine.rules.rest import RestError, apply_short_rest

        character = self.get_on_guild(character_id, guild_id)
        try:
            updated, result = apply_short_rest(
                character, self._engine, dice_to_spend, rng=rng
            )
        except RestError:
            raise
        self._repo.save(updated)
        return result

    def level_up_on_guild(
        self,
        character_id: str,
        guild_id: str,
        *,
        subclass: str | None = None,
        totem_spirit: str | None = None,
        subchoice_value: str | None = None,
        fighting_style: str | None = None,
        lore_bonus_skills: list[str] | tuple[str, ...] | None = None,
        expertise_skills: list[str] | tuple[str, ...] | None = None,
        metamagic_options: list[str] | tuple[str, ...] | None = None,
        eldritch_invocations: list[str] | tuple[str, ...] | None = None,
        pact_boon: str | None = None,
        base_character: Character | None = None,
    ):
        """Montée de niveau SRD — persiste le personnage mis à jour."""
        from dataclasses import replace

        from jdr_engine.rules.character_progression import (
            LevelUpError,
            LevelUpPendingChoice,
            apply_level_up,
        )

        character = self.get_on_guild(character_id, guild_id)
        if base_character is not None:
            merged = dict(character.choices or {})
            merged.update(base_character.choices or {})
            character = replace(character, choices=merged)
        try:
            updated, result = apply_level_up(
                character,
                self._engine,
                subclass=subclass,
                totem_spirit=totem_spirit,
                subchoice_value=subchoice_value,
                fighting_style=fighting_style,
                lore_bonus_skills=lore_bonus_skills,
                expertise_skills=expertise_skills,
                metamagic_options=metamagic_options,
                eldritch_invocations=eldritch_invocations,
                pact_boon=pact_boon,
            )
        except LevelUpPendingChoice:
            raise
        except LevelUpError:
            raise
        self._repo.save(updated)
        return result

    def complete_level_up_choice_on_guild(
        self,
        character_id: str,
        guild_id: str,
        *,
        subclass: str | None = None,
        totem_spirit: str | None = None,
        subchoice_value: str | None = None,
        fighting_style: str | None = None,
        lore_bonus_skills: list[str] | tuple[str, ...] | None = None,
        expertise_skills: list[str] | tuple[str, ...] | None = None,
        metamagic_options: list[str] | tuple[str, ...] | None = None,
        eldritch_invocations: list[str] | tuple[str, ...] | None = None,
        pact_boon: str | None = None,
        base_character: Character | None = None,
    ):
        """Finalise une montée de niveau après choix interactif."""
        return self.level_up_on_guild(
            character_id,
            guild_id,
            subclass=subclass,
            totem_spirit=totem_spirit,
            subchoice_value=subchoice_value,
            fighting_style=fighting_style,
            lore_bonus_skills=lore_bonus_skills,
            expertise_skills=expertise_skills,
            metamagic_options=metamagic_options,
            eldritch_invocations=eldritch_invocations,
            pact_boon=pact_boon,
            base_character=base_character,
        )

    def reset_wizard_grimoire_on_guild(
        self,
        character_id: str,
        guild_id: str,
    ):
        """
        Réinitialise grimoire / cantrips / préparés d'un magicien (P2g / P2h).

        Sans dépendance Discord. No-op persistant si déjà canonique.
        """
        from jdr_engine.application.dto.wizard_grimoire_reset import (
            WizardGrimoireResetResult,
        )
        from jdr_engine.rules.spellcasting.preparation import (
            WizardSpellbookResetError,
            is_wizard_spellcasting_canonical,
            project_wizard_spellcasting_reset,
            rebuild_wizard_spellcasting_at_level,
        )
        from jdr_engine.rules.spellcasting.state import (
            get_cantrips_known,
            get_spellbook,
            get_spells_prepared_list,
        )

        character = self.get_on_guild(character_id, guild_id)
        if character.class_id != "wizard":
            raise CharacterValidationError(
                "Seuls les magiciens possèdent un grimoire réinitialisable."
            )

        cantrips_before = tuple(get_cantrips_known(character))
        spellbook_before = tuple(get_spellbook(character))
        prepared_before = tuple(get_spells_prepared_list(character))

        if is_wizard_spellcasting_canonical(character):
            return WizardGrimoireResetResult(
                character_id=character.id,
                character_name=character.name,
                already_clean=True,
                cantrips_before=cantrips_before,
                cantrips_after=cantrips_before,
                spellbook_before=spellbook_before,
                spellbook_after=spellbook_before,
                prepared_before=prepared_before,
                prepared_after=prepared_before,
            )

        projected = project_wizard_spellcasting_reset(character)
        try:
            updated = rebuild_wizard_spellcasting_at_level(character)
        except WizardSpellbookResetError as exc:
            raise CharacterValidationError(str(exc)) from exc

        self._repo.save(updated)

        return WizardGrimoireResetResult(
            character_id=updated.id,
            character_name=updated.name,
            already_clean=False,
            cantrips_before=cantrips_before,
            cantrips_after=tuple(get_cantrips_known(projected)),
            spellbook_before=spellbook_before,
            spellbook_after=tuple(get_spellbook(projected)),
            prepared_before=prepared_before,
            prepared_after=tuple(get_spells_prepared_list(projected)),
        )
