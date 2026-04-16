#!/usr/bin/env python3
"""Assert 100 percent line and branch coverage for declared components."""

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
    """Covered and total counts for a single coverage metric."""

    covered: int
    total: int

    @property
    def percent(self) -> float:
        """Return the covered percentage for the metric."""
        if self.total <= 0:
            return 100.0
        return (self.covered / self.total) * 100.0


@dataclass
class CoverageStats:
    """Coverage statistics for a named report input."""

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
    """Parse CLI arguments for the coverage gate."""
    parser = argparse.ArgumentParser(
        description="Assert 100% coverage for all declared components."
    )
    parser.add_argument(
        "--xml",
        action="append",
        default=[],
        help="Coverage XML input: name=path",
    )
    parser.add_argument(
        "--lcov",
        action="append",
        default=[],
        help="LCOV input: name=path",
    )
    parser.add_argument(
        "--out-json",
        default="coverage-100/coverage.json",
        help="Output JSON path",
    )
    parser.add_argument(
        "--out-md",
        default="coverage-100/coverage.md",
        help="Output markdown path",
    )
    return parser.parse_args()


def parse_named_path(value: str) -> tuple[str, Path]:
    """Parse a ``name=path`` argument and validate the referenced file."""
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


def _metric_stats_from_xml_attributes(
    *,
    lines_valid_match: re.Match[str] | None,
    lines_covered_match: re.Match[str] | None,
    branches_valid_match: re.Match[str] | None,
    branches_covered_match: re.Match[str] | None,
) -> CoverageStats | None:
    """Build coverage stats directly from XML summary attributes."""
    if not (
        lines_valid_match
        and lines_covered_match
        and branches_valid_match
        and branches_covered_match
    ):
        return None
    return CoverageStats(
        name="",
        path="",
        lines=MetricStats(
            covered=int(float(lines_covered_match.group(1))),
            total=int(float(lines_valid_match.group(1))),
        ),
        branches=MetricStats(
            covered=int(float(branches_covered_match.group(1))),
            total=int(float(branches_valid_match.group(1))),
        ),
    )


def _metric_stats_from_xml_lines(text: str) -> tuple[MetricStats, MetricStats]:
    """Infer coverage stats by scanning XML line entries."""
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

    for _percent_raw, covered_raw, total_raw in _XML_CONDITION_COVERAGE_RE.findall(
        text
    ):
        branch_covered += int(covered_raw)
        branch_total += int(total_raw)

    return (
        MetricStats(covered=line_covered, total=line_total),
        MetricStats(covered=branch_covered, total=branch_total),
    )


def parse_coverage_xml(name: str, path: Path) -> CoverageStats:
    """Load component coverage statistics from a Cobertura XML report."""
    text = path.read_text(encoding="utf-8")
    lines_valid_match = _XML_LINES_VALID_RE.search(text)
    lines_covered_match = _XML_LINES_COVERED_RE.search(text)
    branches_valid_match = _XML_BRANCHES_VALID_RE.search(text)
    branches_covered_match = _XML_BRANCHES_COVERED_RE.search(text)

    direct_stats = _metric_stats_from_xml_attributes(
        lines_valid_match=lines_valid_match,
        lines_covered_match=lines_covered_match,
        branches_valid_match=branches_valid_match,
        branches_covered_match=branches_covered_match,
    )
    if direct_stats is not None:
        return CoverageStats(
            name=name,
            path=str(path),
            lines=direct_stats.lines,
            branches=direct_stats.branches,
        )

    lines, branches = _metric_stats_from_xml_lines(text)

    return CoverageStats(
        name=name,
        path=str(path),
        lines=lines,
        branches=branches,
    )


def parse_lcov(name: str, path: Path) -> CoverageStats:
    """Load component coverage statistics from an LCOV report."""
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


def _metric_finding(
    component_name: str,
    metric_name: str,
    stats: MetricStats,
) -> str | None:
    """Return a human-readable finding when a metric is below 100 percent."""
    if stats.percent >= 100.0:
        return None
    return (
        f"{component_name} {metric_name} coverage below 100%: "
        f"{stats.percent:.2f}% ({stats.covered}/{stats.total})"
    )


def _combined_metric(stats: list[CoverageStats], metric_name: str) -> MetricStats:
    """Combine one metric across all component coverage reports."""
    metrics = [getattr(item, metric_name) for item in stats]
    return MetricStats(
        covered=sum(item.covered for item in metrics),
        total=sum(item.total for item in metrics),
    )


def _metric_label(metric_name: str) -> str:
    """Map internal metric keys to report-friendly labels."""
    return "line" if metric_name == "lines" else "branch"


def evaluate(stats: list[CoverageStats]) -> tuple[str, list[str]]:
    """Evaluate component and combined coverage against the 100 percent gate."""
    findings: list[str] = []
    for item in stats:
        for metric_name in ("lines", "branches"):
            finding = _metric_finding(
                item.name,
                _metric_label(metric_name),
                getattr(item, metric_name),
            )
            if finding is not None:
                findings.append(finding)

    for metric_name in ("lines", "branches"):
        combined = _combined_metric(stats, metric_name)
        finding = _metric_finding("combined", _metric_label(metric_name), combined)
        if finding is not None:
            findings.append(finding)

    status = "pass" if not findings else "fail"
    return status, findings


def _render_md(payload: dict) -> str:
    """Render the coverage gate result as markdown."""
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
            f"- `{item['name']}`: lines "
            f"`{item['lines']['percent']:.2f}%` "
            f"({item['lines']['covered']}/{item['lines']['total']}), "
            f"branches `{item['branches']['percent']:.2f}%` "
            f"({item['branches']['covered']}/{item['branches']['total']}) "
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
    """Resolve an output path while allowing new files to be created."""
    return resolve_workspace_relative_path(
        raw,
        fallback=fallback,
        must_exist=False,
        must_be_file=False,
    )


def _load_stats(args: argparse.Namespace) -> list[CoverageStats]:
    """Load all declared coverage inputs into normalized stats objects."""
    stats: list[CoverageStats] = []
    for item in args.xml:
        name, path = parse_named_path(item)
        stats.append(parse_coverage_xml(name, path))
    for item in args.lcov:
        name, path = parse_named_path(item)
        stats.append(parse_lcov(name, path))
    return stats


def _component_payload(item: CoverageStats) -> dict[str, object]:
    """Serialize one component's coverage stats for output artifacts."""
    return {
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


def _coverage_payload(
    *,
    status: str,
    findings: list[str],
    stats: list[CoverageStats],
) -> dict[str, object]:
    """Build the structured payload written by the coverage gate."""
    return {
        "status": status,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "components": [_component_payload(item) for item in stats],
        "findings": findings,
    }


def _write_outputs(*, out_json: Path, out_md: Path, payload: dict[str, object]) -> None:
    """Write JSON and markdown coverage reports to disk."""
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    out_md.write_text(_render_md(payload), encoding="utf-8")


def main() -> int:
    """Run the coverage gate CLI and write report artifacts."""
    args = _parse_args()
    stats = _load_stats(args)

    if not stats:
        raise SystemExit(
            "No coverage files were provided; pass --xml and/or --lcov inputs."
        )

    status, findings = evaluate(stats)
    payload = _coverage_payload(status=status, findings=findings, stats=stats)

    try:
        out_json = _safe_output_path(args.out_json, "coverage-100/coverage.json")
        out_md = _safe_output_path(args.out_md, "coverage-100/coverage.md")
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    _write_outputs(out_json=out_json, out_md=out_md, payload=payload)
    print(out_md.read_text(encoding="utf-8"), end="")

    return 0 if status == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
