import pytest

from mat_ret.search import contains_all_elements, format_chemsys, parse_search_text


def test_parse_formula_query_returns_reduced_formula() -> None:
    query = parse_search_text("Fe4O6")
    assert query.mode == "formula"
    assert query.formula == "Fe2O3"
    assert query.elements == []
    assert query.display_text == "Fe2O3"


def test_parse_element_query_with_hyphen_and_comma() -> None:
    query_hyphen = parse_search_text("Li-Fe-O")
    assert query_hyphen.mode == "elements_all"
    assert query_hyphen.formula is None
    assert query_hyphen.elements == ["Li", "Fe", "O"]
    assert query_hyphen.display_text == "Li-Fe-O"

    query_comma = parse_search_text("Fe, O")
    assert query_comma.mode == "elements_all"
    assert query_comma.elements == ["Fe", "O"]
    assert query_comma.display_text == "Fe-O"


def test_parse_invalid_element_query_raises_clear_error() -> None:
    with pytest.raises(ValueError, match="Invalid element system"):
        parse_search_text("Xx-O")


def test_format_chemsys_deduplicates_preserving_order() -> None:
    assert format_chemsys(["Fe", "O", "Fe"]) == "Fe-O"


def test_contains_all_elements_formula_behavior() -> None:
    assert contains_all_elements("LiFePO4", ["Li", "Fe", "P", "O"])
    assert not contains_all_elements("LiFePO4", ["Li", "Fe", "Si"])
