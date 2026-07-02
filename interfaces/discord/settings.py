# interfaces/discord/settings.py
"""Configuration Discord / moteur v2."""
from __future__ import annotations

import os
from dataclasses import dataclass


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name, "").strip().lower()
    if not raw:
        return default
    return raw in ("1", "true", "yes", "on")


@dataclass(frozen=True)
class DiscordSettings:
    use_engine_v2: bool = False
    default_ruleset: str = "dnd5e"
    default_locale: str = "fr"
    compendium_strict: bool = True

    @classmethod
    def from_config(cls, config: dict | None = None) -> DiscordSettings:
        config = config or {}
        use_v2 = _env_bool("USE_ENGINE_V2", default=True)
        if "use_engine_v2" in config:
            use_v2 = bool(config["use_engine_v2"])

        ruleset = os.getenv("DEFAULT_RULESET", config.get("default_ruleset", "dnd5e"))
        locale = os.getenv("DEFAULT_LOCALE", config.get("default_locale", "fr"))
        strict = _env_bool(
            "COMPENDIUM_STRICT",
            default=bool(config.get("compendium_strict", True)),
        )
        return cls(
            use_engine_v2=use_v2,
            default_ruleset=ruleset,
            default_locale=locale,
            compendium_strict=strict,
        )
