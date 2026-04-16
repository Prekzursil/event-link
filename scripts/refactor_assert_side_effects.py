"""Rewrites test assertions that have side effects to extract the call first.

CodeQL rule ``py/side-effect-in-assert`` flags assertions like
``assert client.delete(...).status_code == 404`` because a run with
``python -O`` strips the assert and silently skips the HTTP call. The
fix is to capture the call result into a local variable, then assert on
the pure comparison.

This is a libcst-based transformer so formatting and comments survive.
"""

from __future__ import annotations

import pathlib
import sys
from typing import cast

import libcst as cst


SKIP_TOKENS = ("/.venv", "/node_modules", "/alembic/versions/")


def _looks_like_http_call(node: cst.BaseExpression) -> bool:
    """Returns True for ``x.client.method(...).status_code`` style expressions."""
    if not isinstance(node, cst.Attribute) or node.attr.value != "status_code":
        return False
    return isinstance(node.value, cst.Call)


def _is_convertible_assert(
    line: cst.SimpleStatementLine,
) -> cst.Assert | None:
    """Returns the inner ``Assert`` node when this line is a rewritable candidate."""
    if len(line.body) != 1 or not isinstance(line.body[0], cst.Assert):
        return None
    assert_node: cst.Assert = line.body[0]
    test = assert_node.test
    if not isinstance(test, cst.Comparison):
        return None
    if not _looks_like_http_call(test.left) or len(test.comparisons) != 1:
        return None
    target = test.comparisons[0]
    if not isinstance(target.operator, cst.Equal):
        return None
    if not isinstance(target.comparator, (cst.Integer, cst.Float, cst.Name)):
        return None
    return assert_node


def _rewrite_side_effect_assert(
    line: cst.SimpleStatementLine,
    assert_node: cst.Assert,
) -> cst.FlattenSentinel[cst.BaseStatement]:
    """Splits ``assert call.status_code == N`` into ``_response = call`` + assert.

    Callers must pass nodes that already satisfy ``_is_convertible_assert``,
    so the type narrowing below is a static-check helper rather than a runtime
    check (which would violate bandit B101 when compiled with -O).
    """
    test = cast(cst.Comparison, assert_node.test)
    left = cast(cst.Attribute, test.left)
    assign = cst.Assign(
        targets=[cst.AssignTarget(target=cst.Name("_response"))],
        value=left.value,
    )
    new_left = cst.Attribute(value=cst.Name("_response"), attr=left.attr)
    new_assert = assert_node.with_changes(test=test.with_changes(left=new_left))
    assign_line = cst.SimpleStatementLine(
        body=[assign], leading_lines=line.leading_lines
    )
    assert_line = cst.SimpleStatementLine(body=[new_assert])
    return cst.FlattenSentinel([assign_line, assert_line])


class _AssertRewriter(cst.CSTTransformer):
    """Extracts side-effecting ``.status_code == N`` asserts into ``_response = …``."""

    def __init__(self) -> None:
        """Initializes the instance state."""
        super().__init__()
        self.changes = 0

    def stats(self) -> int:
        """Returns the number of successful rewrites so far."""
        return self.changes

    def leave_SimpleStatementLine(  # pylint: disable=invalid-name
        self,
        _original_node: cst.SimpleStatementLine,
        updated_node: cst.SimpleStatementLine,
    ) -> (
        cst.BaseStatement | cst.FlattenSentinel[cst.BaseStatement] | cst.RemovalSentinel
    ):
        """Replaces a single-statement ``assert call.status_code == N`` node."""
        assert_node = _is_convertible_assert(updated_node)
        if assert_node is None:
            return updated_node
        self.changes += 1
        return _rewrite_side_effect_assert(updated_node, assert_node)


def _process(path: pathlib.Path) -> int:
    """Applies the transformer to ``path`` and returns the count of rewrites."""
    src = path.read_text(encoding="utf-8")
    module = cst.parse_module(src)
    transformer = _AssertRewriter()
    updated = module.visit(transformer)
    if transformer.changes:
        path.write_text(updated.code, encoding="utf-8")
    return transformer.changes


def main() -> int:
    """Walks backend/tests and prints per-file counts."""
    total = 0
    files = 0
    root = pathlib.Path("backend/tests")
    if not root.exists():
        print("backend/tests not present - aborting")
        return 1
    for path in root.rglob("*.py"):
        stem = str(path).replace("\\", "/")
        if any(tok in stem for tok in SKIP_TOKENS):
            continue
        replacements = _process(path)
        if replacements:
            files += 1
            total += replacements
            print(f"{path}: {replacements} replacements")
    print(f"\nTotal: files={files} replacements={total}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
