from jdr_engine.compendium.schemas.common import (
    DefinitionSchema,
    EntityRef,
    ENTRY_TYPE_PLURAL_TO_SINGULAR,
    ENTRY_TYPE_SINGULAR_TO_PLURAL,
    normalize_entity_type,
    plural_entity_type,
)
from jdr_engine.compendium.schemas.config import RulesetConfig
from jdr_engine.compendium.schemas.manifest import RulesetManifest

__all__ = [
    "DefinitionSchema",
    "EntityRef",
    "RulesetConfig",
    "RulesetManifest",
    "ENTRY_TYPE_PLURAL_TO_SINGULAR",
    "ENTRY_TYPE_SINGULAR_TO_PLURAL",
    "normalize_entity_type",
    "plural_entity_type",
]
