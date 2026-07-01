"""Tests for the unified retrieval layer: db-subset, retrieve_all, parallel,
save_cif, cross-database merge, and the fetch_all_databases plumbing."""

from pathlib import Path

import pytest

from mat_ret import databases as db_mod
from mat_ret.databases import (
    MaterialsDatabaseRetriever,
    merge_duplicate_materials,
    _populate_computed_fields,
    SUPPORTED_DATABASES,
    DEFAULT_HARD_LIMIT_PER_DB,
)


# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------

class FakeClient:
    def __init__(self, results):
        self._results = results
        self.calls = []
        self.saved = []

    def get_structures(self, formula, limit, elements=None, filters=None):
        self.calls.append(
            {"formula": formula, "limit": limit, "elements": elements, "filters": filters}
        )
        return [dict(r) for r in self._results[:limit]]

    def save_cif(self, material, filename):
        self.saved.append(filename)
        return f"/tmp/{filename}.cif"


class FakeStorage:
    def __init__(self):
        self.saved = []

    def save_material(self, material, *, search_query=None):
        self.saved.append((dict(material), search_query))
        return "rid"


def make_retriever(clients, storage=None, tmp_path=None):
    r = MaterialsDatabaseRetriever.__new__(MaterialsDatabaseRetriever)
    r.storage = storage
    r.output_directory = Path(tmp_path) if tmp_path else Path(".")
    r.enabled_databases = None
    r.clients = clients
    return r


# ---------------------------------------------------------------------------
# Database-subset validation
# ---------------------------------------------------------------------------

def test_validate_databases_accepts_known():
    assert MaterialsDatabaseRetriever._validate_databases(["jarvis", "oqmd"]) == {"jarvis", "oqmd"}


def test_validate_databases_rejects_unknown():
    with pytest.raises(ValueError):
        MaterialsDatabaseRetriever._validate_databases(["jarvis", "bogus"])


def test_supported_databases_constant():
    assert "materials_project" in SUPPORTED_DATABASES
    assert "optimade" in SUPPORTED_DATABASES


# ---------------------------------------------------------------------------
# retrieve_materials forwarding
# ---------------------------------------------------------------------------

def test_retrieve_forwards_elements_and_filters():
    c = FakeClient([{"formula": "Fe2O3"}])
    r = make_retriever({"jarvis": c})
    from mat_ret.search import SearchFilters
    filt = SearchFilters(band_gap_min=1.0)
    r.retrieve_materials("Fe2O3", 3, elements=["Fe", "O"], filters=filt, save_cif=False)
    assert c.calls[0]["elements"] == ["Fe", "O"]
    assert c.calls[0]["filters"] is filt
    assert c.calls[0]["limit"] == 3


def test_retrieve_all_uses_hard_limit():
    c = FakeClient([{"formula": "Fe2O3"}])
    r = make_retriever({"jarvis": c})
    r.retrieve_materials("Fe2O3", 3, retrieve_all=True, save_cif=False)
    assert c.calls[0]["limit"] == DEFAULT_HARD_LIMIT_PER_DB


def test_retrieve_requires_formula_or_elements():
    r = make_retriever({"jarvis": FakeClient([])})
    with pytest.raises(ValueError):
        r.retrieve_materials(None, 3, save_cif=False)


def test_save_cif_false_writes_nothing():
    c = FakeClient([{"formula": "Fe2O3"}, {"formula": "Fe2O3"}])
    r = make_retriever({"jarvis": c})
    r.retrieve_materials("Fe2O3", 5, save_cif=False)
    assert c.saved == []


def test_save_cif_true_writes_each():
    c = FakeClient([{"formula": "Fe2O3"}, {"formula": "Fe2O3"}])
    r = make_retriever({"jarvis": c})
    r.retrieve_materials("Fe2O3", 5, save_cif=True)
    assert len(c.saved) == 2


def test_storage_persistence_independent_of_save_cif():
    c = FakeClient([{"formula": "Fe2O3"}])
    storage = FakeStorage()
    r = make_retriever({"jarvis": c}, storage=storage)
    r.retrieve_materials("Fe2O3", 5, save_cif=False)
    assert len(storage.saved) == 1
    mat, query = storage.saved[0]
    assert mat["source_database"] == "jarvis"
    assert query == "Fe2O3"


def test_database_subset_only_queries_selected():
    a = FakeClient([{"formula": "Fe2O3"}])
    b = FakeClient([{"formula": "SiO2"}])
    r = make_retriever({"jarvis": a, "oqmd": b})
    results = r.retrieve_materials("Fe2O3", 3, databases=["jarvis"], save_cif=False)
    assert set(results.keys()) == {"jarvis"}
    assert a.calls and not b.calls


def test_parallel_matches_sequential():
    def fresh():
        return {
            "jarvis": FakeClient([{"formula": "Fe2O3"}]),
            "oqmd": FakeClient([{"formula": "SiO2"}]),
        }

    seq = make_retriever(fresh()).retrieve_materials("X", 3, save_cif=False)
    par = make_retriever(fresh()).retrieve_materials("X", 3, parallel=True, save_cif=False)
    assert {k: [m["formula"] for m in v] for k, v in seq.items()} == \
           {k: [m["formula"] for m in v] for k, v in par.items()}


def test_client_failure_isolated():
    class Boom(FakeClient):
        def get_structures(self, *a, **k):
            raise RuntimeError("boom")

    r = make_retriever({"jarvis": Boom([]), "oqmd": FakeClient([{"formula": "SiO2"}])})
    results = r.retrieve_materials("X", 3, save_cif=False)
    assert results["jarvis"] == []
    assert len(results["oqmd"]) == 1


