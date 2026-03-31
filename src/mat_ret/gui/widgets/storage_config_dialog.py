"""Dialog for configuring storage backends (File / SQLite / MongoDB)."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional

from PyQt6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)
from PyQt6.QtCore import Qt


class StorageConfigDialog(QDialog):
    """Tabbed dialog for configuring each storage backend."""

    def __init__(self, parent: Optional[QWidget] = None, current_config: Optional[Dict[str, Any]] = None):
        super().__init__(parent)
        self.setWindowTitle("Configure Storage Backend")
        self.setMinimumWidth(500)
        self._config = current_config or {}
        self._setup_ui()
        self._populate()

    # -- UI --------------------------------------------------------------------

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        info = QLabel(
            "Configure where retrieved materials data is stored.\n"
            "File mode saves JSON + CIF files (default). "
            "SQLite and MongoDB allow querying all stored properties."
        )
        info.setWordWrap(True)
        layout.addWidget(info)

        self._tabs = QTabWidget()

        # -- File tab --
        file_tab = QWidget()
        fl = QFormLayout(file_tab)
        self._file_dir_edit = QLineEdit()
        self._file_dir_edit.setPlaceholderText("downloaded_materials (default)")
        browse_btn = QPushButton("Browse…")
        browse_btn.clicked.connect(self._browse_file_dir)
        row = QHBoxLayout()
        row.addWidget(self._file_dir_edit, stretch=1)
        row.addWidget(browse_btn)
        fl.addRow("Output directory:", row)
        self._tabs.addTab(file_tab, "File")

        # -- SQLite tab --
        sqlite_tab = QWidget()
        sl = QFormLayout(sqlite_tab)
        self._sqlite_path_edit = QLineEdit()
        self._sqlite_path_edit.setPlaceholderText("downloaded_materials/mat_ret.db (default)")
        browse_sql_btn = QPushButton("Browse…")
        browse_sql_btn.clicked.connect(self._browse_sqlite_path)
        row2 = QHBoxLayout()
        row2.addWidget(self._sqlite_path_edit, stretch=1)
        row2.addWidget(browse_sql_btn)
        sl.addRow("Database file:", row2)
        self._tabs.addTab(sqlite_tab, "SQLite")

        # -- MongoDB tab --
        mongo_tab = QWidget()
        ml = QFormLayout(mongo_tab)
        self._mongo_uri_edit = QLineEdit()
        self._mongo_uri_edit.setPlaceholderText("mongodb://localhost:27017")
        ml.addRow("Connection URI:", self._mongo_uri_edit)
        self._mongo_db_edit = QLineEdit()
        self._mongo_db_edit.setPlaceholderText("mat_ret")
        ml.addRow("Database name:", self._mongo_db_edit)
        self._mongo_test_btn = QPushButton("Test Connection")
        self._mongo_test_btn.clicked.connect(self._test_mongo)
        ml.addRow("", self._mongo_test_btn)
        self._tabs.addTab(mongo_tab, "MongoDB")

        layout.addWidget(self._tabs)

        # Buttons
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _populate(self) -> None:
        self._file_dir_edit.setText(self._config.get("output_directory", ""))
        self._sqlite_path_edit.setText(self._config.get("sqlite_path", ""))
        self._mongo_uri_edit.setText(self._config.get("mongodb_uri", ""))
        self._mongo_db_edit.setText(self._config.get("mongodb_db_name", ""))

    # -- actions ---------------------------------------------------------------

    def _browse_file_dir(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "Select Output Directory")
        if path:
            self._file_dir_edit.setText(path)

    def _browse_sqlite_path(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Select SQLite Database",
            "",
            "SQLite Files (*.db *.sqlite *.sqlite3);;All Files (*)",
        )
        if path:
            self._sqlite_path_edit.setText(path)

    def _test_mongo(self) -> None:
        uri = self._mongo_uri_edit.text().strip() or "mongodb://localhost:27017"
        db_name = self._mongo_db_edit.text().strip() or "mat_ret"
        try:
            from ...storage.mongo_storage import MongoDBStorage
            storage = MongoDBStorage(uri=uri, db_name=db_name)
            if storage.ping():
                QMessageBox.information(self, "Connection OK", "Successfully connected to MongoDB.")
            else:
                QMessageBox.warning(self, "Connection Failed", "Could not ping MongoDB server.")
            storage.close()
        except ImportError:
            QMessageBox.warning(
                self, "pymongo not installed",
                "Install pymongo to use MongoDB storage:\n  pip install pymongo>=4.0"
            )
        except Exception as exc:
            QMessageBox.critical(self, "Connection Error", str(exc))

    # -- public API ------------------------------------------------------------

    def get_config(self) -> Dict[str, Any]:
        """Return the storage configuration entered by the user."""
        return {
            "output_directory": self._file_dir_edit.text().strip(),
            "sqlite_path": self._sqlite_path_edit.text().strip(),
            "mongodb_uri": self._mongo_uri_edit.text().strip(),
            "mongodb_db_name": self._mongo_db_edit.text().strip(),
        }
