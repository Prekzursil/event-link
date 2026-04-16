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


def _missing(node) -> bool:
    """Returns True when the AST node has no literal string as its first statement."""
    body = getattr(node, "body", None)
    if not body:
        return True
    first = body[0]
    return not (isinstance(first, ast.Expr) and isinstance(first.value, (ast.Constant, ast.Str)))


def scan(root: pathlib.Path) -> tuple[dict, dict, dict]:
    """Walks root and returns missing-class, missing-func and missing-module counts per file."""
    classes: dict[str, int] = defaultdict(int)
    functions: dict[str, int] = defaultdict(int)
    modules: dict[str, int] = defaultdict(int)
    for path in root.rglob("*.py"):
        stem = str(path).replace("\\", "/")
        if any(tok in stem for tok in SKIP_TOKENS):
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8", errors="ignore"))
        except SyntaxError:
            continue
        if _missing(tree):
            modules[stem] += 1
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and _missing(node):
                classes[stem] += 1
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and _missing(node):
                functions[stem] += 1
    return classes, functions, modules


def main() -> None:
    """Entry point for CLI invocation."""
    classes, functions, modules = scan(pathlib.Path("."))
    print("== missing class docstrings (PY-D0002) ==")
    print("total:", sum(classes.values()))
    for stem, count in sorted(classes.items(), key=lambda item: -item[1])[:25]:
        print(count, stem)
    print()
    print("== missing function docstrings (PY-D0003) ==")
    print("total:", sum(functions.values()))
    for stem, count in sorted(functions.items(), key=lambda item: -item[1])[:25]:
        print(count, stem)
    print()
    print("== missing module docstrings ==")
    print("total:", sum(modules.values()))
    for stem, count in sorted(modules.items(), key=lambda item: -item[1])[:25]:
        print(count, stem)


if __name__ == "__main__":
    sys.exit(main())
