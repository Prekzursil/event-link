"""Counts Python lines longer than a threshold. Used for DeepSource FLK-E501 audit."""

from __future__ import annotations

import pathlib
import sys


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


def _is_skipped(path: pathlib.Path) -> bool:
    """Returns True when ``path`` falls under a skip-listed directory."""
    stem = str(path).replace("\\", "/")
    return any(tok in stem for tok in SKIP_TOKENS)


def _count_over(path: pathlib.Path, threshold: int) -> int:
    """Returns the number of lines in ``path`` exceeding ``threshold`` characters."""
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return 0
    return sum(1 for line in text.splitlines() if len(line) > threshold)


def _collect_totals(threshold: int) -> tuple[dict[str, int], int]:
    """Walks the tree and returns ``(per-file totals, grand total)``."""
    totals: dict[str, int] = {}
    grand = 0
    for path in pathlib.Path(".").rglob("*.py"):
        if _is_skipped(path):
            continue
        count = _count_over(path, threshold)
        if count:
            stem = str(path).replace("\\", "/")
            totals[stem] = count
            grand += count
    return totals, grand


def main(threshold: int) -> None:
    """Prints file -> long-line counts grouped by directory."""
    totals, grand = _collect_totals(threshold)
    print(f"total > {threshold}:", grand)
    for stem, count in sorted(totals.items(), key=lambda item: -item[1])[:25]:
        print(count, stem)


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 88)
