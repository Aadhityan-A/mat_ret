"""
Fast headless tests for the GUI filter and database-selector widgets.

Uses pytest-qt (qtbot fixture) so no visible window is needed.
All tests are purely local — no network calls.
"""

import sys
import pytest

from PyQt6.QtCore import Qt

from mat_ret.gui.widgets.search_filters import SearchFiltersWidget
from mat_ret.gui.widgets.database_selector import DatabaseSelectorWidget


# ---------------------------------------------------------------------------
# SearchFiltersWidget tests
# ---------------------------------------------------------------------------

class TestSearchFiltersDefaults:
    """Fresh widget should have every filter inactive."""

    def test_default_filters_all_none(self, qtbot):
        w = SearchFiltersWidget()
        qtbot.addWidget(w)
        f = w.get_filters()

        assert f.band_gap_min is None
        assert f.band_gap_max is None
        assert f.is_metal is None
        assert f.formation_energy_min is None
        assert f.formation_energy_max is None
        assert f.energy_above_hull_max is None
        assert f.is_stable is None
        assert f.density_min is None
        assert f.density_max is None
        assert f.volume_min is None
        assert f.volume_max is None
        assert f.space_group_number is None
        assert f.crystal_system is None
        assert f.num_elements_min is None
        assert f.num_elements_max is None
        assert f.num_sites_min is None
        assert f.num_sites_max is None
        assert f.bulk_modulus_min is None
        assert f.bulk_modulus_max is None
        assert f.shear_modulus_min is None
        assert f.shear_modulus_max is None
        assert f.magnetic_ordering is None
        assert f.total_magnetization_min is None
        assert f.total_magnetization_max is None
        assert f.exclude_theoretical is False
        assert f.active_filter_count() == 0

    def test_has_any_filter_false_by_default(self, qtbot):
        w = SearchFiltersWidget()
        qtbot.addWidget(w)
        assert not w.get_filters().has_any_filter()


class TestSearchFiltersElectronic:
    def test_band_gap_filter(self, qtbot):
        w = SearchFiltersWidget()
        qtbot.addWidget(w)
        w.band_gap_min.setValue(0.5)
        w.band_gap_max.setValue(3.0)
        f = w.get_filters()
        assert f.band_gap_min == pytest.approx(0.5)
        assert f.band_gap_max == pytest.approx(3.0)

    def test_is_metal_combo_metal(self, qtbot):
        w = SearchFiltersWidget()
        qtbot.addWidget(w)
        w.is_metal_combo.setCurrentIndex(1)  # "Metal"
        assert w.get_filters().is_metal is True

    def test_is_metal_combo_nonmetal(self, qtbot):
        w = SearchFiltersWidget()
        qtbot.addWidget(w)
        w.is_metal_combo.setCurrentIndex(2)  # "Non-metal"
        assert w.get_filters().is_metal is False


class TestSearchFiltersEnergetic:
    def test_formation_energy(self, qtbot):
        w = SearchFiltersWidget()
        qtbot.addWidget(w)
        w.form_energy_min.setValue(-2.0)
        w.form_energy_max.setValue(1.0)
        f = w.get_filters()
        assert f.formation_energy_min == pytest.approx(-2.0)
        assert f.formation_energy_max == pytest.approx(1.0)

    def test_e_hull_max(self, qtbot):
        w = SearchFiltersWidget()
        qtbot.addWidget(w)
        w.e_hull_max.setValue(0.05)
        assert w.get_filters().energy_above_hull_max == pytest.approx(0.05)

    def test_stable_only_checkbox(self, qtbot):
        w = SearchFiltersWidget()
        qtbot.addWidget(w)
        w.is_stable_cb.setChecked(True)
        assert w.get_filters().is_stable is True


class TestSearchFiltersStructural:
    def test_crystal_system_combo(self, qtbot):
        w = SearchFiltersWidget()
        qtbot.addWidget(w)
        # Find "cubic" in the combo
        idx = w.crystal_system_combo.findData("cubic")
        assert idx >= 0
        w.crystal_system_combo.setCurrentIndex(idx)
        assert w.get_filters().crystal_system == "cubic"

    def test_space_group_filter(self, qtbot):
        w = SearchFiltersWidget()
        qtbot.addWidget(w)
        w.space_group_spin.setValue(225)
        assert w.get_filters().space_group_number == 225

    def test_density_filter(self, qtbot):
        w = SearchFiltersWidget()
        qtbot.addWidget(w)
        w.density_min.setValue(2.0)
        w.density_max.setValue(5.0)
        f = w.get_filters()
        assert f.density_min == pytest.approx(2.0)
        assert f.density_max == pytest.approx(5.0)

    def test_volume_filter(self, qtbot):
        w = SearchFiltersWidget()
        qtbot.addWidget(w)
        w.volume_min.setValue(10.0)
        w.volume_max.setValue(500.0)
        f = w.get_filters()
        assert f.volume_min == pytest.approx(10.0)
        assert f.volume_max == pytest.approx(500.0)

    def test_num_elements_filter(self, qtbot):
        w = SearchFiltersWidget()
        qtbot.addWidget(w)
        w.num_elements_min.setValue(2)
        w.num_elements_max.setValue(4)
        f = w.get_filters()
        assert f.num_elements_min == 2
        assert f.num_elements_max == 4

    def test_num_sites_filter(self, qtbot):
        w = SearchFiltersWidget()
        qtbot.addWidget(w)
        w.num_sites_min.setValue(1)
        w.num_sites_max.setValue(100)
        f = w.get_filters()
        assert f.num_sites_min == 1
        assert f.num_sites_max == 100


