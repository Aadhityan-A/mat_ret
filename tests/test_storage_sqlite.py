"""Tests for the SQLiteStorage backend."""

import json
import os

import pytest

from mat_ret.storage.sqlite_storage import SQLiteStorage


@pytest.fixture
def db(tmp_path):
    """Create a SQLiteStorage with a temp DB file."""
    path = str(tmp_path / "test.db")
    storage = SQLiteStorage(db_path=path)
    yield storage
    storage.close()


@pytest.fixture
def memory_db():
    """In-memory SQLite database."""
    storage = SQLiteStorage(db_path=":memory:")
    yield storage
    storage.close()


@pytest.fixture
def sample_material():
    return {
        "formula": "Fe2O3",
        "material_id": "mp-5678",
        "source_database": "JARVIS",
        "band_gap": 2.1,
        "density": 5.24,
        "volume": 100.5,
        "space_group": "R-3c",
        "space_group_number": 167,
        "crystal_system": "Trigonal",
        "formation_energy_per_atom": -1.5,
        "energy_per_atom": -6.2,
        "energy_above_hull": 0.0,
        "bulk_modulus": 220.0,
        "shear_modulus": 90.0,
        "magnetic_moment": 4.5,
        "is_metallic": False,
        "cif_path": "/tmp/Fe2O3.cif",
        "elements": ["Fe", "O"],
    }


class TestSQLiteSave:
    def test_save_returns_record_id(self, memory_db, sample_material):
        rid = memory_db.save_material(sample_material)
        assert isinstance(rid, str)
        assert len(rid) > 0

    def test_save_stores_all_columns(self, memory_db, sample_material):
        rid = memory_db.save_material(sample_material, search_query="Fe2O3")
        mat = memory_db.get_material(rid)
        assert mat is not None
        assert mat["formula"] == "Fe2O3"
        assert mat["source_database"] == "JARVIS"
        assert mat["band_gap"] == pytest.approx(2.1)
        assert mat["space_group_number"] == 167
        assert mat["crystal_system"] == "Trigonal"
        assert mat["density"] == pytest.approx(5.24)
        assert mat["bulk_modulus"] == pytest.approx(220.0)
        assert mat["magnetic_moment"] == pytest.approx(4.5)
        assert mat["is_metallic"] is False
        assert mat["search_query"] == "Fe2O3"

    def test_save_stores_raw_data(self, memory_db, sample_material):
        rid = memory_db.save_material(sample_material)
        mat = memory_db.get_material(rid)
        raw = mat.get("raw_data")
        assert isinstance(raw, dict)
        assert raw["formula"] == "Fe2O3"

    def test_save_handles_structure_key(self, memory_db, sample_material):
        """The 'structure' key should not appear in raw_data."""
        class FakeStructure:
            def as_dict(self):
                return {}
        sample_material["structure"] = FakeStructure()
        rid = memory_db.save_material(sample_material)
        mat = memory_db.get_material(rid)
        assert "structure" not in mat.get("raw_data", {})

    def test_save_elements_as_json(self, memory_db, sample_material):
        rid = memory_db.save_material(sample_material)
        mat = memory_db.get_material(rid)
        assert mat["elements"] == ["Fe", "O"]


class TestSQLiteGetMaterial:
    def test_get_existing(self, memory_db, sample_material):
        rid = memory_db.save_material(sample_material)
        assert memory_db.get_material(rid) is not None

    def test_get_nonexistent(self, memory_db):
        assert memory_db.get_material("no-such-id") is None


class TestSQLiteQuery:
    def test_query_by_formula(self, memory_db, sample_material):
        memory_db.save_material(sample_material)
        results = memory_db.query_materials(formula="Fe2O3")
        assert len(results) == 1

    def test_query_case_insensitive(self, memory_db, sample_material):
        memory_db.save_material(sample_material)
        results = memory_db.query_materials(formula="fe2o3")
        assert len(results) == 1

    def test_query_by_source_database(self, memory_db, sample_material):
        memory_db.save_material(sample_material)
        assert len(memory_db.query_materials(source_database="JARVIS")) == 1
        assert len(memory_db.query_materials(source_database="AFLOW")) == 0

    def test_query_by_crystal_system(self, memory_db, sample_material):
        memory_db.save_material(sample_material)
        assert len(memory_db.query_materials(crystal_system="Trigonal")) == 1
        assert len(memory_db.query_materials(crystal_system="Cubic")) == 0

    def test_query_by_space_group_number(self, memory_db, sample_material):
        memory_db.save_material(sample_material)
        assert len(memory_db.query_materials(space_group_number=167)) == 1
        assert len(memory_db.query_materials(space_group_number=1)) == 0

    def test_query_by_band_gap_range(self, memory_db, sample_material):
        memory_db.save_material(sample_material)
        assert len(memory_db.query_materials(band_gap_min=2.0, band_gap_max=3.0)) == 1
        assert len(memory_db.query_materials(band_gap_min=5.0)) == 0
        assert len(memory_db.query_materials(band_gap_max=1.0)) == 0

    def test_query_combined_filters(self, memory_db, sample_material):
        memory_db.save_material(sample_material)
        results = memory_db.query_materials(
            formula="Fe2O3",
            source_database="JARVIS",
            crystal_system="Trigonal",
            band_gap_min=1.0,
            band_gap_max=5.0,
        )
        assert len(results) == 1

    def test_query_pagination(self, memory_db, sample_material):
        for i in range(10):
            m = dict(sample_material, material_id=f"mp-{i}")
            memory_db.save_material(m)
        page1 = memory_db.query_materials(formula="Fe2O3", limit=3, offset=0)
        page2 = memory_db.query_materials(formula="Fe2O3", limit=3, offset=3)
        page3 = memory_db.query_materials(formula="Fe2O3", limit=3, offset=9)
        assert len(page1) == 3
        assert len(page2) == 3
        assert len(page3) == 1

    def test_query_elements_post_filter(self, memory_db, sample_material):
        memory_db.save_material(sample_material)
        assert len(memory_db.query_materials(elements=["Fe", "O"])) == 1
        assert len(memory_db.query_materials(elements=["Si"])) == 0


