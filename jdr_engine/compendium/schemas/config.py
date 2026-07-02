# jdr_engine/compendium/schemas/config.py
from pydantic import BaseModel, Field


class AbilityConfig(BaseModel):
    id: str
    name: dict[str, str]


class LevelEntry(BaseModel):
    proficiency_bonus: int = Field(..., ge=2, le=6)


class RulesetConfig(BaseModel):
    abilities: list[AbilityConfig] = Field(default_factory=list)
    level_table: dict[str, LevelEntry] = Field(default_factory=dict)
    sizes: dict[str, dict[str, dict[str, str]]] = Field(default_factory=dict)

    def proficiency_bonus_at_level(self, level: int) -> int:
        entry = self.level_table.get(str(level))
        if entry is None:
            raise KeyError(f"Niveau {level} absent de level_table")
        return entry.proficiency_bonus
