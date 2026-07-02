# interfaces/discord/formatters/lore_text.py
"""Préparation du lore Compendium pour les embeds Discord."""
from __future__ import annotations

import re

DISCORD_FIELD_MAX = 1024
DISCORD_DESCRIPTION_MAX = 4096


def clean_lore_markdown(text: str) -> str:
    """Retire titres markdown et normalise les espaces."""
    cleaned = re.sub(r"^#+\s*", "", text, flags=re.MULTILINE)
    cleaned = re.sub(r"\*\*(.+?)\*\*", r"\1", cleaned)
    cleaned = re.sub(r"\*(.+?)\*", r"\1", cleaned)
    return " ".join(cleaned.split())


def truncate_lore(text: str, max_length: int = 400) -> str:
    """Tronque proprement à la fin d'un mot."""
    text = clean_lore_markdown(text)
    if len(text) <= max_length:
        return text
    cut = text[: max_length - 1].rsplit(" ", 1)[0]
    return f"{cut}…"


def combine_lore_sections(
    sections: list[tuple[str, str]],
    *,
    max_total: int = 900,
    max_per_section: int = 400,
) -> str | None:
    """Assemble plusieurs blocs lore (ex. race + classe) pour la description embed."""
    parts: list[str] = []
    for label, raw in sections:
        if not raw:
            continue
        excerpt = truncate_lore(raw, max_per_section)
        parts.append(f"**{label}** — _{excerpt}_")
    if not parts:
        return None
    combined = "\n\n".join(parts)
    if len(combined) <= max_total:
        return combined
    return combined[: max_total - 1].rsplit(" ", 1)[0] + "…"
