# tests/unit/test_architecture_doc_paths.py
"""Vérifie que les chemins cités (inline) dans docs/ARCHITECTURE.md existent."""
from __future__ import annotations

import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
ARCHITECTURE_DOC = REPO_ROOT / "docs" / "ARCHITECTURE.md"

KNOWN_EXTENSIONS = (".py", ".json", ".md", ".toml", ".yml", ".yaml", ".db", ".sql")

# Segment entièrement en MAJUSCULES / chiffres / underscore (placeholder type NOM_DU_FICHIER).
_PLACEHOLDER_SEGMENT = re.compile(r"(?:^|/)[A-Z][A-Z0-9_]*(?:/|$)")

# Notation pointée Python sans slash (module qualifié).
_DOT_MODULE = re.compile(r"^[a-zA-Z_][\w.]*$")

# Négation d'existence sur la même ligne (chemin cité pour documenter une absence).
_ABSENCE_PATTERN = re.compile(
    r"n['']existent?\s+pas|n['']est\s+pas\s+implémenté|non\s+implémenté|\babsents?\b|\babsente\b",
    re.IGNORECASE,
)


def _has_known_extension(text: str) -> bool:
    lower = text.lower()
    return any(lower.endswith(ext) for ext in KNOWN_EXTENSIONS)


def _is_extension_only(text: str) -> bool:
    """Extension seule (.json) sans nom de fichier."""
    return text.startswith(".") and "/" not in text and text.count(".") == 1


def is_repo_path_candidate(span: str) -> bool:
    """True si le span inline ressemble à un chemin de dépôt à vérifier."""
    candidate = span.strip()
    if not candidate:
        return False
    if candidate.startswith(("http://", "https://")):
        return False
    if candidate.startswith("/"):
        return False
    if ".." in candidate:
        return False
    if any(ch in candidate for ch in "<>{}*"):
        return False
    if "..." in candidate:
        return False
    if _PLACEHOLDER_SEGMENT.search(candidate):
        return False
    if _is_extension_only(candidate):
        return False

    has_slash = "/" in candidate
    has_ext = _has_known_extension(candidate)

    if has_slash:
        return True
    if has_ext:
        # Fichier à la racine ou sous-chemin sans slash (ex. pyproject.toml, main.py).
        return True
    if "." in candidate and _DOT_MODULE.match(candidate):
        # jdr_engine.domain.rules, bot.cogs.dice — module, pas un chemin.
        return False
    return False


def span_documents_absence(line: str, match_end: int) -> bool:
    """True si le chemin inline est cité pour signaler une absence sur la ligne."""
    tail = line[match_end:]
    if _ABSENCE_PATTERN.search(tail):
        return True
    neg = _ABSENCE_PATTERN.search(line)
    if neg is not None and match_end <= neg.start():
        return True
    return False


def extract_repo_paths(markdown: str) -> list[tuple[int, str]]:
    """Extrait les chemins candidats avec leur numéro de ligne."""
    seen: set[tuple[int, str]] = set()
    results: list[tuple[int, str]] = []
    for line_no, line in _iter_markdown_lines(markdown):
        for match in re.finditer(r"`([^`]+)`", line):
            span = match.group(1)
            if not is_repo_path_candidate(span):
                continue
            if span_documents_absence(line, match.end()):
                continue
            key = (line_no, span)
            if key in seen:
                continue
            seen.add(key)
            results.append((line_no, span))
    return results


def _iter_markdown_lines(markdown: str):
    """Yield (line_no, line) hors blocs ```."""
    in_fence = False
    for line_no, line in enumerate(markdown.splitlines(), start=1):
        stripped = line.strip()
        if stripped.startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        yield line_no, line


def iter_inline_code_spans(markdown: str):
    """Yield (line_no, span) pour chaque inline code hors blocs ```."""
    for line_no, line in _iter_markdown_lines(markdown):
        for match in re.finditer(r"`([^`]+)`", line):
            yield line_no, match.group(1)


def repo_path_exists(repo_root: Path, path: str) -> bool:
    """Vérifie l'existence d'un chemin relativement à la racine du dépôt."""
    is_dir_hint = path.endswith("/")
    normalized = path.rstrip("/")
    if not normalized:
        return False

    full = repo_root / normalized
    if is_dir_hint:
        return full.is_dir()
    if full.is_file() or full.is_dir():
        return True
    if _has_known_extension(normalized):
        return full.is_file()
    return False


class TestArchitecturePathExtraction(unittest.TestCase):
    def test_extracts_valid_repo_path(self):
        md = "Voir `jdr_engine/rules/engine.py` pour le détail."
        self.assertEqual(extract_repo_paths(md), [(1, "jdr_engine/rules/engine.py")])

    def test_ignores_dotted_module_notation(self):
        md = "Import depuis `jdr_engine.domain.rules`."
        self.assertEqual(extract_repo_paths(md), [])

    def test_ignores_path_inside_fenced_block(self):
        md = "```\ncompendium/dnd5e/manifest.yaml\n```"
        self.assertEqual(extract_repo_paths(md), [])

    def test_ignores_placeholder_glob(self):
        md = "Refs `compendium/schemas/*.schema.json` invalides."
        self.assertEqual(extract_repo_paths(md), [])

    def test_ignores_url(self):
        md = "Doc : `https://example.com/foo/bar.py`"
        self.assertEqual(extract_repo_paths(md), [])

    def test_ignores_path_documenting_absence_on_same_line(self):
        md = "Les dossiers `interfaces/api/` **n'existent pas**."
        self.assertEqual(extract_repo_paths(md), [])

    def test_fenced_block_still_ignored_with_absence_rule(self):
        md = "```\ninterfaces/discord/startup.py\n```"
        self.assertEqual(extract_repo_paths(md), [])


class TestArchitectureDocPathsExist(unittest.TestCase):
    def test_architecture_md_cited_paths_exist(self):
        self.assertTrue(
            ARCHITECTURE_DOC.is_file(),
            f"Document introuvable : {ARCHITECTURE_DOC}",
        )
        markdown = ARCHITECTURE_DOC.read_text(encoding="utf-8")
        extracted = extract_repo_paths(markdown)
        self.assertGreater(
            len(extracted),
            10,
            "Trop peu de chemins extraits — filtre probablement trop agressif.",
        )

        missing: list[str] = []
        for line_no, path in extracted:
            if not repo_path_exists(REPO_ROOT, path):
                missing.append(f"  L{line_no}: `{path}`")

        if missing:
            self.fail(
                f"{len(missing)} chemin(s) cité(s) dans docs/ARCHITECTURE.md "
                f"introuvable(s) relativement à {REPO_ROOT}:\n"
                + "\n".join(missing)
            )


if __name__ == "__main__":
    unittest.main(verbosity=2)
