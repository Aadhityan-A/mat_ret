"""Tests for the FileStorage backend."""

import json
import os
import tempfile
from pathlib import Path

import pytest

from mat_ret.storage.file_storage import FileStorage


@pytest.fixture
def tmp_storage(tmp_path):
    """Create a FileStorage backed by a temporary directory."""
    return FileStorage(output_directory=tmp_path)


@pytest.fixture
def sample_material():
    return {
        "formula": "SiO2",
        "material_id": "mp-1234",
        "source_database": "Materials Project",
        "band_gap": 5.5,
        "density": 2.65,
        "volume": 46.3,
        "space_group": "P3_121",
        "space_group_number": 152,
        "crystal_system": "Trigonal",
        "formation_energy_per_atom": -3.1,
        "cif_path": "/tmp/fake.cif",
        "elements": ["Si", "O"],
    }


class TestFileStorageSaveMaterial:
    def test_save_returns_record_id(self, tmp_storage, sample_material):
        rid = tmp_storage.save_material(sample_material)
        assert isinstance(rid, str) and len(rid) > 0

    def test_save_creates_json_file(self, tmp_storage, sample_material):
        rid = tmp_storage.save_material(sample_material)
        json_path = tmp_storage.output_dir / f"{rid}.json"
        assert json_path.exists()
        data = json.loads(json_path.read_text(encoding="utf-8"))
        assert data["formula"] == "SiO2"

    def test_save_updates_index(self, tmp_storage, sample_material):
        rid = tmp_storage.save_material(sample_material, search_query="SiO2")
        assert rid in tmp_storage._index
        assert tmp_storage._index[rid]["formula"] == "SiO2"
        assert tmp_storage._index[rid]["search_query"] == "SiO2"

    def test_save_strips_structure_key(self, tmp_storage, sample_material):
        class FakeStructure:
            def as_dict(self):
                return {"lattice": []}
        sample_material["structure"] = FakeStructure()
        rid = tmp_storage.save_material(sample_material)
        data = json.loads((tmp_storage.output_dir / f"{rid}.json").read_text())
        assert "structure" not in data


class TestFileStorageGetMaterial:
    def test_get_existing(self, tmp_storage, sample_material):
        rid = tmp_storage.save_material(sample_material)
        mat = tmp_storage.get_material(rid)
        assert mat is not None
        assert mat["formula"] == "SiO2"

    def test_get_nonexistent(self, tmp_storage):
        assert tmp_storage.get_material("no-such-id") is None


class TestFileStorageQuery:
    def test_query_by_formula(self, tmp_storage, sample_material):
        tmp_storage.save_material(sample_material)
        results = tmp_storage.query_materials(formula="SiO2")
        assert len(results) == 1
        assert results[0]["formula"] == "SiO2"

    def test_query_by_formula_case_insensitive(self, tmp_storage, sample_material):
        tmp_storage.save_material(sample_material)
        results = tmp_storage.query_materials(formula="sio2")
        assert len(results) == 1

    def test_query_by_source(self, tmp_storage, sample_material):
        tmp_storage.save_material(sample_material)
        results = tmp_storage.query_materials(source_database="Materials Project")
        assert len(results) == 1

    def test_query_by_crystal_system(self, tmp_storage, sample_material):
        tmp_storage.save_material(sample_material)
        results = tmp_storage.query_materials(crystal_system="Trigonal")
        assert len(results) == 1

    def test_query_by_band_gap_range(self, tmp_storage, sample_material):
        tmp_storage.save_material(sample_material)
        assert len(tmp_storage.query_materials(band_gap_min=5.0, band_gap_max=6.0)) == 1
        assert len(tmp_storage.query_materials(band_gap_min=6.0)) == 0

    def test_query_by_space_group_number(self, tmp_storage, sample_material):
        tmp_storage.save_material(sample_material)
        assert len(tmp_storage.query_materials(space_group_number=152)) == 1
        assert len(tmp_storage.query_materials(space_group_number=999)) == 0

    def test_query_pagination(self, tmp_storage, sample_material):
        for i in range(5):
            m = dict(sample_material, material_id=f"mp-{i}")
            tmp_storage.save_material(m)
        page1 = tmp_storage.query_materials(formula="SiO2", limit=2, offset=0)
        page2 = tmp_storage.query_materials(formula="SiO2", limit=2, offset=2)
        assert len(page1) == 2
        assert len(page2) == 2

    def test_query_no_match(self, tmp_storage, sample_material):
        tmp_storage.save_material(sample_material)
        assert tmp_storage.query_materials(formula="Fe2O3") == []


class TestFileStorageListAndCount:
    def test_list_materials(self, tmp_storage, sample_material):
        tmp_storage.save_material(sample_material)
        items = tmp_storage.list_materials()
        assert len(items) == 1

    def test_count_all(self, tmp_storage, sample_material):
        assert tmp_storage.count_materials() == 0
        tmp_storage.save_material(sample_material)
        assert tmp_storage.count_materials() == 1

    def test_count_by_source(self, tmp_storage, sample_material):
        tmp_storage.save_material(sample_material)
        assert tmp_storage.count_materials(source_database="Materials Project") == 1
        assert tmp_storage.count_materials(source_database="JARVIS") == 0


class TestFileStorageDelete:
    def test_delete_existing(self, tmp_storage, sample_material):
        rid = tmp_storage.save_material(sample_material)
        assert tmp_storage.delete_material(rid) is True
        assert tmp_storage.get_material(rid) is None
        assert tmp_storage.count_materials() == 0

    def test_delete_nonexistent(self, tmp_storage):
        assert tmp_storage.delete_material("no-such-id") is False


class TestFileStorageSearchHelpers:
    def test_search_by_formula(self, tmp_storage, sample_material):
        tmp_storage.save_material(sample_material)
        assert len(tmp_storage.search_by_formula("SiO2")) == 1

    def test_search_by_elements(self, tmp_storage, sample_material):
        tmp_storage.save_material(sample_material)
        assert len(tmp_storage.search_by_elements(["Si", "O"])) == 1
        assert len(tmp_storage.search_by_elements(["Fe"])) == 0


class TestFileStorageCifPath:
    def test_get_cif_path(self, tmp_storage, sample_material):
        rid = tmp_storage.save_material(sample_material)
        assert tmp_storage.get_cif_path(rid) == "/tmp/fake.cif"

    def test_get_cif_path_missing(self, tmp_storage):
        assert tmp_storage.get_cif_path("no-such-id") is None


class TestFileStorageSaveMany:
    def test_save_many(self, tmp_storage, sample_material):
        materials = [dict(sample_material, material_id=f"mp-{i}") for i in range(3)]
        rids = tmp_storage.save_many(materials, search_query="batch")
        assert len(rids) == 3
        assert tmp_storage.count_materials() == 3


class TestFileStorageContextManager:
    def test_context_manager(self, tmp_path, sample_material):
        with FileStorage(output_directory=tmp_path) as storage:
            storage.save_material(sample_material)
            assert storage.count_materials() == 1


class TestFileStoragePersistence:
    def test_index_survives_reload(self, tmp_path, sample_material):
        storage1 = FileStorage(output_directory=tmp_path)
        rid = storage1.save_material(sample_material)

        storage2 = FileStorage(output_directory=tmp_path)
        assert storage2.count_materials() == 1
        assert storage2.get_material(rid) is not None
