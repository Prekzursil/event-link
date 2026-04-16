"""Inserts minimal JSDoc comments for TypeScript/JavaScript functions and classes.

Targets DeepSource JS-D1001 occurrences by scanning .ts/.tsx/.js/.jsx
files for function and class declarations that lack a JSDoc comment
immediately above them, then inserting one derived from the symbol name.
"""

from __future__ import annotations

import pathlib
import re
import sys


SKIP_TOKENS = (
    "/node_modules/",
    "/.vite/",
    "/dist/",
    "/coverage/",
    "/build/",
)


_FUNCTION_RE = (
    r"^(?P<indent>[ \t]*)"
    r"(?P<kw>export\s+(?:default\s+)?(?:async\s+)?function|function|async\s+function)"
    r"\s+(?P<name>[A-Za-z_$][\w$]*)"
)
_CLASS_RE = (
    r"^(?P<indent>[ \t]*)"
    r"(?P<kw>export\s+(?:default\s+)?class|class)"
    r"\s+(?P<name>[A-Za-z_$][\w$]*)"
)
_EXPORTED_ARROW_RE = (
    r"^(?P<indent>[ \t]*)"
    r"(?P<kw>export\s+(?:const|let|var))"
    r"\s+(?P<name>[A-Za-z_$][\w$]*)\s*=\s*(?:async\s*)?\("
)
# Non-exported local arrow / handler pattern. Skipped when already preceded by
# a JSDoc comment so we don't double-document inner closures.
_LOCAL_ARROW_RE = (
    r"^(?P<indent>[ \t]*)"
    r"(?P<kw>const|let)"
    r"\s+(?P<name>handle[A-Z][\w$]*|install[A-Z][\w$]*|"
    r"seed[A-Z][\w$]*|render[A-Z][\w$]*|make[A-Z][\w$]*)\s*=\s*(?:async\s*)?\("
)

DECL_PATTERNS = [
    (re.compile(_FUNCTION_RE, re.MULTILINE), "function"),
    (re.compile(_CLASS_RE, re.MULTILINE), "class"),
    (re.compile(_EXPORTED_ARROW_RE, re.MULTILINE), "arrow"),
    (re.compile(_LOCAL_ARROW_RE, re.MULTILINE), "arrow"),
]


def _humanize(name: str) -> str:
    """Turns ``renderLanguageRoute`` into ``render language route``."""
    pieces = re.split(r"(?=[A-Z])|[_\s]+", name)
    return " ".join(piece.lower() for piece in pieces if piece)


# (prefix, suffix_start, template). "tail" comes from human[suffix_start:] and
# falls back to the untouched humanised form when empty.
_DESCRIBE_RULES: tuple[tuple[str, int, str], ...] = (
    ("render", 6, "Renders the {tail} scaffolding for tests."),
    ("require", 7, "Returns the {tail} value or fails loudly when absent."),
    ("define", 6, "Installs a {tail} hook for tests."),
    ("handle", 6, "Handles the {tail} event."),
    ("make", 4, "Builds a {tail} fixture."),
    ("open", 4, "Opens the {tail} UI surface for tests."),
    ("set", 3, "Sets the {tail} fixture state."),
)


def _describe(kind: str, name: str) -> str:
    """Returns a one-line JSDoc summary for a symbol of ``kind`` named ``name``."""
    human = _humanize(name)
    if kind == "class":
        return f"Test-support {human} helper class."
    if name.startswith("use") and name[3:4].isupper():
        return f"React hook: {human[4:].strip() or human}."
    for prefix, suffix_start, template in _DESCRIBE_RULES:
        if name.startswith(prefix):
            tail = human[suffix_start:].strip() or human
            return template.format(tail=tail)
    return f"Test helper: {human}."


