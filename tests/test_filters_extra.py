"""Tests for the expanded SearchFilters and apply_post_filters behaviour."""

from dataclasses import fields

import pytest

from mat_ret.search import SearchFilters, apply_post_filters, _FILTER_ATTRS
from mat_ret.property_mapping import STANDARD_PROPERTIES


SP = STANDARD_PROPERTIES


def _apply(materials, **filter_kwargs):
    return apply_post_filters(materials, SearchFilters(**filter_kwargs), SP)


# ---------------------------------------------------------------------------
# Introspection / DRY
# ---------------------------------------------------------------------------

def test_filter_attrs_covers_every_field():
    """_FILTER_ATTRS plus exclude_theoretical must equal the dataclass fields."""
    field_names = {f.name for f in fields(SearchFilters)}
    assert set(_FILTER_ATTRS) | {"exclude_theoretical"} == field_names


def test_empty_element_lists_are_inactive():
    f = SearchFilters(include_elements=[], exclude_elements=[])
    assert f.include_elements is None
    assert f.exclude_elements is None
    assert not f.has_any_filter()
    assert f.active_filter_count() == 0


def test_active_filter_count_includes_new_fields():
    f = SearchFilters(include_elements=["Fe"], exclude_elements=["Pb"])
    assert f.active_filter_count() == 2
    assert f.has_any_filter()


# ---------------------------------------------------------------------------
# num_sites resolution via standardized key
# ---------------------------------------------------------------------------

def test_num_sites_uses_standardized_key():
    mats = [{"formula": "Fe2O3", "num_sites": 10}]
    assert len(_apply(mats, num_sites_min=5)) == 1
    assert len(_apply(mats, num_sites_min=12)) == 0
    assert len(_apply(mats, num_sites_max=8)) == 0


def test_num_sites_missing_is_excluded():
    mats = [{"formula": "Fe2O3"}]
    assert len(_apply(mats, num_sites_min=1)) == 0


# ---------------------------------------------------------------------------
# total_magnetization resolution
# ---------------------------------------------------------------------------

def test_total_magnetization_from_magnetic_moment():
    mats = [{"formula": "Fe", "magnetic_moment": 2.2}]
    assert len(_apply(mats, total_magnetization_min=2.0)) == 1
    assert len(_apply(mats, total_magnetization_min=3.0)) == 0


def test_total_magnetization_fallback_key():
    mats = [{"formula": "Fe", "total_magnetization": 4.0}]
    assert len(_apply(mats, total_magnetization_max=5.0)) == 1
    assert len(_apply(mats, total_magnetization_max=3.0)) == 0


# ---------------------------------------------------------------------------
# is_metal epsilon handling
# ---------------------------------------------------------------------------

def test_is_metal_treats_near_zero_gap_as_metal():
    mats = [{"formula": "Fe", "band_gap": 1e-7}]
    assert len(_apply(mats, is_metal=True)) == 1
    assert len(_apply(mats, is_metal=False)) == 0


def test_is_metal_nonmetal_for_real_gap():
    mats = [{"formula": "Si", "band_gap": 1.1}]
    assert len(_apply(mats, is_metal=False)) == 1
    assert len(_apply(mats, is_metal=True)) == 0


# ---------------------------------------------------------------------------
# exclude_theoretical
# ---------------------------------------------------------------------------

def test_exclude_theoretical_drops_flagged_records():
    mats = [
        {"formula": "Fe2O3", "is_theoretical": True},
        {"formula": "SiO2", "functional": "theoretical GGA"},
        {"formula": "MgO", "functional": "GGA PBE"},
    ]
    kept = _apply(mats, exclude_theoretical=True)
    assert [m["formula"] for m in kept] == ["MgO"]


# ---------------------------------------------------------------------------
# include / exclude elements
# ---------------------------------------------------------------------------

def test_include_elements_via_elements_key():
    mats = [
        {"formula": "Fe2O3", "elements": ["Fe", "O"]},
        {"formula": "SiO2", "elements": ["Si", "O"]},
    ]
    kept = _apply(mats, include_elements=["Fe"])
    assert [m["formula"] for m in kept] == ["Fe2O3"]


def test_include_elements_requires_all():
    mats = [{"formula": "Fe2O3", "elements": ["Fe", "O"]}]
    assert len(_apply(mats, include_elements=["Fe", "O"])) == 1
    assert len(_apply(mats, include_elements=["Fe", "Cu"])) == 0


def test_exclude_elements():
    mats = [
        {"formula": "PbO", "elements": ["Pb", "O"]},
        {"formula": "MgO", "elements": ["Mg", "O"]},
    ]
    kept = _apply(mats, exclude_elements=["Pb"])
    assert [m["formula"] for m in kept] == ["MgO"]


def test_include_elements_falls_back_to_formula():
    mats = [{"formula": "LiFePO4"}]  # no elements key
    assert len(_apply(mats, include_elements=["Fe", "P"])) == 1
    assert len(_apply(mats, include_elements=["Cu"])) == 0
