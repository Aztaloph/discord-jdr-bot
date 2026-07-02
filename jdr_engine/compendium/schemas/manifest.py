# jdr_engine/compendium/schemas/manifest.py
from pydantic import BaseModel, Field


class RulesetManifest(BaseModel):
    id: str
    name: dict[str, str]
    version: str
    schema_version: str
    compatible_engine: str = ">=0.1.0"
    locales: list[str] = Field(default_factory=lambda: ["fr"])
    default_locale: str = "fr"
    license: str | None = None
    entry_types: list[str] = Field(default_factory=list)
    dependencies: list[str] = Field(default_factory=list)
