"""Reformats any single-line triple-quoted docstring longer than the limit.

Covers the tail of FLK-E501 violations left by add_docstrings.py: test
functions with very long imperative names produce one-liner docstrings
that exceed 99 characters. This script rewrites those as triple-quoted
multi-line strings indented to match the function body.
"""

from __future__ import annotations

import pathlib
import re
import sys


LINE_LIMIT = 88

SKIP_TOKENS = (
    "/.venv",
    "/node_modules",
    "/dist/",
    "/coverage/",
    "/.pytest_cache/",
    "/alembic/versions/",
)

_DOCSTRING_RE = re.compile(
    r'^(?P<indent>[ \t]+)(?P<triple>"""|\'\'\')(?P<body>.+?)(?P=triple)\s*$'
)


def _wrap(text: str, indent: str, triple: str) -> str:
    """Wraps the single-line docstring body across multiple indented lines."""
    width_first = max(LINE_LIMIT - len(indent) - len(triple), 30)
    width_rest = max(LINE_LIMIT - len(indent), 40)
    tokens = text.split()
    if not tokens:
        return f"{indent}{triple}{triple}\n"
    lines: list[str] = []
    current = tokens[0]
    limit = width_first
    for token in tokens[1:]:
        if len(current) + 1 + len(token) <= limit:
            current = f"{current} {token}"
        else:
            lines.append(current)
            current = token
            limit = width_rest
    lines.append(current)
    if len(lines) == 1:
        return f"{indent}{triple}{lines[0]}{triple}\n"
    pieces = [f"{indent}{triple}{lines[0]}"] + [f"{indent}{line}" for line in lines[1:]]
    pieces.append(f"{indent}{triple}")
    return "\n".join(pieces) + "\n"


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
    """Normalizes ``path`` and returns a string path; raises for anything outside repo
    root.
    """
    import os as _os

    absolute = _os.path.normpath(_os.path.abspath(str(path)))
    prefix = _ALLOWED_ROOT + _os.sep
    if not absolute.startswith(prefix) and absolute != _ALLOWED_ROOT:
        raise PermissionError(f"refusing to touch file outside repo root: {absolute}")
    return absolute


def _process(path: pathlib.Path) -> int:
    """Rewrites overlong docstrings in ``path``; returns lines changed."""
    safe_str = _safe_resolve_in_repo(path)
    with open(safe_str, "r", encoding="utf-8") as handle:
        src = handle.read()
    changes = 0
    out_lines: list[str] = []
    for line in src.splitlines(keepends=True):
        if len(line.rstrip("\n")) <= LINE_LIMIT:
            out_lines.append(line)
            continue
        match = _DOCSTRING_RE.match(line)
        if not match:
            out_lines.append(line)
            continue
        indent = match.group("indent")
        body = match.group("body").strip()
        triple = match.group("triple")
        wrapped = _wrap(body, indent, triple)
        out_lines.append(wrapped)
        changes += 1
    if changes:
        with open(safe_str, "w", encoding="utf-8") as handle:
            handle.write("".join(out_lines))
    return changes


def main() -> int:
    """Walks the tree and applies `_process` to each Python file."""
    total = 0
    touched = 0
    for target in ("backend", "scripts"):
        base = pathlib.Path(target)
        if not base.exists():
            continue
        for path in base.rglob("*.py"):
            stem = str(path).replace("\\", "/")
            if any(tok in stem for tok in SKIP_TOKENS):
                continue
            changes = _process(path)
            if changes:
                touched += 1
                total += changes
                print(f"{path}: wrapped {changes} docstring(s)")
    print(f"\nTotal: files={touched} wrapped_docstrings={total}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