# ---------------------------------------------------------------------------
# retrieve_unified
# ---------------------------------------------------------------------------

def test_retrieve_unified_envelope():
    r = make_retriever({
        "materials_project": FakeClient([{"formula": "Fe2O3", "num_sites": 10, "space_group_number": 167}]),
        "jarvis": FakeClient([{"formula": "Fe2O3", "num_sites": 10, "space_group_number": 167}]),
    })
    env = r.retrieve_unified("Fe2O3", 3, save_cif=False)
    assert env["metadata"]["total_before_dedup"] == 2
    assert env["metadata"]["total_after_dedup"] == 1
    assert len(env["materials"]) == 1
    assert set(env["materials"][0]["source_databases"]) == {"materials_project", "jarvis"}


# ---------------------------------------------------------------------------
# merge_duplicate_materials
# ---------------------------------------------------------------------------

def test_merge_precedence_and_fill():
    by_db = {
        "jarvis": [{"formula": "Fe2O3", "num_sites": 10, "space_group_number": 167,
                    "band_gap": 1.5, "density": 5.2}],
        "materials_project": [{"formula": "Fe2O3", "num_sites": 10, "space_group_number": 167,
                               "band_gap": 2.0}],
    }
    merged = merge_duplicate_materials(by_db)
    assert len(merged) == 1
    m = merged[0]
    assert m["band_gap"] == 2.0          # MP wins (higher precedence)
    assert m["density"] == 5.2           # filled from JARVIS
    assert m["source_database"] == "materials_project"
    assert set(m["source_databases"]) == {"jarvis", "materials_project"}


def test_merge_keeps_distinct_materials():
    by_db = {
        "oqmd": [
            {"formula": "Fe2O3", "num_sites": 10, "space_group_number": 167},
            {"formula": "SiO2", "num_sites": 6, "space_group_number": 152},
        ],
    }
    assert len(merge_duplicate_materials(by_db)) == 2


def test_merge_no_merge_without_structural_keys():
    # No num_sites / space_group → cannot identify → kept separate.
    by_db = {
        "a": [{"formula": "Fe2O3"}],
        "b": [{"formula": "Fe2O3"}],
    }
    assert len(merge_duplicate_materials(by_db)) == 2


# ---------------------------------------------------------------------------
# _populate_computed_fields
# ---------------------------------------------------------------------------

def test_populate_computed_from_formula():
    sd = {"formula": "LiFePO4"}
    _populate_computed_fields(sd, "LiFePO4")
    assert sd["elements"] == ["Fe", "Li", "O", "P"]
    assert sd["num_elements"] == 4


def test_populate_computed_does_not_overwrite():
    sd = {"formula": "Fe2O3", "num_sites": 99, "elements": ["X"]}
    _populate_computed_fields(sd, "Fe2O3")
    assert sd["num_sites"] == 99
    assert sd["elements"] == ["X"]


# ---------------------------------------------------------------------------
# fetch_all_databases plumbing
# ---------------------------------------------------------------------------

class RecordingRetriever:
    last = {}

    def __init__(self, **kwargs):
        RecordingRetriever.last = {"init": kwargs}

    def retrieve_materials(self, formula, limit_per_db, **kwargs):
        RecordingRetriever.last["call"] = {"formula": formula, "limit": limit_per_db, **kwargs}
        return {"jarvis": [{"formula": "Fe2O3"}]}

    def retrieve_unified(self, formula, limit_per_db, **kwargs):
        RecordingRetriever.last["unified"] = {"formula": formula, "limit": limit_per_db, **kwargs}
        return {"materials": [], "by_database": {}, "metadata": {}}


def test_fetch_all_databases_positional_returns_dict(monkeypatch):
    monkeypatch.setattr("mat_ret.api.MaterialsDatabaseRetriever", RecordingRetriever)
    from mat_ret.api import fetch_all_databases
    out = fetch_all_databases("Fe2O3", limit_per_database=2)
    assert isinstance(out, dict)
    assert RecordingRetriever.last["call"]["formula"] == "Fe2O3"
    assert RecordingRetriever.last["call"]["limit"] == 2


def test_fetch_all_databases_forwards_new_params(monkeypatch):
    monkeypatch.setattr("mat_ret.api.MaterialsDatabaseRetriever", RecordingRetriever)
    from mat_ret.api import fetch_all_databases
    from mat_ret.search import SearchFilters
    filt = SearchFilters(band_gap_min=1.0)
    fetch_all_databases(
        elements=["Fe", "O"], databases=["jarvis"], filters=filt,
        retrieve_all=True, parallel=True, save_cif=False,
    )
    call = RecordingRetriever.last["call"]
    assert call["elements"] == ["Fe", "O"]
    assert call["databases"] == ["jarvis"]
    assert call["filters"] is filt
    assert call["retrieve_all"] is True
    assert call["parallel"] is True
    assert call["save_cif"] is False
    assert RecordingRetriever.last["init"]["databases"] == ["jarvis"]


def test_fetch_all_databases_merge_duplicates_uses_unified(monkeypatch):
    monkeypatch.setattr("mat_ret.api.MaterialsDatabaseRetriever", RecordingRetriever)
    from mat_ret.api import fetch_all_databases
    out = fetch_all_databases("Fe2O3", merge_duplicates=True)
    assert "materials" in out and "metadata" in out
    assert "unified" in RecordingRetriever.last
