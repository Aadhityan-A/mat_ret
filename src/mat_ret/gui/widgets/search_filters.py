"""
Search Filters Widget

Provides collapsible filter groups for constraining database searches by
electronic, energetic, structural, mechanical, magnetic, and other properties.
"""

from typing import Optional

import re

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QDoubleSpinBox, QSpinBox, QComboBox, QCheckBox, QPushButton, QLineEdit,
    QFrame, QSizePolicy,
)
from PyQt6.QtCore import pyqtSignal, Qt
from PyQt6.QtGui import QFont

from .collapsible import CollapsibleSection
from ...search import SearchFilters, CRYSTAL_SYSTEMS


def _parse_element_list(text: str):
    """Parse a free-text element list (e.g. ``"Fe, O"``) into symbols, or None."""
    tokens = [tok.strip() for tok in re.split(r"[,\s/]+", text or "") if tok.strip()]
    cleaned = []
    for tok in tokens:
        sym = tok[0].upper() + tok[1:].lower() if tok else tok
        if sym and sym not in cleaned:
            cleaned.append(sym)
    return cleaned or None

# Which databases natively support each filter group (for tooltips)
_DB_SUPPORT = {
    "Electronic": "Server-side: Materials Project. Post-filter: JARVIS, AFLOW, OQMD, Alexandria, Materials Cloud, OPTIMADE.",
    "Energetic": "Server-side: Materials Project, OQMD. Post-filter: JARVIS, AFLOW, Alexandria, Materials Cloud, OPTIMADE.",
    "Structural": "Server-side: Materials Project, AFLOW (space group, nelements), OPTIMADE (nelements/nsites). Post-filter: others.",
    "Composition": "Post-filter on all databases — require / exclude specific elements (uses each result's element set).",
    "Mechanical": "Post-filter on all databases (bulk/shear modulus returned by MP, JARVIS, AFLOW).",
    "Magnetic": "Server-side: Materials Project. Post-filter: JARVIS.",
    "Other": "Exclude theoretical: Materials Project only.",
}

# Section icons
_SECTION_ICONS = {
    "Electronic": "⚡",
    "Energetic": "🔋",
    "Structural": "🔬",
    "Composition": "🧪",
    "Mechanical": "⚙️",
    "Magnetic": "🧲",
    "Other": "📋",
}

_SPIN_SS = """
    QDoubleSpinBox, QSpinBox {
        padding: 4px 6px;
        border: 1px solid #d0d5dd;
        border-radius: 4px;
        font-size: 11px;
        background: #fafbfc;
    }
    QDoubleSpinBox:focus, QSpinBox:focus {
        border: 1.5px solid #1976D2;
        background: white;
    }
"""

_COMBO_SS = """
    QComboBox {
        padding: 4px 8px;
        border: 1px solid #d0d5dd;
        border-radius: 4px;
        font-size: 11px;
        background: #fafbfc;
    }
    QComboBox:focus { border: 1.5px solid #1976D2; background: white; }
    QComboBox::drop-down { border: none; }
"""

_LABEL_SS = "color: #444; font-size: 11px;"
_SEPARATOR_SS = "color: #999; font-size: 11px;"
_CHECKBOX_SS = "font-size: 11px; color: #444;"


def _make_double_spin(
    minimum: float = -9999.0,
    maximum: float = 9999.0,
    decimals: int = 3,
    suffix: str = "",
    special_value: str = "Any",
) -> QDoubleSpinBox:
    spin = QDoubleSpinBox()
    spin.setRange(minimum, maximum)
    spin.setDecimals(decimals)
    spin.setSuffix(suffix)
    spin.setSpecialValueText(special_value)
    spin.setValue(minimum)  # shows "Any"
    spin.setStyleSheet(_SPIN_SS)
    return spin


def _make_int_spin(
    minimum: int = 0,
    maximum: int = 9999,
    special_value: str = "Any",
) -> QSpinBox:
    spin = QSpinBox()
    spin.setRange(minimum, maximum)
    spin.setSpecialValueText(special_value)
    spin.setValue(minimum)
    spin.setStyleSheet(_SPIN_SS)
    return spin


