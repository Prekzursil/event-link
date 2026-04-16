"""Counts Python lines longer than a threshold. Used for DeepSource FLK-E501 audit."""

from __future__ import annotations

import pathlib
import sys


def main(threshold: int) -> None:
    """Prints file -> long-line counts grouped by directory."""
    totals: dict[str, int] = {}
    grand = 0
    skip_tokens = (
        "/.venv",
        "/.venv-quality-zero",
        "/node_modules",
        "/dist/",
        "/coverage/",
        "/ui/",
        "/.pytest_cache/",
        "/alembic/versions/",
    )
    for path in pathlib.Path(".").rglob("*.py"):
        stem = str(path).replace("\\", "/")
        if any(tok in stem for tok in skip_tokens):
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        count = sum(1 for line in text.splitlines() if len(line) > threshold)
        if count:
            totals[stem] = count
            grand += count
    print(f"total > {threshold}:", grand)
    for stem, count in sorted(totals.items(), key=lambda item: -item[1])[:25]:
        print(count, stem)


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 88)
