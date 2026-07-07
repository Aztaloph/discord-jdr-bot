# interfaces/discord/formatters/embed_fields.py
"""Utilitaires embed Discord — limites API (fields 1024, embed 6000)."""
from __future__ import annotations

import discord

DISCORD_FIELD_VALUE_MAX = 1024
DISCORD_FIELD_NAME_MAX = 256
DISCORD_EMBED_MAX_FIELDS = 25
DISCORD_EMBED_MAX_CHARS = 6000
_TRUNCATION_SUFFIX = "…"


def chunk_field_value(value: str, *, max_len: int = DISCORD_FIELD_VALUE_MAX) -> list[str]:
    """
    Découpe ``value`` en morceaux ≤ ``max_len``, toujours entre deux lignes.

    Ne coupe jamais au milieu d'une ligne.
    """
    text = value.strip() if value else ""
    if not text:
        return ["_—_"]
    if len(text) <= max_len:
        return [text]

    lines = text.split("\n")
    chunks: list[str] = []
    current: list[str] = []
    current_len = 0

    for line in lines:
        sep = 1 if current else 0
        add_len = len(line) + sep
        if current and current_len + add_len > max_len:
            chunks.append("\n".join(current))
            current = [line]
            current_len = len(line)
        else:
            current.append(line)
            current_len += add_len

    if current:
        chunks.append("\n".join(current))
    return chunks


def add_field_chunked(
    embed: discord.Embed,
    *,
    name: str,
    value: str,
    inline: bool = False,
    max_value_len: int = DISCORD_FIELD_VALUE_MAX,
) -> int:
    """
    Ajoute un field (ou plusieurs si découpage nécessaire).

    Returns:
        Nombre de fields ajoutés.
    """
    base_name = name[:DISCORD_FIELD_NAME_MAX]
    chunks = chunk_field_value(value, max_len=max_value_len)
    for index, chunk in enumerate(chunks):
        field_name = base_name if index == 0 else f"{base_name} (suite)"
        embed.add_field(
            name=field_name[:DISCORD_FIELD_NAME_MAX],
            value=chunk[:max_value_len],
            inline=inline,
        )
    return len(chunks)


def _embed_char_count(embed: discord.Embed) -> int:
    total = len(embed.title or "") + len(embed.description or "")
    if embed.footer and embed.footer.text:
        total += len(embed.footer.text)
    for field in embed.fields:
        total += len(field.name) + len(field.value)
    return total


def enforce_embed_limits(
    embed: discord.Embed,
    *,
    max_fields: int = DISCORD_EMBED_MAX_FIELDS,
    max_chars: int = DISCORD_EMBED_MAX_CHARS,
) -> None:
    """
    Tronque l'embed si les limites Discord sont dépassées (fields ou caractères).

    Modifie ``embed`` sur place. Ajoute « … » en fin de troncature.
    """
    while len(embed.fields) > max_fields:
        embed.remove_field(max_fields)

    if len(embed.fields) >= max_fields and _embed_char_count(embed) > max_chars:
        embed.remove_field(max_fields - 1)

    while _embed_char_count(embed) > max_chars and embed.fields:
        last = embed.fields[-1]
        embed.remove_field(len(embed.fields) - 1)
        allowed = max_chars - (_embed_char_count(embed) + len(last.name))
        if allowed <= len(_TRUNCATION_SUFFIX):
            continue
        trimmed = last.value[: allowed - len(_TRUNCATION_SUFFIX)].rstrip()
        if not trimmed:
            continue
        embed.add_field(
            name=last.name[:DISCORD_FIELD_NAME_MAX],
            value=trimmed + _TRUNCATION_SUFFIX,
            inline=last.inline,
        )
        break

    if len(embed.fields) > max_fields:
        while len(embed.fields) > max_fields:
            embed.remove_field(max_fields)