def _label(text: str) -> QLabel:
    lbl = QLabel(text)
    lbl.setStyleSheet(_LABEL_SS)
    lbl.setFixedWidth(120)
    return lbl


def _sep() -> QLabel:
    lbl = QLabel("–")
    lbl.setStyleSheet(_SEPARATOR_SS)
    lbl.setFixedWidth(12)
    lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
    return lbl


class SearchFiltersWidget(QWidget):
    """Collapsible panel exposing all search filters for materials databases."""

    filters_changed = pyqtSignal()  # emitted whenever any filter value changes

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._setup_ui()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _setup_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(10, 6, 10, 10)
        outer.setSpacing(4)

        # Title + active count badge
        title_row = QHBoxLayout()
        title_row.setContentsMargins(2, 4, 2, 6)
        title = QLabel("Search Filters")
        title.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
        title.setStyleSheet("color: #1565C0;")
        title_row.addWidget(title)
        title_row.addStretch()

        self._badge = QLabel("0 active")
        self._badge.setStyleSheet(
            "background: #e3f2fd; color: #1565C0; padding: 2px 8px; "
            "border-radius: 10px; font-size: 10px; font-weight: bold;"
        )
        title_row.addWidget(self._badge)
        outer.addLayout(title_row)

        # --- Electronic ---
        sec = CollapsibleSection("Electronic", icon=_SECTION_ICONS["Electronic"], expanded=True)
        sec.setToolTip(_DB_SUPPORT["Electronic"])
        lay = sec.content_layout()

        row = QHBoxLayout()
        row.addWidget(_label("Band gap (eV):"))
        self.band_gap_min = _make_double_spin(minimum=-9999.0, maximum=100.0, suffix=" eV")
        self.band_gap_max = _make_double_spin(minimum=-9999.0, maximum=100.0, suffix=" eV")
        row.addWidget(self.band_gap_min)
        row.addWidget(_sep())
        row.addWidget(self.band_gap_max)
        lay.addLayout(row)

        row2 = QHBoxLayout()
        row2.addWidget(_label("Metallicity:"))
        self.is_metal_combo = QComboBox()
        self.is_metal_combo.addItems(["Any", "Metal", "Non-metal"])
        self.is_metal_combo.setStyleSheet(_COMBO_SS)
        row2.addWidget(self.is_metal_combo)
        row2.addStretch()
        lay.addLayout(row2)

        outer.addWidget(sec)

        # --- Energetic ---
        sec = CollapsibleSection("Energetic", icon=_SECTION_ICONS["Energetic"], expanded=False)
        sec.setToolTip(_DB_SUPPORT["Energetic"])
        lay = sec.content_layout()

        row = QHBoxLayout()
        row.addWidget(_label("Form. energy (eV/at):"))
        self.form_energy_min = _make_double_spin(suffix=" eV")
        self.form_energy_max = _make_double_spin(suffix=" eV")
        row.addWidget(self.form_energy_min)
        row.addWidget(_sep())
        row.addWidget(self.form_energy_max)
        lay.addLayout(row)

        row2 = QHBoxLayout()
        row2.addWidget(_label("E above hull ≤"))
        self.e_hull_max = _make_double_spin(minimum=-9999.0, maximum=10.0, suffix=" eV")
        row2.addWidget(self.e_hull_max)
        row2.addStretch()
        lay.addLayout(row2)

        self.is_stable_cb = QCheckBox("Stable only (Ehull = 0)")
        self.is_stable_cb.setStyleSheet(_CHECKBOX_SS)
        lay.addWidget(self.is_stable_cb)

        outer.addWidget(sec)

        # --- Structural ---
        sec = CollapsibleSection("Structural", icon=_SECTION_ICONS["Structural"], expanded=False)
        sec.setToolTip(_DB_SUPPORT["Structural"])
        lay = sec.content_layout()

        row = QHBoxLayout()
        row.addWidget(_label("Crystal system:"))
        self.crystal_system_combo = QComboBox()
        self.crystal_system_combo.addItem("Any", None)
        for cs in CRYSTAL_SYSTEMS:
            self.crystal_system_combo.addItem(cs.capitalize(), cs)
        self.crystal_system_combo.setStyleSheet(_COMBO_SS)
        row.addWidget(self.crystal_system_combo)
        row.addStretch()
        lay.addLayout(row)

        row2 = QHBoxLayout()
        row2.addWidget(_label("Space group #:"))
        self.space_group_spin = _make_int_spin(minimum=0, maximum=230)
        row2.addWidget(self.space_group_spin)
        row2.addStretch()
        lay.addLayout(row2)

        row3 = QHBoxLayout()
        row3.addWidget(_label("Density (g/cm³):"))
        self.density_min = _make_double_spin(minimum=-9999.0, maximum=100.0, suffix=" g/cm³")
        self.density_max = _make_double_spin(minimum=-9999.0, maximum=100.0, suffix=" g/cm³")
        row3.addWidget(self.density_min)
        row3.addWidget(_sep())
        row3.addWidget(self.density_max)
        lay.addLayout(row3)

        row4 = QHBoxLayout()
        row4.addWidget(_label("Volume (ų):"))
        self.volume_min = _make_double_spin(minimum=-9999.0, maximum=99999.0, suffix=" ų")
        self.volume_max = _make_double_spin(minimum=-9999.0, maximum=99999.0, suffix=" ų")
        row4.addWidget(self.volume_min)
        row4.addWidget(_sep())
        row4.addWidget(self.volume_max)
        lay.addLayout(row4)

        row5 = QHBoxLayout()
        row5.addWidget(_label("# Elements:"))
        self.num_elements_min = _make_int_spin(minimum=0, maximum=20)
        self.num_elements_max = _make_int_spin(minimum=0, maximum=20)
        row5.addWidget(self.num_elements_min)
        row5.addWidget(_sep())
        row5.addWidget(self.num_elements_max)
        lay.addLayout(row5)

        row6 = QHBoxLayout()
        row6.addWidget(_label("# Sites:"))
        self.num_sites_min = _make_int_spin(minimum=0, maximum=9999)
        self.num_sites_max = _make_int_spin(minimum=0, maximum=9999)
        row6.addWidget(self.num_sites_min)
        row6.addWidget(_sep())
        row6.addWidget(self.num_sites_max)
        lay.addLayout(row6)

        outer.addWidget(sec)

        # --- Composition ---
        sec = CollapsibleSection("Composition", icon=_SECTION_ICONS["Composition"], expanded=False)
        sec.setToolTip(_DB_SUPPORT["Composition"])
        lay = sec.content_layout()

        _line_ss = (
            "QLineEdit { padding: 4px 6px; border: 1px solid #d0d5dd; "
            "border-radius: 4px; font-size: 11px; background: #fafbfc; } "
            "QLineEdit:focus { border: 1.5px solid #1976D2; background: white; }"
        )

        row = QHBoxLayout()
        row.addWidget(_label("Must contain:"))
        self.include_elements_edit = QLineEdit()
        self.include_elements_edit.setPlaceholderText("e.g. Fe, O")
        self.include_elements_edit.setStyleSheet(_line_ss)
        row.addWidget(self.include_elements_edit)
        lay.addLayout(row)

        row2 = QHBoxLayout()
        row2.addWidget(_label("Exclude:"))
        self.exclude_elements_edit = QLineEdit()
        self.exclude_elements_edit.setPlaceholderText("e.g. Pb, Hg")
        self.exclude_elements_edit.setStyleSheet(_line_ss)
        row2.addWidget(self.exclude_elements_edit)
        lay.addLayout(row2)

        outer.addWidget(sec)

        # --- Mechanical ---
        sec = CollapsibleSection("Mechanical", icon=_SECTION_ICONS["Mechanical"], expanded=False)
        sec.setToolTip(_DB_SUPPORT["Mechanical"])
        lay = sec.content_layout()

        row = QHBoxLayout()
        row.addWidget(_label("Bulk mod. (GPa):"))
        self.bulk_mod_min = _make_double_spin(minimum=-9999.0, maximum=9999.0, suffix=" GPa")
        self.bulk_mod_max = _make_double_spin(minimum=-9999.0, maximum=9999.0, suffix=" GPa")
        row.addWidget(self.bulk_mod_min)
        row.addWidget(_sep())
        row.addWidget(self.bulk_mod_max)
        lay.addLayout(row)

        row2 = QHBoxLayout()
        row2.addWidget(_label("Shear mod. (GPa):"))
        self.shear_mod_min = _make_double_spin(minimum=-9999.0, maximum=9999.0, suffix=" GPa")
        self.shear_mod_max = _make_double_spin(minimum=-9999.0, maximum=9999.0, suffix=" GPa")
        row2.addWidget(self.shear_mod_min)
        row2.addWidget(_sep())
        row2.addWidget(self.shear_mod_max)
        lay.addLayout(row2)

        outer.addWidget(sec)

        # --- Magnetic ---
        sec = CollapsibleSection("Magnetic", icon=_SECTION_ICONS["Magnetic"], expanded=False)
        sec.setToolTip(_DB_SUPPORT["Magnetic"])
        lay = sec.content_layout()

        row = QHBoxLayout()
        row.addWidget(_label("Ordering:"))
        self.mag_ordering_combo = QComboBox()
        self.mag_ordering_combo.addItems(["Any", "FM", "AFM", "FiM", "NM"])
        self.mag_ordering_combo.setStyleSheet(_COMBO_SS)
        row.addWidget(self.mag_ordering_combo)
        row.addStretch()
        lay.addLayout(row)

        row2 = QHBoxLayout()
        row2.addWidget(_label("Tot. magnet. (μB):"))
        self.mag_min = _make_double_spin(minimum=-9999.0, maximum=9999.0, suffix=" μB")
        self.mag_max = _make_double_spin(minimum=-9999.0, maximum=9999.0, suffix=" μB")
        row2.addWidget(self.mag_min)
        row2.addWidget(_sep())
        row2.addWidget(self.mag_max)
        lay.addLayout(row2)

        outer.addWidget(sec)

        # --- Other ---
        sec = CollapsibleSection("Other", icon=_SECTION_ICONS["Other"], expanded=False)
        sec.setToolTip(_DB_SUPPORT["Other"])
        lay = sec.content_layout()

        self.exclude_theoretical_cb = QCheckBox("Exclude theoretical structures")
        self.exclude_theoretical_cb.setStyleSheet(_CHECKBOX_SS)
        lay.addWidget(self.exclude_theoretical_cb)

        outer.addWidget(sec)

        # Clear button — outline style
        btn_row = QHBoxLayout()
        btn_row.setContentsMargins(0, 6, 0, 0)
        clear_btn = QPushButton("Clear All Filters")
        clear_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: #c62828;
                border: 1.5px solid #ef9a9a;
                padding: 5px 16px;
                border-radius: 4px;
                font-size: 11px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #ffebee;
                border-color: #c62828;
            }
        """)
        clear_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        clear_btn.clicked.connect(self.clear_filters)
        btn_row.addStretch()
        btn_row.addWidget(clear_btn)
        btn_row.addStretch()
        outer.addLayout(btn_row)

        outer.addStretch()

        # Connect all widgets to _on_change
        self._connect_signals()

    def _connect_signals(self) -> None:
        for spin in (
            self.band_gap_min, self.band_gap_max,
            self.form_energy_min, self.form_energy_max,
            self.e_hull_max,
            self.density_min, self.density_max,
            self.volume_min, self.volume_max,
            self.bulk_mod_min, self.bulk_mod_max,
            self.shear_mod_min, self.shear_mod_max,
            self.mag_min, self.mag_max,
        ):
            spin.valueChanged.connect(self._on_change)

        for spin in (
            self.space_group_spin,
            self.num_elements_min, self.num_elements_max,
            self.num_sites_min, self.num_sites_max,
        ):
            spin.valueChanged.connect(self._on_change)

        for combo in (self.is_metal_combo, self.crystal_system_combo, self.mag_ordering_combo):
            combo.currentIndexChanged.connect(self._on_change)

        for cb in (self.is_stable_cb, self.exclude_theoretical_cb):
            cb.stateChanged.connect(self._on_change)

        for edit in (self.include_elements_edit, self.exclude_elements_edit):
            edit.textChanged.connect(self._on_change)

    def _on_change(self, *_args) -> None:
        f = self.get_filters()
        count = f.active_filter_count()
        self._badge.setText(f"{count} active")
        self._badge.setStyleSheet(
            f"background: {'#ffcdd2' if count else '#e3f2fd'}; "
            f"color: {'#c62828' if count else '#1565C0'}; "
            "padding: 2px 8px; border-radius: 10px; font-size: 10px; font-weight: bold;"
        )
        self.filters_changed.emit()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def _opt_float(self, spin: QDoubleSpinBox) -> Optional[float]:
        """Return None when the spin box shows its special 'Any' value."""
        if spin.value() <= spin.minimum():
            return None
        return spin.value()

    def _opt_int(self, spin: QSpinBox) -> Optional[int]:
        if spin.value() <= spin.minimum():
            return None
        return spin.value()

    def get_filters(self) -> SearchFilters:
        """Collect all widget values into a SearchFilters instance."""
        is_metal: Optional[bool] = None
        idx = self.is_metal_combo.currentIndex()
        if idx == 1:
            is_metal = True
        elif idx == 2:
            is_metal = False

        crystal_system: Optional[str] = self.crystal_system_combo.currentData()

        mag_ordering: Optional[str] = None
        mag_text = self.mag_ordering_combo.currentText()
        if mag_text != "Any":
            mag_ordering = mag_text

        return SearchFilters(
            band_gap_min=self._opt_float(self.band_gap_min),
            band_gap_max=self._opt_float(self.band_gap_max),
            is_metal=is_metal,
            formation_energy_min=self._opt_float(self.form_energy_min),
            formation_energy_max=self._opt_float(self.form_energy_max),
            energy_above_hull_max=self._opt_float(self.e_hull_max),
            is_stable=True if self.is_stable_cb.isChecked() else None,
            density_min=self._opt_float(self.density_min),
            density_max=self._opt_float(self.density_max),
            volume_min=self._opt_float(self.volume_min),
            volume_max=self._opt_float(self.volume_max),
            space_group_number=self._opt_int(self.space_group_spin),
            crystal_system=crystal_system,
            num_elements_min=self._opt_int(self.num_elements_min),
            num_elements_max=self._opt_int(self.num_elements_max),
            num_sites_min=self._opt_int(self.num_sites_min),
            num_sites_max=self._opt_int(self.num_sites_max),
            include_elements=_parse_element_list(self.include_elements_edit.text()),
            exclude_elements=_parse_element_list(self.exclude_elements_edit.text()),
            bulk_modulus_min=self._opt_float(self.bulk_mod_min),
            bulk_modulus_max=self._opt_float(self.bulk_mod_max),
            shear_modulus_min=self._opt_float(self.shear_mod_min),
            shear_modulus_max=self._opt_float(self.shear_mod_max),
            magnetic_ordering=mag_ordering,
            total_magnetization_min=self._opt_float(self.mag_min),
            total_magnetization_max=self._opt_float(self.mag_max),
            exclude_theoretical=self.exclude_theoretical_cb.isChecked(),
        )

    def clear_filters(self) -> None:
        """Reset every filter widget to its default (inactive) state."""
        for spin in (
            self.band_gap_min, self.band_gap_max,
            self.form_energy_min, self.form_energy_max,
            self.e_hull_max,
            self.density_min, self.density_max,
            self.volume_min, self.volume_max,
            self.bulk_mod_min, self.bulk_mod_max,
            self.shear_mod_min, self.shear_mod_max,
            self.mag_min, self.mag_max,
        ):
            spin.setValue(spin.minimum())

        for spin in (
            self.space_group_spin,
            self.num_elements_min, self.num_elements_max,
            self.num_sites_min, self.num_sites_max,
        ):
            spin.setValue(spin.minimum())

        self.is_metal_combo.setCurrentIndex(0)
        self.crystal_system_combo.setCurrentIndex(0)
        self.mag_ordering_combo.setCurrentIndex(0)
        self.is_stable_cb.setChecked(False)
        self.exclude_theoretical_cb.setChecked(False)
        self.include_elements_edit.clear()
        self.exclude_elements_edit.clear()
