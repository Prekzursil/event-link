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

import libcst as cst


SKIP_TOKENS = ("/.venv", "/node_modules", "/alembic/versions/")


def _looks_like_http_call(node: cst.BaseExpression) -> bool:
    """Returns True for ``x.client.method(...).status_code`` style expressions."""
    if not isinstance(node, cst.Attribute) or node.attr.value != "status_code":
        return False
    current = node.value
    return isinstance(current, cst.Call)


class _AssertRewriter(cst.CSTTransformer):
    """Extracts side-effecting ``.status_code == N`` asserts into ``_response = …``."""

    def __init__(self) -> None:
        """Initializes the instance state."""
        super().__init__()
        self.changes = 0

    def leave_SimpleStatementLine(
        self,
        original_node: cst.SimpleStatementLine,
        updated_node: cst.SimpleStatementLine,
    ) -> (
        cst.BaseStatement | cst.FlattenSentinel[cst.BaseStatement] | cst.RemovalSentinel
    ):
        """Replaces a single-statement ``assert call.status_code == N`` node."""
        if len(updated_node.body) != 1 or not isinstance(
            updated_node.body[0], cst.Assert
        ):
            return updated_node
        assert_node: cst.Assert = updated_node.body[0]
        test = assert_node.test
        if not isinstance(test, cst.Comparison):
            return updated_node
        left = test.left
        if not _looks_like_http_call(left):
            return updated_node
        if len(test.comparisons) != 1:
            return updated_node
        target = test.comparisons[0]
        comparator = target.comparator
        if not isinstance(target.operator, cst.Equal):
            return updated_node
        # Reject if the comparator has any side effects; comparing to a call
        # (e.g., status_code == response.status_code) would itself be a bug.
        if not isinstance(comparator, (cst.Integer, cst.Float, cst.Name)):
            return updated_node
        # Build `_response = <left.value>` where <left.value> is the call.
        assign_target = cst.Name("_response")
        assign = cst.Assign(
            targets=[cst.AssignTarget(target=assign_target)],
            value=left.value,
        )
        new_left = cst.Attribute(value=cst.Name("_response"), attr=left.attr)
        new_comparison = test.with_changes(left=new_left)
        new_assert = assert_node.with_changes(test=new_comparison)
        self.changes += 1
        assign_line = cst.SimpleStatementLine(
            body=[assign], leading_lines=updated_node.leading_lines
        )
        assert_line = cst.SimpleStatementLine(body=[new_assert])
        return cst.FlattenSentinel([assign_line, assert_line])


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
        n = _process(path)
        if n:
            files += 1
            total += n
            print(f"{path}: {n} replacements")
    print(f"\nTotal: files={files} replacements={total}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
