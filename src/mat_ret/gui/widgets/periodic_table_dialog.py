"""Periodic table element picker dialog for GUI search."""

from __future__ import annotations

from typing import Dict, Iterable, List, Optional

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
)
from pymatgen.core.periodic_table import Element

from ...search import format_chemsys


class PeriodicTableDialog(QDialog):
    """Periodic-table selector for element-set search."""

    def __init__(self, parent=None, selected_elements: Optional[Iterable[str]] = None):
        super().__init__(parent)
        self.setWindowTitle("Select Elements")
        self.setMinimumSize(1000, 640)

        self._buttons: Dict[str, QPushButton] = {}
        self._atomic_numbers: Dict[str, int] = {}

        self._build_ui()

        if selected_elements:
            for raw in selected_elements:
                symbol = str(raw or "").strip()
                if symbol in self._buttons:
                    self._buttons[symbol].setChecked(True)

        self._update_summary()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        title = QLabel("Choose Elements for Contains-All Search")
        title.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        layout.addWidget(title)

        subtitle = QLabel("Select one or more elements. Search uses contains-all semantics across supported databases.")
        subtitle.setWordWrap(True)
        subtitle.setStyleSheet("color: #444;")
        layout.addWidget(subtitle)

        self._summary_label = QLabel()
        self._summary_label.setStyleSheet("font-weight: bold;")
        layout.addWidget(self._summary_label)

        self._chemsys_label = QLabel()
        self._chemsys_label.setStyleSheet("color: #333;")
        layout.addWidget(self._chemsys_label)

        grid_frame = QFrame()
        grid_frame.setStyleSheet("QFrame { background: #f8f9fb; border: 1px solid #dde3ea; border-radius: 8px; }")
        grid_layout = QGridLayout(grid_frame)
        grid_layout.setContentsMargins(8, 8, 8, 8)
        grid_layout.setHorizontalSpacing(3)
        grid_layout.setVerticalSpacing(3)

        for group in range(1, 19):
            group_label = QLabel(str(group))
            group_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            group_label.setStyleSheet("font-size: 10px; color: #506070;")
            grid_layout.addWidget(group_label, 0, group)

        for period in range(1, 8):
            period_label = QLabel(str(period))
            period_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            period_label.setStyleSheet("font-size: 10px; color: #506070;")
            grid_layout.addWidget(period_label, period, 0)

        ln_label = QLabel("Lanthanides")
        ln_label.setStyleSheet("font-size: 10px; color: #506070;")
        grid_layout.addWidget(ln_label, 9, 0, 1, 3)

        ac_label = QLabel("Actinides")
        ac_label.setStyleSheet("font-size: 10px; color: #506070;")
        grid_layout.addWidget(ac_label, 11, 0, 1, 3)

        for atomic_number in range(1, 119):
            element = Element.from_Z(atomic_number)
            row, column = self._grid_position(element, atomic_number)
            button = QPushButton(element.symbol)
            button.setCheckable(True)
            button.setFixedSize(44, 30)
            button.setToolTip(f"{element.long_name} ({element.symbol})")
            button.setStyleSheet(
                """
                QPushButton {
                    border: 1px solid #bbc6d0;
                    border-radius: 4px;
                    background: white;
                    font-weight: 600;
                    font-size: 11px;
                }
                QPushButton:hover {
                    border-color: #1976D2;
                    background: #eef4fb;
                }
                QPushButton:checked {
                    background: #1976D2;
                    color: white;
                    border-color: #12579c;
                }
                """
            )
            button.toggled.connect(self._update_summary)

            self._buttons[element.symbol] = button
            self._atomic_numbers[element.symbol] = atomic_number
            grid_layout.addWidget(button, row, column)

        layout.addWidget(grid_frame, 1)

        controls = QHBoxLayout()
        controls.setSpacing(8)

        clear_button = QPushButton("Clear")
        clear_button.clicked.connect(self._clear_selection)
        controls.addWidget(clear_button)
        controls.addStretch()

        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        apply_button = button_box.button(QDialogButtonBox.StandardButton.Ok)
        if apply_button is not None:
            apply_button.setText("Apply")
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        controls.addWidget(button_box)

        layout.addLayout(controls)

    def _grid_position(self, element: Element, atomic_number: int) -> tuple[int, int]:
        if element.is_lanthanoid:
            return 10, atomic_number - 57 + 4
        if element.is_actinoid:
            return 12, atomic_number - 89 + 4

        row = int(element.row)
        column = int(element.group)
        return row, column

    def _selected_symbols(self) -> List[str]:
        selected = [
            symbol
            for symbol, button in self._buttons.items()
            if button.isChecked()
        ]
        selected.sort(key=lambda symbol: self._atomic_numbers[symbol])
        return selected

    def _update_summary(self) -> None:
        selected = self._selected_symbols()
        if not selected:
            self._summary_label.setText("Selected elements: none")
            self._chemsys_label.setText("Search text: (empty)")
            return

        self._summary_label.setText(f"Selected elements ({len(selected)}): {', '.join(selected)}")
        self._chemsys_label.setText(f"Search text: {format_chemsys(selected)}")

    def _clear_selection(self) -> None:
        for button in self._buttons.values():
            button.setChecked(False)
        self._update_summary()

    def selected_elements(self) -> List[str]:
        """Return selected element symbols in ascending atomic number order."""
        return self._selected_symbols()
