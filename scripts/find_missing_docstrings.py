"""Scans Python source for functions/classes/modules lacking docstrings.

Matches DeepSource PY-D0002 (classes) and PY-D0003 (functions/modules).
Prints a JSON-like summary and per-file counts so remediation can be
planned without relying on the external dashboard.
"""

from __future__ import annotations

import ast
import pathlib
import sys
from collections import defaultdict


SKIP_TOKENS = (
    "/.venv",
    "/.venv-quality-zero",
    "/node_modules",
    "/dist/",
    "/coverage/",
    "/ui/",
    "/.pytest_cache/",
    "/alembic/versions/",
)


def _has_str_docstring(node) -> bool:
    """Returns True if the first statement of ``node`` is a string literal."""
    body = getattr(node, "body", None)
    if not body:
        return False
    first = body[0]
    if not isinstance(first, ast.Expr):
        return False
    return isinstance(first.value, ast.Constant) and isinstance(first.value.value, str)


def _missing(node) -> bool:
    """Returns True when ``node`` has no docstring as its first statement."""
    return not _has_str_docstring(node)


def _is_skipped(path: pathlib.Path) -> bool:
    """Returns True for any path under a skip-listed directory."""
    stem = str(path).replace("\\", "/")
    return any(tok in stem for tok in SKIP_TOKENS)


def _parse_tree(path: pathlib.Path) -> ast.AST | None:
    """Parses ``path`` and returns its AST, or ``None`` on SyntaxError."""
    try:
        return ast.parse(path.read_text(encoding="utf-8", errors="ignore"))
    except SyntaxError:
        return None


def _tally_node_types(
    tree: ast.AST,
    stem: str,
    classes: dict[str, int],
    functions: dict[str, int],
) -> None:
    """Walks ``tree`` and increments the class/function counters for missing doc."""
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and _missing(node):
            classes[stem] += 1
        elif isinstance(
            node, (ast.FunctionDef, ast.AsyncFunctionDef)
        ) and _missing(node):
            functions[stem] += 1


def scan(root: pathlib.Path) -> tuple[dict, dict, dict]:
    """Walks root and returns missing-class, missing-func, missing-module counts."""
    classes: dict[str, int] = defaultdict(int)
    functions: dict[str, int] = defaultdict(int)
    modules: dict[str, int] = defaultdict(int)
    for path in root.rglob("*.py"):
        if _is_skipped(path):
            continue
        tree = _parse_tree(path)
        if tree is None:
            continue
        stem = str(path).replace("\\", "/")
        if _missing(tree):
            modules[stem] += 1
        _tally_node_types(tree, stem, classes, functions)
    return classes, functions, modules


_TOTAL_HEADER = "total:"


def _print_section(header: str, counts: dict[str, int]) -> None:
    """Prints ``header`` followed by the top 25 file counts in descending order."""
    print(header)
    print(_TOTAL_HEADER, sum(counts.values()))
    for stem, count in sorted(counts.items(), key=lambda item: -item[1])[:25]:
        print(count, stem)
    print()


def main() -> int:
    """Entry point for CLI invocation; returns the POSIX exit code."""
    classes, functions, modules = scan(pathlib.Path("."))
    _print_section("== missing class docstrings (PY-D0002) ==", classes)
    _print_section("== missing function docstrings (PY-D0003) ==", functions)
    _print_section("== missing module docstrings ==", modules)
    return 0


if __name__ == "__main__":
    sys.exit(main())
