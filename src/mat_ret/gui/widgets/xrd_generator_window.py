"""XRD generator window for interactive CIF/structure diffraction analysis."""

from __future__ import annotations

from pathlib import Path
from typing import Dict, Optional

from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qtagg import NavigationToolbar2QT as NavigationToolbar
from matplotlib.figure import Figure
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSplitter,
    QStatusBar,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ...xrd import (
    XRDConfig,
    XRDResult,
    export_xrd_pattern_csv,
    export_xrd_peaks_csv,
    generate_xrd_from_cif,
    generate_xrd_from_structure,
    list_supported_radiations,
)


PROFILE_OPTIONS = [
    ("Stick", "stick"),
    ("Gaussian", "gaussian"),
    ("Lorentzian", "lorentzian"),
    ("Pseudo-Voigt", "pseudo_voigt"),
]


class XRDGeneratorWindow(QMainWindow):
    """Interactive XRD pattern generation and analysis window."""

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.current_material: Optional[Dict] = None
        self.active_structure = None
        self.current_result: Optional[XRDResult] = None
        self.active_source_mode: str = "none"

        self.setWindowTitle("XRD Generator")
        self.setMinimumSize(1200, 800)
        self.resize(1320, 900)

        self._setup_ui()
        self._clear_plot()
        self._update_context_label()
        self._update_control_states()

    def _setup_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(10)

        title = QLabel("XRD Generator")
        title.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        title.setStyleSheet("color: #1976D2;")
        root.addWidget(title)

        controls_frame = QFrame()
        controls_layout = QHBoxLayout(controls_frame)
        controls_layout.setContentsMargins(0, 0, 0, 0)
        controls_layout.setSpacing(10)

        controls_layout.addWidget(self._create_source_group(), stretch=2)
        controls_layout.addWidget(self._create_settings_group(), stretch=3)
        controls_layout.addWidget(self._create_peak_group(), stretch=3)
        root.addWidget(controls_frame)

        button_row = QHBoxLayout()
        button_row.setSpacing(10)

        self.generate_button = QPushButton("Generate")
        self.generate_button.setStyleSheet(
            """
            QPushButton {
                background-color: #2E7D32;
                color: white;
                padding: 8px 18px;
                border-radius: 5px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #1B5E20; }
            """
        )
        self.generate_button.clicked.connect(self._generate_pattern)
        button_row.addWidget(self.generate_button)

        self.clear_button = QPushButton("Clear")
        self.clear_button.clicked.connect(self._clear_result)
        button_row.addWidget(self.clear_button)

        self.export_plot_button = QPushButton("Export Plot")
        self.export_plot_button.clicked.connect(self._export_plot)
        self.export_plot_button.setEnabled(False)
        button_row.addWidget(self.export_plot_button)

        self.export_pattern_button = QPushButton("Export Pattern CSV")
        self.export_pattern_button.clicked.connect(self._export_pattern_csv)
        self.export_pattern_button.setEnabled(False)
        button_row.addWidget(self.export_pattern_button)

        self.export_peaks_button = QPushButton("Export Peaks CSV")
        self.export_peaks_button.clicked.connect(self._export_peaks_csv)
        self.export_peaks_button.setEnabled(False)
        button_row.addWidget(self.export_peaks_button)

        button_row.addStretch()
        root.addLayout(button_row)

        output_splitter = QSplitter(Qt.Orientation.Horizontal)
        output_splitter.addWidget(self._create_plot_panel())
        output_splitter.addWidget(self._create_peak_table_panel())
        output_splitter.setSizes([850, 420])
        root.addWidget(output_splitter, stretch=1)

        self.setStatusBar(QStatusBar())
        self.statusBar().showMessage("Ready. Select CIF or use current structure and click Generate.")

    def _create_source_group(self) -> QGroupBox:
        group = QGroupBox("Source")
        layout = QVBoxLayout(group)
        layout.setSpacing(8)

        cif_row = QHBoxLayout()
        self.cif_path_input = QLineEdit()
        self.cif_path_input.setPlaceholderText("Select a CIF file")
        self.cif_path_input.textChanged.connect(self._on_cif_path_changed)
        cif_row.addWidget(self.cif_path_input, stretch=1)

        browse = QPushButton("Browse...")
        browse.clicked.connect(self._browse_cif_file)
        cif_row.addWidget(browse)
        layout.addLayout(cif_row)

        self.use_structure_button = QPushButton("Use Current Selected Structure")
        self.use_structure_button.clicked.connect(self._use_current_structure)
        layout.addWidget(self.use_structure_button)

        self.source_mode_label = QLabel("Active source: none")
        self.source_mode_label.setStyleSheet("color: #555; font-size: 11px;")
        layout.addWidget(self.source_mode_label)

        self.context_label = QLabel("")
        self.context_label.setWordWrap(True)
        self.context_label.setStyleSheet("color: #333; font-size: 11px;")
        layout.addWidget(self.context_label)

        layout.addStretch()
        return group

    def _create_settings_group(self) -> QGroupBox:
        group = QGroupBox("Pattern Settings")
        layout = QGridLayout(group)
        layout.setHorizontalSpacing(8)
        layout.setVerticalSpacing(6)

        self.radiation_combo = QComboBox()
        for radiation in list_supported_radiations():
            self.radiation_combo.addItem(radiation)
        self.radiation_combo.setCurrentText("CuKa")
        layout.addWidget(QLabel("Radiation"), 0, 0)
        layout.addWidget(self.radiation_combo, 0, 1)

        self.custom_wavelength_check = QCheckBox("Custom wavelength (A)")
        self.custom_wavelength_check.toggled.connect(self._update_control_states)
        layout.addWidget(self.custom_wavelength_check, 1, 0)

        self.custom_wavelength_spin = QDoubleSpinBox()
        self.custom_wavelength_spin.setRange(0.1, 5.0)
        self.custom_wavelength_spin.setDecimals(5)
        self.custom_wavelength_spin.setSingleStep(0.0001)
        self.custom_wavelength_spin.setValue(1.54184)
        layout.addWidget(self.custom_wavelength_spin, 1, 1)

        self.two_theta_min_spin = QDoubleSpinBox()
        self.two_theta_min_spin.setRange(0.0, 180.0)
        self.two_theta_min_spin.setDecimals(2)
        self.two_theta_min_spin.setValue(5.0)
        layout.addWidget(QLabel("2theta min (deg)"), 2, 0)
        layout.addWidget(self.two_theta_min_spin, 2, 1)

        self.two_theta_max_spin = QDoubleSpinBox()
        self.two_theta_max_spin.setRange(0.1, 180.0)
        self.two_theta_max_spin.setDecimals(2)
        self.two_theta_max_spin.setValue(90.0)
        layout.addWidget(QLabel("2theta max (deg)"), 3, 0)
        layout.addWidget(self.two_theta_max_spin, 3, 1)

        self.two_theta_step_spin = QDoubleSpinBox()
        self.two_theta_step_spin.setRange(0.001, 1.0)
        self.two_theta_step_spin.setDecimals(3)
        self.two_theta_step_spin.setSingleStep(0.001)
        self.two_theta_step_spin.setValue(0.02)
        layout.addWidget(QLabel("2theta step (deg)"), 4, 0)
        layout.addWidget(self.two_theta_step_spin, 4, 1)

        self.profile_combo = QComboBox()
        for label, value in PROFILE_OPTIONS:
            self.profile_combo.addItem(label, value)
        self.profile_combo.setCurrentIndex(3)
        self.profile_combo.currentIndexChanged.connect(self._update_control_states)
        layout.addWidget(QLabel("Profile model"), 5, 0)
        layout.addWidget(self.profile_combo, 5, 1)

        self.fwhm_spin = QDoubleSpinBox()
        self.fwhm_spin.setRange(0.001, 5.0)
        self.fwhm_spin.setDecimals(3)
        self.fwhm_spin.setSingleStep(0.005)
        self.fwhm_spin.setValue(0.15)
        layout.addWidget(QLabel("FWHM (deg)"), 6, 0)
        layout.addWidget(self.fwhm_spin, 6, 1)

        self.eta_spin = QDoubleSpinBox()
        self.eta_spin.setRange(0.0, 1.0)
        self.eta_spin.setDecimals(3)
        self.eta_spin.setSingleStep(0.05)
        self.eta_spin.setValue(0.5)
        layout.addWidget(QLabel("Pseudo-Voigt eta"), 7, 0)
        layout.addWidget(self.eta_spin, 7, 1)

        return group

    def _create_peak_group(self) -> QGroupBox:
        group = QGroupBox("Peak Finder")
        form = QFormLayout(group)
        form.setSpacing(6)

        self.peak_enable_check = QCheckBox("Enable peak detection")
        self.peak_enable_check.setChecked(True)
        self.peak_enable_check.toggled.connect(self._update_control_states)
        form.addRow(self.peak_enable_check)

        self.peak_height_spin = QDoubleSpinBox()
        self.peak_height_spin.setRange(0.0, 1000.0)
        self.peak_height_spin.setDecimals(2)
        self.peak_height_spin.setValue(5.0)
        form.addRow("Min height", self.peak_height_spin)

        self.peak_prominence_spin = QDoubleSpinBox()
        self.peak_prominence_spin.setRange(0.0, 1000.0)
        self.peak_prominence_spin.setDecimals(2)
        self.peak_prominence_spin.setValue(2.0)
        form.addRow("Prominence", self.peak_prominence_spin)

        self.peak_distance_spin = QDoubleSpinBox()
        self.peak_distance_spin.setRange(0.0, 20.0)
        self.peak_distance_spin.setDecimals(3)
        self.peak_distance_spin.setValue(0.10)
        form.addRow("Min distance (deg)", self.peak_distance_spin)

        self.peak_width_spin = QDoubleSpinBox()
        self.peak_width_spin.setRange(0.0, 20.0)
        self.peak_width_spin.setDecimals(3)
        self.peak_width_spin.setValue(0.0)
        form.addRow("Min width (deg)", self.peak_width_spin)

        self.peak_match_tol_spin = QDoubleSpinBox()
        self.peak_match_tol_spin.setRange(0.01, 5.0)
        self.peak_match_tol_spin.setDecimals(3)
        self.peak_match_tol_spin.setValue(0.25)
        form.addRow("Match tolerance (deg)", self.peak_match_tol_spin)

        return group

    def _create_plot_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)

        self.figure = Figure(figsize=(8, 6), dpi=100)
        self.canvas = FigureCanvas(self.figure)
        self.toolbar = NavigationToolbar(self.canvas, panel)
        self.axes = self.figure.add_subplot(111)

        layout.addWidget(self.toolbar)
        layout.addWidget(self.canvas, stretch=1)
        return panel

    def _create_peak_table_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)

        label = QLabel("Detected Peaks")
        label.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        layout.addWidget(label)

        self.peaks_table = QTableWidget(0, 5)
        self.peaks_table.setHorizontalHeaderLabels(
            [
                "2theta (deg)",
                "Intensity",
                "d (A)",
                "HKLs",
                "Stick 2theta",
            ]
        )
        self.peaks_table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.peaks_table, stretch=1)
        return panel

    def set_current_material(self, material: Optional[Dict]) -> None:
        """Update the selected material context from main window."""
        self.current_material = material
        if self.active_source_mode == "structure":
            self.active_structure = material.get("structure") if material else None
        self._update_context_label()

    def _browse_cif_file(self) -> None:
        filename, _ = QFileDialog.getOpenFileName(
            self,
            "Select CIF file",
            "",
            "CIF Files (*.cif);;All Files (*)",
        )
        if filename:
            self.cif_path_input.setText(filename)
            self.active_source_mode = "cif"
            self._update_context_label()

    def _on_cif_path_changed(self, text: str) -> None:
        if text.strip():
            self.active_source_mode = "cif"
        elif self.active_source_mode == "cif":
            self.active_source_mode = "none"
        self._update_context_label()

    def _use_current_structure(self) -> None:
        if not self.current_material:
            QMessageBox.warning(self, "No Material Selected", "Select a material in the main window first.")
            return
        structure = self.current_material.get("structure")
        if structure is None:
            QMessageBox.warning(self, "No Structure", "The selected material has no structure object.")
            return
        self.active_structure = structure
        self.active_source_mode = "structure"
        self._update_context_label()
        self.statusBar().showMessage("Using current selected structure as XRD source.")

    def _update_context_label(self) -> None:
        if not self.current_material:
            self.context_label.setText("Current material: none")
            self.use_structure_button.setEnabled(False)
        else:
            formula = self.current_material.get("formula", "Unknown")
            material_id = self.current_material.get("material_id", "")
            has_structure = self.current_material.get("structure") is not None
            suffix = f" ({material_id})" if material_id else ""
            self.context_label.setText(
                f"Current material: {formula}{suffix} | Structure: {'available' if has_structure else 'missing'}"
            )
            self.use_structure_button.setEnabled(has_structure)
        self.source_mode_label.setText(f"Active source: {self.active_source_mode}")

    def _update_control_states(self) -> None:
        self.custom_wavelength_spin.setEnabled(self.custom_wavelength_check.isChecked())

        profile_value = self.profile_combo.currentData()
        uses_fwhm = profile_value in ("gaussian", "lorentzian", "pseudo_voigt")
        self.fwhm_spin.setEnabled(uses_fwhm)
        self.eta_spin.setEnabled(profile_value == "pseudo_voigt")

        peak_controls_enabled = self.peak_enable_check.isChecked()
        self.peak_height_spin.setEnabled(peak_controls_enabled)
        self.peak_prominence_spin.setEnabled(peak_controls_enabled)
        self.peak_distance_spin.setEnabled(peak_controls_enabled)
        self.peak_width_spin.setEnabled(peak_controls_enabled)
        self.peak_match_tol_spin.setEnabled(peak_controls_enabled)

    def _build_config(self) -> XRDConfig:
        return XRDConfig(
            radiation=self.radiation_combo.currentText(),
            custom_wavelength=(
                self.custom_wavelength_spin.value() if self.custom_wavelength_check.isChecked() else None
            ),
            two_theta_min=self.two_theta_min_spin.value(),
            two_theta_max=self.two_theta_max_spin.value(),
            two_theta_step=self.two_theta_step_spin.value(),
            profile=self.profile_combo.currentData(),
            fwhm=self.fwhm_spin.value(),
            eta=self.eta_spin.value(),
            peak_finder_enabled=self.peak_enable_check.isChecked(),
            peak_min_height=self.peak_height_spin.value(),
            peak_prominence=self.peak_prominence_spin.value(),
            peak_distance=self.peak_distance_spin.value(),
            peak_width=self.peak_width_spin.value(),
            peak_match_tolerance=self.peak_match_tol_spin.value(),
        )

    def _generate_pattern(self) -> None:
        config = self._build_config()
        try:
            if self.active_source_mode == "structure":
                if self.active_structure is None:
                    QMessageBox.warning(self, "No Active Structure", "Select a valid structure source first.")
                    return
                result = generate_xrd_from_structure(self.active_structure, config=config)
                result.source = "selected_structure"
            elif self.active_source_mode == "cif":
                cif_path = self.cif_path_input.text().strip()
                if not cif_path:
                    QMessageBox.warning(self, "No CIF File", "Select a CIF file first.")
                    return
                result = generate_xrd_from_cif(cif_path, config=config)
            else:
                QMessageBox.warning(
                    self,
                    "No Source Selected",
                    "Use a CIF file or click 'Use Current Selected Structure' before generating.",
                )
                return

            self.current_result = result
            self._plot_result(result)
            self._populate_peaks_table(result)
            self.export_plot_button.setEnabled(True)
            self.export_pattern_button.setEnabled(True)
            self.export_peaks_button.setEnabled(True)

            self.statusBar().showMessage(
                f"Generated XRD using {result.radiation} ({result.wavelength:.5f} A); "
                f"{len(result.peaks)} peaks detected."
            )
        except Exception as exc:
            QMessageBox.critical(self, "XRD Generation Error", str(exc))

    def _plot_result(self, result: XRDResult) -> None:
        self.axes.clear()

        self.axes.plot(
            result.two_theta_profile,
            result.intensity_profile,
            color="#1565C0",
            linewidth=1.4,
            label="Profile",
        )
        self.axes.vlines(
            result.two_theta_stick,
            0.0,
            result.intensity_stick,
            color="#D32F2F",
            linewidth=0.8,
            alpha=0.75,
            label="Bragg sticks",
        )
        if result.peaks:
            x_vals = [peak.two_theta for peak in result.peaks]
            y_vals = [peak.intensity for peak in result.peaks]
            self.axes.scatter(x_vals, y_vals, s=22, color="#2E7D32", marker="o", label="Detected peaks")

        self.axes.set_xlabel("2theta (deg)")
        self.axes.set_ylabel("Relative intensity")
        self.axes.set_xlim(result.config.two_theta_min, result.config.two_theta_max)
        self.axes.set_ylim(0, 105)
        self.axes.grid(True, alpha=0.25)
        self.axes.legend(loc="upper right", fontsize=9)
        self.axes.set_title(
            f"XRD Pattern | Radiation: {result.radiation} ({result.wavelength:.5f} A) | "
            f"Profile: {result.config.profile}"
        )
        self.figure.tight_layout()
        self.canvas.draw_idle()

    def _populate_peaks_table(self, result: XRDResult) -> None:
        peaks = result.peaks
        self.peaks_table.setRowCount(len(peaks))
        for row, peak in enumerate(peaks):
            values = [
                f"{peak.two_theta:.4f}",
                f"{peak.intensity:.2f}",
                "" if peak.d_spacing is None else f"{peak.d_spacing:.4f}",
                peak.hkls,
                "" if peak.matched_stick_two_theta is None else f"{peak.matched_stick_two_theta:.4f}",
            ]
            for col, value in enumerate(values):
                self.peaks_table.setItem(row, col, QTableWidgetItem(value))
        self.peaks_table.resizeColumnsToContents()

    def _clear_result(self) -> None:
        self.current_result = None
        self.peaks_table.setRowCount(0)
        self._clear_plot()
        self.export_plot_button.setEnabled(False)
        self.export_pattern_button.setEnabled(False)
        self.export_peaks_button.setEnabled(False)
        self.statusBar().showMessage("Cleared XRD results.")

    def _clear_plot(self) -> None:
        self.axes.clear()
        self.axes.set_xlabel("2theta (deg)")
        self.axes.set_ylabel("Relative intensity")
        self.axes.set_title("No XRD pattern generated")
        self.axes.grid(True, alpha=0.25)
        self.figure.tight_layout()
        self.canvas.draw_idle()

    def _export_plot(self) -> None:
        if self.current_result is None:
            QMessageBox.information(self, "No Result", "Generate a pattern first.")
            return
        filename, _ = QFileDialog.getSaveFileName(
            self,
            "Export Plot",
            "xrd_pattern.png",
            "PNG (*.png);;SVG (*.svg);;PDF (*.pdf)",
        )
        if not filename:
            return
        self.figure.savefig(filename, dpi=300, bbox_inches="tight")
        self.statusBar().showMessage(f"Plot exported: {filename}")

    def _export_pattern_csv(self) -> None:
        if self.current_result is None:
            QMessageBox.information(self, "No Result", "Generate a pattern first.")
            return
        filename, _ = QFileDialog.getSaveFileName(
            self,
            "Export Pattern CSV",
            "xrd_pattern.csv",
            "CSV Files (*.csv)",
        )
        if not filename:
            return
        export_xrd_pattern_csv(self.current_result, Path(filename))
        self.statusBar().showMessage(f"Pattern exported: {filename}")

    def _export_peaks_csv(self) -> None:
        if self.current_result is None:
            QMessageBox.information(self, "No Result", "Generate a pattern first.")
            return
        filename, _ = QFileDialog.getSaveFileName(
            self,
            "Export Peaks CSV",
            "xrd_peaks.csv",
            "CSV Files (*.csv)",
        )
        if not filename:
            return
        export_xrd_peaks_csv(self.current_result, Path(filename))
        self.statusBar().showMessage(f"Peaks exported: {filename}")
