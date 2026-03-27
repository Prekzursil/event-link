#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from _security_import import load_security_helpers

_security_helpers = load_security_helpers(__file__)
resolve_workspace_relative_path = _security_helpers.resolve_workspace_relative_path


@dataclass
class MetricStats:
    covered: int
    total: int

    @property
    def percent(self) -> float:
        if self.total <= 0:
            return 100.0
        return (self.covered / self.total) * 100.0


@dataclass
class CoverageStats:
    name: str
    path: str
    lines: MetricStats
    branches: MetricStats


_PAIR_RE = re.compile(r"^(?P<name>[^=]+)=(?P<path>.+)$")
_XML_LINES_VALID_RE = re.compile(r'lines-valid="(\d+(?:\.\d+)?)"')
_XML_LINES_COVERED_RE = re.compile(r'lines-covered="(\d+(?:\.\d+)?)"')
_XML_BRANCHES_VALID_RE = re.compile(r'branches-valid="(\d+(?:\.\d+)?)"')
_XML_BRANCHES_COVERED_RE = re.compile(r'branches-covered="(\d+(?:\.\d+)?)"')
_XML_LINE_HITS_RE = re.compile(r'<line\b[^>]*\bhits="(\d+(?:\.\d+)?)"')
_XML_CONDITION_COVERAGE_RE = re.compile(r'condition-coverage="(\d+)% \((\d+)/(\d+)\)"')


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Assert 100% coverage for all declared components.")
    parser.add_argument("--xml", action="append", default=[], help="Coverage XML input: name=path")
    parser.add_argument("--lcov", action="append", default=[], help="LCOV input: name=path")
    parser.add_argument("--out-json", default="coverage-100/coverage.json", help="Output JSON path")
    parser.add_argument("--out-md", default="coverage-100/coverage.md", help="Output markdown path")
    return parser.parse_args()


def parse_named_path(value: str) -> tuple[str, Path]:
    match = _PAIR_RE.match(value.strip())
    if not match:
        raise ValueError(f"Invalid input '{value}'. Expected format: name=path")

    name = match.group("name").strip()
    raw_path = match.group("path").strip()
    if not name:
        raise ValueError(f"Invalid input '{value}'. Name cannot be empty")

    validated = resolve_workspace_relative_path(
        raw_path,
        fallback=raw_path,
        must_exist=True,
        must_be_file=True,
    )
    return name, validated


def parse_coverage_xml(name: str, path: Path) -> CoverageStats:
    text = path.read_text(encoding="utf-8")
    lines_valid_match = _XML_LINES_VALID_RE.search(text)
    lines_covered_match = _XML_LINES_COVERED_RE.search(text)
    branches_valid_match = _XML_BRANCHES_VALID_RE.search(text)
    branches_covered_match = _XML_BRANCHES_COVERED_RE.search(text)

    if lines_valid_match and lines_covered_match and branches_valid_match and branches_covered_match:
        return CoverageStats(
            name=name,
            path=str(path),
            lines=MetricStats(
                covered=int(float(lines_covered_match.group(1))),
                total=int(float(lines_valid_match.group(1))),
            ),
            branches=MetricStats(
                covered=int(float(branches_covered_match.group(1))),
                total=int(float(branches_valid_match.group(1))),
            ),
        )

    line_total = 0
    line_covered = 0
    branch_total = 0
    branch_covered = 0
    for hits_raw in _XML_LINE_HITS_RE.findall(text):
        line_total += 1
        try:
            if int(float(hits_raw)) > 0:
                line_covered += 1
        except ValueError:
            continue

    for _percent_raw, covered_raw, total_raw in _XML_CONDITION_COVERAGE_RE.findall(text):
        branch_covered += int(covered_raw)
        branch_total += int(total_raw)

    return CoverageStats(
        name=name,
        path=str(path),
        lines=MetricStats(covered=line_covered, total=line_total),
        branches=MetricStats(covered=branch_covered, total=branch_total),
    )


