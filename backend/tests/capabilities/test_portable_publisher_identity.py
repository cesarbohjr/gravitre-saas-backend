from app.capabilities.provenance import publisher_declaration_candidates


def test_string_publisher_declaration_candidates() -> None:
    assert publisher_declaration_candidates({"publisher": "Acme Labs"}) == {"acme labs"}


def test_object_publisher_declaration_candidates_include_slug_and_name() -> None:
    assert publisher_declaration_candidates(
        {"publisher": {"slug": "acme", "name": "Acme Labs"}}
    ) == {"acme", "acme labs"}


def test_author_is_fallback_when_publisher_missing() -> None:
    assert publisher_declaration_candidates({"author": "Acme Labs"}) == {"acme labs"}


def test_publisher_precedence_ignores_author_when_publisher_declared() -> None:
    assert publisher_declaration_candidates(
        {"publisher": "Acme", "author": "Other Co"}
    ) == {"acme"}
