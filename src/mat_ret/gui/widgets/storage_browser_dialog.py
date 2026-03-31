"""Dialog for browsing/querying stored materials."""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)
from PyQt6.QtCore import Qt


# Columns shown in the browse table
_COLUMNS = [
    ("record_id", "Record ID"),
    ("formula", "Formula"),
    ("source_database", "Source"),
    ("material_id", "Material ID"),
    ("space_group_number", "Space Group #"),
    ("crystal_system", "Crystal System"),
    ("band_gap", "Band Gap"),
    ("density", "Density"),
    ("cif_path", "CIF Path"),
    ("created_at", "Stored At"),
]


class StorageBrowserDialog(QDialog):
    """Browse and query stored materials."""

    def __init__(self, storage, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._storage = storage
        self._page = 0
        self._page_size = 50
        self._results: List[Dict[str, Any]] = []
        self.setWindowTitle("Browse Stored Materials")
        self.setMinimumSize(1000, 600)
        self._setup_ui()
        self._refresh()

    # -- UI --------------------------------------------------------------------

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(8)

        # -- Filter bar --------------------------------------------------------
        filter_bar = QHBoxLayout()

        filter_bar.addWidget(QLabel("Formula:"))
        self._formula_edit = QLineEdit()
        self._formula_edit.setPlaceholderText("e.g. SiO2")
        self._formula_edit.setMaximumWidth(140)
        filter_bar.addWidget(self._formula_edit)

        filter_bar.addWidget(QLabel("Source:"))
        self._source_combo = QComboBox()
        self._source_combo.addItem("All")
        self._source_combo.setMinimumWidth(120)
        filter_bar.addWidget(self._source_combo)

        filter_bar.addWidget(QLabel("Crystal System:"))
        self._crystal_combo = QComboBox()
        self._crystal_combo.addItems([
            "All", "Cubic", "Hexagonal", "Trigonal",
            "Tetragonal", "Orthorhombic", "Monoclinic", "Triclinic",
        ])
        filter_bar.addWidget(self._crystal_combo)

        filter_bar.addWidget(QLabel("Band Gap ≥"))
        self._bg_min = QLineEdit()
        self._bg_min.setMaximumWidth(60)
        filter_bar.addWidget(self._bg_min)
        filter_bar.addWidget(QLabel("≤"))
        self._bg_max = QLineEdit()
        self._bg_max.setMaximumWidth(60)
        filter_bar.addWidget(self._bg_max)

        self._search_btn = QPushButton("Search")
        self._search_btn.clicked.connect(self._on_search)
        filter_bar.addWidget(self._search_btn)

        self._clear_btn = QPushButton("Clear")
        self._clear_btn.clicked.connect(self._on_clear_filters)
        filter_bar.addWidget(self._clear_btn)

        filter_bar.addStretch()

        layout.addLayout(filter_bar)

        # -- Stats -------------------------------------------------------------
        stats_bar = QHBoxLayout()
        self._count_label = QLabel("0 materials stored")
        stats_bar.addWidget(self._count_label)
        stats_bar.addStretch()
        layout.addLayout(stats_bar)

        # -- Table -------------------------------------------------------------
        self._table = QTableWidget()
        self._table.setColumnCount(len(_COLUMNS))
        self._table.setHorizontalHeaderLabels([c[1] for c in _COLUMNS])
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.horizontalHeader().setStretchLastSection(True)
        self._table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        layout.addWidget(self._table, stretch=1)

        # -- Pagination --------------------------------------------------------
        page_bar = QHBoxLayout()
        self._prev_btn = QPushButton("◀ Previous")
        self._prev_btn.clicked.connect(self._prev_page)
        page_bar.addWidget(self._prev_btn)

        self._page_label = QLabel("Page 1")
        page_bar.addWidget(self._page_label)

        self._next_btn = QPushButton("Next ▶")
        self._next_btn.clicked.connect(self._next_page)
        page_bar.addWidget(self._next_btn)

        page_bar.addStretch()

        # -- Actions -----------------------------------------------------------
        self._open_cif_btn = QPushButton("Open CIF Location")
        self._open_cif_btn.clicked.connect(self._open_cif)
        page_bar.addWidget(self._open_cif_btn)

        self._delete_btn = QPushButton("Delete Selected")
        self._delete_btn.clicked.connect(self._delete_selected)
        page_bar.addWidget(self._delete_btn)

        self._export_btn = QPushButton("Export Results…")
        self._export_btn.clicked.connect(self._export_results)
        page_bar.addWidget(self._export_btn)

        layout.addLayout(page_bar)

    # -- data ------------------------------------------------------------------

    def _build_query_kwargs(self) -> Dict[str, Any]:
        kwargs: Dict[str, Any] = {
            "limit": self._page_size,
            "offset": self._page * self._page_size,
        }
        formula = self._formula_edit.text().strip()
        if formula:
            kwargs["formula"] = formula
        source = self._source_combo.currentText()
        if source and source != "All":
            kwargs["source_database"] = source
        crystal = self._crystal_combo.currentText()
        if crystal and crystal != "All":
            kwargs["crystal_system"] = crystal
        try:
            bg_min = float(self._bg_min.text())
            kwargs["band_gap_min"] = bg_min
        except (ValueError, TypeError):
            pass
        try:
            bg_max = float(self._bg_max.text())
            kwargs["band_gap_max"] = bg_max
        except (ValueError, TypeError):
            pass
        return kwargs

    def _refresh(self) -> None:
        if self._storage is None:
            self._count_label.setText("No storage backend active")
            return
        try:
            total = self._storage.count_materials()
            self._count_label.setText(f"{total} materials stored")
            kwargs = self._build_query_kwargs()
            self._results = self._storage.query_materials(**kwargs) if any(
                k not in ("limit", "offset") for k in kwargs
            ) else self._storage.list_materials(limit=kwargs["limit"], offset=kwargs["offset"])
            self._populate_table()
        except Exception as exc:
            self._count_label.setText(f"Error: {exc}")

    def _populate_table(self) -> None:
        self._table.setRowCount(len(self._results))
        for row_idx, mat in enumerate(self._results):
            for col_idx, (key, _) in enumerate(_COLUMNS):
                value = mat.get(key, "")
                if value is None:
                    value = ""
                item = QTableWidgetItem(str(value))
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self._table.setItem(row_idx, col_idx, item)
        self._page_label.setText(f"Page {self._page + 1}")
        self._prev_btn.setEnabled(self._page > 0)
        self._next_btn.setEnabled(len(self._results) == self._page_size)

    # -- slots -----------------------------------------------------------------

    def _on_search(self) -> None:
        self._page = 0
        self._refresh()

    def _on_clear_filters(self) -> None:
        self._formula_edit.clear()
        self._source_combo.setCurrentIndex(0)
        self._crystal_combo.setCurrentIndex(0)
        self._bg_min.clear()
        self._bg_max.clear()
        self._page = 0
        self._refresh()

    def _prev_page(self) -> None:
        if self._page > 0:
            self._page -= 1
            self._refresh()

    def _next_page(self) -> None:
        self._page += 1
        self._refresh()

    def _open_cif(self) -> None:
        row = self._table.currentRow()
        if row < 0 or row >= len(self._results):
            return
        mat = self._results[row]
        cif_path = mat.get("cif_path", "")
        if not cif_path:
            record_id = mat.get("record_id") or mat.get("_record_id", "")
            if record_id and self._storage:
                cif_path = self._storage.get_cif_path(record_id) or ""
        if cif_path and os.path.isfile(cif_path):
            folder = os.path.dirname(os.path.abspath(cif_path))
            import subprocess, sys
            if sys.platform == "linux":
                subprocess.Popen(["xdg-open", folder])
            elif sys.platform == "darwin":
                subprocess.Popen(["open", folder])
            elif sys.platform == "win32":
                subprocess.Popen(["explorer", folder])
        else:
            QMessageBox.information(self, "CIF Not Found", f"CIF file not found:\n{cif_path}")

    def _delete_selected(self) -> None:
        rows = sorted(set(idx.row() for idx in self._table.selectedIndexes()), reverse=True)
        if not rows:
            return
        reply = QMessageBox.question(
            self,
            "Confirm Delete",
            f"Delete {len(rows)} selected material(s) from storage?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        for row in rows:
            mat = self._results[row]
            record_id = mat.get("record_id") or mat.get("_record_id", "")
            if record_id and self._storage:
                self._storage.delete_material(record_id)
        self._refresh()

    def _export_results(self) -> None:
        from PyQt6.QtWidgets import QFileDialog
        import json
        path, _ = QFileDialog.getSaveFileName(self, "Export", "", "JSON (*.json);;CSV (*.csv)")
        if not path:
            return
        try:
            if path.endswith(".csv"):
                import csv
                with open(path, "w", newline="", encoding="utf-8") as f:
                    writer = csv.DictWriter(f, fieldnames=[c[0] for c in _COLUMNS])
                    writer.writeheader()
                    for mat in self._results:
                        writer.writerow({k: mat.get(k, "") for k, _ in _COLUMNS})
            else:
                with open(path, "w", encoding="utf-8") as f:
                    json.dump(self._results, f, indent=2, default=str)
            QMessageBox.information(self, "Exported", f"Exported to:\n{path}")
        except Exception as exc:
            QMessageBox.critical(self, "Export Failed", str(exc))
