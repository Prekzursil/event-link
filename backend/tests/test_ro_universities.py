from app import ro_universities


def test_normalize_university_name_handles_none_and_empty():
    assert ro_universities.normalize_university_name(None) is None
    assert ro_universities.normalize_university_name("") is None
    assert ro_universities.normalize_university_name("   ") is None


def test_normalize_university_name_aliases_legacy_typos():
    assert (
        ro_universities.normalize_university_name(' University "Transilvany" of Brasov ')
        == 'University "Transilvania" of Brasov'
    )
    assert ro_universities.normalize_university_name("University Oil- Gas Ploiesti") == "University Oil-Gas Ploiesti"
    assert ro_universities.normalize_university_name("University Oil - Gas Ploiesti") == "University Oil-Gas Ploiesti"


def test_university_catalog_includes_aliases():
    items = ro_universities.get_university_catalog()
    transilvania = next(item for item in items if item["name"] == 'University "Transilvania" of Brasov')
    assert 'University "Transilvany" of Brasov' in transilvania["aliases"]
