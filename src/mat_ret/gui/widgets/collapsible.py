"""
Collapsible Section Widget

A professional, reusable collapsible section with a styled header bar,
arrow indicator, and smooth toggle for content visibility.
"""

from typing import Optional

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QToolButton, QLabel, QFrame,
    QSizePolicy,
)
from PyQt6.QtCore import Qt, pyqtSignal, QPropertyAnimation, QEasingCurve
from PyQt6.QtGui import QFont


class CollapsibleSection(QFrame):
    """A collapsible section with a clickable header and hideable content area.

    Parameters
    ----------
    title : str
        Section title displayed in the header.
    icon : str
        Emoji or short text shown before the title.
    expanded : bool
        Whether the section starts expanded (default True).
    parent : QWidget | None
        Parent widget.
    """

    toggled = pyqtSignal(bool)  # emitted with the new expanded state

    _HEADER_SS = """
        QToolButton {{
            background-color: {bg};
            border: none;
            border-radius: 6px;
            padding: 7px 10px;
            font-size: 12px;
            font-weight: bold;
            color: {fg};
            text-align: left;
        }}
        QToolButton:hover {{
            background-color: {hover_bg};
        }}
    """

    _FRAME_SS = """
        CollapsibleSection {{
            background-color: white;
            border: 1px solid #e8e8e8;
            border-radius: 8px;
        }}
    """

    _CONTENT_SS = """
        QWidget#collapsible_content {{
            background-color: white;
            border: none;
        }}
    """

    def __init__(
        self,
        title: str,
        icon: str = "",
        expanded: bool = True,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self.setObjectName("collapsibleSection")
        self._expanded = expanded

        self.setStyleSheet(self._FRAME_SS)
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # --- Header row ---
        self._toggle_btn = QToolButton()
        self._toggle_btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self._toggle_btn.setCheckable(True)
        self._toggle_btn.setChecked(expanded)
        arrow = "▾" if expanded else "▸"
        display = f"{arrow}  {icon}  {title}" if icon else f"{arrow}  {title}"
        self._toggle_btn.setText(display)
        self._toggle_btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._toggle_btn.setStyleSheet(self._HEADER_SS.format(
            bg="#f0f4f8", fg="#1565C0", hover_bg="#e3ecf5",
        ))
        self._toggle_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._toggle_btn.toggled.connect(self._on_toggle)

        self._title_text = title
        self._icon_text = icon

        root.addWidget(self._toggle_btn)

        # --- Content area ---
        self._content = QFrame()
        self._content.setObjectName("collapsible_content")
        self._content.setStyleSheet(self._CONTENT_SS)
        self._content_layout = QVBoxLayout(self._content)
        self._content_layout.setContentsMargins(10, 6, 10, 10)
        self._content_layout.setSpacing(6)

        self._content.setVisible(expanded)
        root.addWidget(self._content)

    # ------------------------------------------------------------------
    # Public helpers
    # ------------------------------------------------------------------

    def content_layout(self) -> QVBoxLayout:
        """Return the layout inside the content area (add your widgets here)."""
        return self._content_layout

    def add_widget(self, widget: QWidget) -> None:
        self._content_layout.addWidget(widget)

    def add_layout(self, layout) -> None:
        self._content_layout.addLayout(layout)

    def is_expanded(self) -> bool:
        return self._expanded

    def set_expanded(self, expanded: bool) -> None:
        self._toggle_btn.setChecked(expanded)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _on_toggle(self, checked: bool) -> None:
        self._expanded = checked
        arrow = "▾" if checked else "▸"
        icon = self._icon_text
        display = f"{arrow}  {icon}  {self._title_text}" if icon else f"{arrow}  {self._title_text}"
        self._toggle_btn.setText(display)
        self._content.setVisible(checked)
        self.toggled.emit(checked)
