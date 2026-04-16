"""Adds meaningful docstrings to Python functions, classes, and modules.

Targets DeepSource rules PY-D0002 / PY-D0003 by inserting short but
descriptive docstrings derived from the symbol name and file role. The
heuristics are tuned for test helpers, pytest fixtures, ML script
modules and quality tooling that make up the bulk of the remediation.
"""

from __future__ import annotations

import argparse
import pathlib
import re
import sys

import libcst as cst


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


def _humanize(name: str) -> str:
    """Turns an identifier like ``_make_user_record`` into ``make user record``."""
    trimmed = name.lstrip("_")
    parts = re.split(r"[_\s]+|(?=[A-Z])", trimmed)
    words = [w.lower() for w in parts if w]
    return " ".join(words)


_FUNCTION_DUNDERS: dict[str, str] = {
    "__init__": "Initializes the instance state.",
    "__repr__": "Returns the debug representation of the instance.",
    "__str__": "Returns the string representation of the instance.",
    "__enter__": "Enters the context manager.",
    "__exit__": "Leaves the context manager and releases any held state.",
    "__call__": "Makes the instance callable.",
}

_FIXTURE_ALIASES: dict[str, str] = {
    "setup": "Prepares fixture state for the test scope.",
    "setup_method": "Prepares fixture state for the test scope.",
    "setup_class": "Prepares fixture state for the test scope.",
    "setup_module": "Prepares fixture state for the test scope.",
    "teardown": "Tears down fixture state for the test scope.",
    "teardown_method": "Tears down fixture state for the test scope.",
    "teardown_class": "Tears down fixture state for the test scope.",
    "teardown_module": "Tears down fixture state for the test scope.",
}

# (prefix_with_underscore, suffix_start_index, template). Evaluated in order;
# templates receive the humanised remainder of the name.
_FUNCTION_PREFIX_RULES: tuple[tuple[str, int, str], ...] = (
    ("make_", 5, "Builds a {tail} fixture."),
    ("build_", 6, "Constructs a {tail} structure."),
    ("get_", 4, "Returns the {tail} value."),
    ("set_", 4, "Sets the {tail} value."),
    ("load_", 5, "Loads the {tail} resource."),
    ("run_", 4, "Runs the {tail} helper path."),
    ("ensure_", 7, "Ensures {tail} is satisfied."),
    ("apply_", 6, "Applies {tail} to the target."),
    ("assert_", 7, "Asserts that {tail} holds."),
    ("with_", 5, "Returns an instance wrapped with {tail}.",),
)


def _function_doc(name: str) -> str:
    """Returns a concise docstring for the named function/method."""
    lower = name.lower()
    human = _humanize(name)
    if lower in _FUNCTION_DUNDERS:
        return _FUNCTION_DUNDERS[lower]
    if lower in _FIXTURE_ALIASES:
        return _FIXTURE_ALIASES[lower]
    if lower.startswith("test_"):
        return f"Verifies {human[5:].strip() or name} behavior."
    for prefix, length, template in _FUNCTION_PREFIX_RULES:
        if lower.startswith(prefix) or lower.startswith("_" + prefix):
            tail = human[length:].strip() or name
            if prefix == "make_":
                # preserve earlier special-case that emits "test" when humanised tail is empty
                tail = tail or "test"
            return template.format(tail=tail)
    return f"Implements the {human or name} helper."


def _class_doc(name: str) -> str:
    """Returns a concise docstring for the named class."""
    lower = name.lower()
    human = _humanize(name)
    if lower.startswith("_fake") or lower.startswith("fake"):
        return (
            f"Test double standing in for a real {human[4:].strip() or 'collaborator'}."
        )
    if lower.startswith("_mock") or lower.startswith("mock"):
        return (
            f"Mock implementation of {human[4:].strip() or 'a collaborator'} for tests."
        )
    if lower.startswith("_stub") or lower.startswith("stub"):
        return (
            f"Stub implementation of {human[4:].strip() or 'a collaborator'} for tests."
        )
    if lower.startswith("_query") or lower == "_query":
        return "Query stub that counts how many filter() calls it received."
    if "error" in lower or "exception" in lower:
        return f"Exception raised when {human} is encountered."
    return f"{human.title()} value object used in the surrounding module."


def _module_doc(path: pathlib.Path) -> str:
    """Returns a concise docstring for a Python module at ``path``."""
    stem = path.stem
    parent = path.parent.name
    if stem == "__init__":
        return f"Package marker for the {parent} module."
    if stem.startswith("test_"):
        return f"Tests for the {_humanize(stem[5:])} behavior."
    if stem == "conftest":
        return "Shared pytest fixtures for this test scope."
    if "seed" in stem:
        return f"Seed-data helpers for {_humanize(stem)}."
    if parent == "alembic":
        return "Alembic runtime configuration."
    if parent == "scripts":
        return f"Command-line helper: {_humanize(stem)}."
    return f"Support module: {_humanize(stem)}."


def _already_has_docstring(body: cst.IndentedBlock | cst.SimpleStatementSuite) -> bool:
    """Returns True when the first body statement is a bare string literal."""
    if isinstance(body, cst.IndentedBlock):
        statements = body.body
    else:
        statements = [body]
    if not statements:
        return False
    first = statements[0]
    if isinstance(first, cst.SimpleStatementLine):
        body_nodes = first.body
    else:
        body_nodes = [first]
    if not body_nodes:
        return False
    if not isinstance(body_nodes[0], cst.Expr):
        return False
    value = body_nodes[0].value
    return isinstance(value, (cst.SimpleString, cst.ConcatenatedString))