def parse_lcov(name: str, path: Path) -> CoverageStats:
    line_total = 0
    line_covered = 0
    branch_total = 0
    branch_covered = 0

    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if line.startswith("LF:"):
            line_total += int(line.split(":", 1)[1])
        elif line.startswith("LH:"):
            line_covered += int(line.split(":", 1)[1])
        elif line.startswith("BRF:"):
            branch_total += int(line.split(":", 1)[1])
        elif line.startswith("BRH:"):
            branch_covered += int(line.split(":", 1)[1])

    return CoverageStats(
        name=name,
        path=str(path),
        lines=MetricStats(covered=line_covered, total=line_total),
        branches=MetricStats(covered=branch_covered, total=branch_total),
    )


def evaluate(stats: list[CoverageStats]) -> tuple[str, list[str]]:
    findings: list[str] = []
    for item in stats:
        if item.lines.percent < 100.0:
            findings.append(
                f"{item.name} line coverage below 100%: {item.lines.percent:.2f}% ({item.lines.covered}/{item.lines.total})"
            )
        if item.branches.percent < 100.0:
            findings.append(
                f"{item.name} branch coverage below 100%: {item.branches.percent:.2f}% ({item.branches.covered}/{item.branches.total})"
            )

    combined_lines_total = sum(item.lines.total for item in stats)
    combined_lines_covered = sum(item.lines.covered for item in stats)
    combined_branches_total = sum(item.branches.total for item in stats)
    combined_branches_covered = sum(item.branches.covered for item in stats)
    combined_lines = 100.0 if combined_lines_total <= 0 else (combined_lines_covered / combined_lines_total) * 100.0
    combined_branches = (
        100.0 if combined_branches_total <= 0 else (combined_branches_covered / combined_branches_total) * 100.0
    )

    if combined_lines < 100.0:
        findings.append(
            f"combined line coverage below 100%: {combined_lines:.2f}% ({combined_lines_covered}/{combined_lines_total})"
        )
    if combined_branches < 100.0:
        findings.append(
            f"combined branch coverage below 100%: {combined_branches:.2f}% ({combined_branches_covered}/{combined_branches_total})"
        )

    status = "pass" if not findings else "fail"
    return status, findings


def _render_md(payload: dict) -> str:
    lines = [
        "# Coverage 100 Gate",
        "",
        f"- Status: `{payload['status']}`",
        f"- Timestamp (UTC): `{payload['timestamp_utc']}`",
        "",
        "## Components",
    ]

    for item in payload.get("components", []):
        lines.append(
            f"- `{item['name']}`: lines `{item['lines']['percent']:.2f}%` ({item['lines']['covered']}/{item['lines']['total']}), "
            f"branches `{item['branches']['percent']:.2f}%` ({item['branches']['covered']}/{item['branches']['total']}) "
            f"from `{item['path']}`"
        )

    if not payload.get("components"):
        lines.append("- None")

    lines.extend(["", "## Findings"])
    findings = payload.get("findings") or []
    if findings:
        lines.extend(f"- {finding}" for finding in findings)
    else:
        lines.append("- None")

    return "\n".join(lines) + "\n"


def _safe_output_path(raw: str, fallback: str) -> Path:
    return resolve_workspace_relative_path(raw, fallback=fallback, must_exist=False, must_be_file=False)


def main() -> int:
    args = _parse_args()

    stats: list[CoverageStats] = []
    for item in args.xml:
        name, path = parse_named_path(item)
        stats.append(parse_coverage_xml(name, path))
    for item in args.lcov:
        name, path = parse_named_path(item)
        stats.append(parse_lcov(name, path))

    if not stats:
        raise SystemExit("No coverage files were provided; pass --xml and/or --lcov inputs.")

    status, findings = evaluate(stats)
    payload = {
        "status": status,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "components": [
            {
                "name": item.name,
                "path": item.path,
                "lines": {
                    "covered": item.lines.covered,
                    "total": item.lines.total,
                    "percent": item.lines.percent,
                },
                "branches": {
                    "covered": item.branches.covered,
                    "total": item.branches.total,
                    "percent": item.branches.percent,
                },
            }
            for item in stats
        ],
        "findings": findings,
    }

    try:
        out_json = _safe_output_path(args.out_json, "coverage-100/coverage.json")
        out_md = _safe_output_path(args.out_md, "coverage-100/coverage.md")
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    out_md.write_text(_render_md(payload), encoding="utf-8")
    print(out_md.read_text(encoding="utf-8"), end="")

    return 0 if status == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