class TestSQLiteListAndCount:
    def test_list_materials(self, memory_db, sample_material):
        memory_db.save_material(sample_material)
        items = memory_db.list_materials()
        assert len(items) == 1

    def test_list_pagination(self, memory_db, sample_material):
        for i in range(5):
            memory_db.save_material(dict(sample_material, material_id=f"mp-{i}"))
        assert len(memory_db.list_materials(limit=2)) == 2
        assert len(memory_db.list_materials(limit=2, offset=4)) == 1

    def test_count_all(self, memory_db, sample_material):
        assert memory_db.count_materials() == 0
        memory_db.save_material(sample_material)
        assert memory_db.count_materials() == 1

    def test_count_by_source(self, memory_db, sample_material):
        memory_db.save_material(sample_material)
        memory_db.save_material(dict(sample_material, source_database="AFLOW"))
        assert memory_db.count_materials(source_database="JARVIS") == 1
        assert memory_db.count_materials(source_database="AFLOW") == 1
        assert memory_db.count_materials() == 2


class TestSQLiteDelete:
    def test_delete_existing(self, memory_db, sample_material):
        rid = memory_db.save_material(sample_material)
        assert memory_db.delete_material(rid) is True
        assert memory_db.get_material(rid) is None
        assert memory_db.count_materials() == 0

    def test_delete_nonexistent(self, memory_db):
        assert memory_db.delete_material("no-such-id") is False


class TestSQLiteSearchHelpers:
    def test_search_by_formula(self, memory_db, sample_material):
        memory_db.save_material(sample_material)
        assert len(memory_db.search_by_formula("Fe2O3")) == 1

    def test_search_by_elements(self, memory_db, sample_material):
        memory_db.save_material(sample_material)
        assert len(memory_db.search_by_elements(["Fe"])) == 1
        assert len(memory_db.search_by_elements(["Si"])) == 0


class TestSQLiteCifPath:
    def test_get_cif_path(self, memory_db, sample_material):
        rid = memory_db.save_material(sample_material)
        assert memory_db.get_cif_path(rid) == "/tmp/Fe2O3.cif"

    def test_get_cif_path_missing(self, memory_db):
        assert memory_db.get_cif_path("no-such-id") is None


class TestSQLiteSaveMany:
    def test_save_many(self, memory_db, sample_material):
        materials = [dict(sample_material, material_id=f"mp-{i}") for i in range(5)]
        rids = memory_db.save_many(materials, search_query="batch_test")
        assert len(rids) == 5
        assert memory_db.count_materials() == 5


class TestSQLiteContextManager:
    def test_context_manager(self, tmp_path, sample_material):
        path = str(tmp_path / "ctx.db")
        with SQLiteStorage(db_path=path) as storage:
            storage.save_material(sample_material)
            assert storage.count_materials() == 1


class TestSQLitePersistence:
    def test_data_survives_reconnect(self, tmp_path, sample_material):
        path = str(tmp_path / "persist.db")
        s1 = SQLiteStorage(db_path=path)
        rid = s1.save_material(sample_material)
        s1.close()

        s2 = SQLiteStorage(db_path=path)
        assert s2.count_materials() == 1
        mat = s2.get_material(rid)
        assert mat is not None
        assert mat["formula"] == "Fe2O3"
        s2.close()


class TestSQLiteNullHandling:
    def test_missing_optional_fields(self, memory_db):
        minimal = {"formula": "NaCl", "source_database": "test"}
        rid = memory_db.save_material(minimal)
        mat = memory_db.get_material(rid)
        assert mat is not None
        assert mat["formula"] == "NaCl"
        assert mat["band_gap"] is None
        assert mat["density"] is None