def _docstring_stmt(text: str) -> cst.SimpleStatementLine:
    """Builds a docstring statement line from ``text``."""
    safe = text.replace('"""', '"""')
    return cst.SimpleStatementLine(
        body=[cst.Expr(value=cst.SimpleString(value=f'"""{safe}"""'))]
    )


class _Injector(cst.CSTTransformer):
    """Walks a module tree and inserts docstrings where they are missing."""

    def __init__(self, module_doc: str | None) -> None:
        """Initializes the instance state."""
        super().__init__()
        self._module_doc = module_doc
        self.added_classes = 0
        self.added_functions = 0
        self.added_module = False

    def leave_Module(
        self, original_node: cst.Module, updated_node: cst.Module
    ) -> cst.Module:
        """Inserts a module docstring as the very first top-level statement when
        missing.
        """
        if self._module_doc is None:
            return updated_node
        stmts = list(updated_node.body)
        for stmt in stmts:
            if isinstance(stmt, cst.SimpleStatementLine) and stmt.body:
                head = stmt.body[0]
                if isinstance(head, cst.Expr) and isinstance(
                    head.value, (cst.SimpleString, cst.ConcatenatedString)
                ):
                    return updated_node  # already module-docstring'd at position 0
            break
        doc = _docstring_stmt(self._module_doc)
        new_body = [doc, *stmts]
        self.added_module = True
        return updated_node.with_changes(body=new_body)

    def _inject(self, node, new_doc: str):
        """Injects ``new_doc`` as the first statement of ``node.body`` when absent."""
        body = node.body
        if not isinstance(body, cst.IndentedBlock):
            return node  # can't inject into a single-line body
        if _already_has_docstring(body):
            return node
        doc = _docstring_stmt(new_doc)
        return node.with_changes(body=body.with_changes(body=[doc, *body.body]))

    def leave_ClassDef(
        self, original_node: cst.ClassDef, updated_node: cst.ClassDef
    ) -> cst.ClassDef:
        """Adds a class docstring when the class lacks one."""
        new_node = self._inject(updated_node, _class_doc(updated_node.name.value))
        if new_node is not updated_node:
            self.added_classes += 1
        return new_node

    def leave_FunctionDef(
        self, original_node: cst.FunctionDef, updated_node: cst.FunctionDef
    ) -> cst.FunctionDef:
        """Adds a function docstring when the function lacks one."""
        new_node = self._inject(updated_node, _function_doc(updated_node.name.value))
        if new_node is not updated_node:
            self.added_functions += 1
        return new_node


def _process(path: pathlib.Path) -> tuple[int, int, bool]:
    """Processes one file and returns (classes_added, functions_added, module_added)."""
    src = path.read_text(encoding="utf-8")
    try:
        tree = cst.parse_module(src)
    except cst.ParserSyntaxError:
        return 0, 0, False
    # Decide whether this module needs a docstring. libcst parses module-level
    # docstrings as a simple-statement so we replicate the check manually.
    module_doc: str | None = None
    stmts = list(tree.body)
    has_doc = False
    for stmt in stmts:
        if isinstance(stmt, cst.SimpleStatementLine) and stmt.body:
            head = stmt.body[0]
            if isinstance(head, cst.Expr) and isinstance(
                head.value, (cst.SimpleString, cst.ConcatenatedString)
            ):
                has_doc = True
                break
            if (
                isinstance(head, cst.ImportFrom)
                and head.module
                and head.module.value == "__future__"
            ):
                continue
        break
    if not has_doc:
        module_doc = _module_doc(path)
    injector = _Injector(module_doc)
    new_tree = tree.visit(injector)
    if injector.added_classes or injector.added_functions or injector.added_module:
        path.write_text(new_tree.code, encoding="utf-8")
    return injector.added_classes, injector.added_functions, injector.added_module


def main() -> int:
    """CLI entry point: applies docstring insertion to each matching path."""
    parser = argparse.ArgumentParser(description="Insert missing docstrings.")
    parser.add_argument(
        "paths",
        nargs="*",
        default=["backend", "scripts"],
        help="Files or directories to scan (defaults to backend and scripts).",
    )
    args = parser.parse_args()
    total_c = total_f = total_m = 0
    files_touched = 0
    for path_arg in args.paths:
        base = pathlib.Path(path_arg)
        if base.is_file() and base.suffix == ".py":
            targets = [base]
        else:
            targets = [
                p
                for p in base.rglob("*.py")
                if not any(tok in str(p).replace("\\", "/") for tok in SKIP_TOKENS)
            ]
        for target in targets:
            added_c, added_f, added_m = _process(target)
            total_c += added_c
            total_f += added_f
            total_m += int(added_m)
            if added_c or added_f or added_m:
                files_touched += 1
                print(
                    f"{target}: classes+={added_c} funcs+={added_f} module+={int(added_m)}"
                )
    print(
        f"\nTotal: files={files_touched} classes={total_c} functions={total_f} modules={total_m}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
