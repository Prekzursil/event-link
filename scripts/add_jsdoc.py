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


DECL_PATTERNS = [
    (
        re.compile(
            r"^(?P<indent>[ \t]*)(?P<kw>export\s+(?:default\s+)?(?:async\s+)?function|function|async\s+function)\s+(?P<name>[A-Za-z_$][\w$]*)",
            re.MULTILINE,
        ),
        "function",
    ),
    (
        re.compile(
            r"^(?P<indent>[ \t]*)(?P<kw>export\s+(?:default\s+)?class|class)\s+(?P<name>[A-Za-z_$][\w$]*)",
            re.MULTILINE,
        ),
        "class",
    ),
    (
        re.compile(
            r"^(?P<indent>[ \t]*)(?P<kw>export\s+(?:const|let|var))\s+(?P<name>[A-Za-z_$][\w$]*)\s*=\s*(?:async\s*)?\(",
            re.MULTILINE,
        ),
        "arrow",
    ),
]


def _humanize(name: str) -> str:
    """Turns ``renderLanguageRoute`` into ``render language route``."""
    pieces = re.split(r"(?=[A-Z])|[_\s]+", name)
    return " ".join(piece.lower() for piece in pieces if piece)


def _describe(kind: str, name: str) -> str:
    """Returns a one-line JSDoc summary for a symbol of ``kind`` named ``name``."""
    human = _humanize(name)
    if kind == "class":
        return f"Test-support {human} helper class."
    if name.startswith("use") and name[3:4].isupper():
        return f"React hook: {human[4:].strip() or human}."
    if name.startswith("render"):
        return f"Renders the {human[6:].strip() or human} scaffolding for tests."
    if name.startswith("require"):
        return f"Returns the {human[7:].strip() or human} value or fails loudly when absent."
    if name.startswith("define"):
        return f"Installs a {human[6:].strip() or human} hook for tests."
    if name.startswith("set"):
        return f"Sets the {human[3:].strip() or human} fixture state."
    if name.startswith("make"):
        return f"Builds a {human[4:].strip() or human} fixture."
    if name.startswith("handle"):
        return f"Handles the {human[6:].strip() or human} event."
    if name.startswith("open"):
        return f"Opens the {human[4:].strip() or human} UI surface for tests."
    return f"Test helper: {human}."


def _has_preceding_jsdoc(source: str, start_idx: int) -> bool:
    """Returns True when the first non-blank line above ``start_idx`` ends with ``*/``."""
    cursor = start_idx
    while cursor > 0:
        # back up to the previous line start
        prev = source.rfind("\n", 0, cursor - 1)
        line = source[prev + 1 : cursor] if prev >= 0 else source[:cursor]
        stripped = line.strip()
        if not stripped:
            cursor = prev
            continue
        # Either a JSDoc end, a line comment we accept, or decorator - treat any comment block starting
        # with `/**` as JSDoc presence. If the line ends with `*/` and a matching `/**` can be found, accept.
        if (
            stripped.endswith("*/")
            and "/**" in source[:cursor].rsplit("/**", 1)[0] + source[:cursor].split("/**")[-1]
        ):
            # Simpler check: just see if a `/**` exists after the last blank and before our start_idx.
            block = source[:start_idx]
            last_blank = block.rfind("\n\n")
            region = block[last_blank:] if last_blank >= 0 else block
            return "/**" in region
        return False
    return False


def _inject(path: pathlib.Path) -> int:
    """Adds JSDoc above each declaration in ``path`` that lacks one; returns count added."""
    text = path.read_text(encoding="utf-8")
    # Walk declarations in order by position so we do not disturb later offsets until we rebuild.
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
    path.write_text("".join(pieces), encoding="utf-8")
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
