"""Headless GUI tests for the new composition filters, retrieve-all toggle,
and incremental results display."""

import pytest

pytest.importorskip("PyQt6")

from mat_ret.gui.widgets.search_filters import SearchFiltersWidget, _parse_element_list
from mat_ret.gui.widgets.database_selector import DatabaseSelectorWidget
from mat_ret.gui.widgets.results_view import ResultsViewWidget
from mat_ret.gui.workers import FetchWorker, RETRIEVE_ALL_LIMIT


# ---------------------------------------------------------------------------
# Element-list parsing helper
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("text,expected", [
    ("Fe, O", ["Fe", "O"]),
    ("fe o", ["Fe", "O"]),
    ("Fe/O,Fe", ["Fe", "O"]),
    ("", None),
    ("   ", None),
])
def test_parse_element_list(text, expected):
    assert _parse_element_list(text) == expected


# ---------------------------------------------------------------------------
# Composition filters in the widget
# ---------------------------------------------------------------------------

def test_composition_filters_default_none(qtbot):
    w = SearchFiltersWidget()
    qtbot.addWidget(w)
    f = w.get_filters()
    assert f.include_elements is None
    assert f.exclude_elements is None
    assert f.active_filter_count() == 0


def test_composition_filters_parsed(qtbot):
    w = SearchFiltersWidget()
    qtbot.addWidget(w)
    w.include_elements_edit.setText("Fe, O")
    w.exclude_elements_edit.setText("Pb")
    f = w.get_filters()
    assert f.include_elements == ["Fe", "O"]
    assert f.exclude_elements == ["Pb"]
    assert f.active_filter_count() == 2


def test_clear_resets_composition(qtbot):
    w = SearchFiltersWidget()
    qtbot.addWidget(w)
    w.include_elements_edit.setText("Fe")
    w.exclude_elements_edit.setText("Pb")
    w.clear_filters()
    f = w.get_filters()
    assert f.include_elements is None
    assert f.exclude_elements is None


# ---------------------------------------------------------------------------
# Retrieve-all toggle
# ---------------------------------------------------------------------------

def test_retrieve_all_default_false(qtbot):
    w = DatabaseSelectorWidget()
    qtbot.addWidget(w)
    assert w.get_retrieve_all() is False
    assert w.get_limit() == 10


def test_retrieve_all_toggle_disables_limit(qtbot):
    w = DatabaseSelectorWidget()
    qtbot.addWidget(w)
    w.retrieve_all_cb.setChecked(True)
    assert w.get_retrieve_all() is True
    assert not w.limit_spinner.isEnabled()


def test_limit_spinner_allows_large_values(qtbot):
    w = DatabaseSelectorWidget()
    qtbot.addWidget(w)
    w.limit_spinner.setValue(2000)
    assert w.get_limit() == 2000


# ---------------------------------------------------------------------------
# FetchWorker effective limit
# ---------------------------------------------------------------------------

def test_fetch_worker_stores_retrieve_all():
    worker = FetchWorker(formula="Fe2O3", databases=["jarvis"], limit=10, retrieve_all=True)
    assert worker.retrieve_all is True
    assert RETRIEVE_ALL_LIMIT >= 1000


# ---------------------------------------------------------------------------
# Incremental display + merge toggle
# ---------------------------------------------------------------------------

def test_append_results_incremental(qtbot):
    w = ResultsViewWidget()
    qtbot.addWidget(w)
    w.clear_results()
    w.append_results("jarvis", [{"formula": "Fe2O3", "material_id": "j1"}])
    assert "jarvis" in w.results_data
    assert w.export_json_btn.isEnabled()
    w.append_results("oqmd", [{"formula": "SiO2", "material_id": "o1"}])
    assert len(w.results_data) == 2


def test_merge_toggle_renders(qtbot):
    w = ResultsViewWidget()
    qtbot.addWidget(w)
    w.set_results({
        "materials_project": [{"formula": "Fe2O3", "num_sites": 10, "space_group_number": 167, "material_id": "mp-1"}],
        "jarvis": [{"formula": "Fe2O3", "num_sites": 10, "space_group_number": 167, "material_id": "j-1"}],
    })
    w.dedupe_cb.setChecked(True)  # triggers _show_all_results via toggled signal
    # Merged view collapses the duplicate into a single table row.
    assert w.results_table.rowCount() == 1
