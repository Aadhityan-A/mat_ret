"""Tests for storage query parity with SearchFilters and pagination fixes."""

import pytest

from mat_ret.search import SearchFilters
from mat_ret.storage.sqlite_storage import SQLiteStorage
from mat_ret.storage.file_storage import FileStorage


@pytest.fixture
def sqlite_db():
    db = SQLiteStorage(db_path=":memory:")
    yield db
    db.close()


@pytest.fixture
def file_db(tmp_path):
    return FileStorage(output_directory=tmp_path)


def _save_set(storage):
    storage.save_material({
        "formula": "Fe2O3", "source_database": "mp", "band_gap": 2.2,
        "energy_above_hull": 0.0, "num_sites": 10, "density": 5.2,
        "elements": ["Fe", "O"],
    })
    storage.save_material({
        "formula": "SiO2", "source_database": "jarvis", "band_gap": 8.9,
        "energy_above_hull": 0.05, "num_sites": 6, "density": 2.6,
        "elements": ["Si", "O"],
    })
    storage.save_material({
        "formula": "Cu", "source_database": "oqmd", "band_gap": 0.0,
        "energy_above_hull": 0.2, "num_sites": 4, "density": 8.9,
        "elements": ["Cu"],
    })


# ---------------------------------------------------------------------------
# SQLite
# ---------------------------------------------------------------------------

def test_sqlite_filters_band_gap(sqlite_db):
    _save_set(sqlite_db)
    out = sqlite_db.query_materials(filters=SearchFilters(band_gap_min=2.0, band_gap_max=5.0))
    assert {m["formula"] for m in out} == {"Fe2O3"}


def test_sqlite_filters_energy_above_hull(sqlite_db):
    _save_set(sqlite_db)
    out = sqlite_db.query_materials(filters=SearchFilters(energy_above_hull_max=0.06))
    assert {m["formula"] for m in out} == {"Fe2O3", "SiO2"}


def test_sqlite_filters_num_sites_hoisted_from_raw(sqlite_db):
    _save_set(sqlite_db)
    out = sqlite_db.query_materials(filters=SearchFilters(num_sites_min=8))
    assert {m["formula"] for m in out} == {"Fe2O3"}


def test_sqlite_filters_include_elements(sqlite_db):
    _save_set(sqlite_db)
    out = sqlite_db.query_materials(filters=SearchFilters(include_elements=["O"]))
    assert {m["formula"] for m in out} == {"Fe2O3", "SiO2"}


def test_sqlite_element_filter_not_truncated_by_limit(sqlite_db):
    # 12 Fe-O materials interleaved with non-matching ones; small default limit
    # must still surface matches because element filtering happens before paging.
    for i in range(12):
        sqlite_db.save_material({"formula": f"Fe{i}O", "elements": ["Fe", "O"]})
        sqlite_db.save_material({"formula": f"Si{i}", "elements": ["Si"]})
    out = sqlite_db.query_materials(elements=["Fe", "O"], limit=100)
    assert len(out) == 12


def test_sqlite_plain_pagination_unchanged(sqlite_db):
    for _ in range(10):
        sqlite_db.save_material({"formula": "Fe2O3", "elements": ["Fe", "O"]})
    page1 = sqlite_db.query_materials(formula="Fe2O3", limit=3, offset=0)
    page2 = sqlite_db.query_materials(formula="Fe2O3", limit=3, offset=3)
    assert len(page1) == 3 and len(page2) == 3
    assert {m["record_id"] for m in page1}.isdisjoint({m["record_id"] for m in page2})


# ---------------------------------------------------------------------------
# FileStorage
# ---------------------------------------------------------------------------

def test_file_filters_band_gap(file_db):
    _save_set(file_db)
    out = file_db.query_materials(filters=SearchFilters(band_gap_min=2.0, band_gap_max=5.0))
    assert {m["formula"] for m in out} == {"Fe2O3"}


def test_file_filters_energy_above_hull(file_db):
    _save_set(file_db)
    out = file_db.query_materials(filters=SearchFilters(energy_above_hull_max=0.06))
    assert {m["formula"] for m in out} == {"Fe2O3", "SiO2"}


def test_file_filters_num_sites(file_db):
    _save_set(file_db)
    out = file_db.query_materials(filters=SearchFilters(num_sites_min=8))
    assert {m["formula"] for m in out} == {"Fe2O3"}


def test_file_list_is_most_recent_first(file_db):
    import time
    ids = []
    for f in ("A", "B", "C"):
        ids.append(file_db.save_material({"formula": f, "elements": []}))
        time.sleep(0.005)  # ensure distinct created_at timestamps
    listed = [m["formula"] for m in file_db.list_materials()]
    assert listed == ["C", "B", "A"]
