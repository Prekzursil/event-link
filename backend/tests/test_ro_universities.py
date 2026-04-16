"""Tests for the ro universities behavior."""

from app import ro_universities


def test_normalize_university_name_handles_none_and_empty():
    """Verifies normalize university name handles none and empty behavior."""
    assert ro_universities.normalize_university_name(None) is None
    assert ro_universities.normalize_university_name("") is None
    assert ro_universities.normalize_university_name("   ") is None


def test_normalize_university_name_aliases_legacy_typos():
    """Verifies normalize university name aliases legacy typos behavior."""
    assert (
        ro_universities.normalize_university_name(' University "Transilvany" of Brasov ')
        == 'University "Transilvania" of Brasov'
    )
    assert (
        ro_universities.normalize_university_name("University Oil- Gas Ploiesti")
        == "University Oil-Gas Ploiesti"
    )
    assert (
        ro_universities.normalize_university_name("University Oil - Gas Ploiesti")
        == "University Oil-Gas Ploiesti"
    )


def test_university_catalog_includes_aliases():
    """Verifies university catalog includes aliases behavior."""
    items = ro_universities.get_university_catalog()
    transilvania = next(
        (item for item in items if item["name"] == 'University "Transilvania" of Brasov'),
        None,
    )
    assert transilvania is not None, "Transilvania university should be in the catalog"
    assert 'University "Transilvany" of Brasov' in transilvania["aliases"]