class TestSearchFiltersMechanical:
    def test_bulk_modulus(self, qtbot):
        w = SearchFiltersWidget()
        qtbot.addWidget(w)
        w.bulk_mod_min.setValue(50.0)
        w.bulk_mod_max.setValue(200.0)
        f = w.get_filters()
        assert f.bulk_modulus_min == pytest.approx(50.0)
        assert f.bulk_modulus_max == pytest.approx(200.0)

    def test_shear_modulus(self, qtbot):
        w = SearchFiltersWidget()
        qtbot.addWidget(w)
        w.shear_mod_min.setValue(10.0)
        f = w.get_filters()
        assert f.shear_modulus_min == pytest.approx(10.0)
        assert f.shear_modulus_max is None


class TestSearchFiltersMagnetic:
    def test_magnetic_ordering_combo(self, qtbot):
        w = SearchFiltersWidget()
        qtbot.addWidget(w)
        w.mag_ordering_combo.setCurrentText("FM")
        assert w.get_filters().magnetic_ordering == "FM"

    def test_magnetization_range(self, qtbot):
        w = SearchFiltersWidget()
        qtbot.addWidget(w)
        w.mag_min.setValue(0.5)
        w.mag_max.setValue(5.0)
        f = w.get_filters()
        assert f.total_magnetization_min == pytest.approx(0.5)
        assert f.total_magnetization_max == pytest.approx(5.0)


class TestSearchFiltersOther:
    def test_exclude_theoretical(self, qtbot):
        w = SearchFiltersWidget()
        qtbot.addWidget(w)
        w.exclude_theoretical_cb.setChecked(True)
        assert w.get_filters().exclude_theoretical is True


class TestSearchFiltersClear:
    def test_clear_filters_resets_all(self, qtbot):
        w = SearchFiltersWidget()
        qtbot.addWidget(w)

        # Set many filters
        w.band_gap_min.setValue(1.0)
        w.is_metal_combo.setCurrentIndex(1)
        w.form_energy_max.setValue(0.0)
        w.is_stable_cb.setChecked(True)
        w.space_group_spin.setValue(225)
        w.crystal_system_combo.setCurrentIndex(1)
        w.bulk_mod_min.setValue(100.0)
        w.mag_ordering_combo.setCurrentText("AFM")
        w.exclude_theoretical_cb.setChecked(True)

        assert w.get_filters().active_filter_count() > 0

        w.clear_filters()

        f = w.get_filters()
        assert f.active_filter_count() == 0
        assert f.band_gap_min is None
        assert f.is_metal is None
        assert f.is_stable is None
        assert f.space_group_number is None
        assert f.crystal_system is None
        assert f.magnetic_ordering is None
        assert f.exclude_theoretical is False


class TestSearchFiltersSignal:
    def test_filters_changed_signal(self, qtbot):
        w = SearchFiltersWidget()
        qtbot.addWidget(w)

        with qtbot.waitSignal(w.filters_changed, timeout=1000):
            w.band_gap_min.setValue(1.0)

    def test_active_filter_count_updates(self, qtbot):
        w = SearchFiltersWidget()
        qtbot.addWidget(w)

        w.band_gap_min.setValue(1.0)
        w.band_gap_max.setValue(5.0)
        w.is_metal_combo.setCurrentIndex(2)
        assert w.get_filters().active_filter_count() == 3

        badge_text = w._badge.text()
        assert "3" in badge_text


# ---------------------------------------------------------------------------
# DatabaseSelectorWidget tests
# ---------------------------------------------------------------------------

@pytest.fixture
def db_widget(qtbot, monkeypatch):
    """Create a DatabaseSelectorWidget with OPTIMADE loading disabled."""
    monkeypatch.setattr(
        DatabaseSelectorWidget, "_load_optimade_providers", lambda self: None
    )
    w = DatabaseSelectorWidget()
    qtbot.addWidget(w)
    return w


class TestDatabaseSelectorDefaults:
    def test_default_selected_databases(self, db_widget):
        selected = db_widget.get_selected_databases()
        # Free DBs should be selected, paid ones (mpds) not
        assert "jarvis" in selected
        assert "aflow" in selected
        assert "alexandria" in selected
        assert "materials_cloud" in selected
        assert "oqmd" in selected
        assert "mpds" not in selected

    def test_default_limit(self, db_widget):
        assert db_widget.get_limit() == 10

    def test_default_api_keys_empty(self, db_widget):
        keys = db_widget.get_api_keys()
        # Keys may be loaded from config, but should at least exist
        assert "mp_api_key" in keys
        assert "mpds_api_key" in keys


class TestDatabaseSelectorActions:
    def test_select_all(self, db_widget):
        db_widget._select_all()
        selected = db_widget.get_selected_databases()
        for db_id in ("jarvis", "aflow", "alexandria", "materials_cloud",
                       "oqmd", "materials_project", "mpds"):
            assert db_id in selected

    def test_clear_all(self, db_widget):
        db_widget._select_none()
        selected = db_widget.get_selected_databases()
        assert len(selected) == 0

    def test_selection_changed_signal(self, qtbot, db_widget):
        with qtbot.waitSignal(db_widget.selection_changed, timeout=1000):
            db_widget._select_all()

    def test_limit_spinner(self, db_widget):
        db_widget.limit_spinner.setValue(50)
        assert db_widget.get_limit() == 50