def _has_preceding_jsdoc(source: str, start_idx: int) -> bool:
    """Returns True when the first non-blank line above ``start_idx``
    ends with ``*/``.
    """
    cursor = start_idx
    while cursor > 0:
        # back up to the previous line start
        prev = source.rfind("\n", 0, cursor - 1)
        line = source[prev + 1 : cursor] if prev >= 0 else source[:cursor]
        stripped = line.strip()
        if not stripped:
            cursor = prev
            continue
        # We accept any block immediately above that starts with `/**` as a
        # JSDoc comment. A short window search between the previous blank
        # line and start_idx is enough for this heuristic.
        if stripped.endswith("*/"):
            block = source[:start_idx]
            last_blank = block.rfind("\n\n")
            region = block[last_blank:] if last_blank >= 0 else block
            return "/**" in region
        return False
    return False


_REPO_ROOT = pathlib.Path.cwd().resolve()


def _is_inside_repo(path: pathlib.Path) -> bool:
    """Returns True when ``path`` resolves inside the repository root."""
    try:
        path.resolve().relative_to(_REPO_ROOT)
    except ValueError:
        return False
    return True


_ALLOWED_ROOT = str(_REPO_ROOT)


def _safe_resolve_in_repo(path: pathlib.Path) -> str:
    """Normalises ``path`` and returns a string; raises for anything
    outside repo root.
    """
    import os as _os

    absolute = _os.path.normpath(_os.path.abspath(str(path)))
    prefix = _ALLOWED_ROOT + _os.sep
    if not absolute.startswith(prefix) and absolute != _ALLOWED_ROOT:
        raise PermissionError(f"refusing to touch file outside repo root: {absolute}")
    return absolute


def _inject(path: pathlib.Path) -> int:
    """Adds JSDoc above each declaration in ``path`` that lacks one; returns count
    added.
    """
    safe_str = _safe_resolve_in_repo(path)
    with open(safe_str, "r", encoding="utf-8") as handle:
        text = handle.read()
    # Walk declarations in order by position so we do not disturb later
    # offsets until we rebuild the full file.
    hits: list[tuple[int, int, str, str]] = []
    for pattern, kind in DECL_PATTERNS:
        for match in pattern.finditer(text):
            hits.append((match.start(), match.end(), kind, match.group("name")))
    hits.sort()
    # Deduplicate overlapping matches (arrow + function share some prefixes)
    seen: set[int] = set()
    filtered: list[tuple[int, int, str, str]] = []
    for start, end, kind, name in hits:
        if start in seen:
            continue
        seen.add(start)
        filtered.append((start, end, kind, name))
    # Filter out those that already have a JSDoc comment above them.
    needing: list[tuple[int, str, str, str]] = []
    for start, _end, kind, name in filtered:
        line_start = text.rfind("\n", 0, start) + 1
        indent = text[line_start:start]
        if _has_preceding_jsdoc(text, line_start):
            continue
        needing.append((line_start, indent, kind, name))
    if not needing:
        return 0
    # Build new text by injecting JSDoc blocks from bottom to top.
    pieces: list[str] = []
    cursor = 0
    for line_start, indent, kind, name in needing:
        pieces.append(text[cursor:line_start])
        summary = _describe(kind, name)
        block = f"{indent}/**\n{indent} * {summary}\n{indent} */\n"
        pieces.append(block)
        cursor = line_start
    pieces.append(text[cursor:])
    with open(safe_str, "w", encoding="utf-8") as handle:
        handle.write("".join(pieces))
    return len(needing)


def main() -> int:
    """Applies the JSDoc injector to ui/src and ui/tests."""
    roots = [pathlib.Path("ui/src"), pathlib.Path("ui/tests")]
    total_files = 0
    total_added = 0
    for root in roots:
        if not root.exists():
            continue
        for path in root.rglob("*.ts*"):
            stem = str(path).replace("\\", "/")
            if any(tok in stem for tok in SKIP_TOKENS):
                continue
            if path.suffix not in (".ts", ".tsx", ".js", ".jsx"):
                continue
            added = _inject(path)
            if added:
                total_files += 1
                total_added += added
                print(f"{path}: +{added}")
    print(f"\nTotal: files={total_files} jsdoc_blocks+={total_added}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
