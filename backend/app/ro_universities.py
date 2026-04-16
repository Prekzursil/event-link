"""Romanian university catalog helpers."""

from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path
from typing import TypedDict


class UniversityCatalogItem(TypedDict, total=False):
    """Serialized university catalog entry."""

    name: str
    city: str | None
    faculties: list[str]
    aliases: list[str]


def _normalize_university_key(value: str) -> str:
    """Normalize a university name into a stable lookup key."""
    value = value.strip().casefold()
    value = (
        value.replace("“", '"')
        .replace("”", '"')
        .replace("’", "'")
        .replace("–", "-")
        .replace("—", "-")
    )
    value = unicodedata.normalize("NFKD", value)
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    value = re.sub(r"[^a-z0-9]+", " ", value)
    return " ".join(value.split())


def _catalog_path() -> Path:
    """Return the path to the bundled university catalog JSON file."""
    return Path(__file__).with_name("ro_universities_catalog.json")


def _load_catalog() -> list[UniversityCatalogItem]:
    """Load and normalize the bundled university catalog."""
    raw_items = json.loads(_catalog_path().read_text(encoding="utf-8"))
    items: list[UniversityCatalogItem] = []
    for raw in raw_items:
        items.append(
            {
                "name": str(raw["name"]),
                "city": raw.get("city"),
                "faculties": [str(item) for item in raw.get("faculties", [])],
                "aliases": [str(item) for item in raw.get("aliases", [])],
            }
        )
    return items


_UNIVERSITY_CATALOG = _load_catalog()
_UNIVERSITY_KEY_TO_CANONICAL: dict[str, str] = {}
for item in _UNIVERSITY_CATALOG:
    canonical = item["name"]
    _UNIVERSITY_KEY_TO_CANONICAL[_normalize_university_key(canonical)] = canonical
    for alias in item.get("aliases", []):
        _UNIVERSITY_KEY_TO_CANONICAL[_normalize_university_key(alias)] = canonical


def normalize_university_name(name: str | None) -> str | None:
    """Resolve an input name to the catalog's canonical university name."""
    if name is None:
        return None
    trimmed = name.strip()
    if not trimmed:
        return None
    canonical_name = _UNIVERSITY_KEY_TO_CANONICAL.get(_normalize_university_key(trimmed))
    return canonical_name or trimmed


def get_university_catalog() -> list[UniversityCatalogItem]:
    """Return a defensive copy of the university catalog."""
    return [
        {
            "name": item["name"],
            "city": item.get("city"),
            "faculties": list(item.get("faculties", [])),
            "aliases": list(item.get("aliases", [])),
        }
        for item in _UNIVERSITY_CATALOG
    ]
