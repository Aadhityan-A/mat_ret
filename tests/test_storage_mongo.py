"""Tests for the MongoDBStorage backend using mongomock."""

import pytest

# Skip entire module if mongomock is not installed
mongomock = pytest.importorskip("mongomock", reason="mongomock not installed")

import unittest.mock as mock

from mat_ret.storage.mongo_storage import MongoDBStorage, HAS_PYMONGO


@pytest.fixture
def mongo_db():
    """Create a MongoDBStorage backed by mongomock."""
    with mock.patch("mat_ret.storage.mongo_storage.MongoClient", mongomock.MongoClient):
        storage = MongoDBStorage(
            uri="mongodb://localhost:27017",
            db_name="test_mat_ret",
            collection_name="test_materials",
        )
        yield storage
        # Clean up collection
        storage._collection.drop()
        storage.close()


@pytest.fixture
def sample_material():
    return {
        "formula": "TiO2",
        "material_id": "jvasp-100",
        "source_database": "JARVIS",
        "band_gap": 3.0,
        "density": 4.23,
        "volume": 62.4,
        "space_group": "P4_2/mnm",
        "space_group_number": 136,
        "crystal_system": "Tetragonal",
        "formation_energy_per_atom": -3.4,
        "cif_path": "/tmp/TiO2.cif",
        "elements": ["Ti", "O"],
    }


class TestMongoDBSave:
    def test_save_returns_record_id(self, mongo_db, sample_material):
        rid = mongo_db.save_material(sample_material)
        assert isinstance(rid, str)
        assert len(rid) > 0

    def test_save_stores_data(self, mongo_db, sample_material):
        rid = mongo_db.save_material(sample_material, search_query="TiO2")
        mat = mongo_db.get_material(rid)
        assert mat is not None
        assert mat["formula"] == "TiO2"
        assert mat["source_database"] == "JARVIS"
        assert mat["search_query"] == "TiO2"

    def test_save_skips_structure(self, mongo_db, sample_material):
        class FakeStructure:
            def as_dict(self):
                return {}
        sample_material["structure"] = FakeStructure()
        rid = mongo_db.save_material(sample_material)
        mat = mongo_db.get_material(rid)
        assert "structure" not in mat


class TestMongoDBGet:
    def test_get_existing(self, mongo_db, sample_material):
        rid = mongo_db.save_material(sample_material)
        assert mongo_db.get_material(rid) is not None

    def test_get_nonexistent(self, mongo_db):
        assert mongo_db.get_material("no-such-id") is None


class TestMongoDBQuery:
    def test_query_by_formula(self, mongo_db, sample_material):
        mongo_db.save_material(sample_material)
        results = mongo_db.query_materials(formula="TiO2")
        assert len(results) == 1

    def test_query_case_insensitive(self, mongo_db, sample_material):
        mongo_db.save_material(sample_material)
        results = mongo_db.query_materials(formula="tio2")
        assert len(results) == 1

    def test_query_by_source(self, mongo_db, sample_material):
        mongo_db.save_material(sample_material)
        assert len(mongo_db.query_materials(source_database="JARVIS")) == 1
        assert len(mongo_db.query_materials(source_database="AFLOW")) == 0

    def test_query_by_crystal_system(self, mongo_db, sample_material):
        mongo_db.save_material(sample_material)
        assert len(mongo_db.query_materials(crystal_system="Tetragonal")) == 1

    def test_query_by_space_group_number(self, mongo_db, sample_material):
        mongo_db.save_material(sample_material)
        assert len(mongo_db.query_materials(space_group_number=136)) == 1
        assert len(mongo_db.query_materials(space_group_number=1)) == 0

    def test_query_by_band_gap_range(self, mongo_db, sample_material):
        mongo_db.save_material(sample_material)
        assert len(mongo_db.query_materials(band_gap_min=2.0, band_gap_max=4.0)) == 1
        assert len(mongo_db.query_materials(band_gap_min=5.0)) == 0

    def test_query_by_elements(self, mongo_db, sample_material):
        mongo_db.save_material(sample_material)
        assert len(mongo_db.query_materials(elements=["Ti", "O"])) == 1
        assert len(mongo_db.query_materials(elements=["Fe"])) == 0

    def test_query_pagination(self, mongo_db, sample_material):
        for i in range(8):
            mongo_db.save_material(dict(sample_material, material_id=f"jvasp-{i}"))
        page1 = mongo_db.query_materials(formula="TiO2", limit=3, offset=0)
        page2 = mongo_db.query_materials(formula="TiO2", limit=3, offset=3)
        page3 = mongo_db.query_materials(formula="TiO2", limit=3, offset=6)
        assert len(page1) == 3
        assert len(page2) == 3
        assert len(page3) == 2


class TestMongoDBListAndCount:
    def test_list_materials(self, mongo_db, sample_material):
        mongo_db.save_material(sample_material)
        items = mongo_db.list_materials()
        assert len(items) == 1

    def test_count_all(self, mongo_db, sample_material):
        assert mongo_db.count_materials() == 0
        mongo_db.save_material(sample_material)
        assert mongo_db.count_materials() == 1

    def test_count_by_source(self, mongo_db, sample_material):
        mongo_db.save_material(sample_material)
        assert mongo_db.count_materials(source_database="JARVIS") == 1
        assert mongo_db.count_materials(source_database="AFLOW") == 0


class TestMongoDBDelete:
    def test_delete_existing(self, mongo_db, sample_material):
        rid = mongo_db.save_material(sample_material)
        assert mongo_db.delete_material(rid) is True
        assert mongo_db.get_material(rid) is None

    def test_delete_nonexistent(self, mongo_db):
        assert mongo_db.delete_material("no-such-id") is False


class TestMongoDBSearchHelpers:
    def test_search_by_formula(self, mongo_db, sample_material):
        mongo_db.save_material(sample_material)
        assert len(mongo_db.search_by_formula("TiO2")) == 1

    def test_search_by_elements(self, mongo_db, sample_material):
        mongo_db.save_material(sample_material)
        assert len(mongo_db.search_by_elements(["Ti"])) == 1
        assert len(mongo_db.search_by_elements(["Fe"])) == 0


class TestMongoDBCifPath:
    def test_get_cif_path(self, mongo_db, sample_material):
        rid = mongo_db.save_material(sample_material)
        assert mongo_db.get_cif_path(rid) == "/tmp/TiO2.cif"

    def test_get_cif_path_missing(self, mongo_db):
        assert mongo_db.get_cif_path("no-such-id") is None


class TestMongoDBSaveMany:
    def test_save_many(self, mongo_db, sample_material):
        materials = [dict(sample_material, material_id=f"jvasp-{i}") for i in range(4)]
        rids = mongo_db.save_many(materials, search_query="batch")
        assert len(rids) == 4
        assert mongo_db.count_materials() == 4
