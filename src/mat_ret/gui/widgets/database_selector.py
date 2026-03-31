"""
Database Selector Widget

Provides a tree view for selecting which materials databases to query.
"""

from typing import Dict, List, Optional

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QSpinBox, QPushButton,
    QFrame, QFormLayout, QTreeWidget, QTreeWidgetItem
)
from PyQt6.QtCore import pyqtSignal, Qt, QThread
from PyQt6.QtGui import QFont

from .collapsible import CollapsibleSection


# Database configuration with metadata
DATABASE_CONFIG = {
    'materials_project': {
        'name': 'Materials Project',
        'requires_api_key': True,
        'api_key_name': 'MP API Key',
        'description': 'Largest DFT database',
        'color': '#2196F3',  # Blue
        'icon': '🔷'
    },
    'jarvis': {
        'name': 'JARVIS',
        'requires_api_key': False,
        'description': 'NIST DFT database',
        'color': '#4CAF50',  # Green
        'icon': '🟢'
    },
    'aflow': {
        'name': 'AFLOW',
        'requires_api_key': False,
        'description': 'Duke University database',
        'color': '#FF9800',  # Orange
        'icon': '🟠'
    },
    'alexandria': {
        'name': 'Alexandria',
        'requires_api_key': False,
        'description': 'OPTIMADE-based database',
        'color': '#9C27B0',  # Purple
        'icon': '🟣'
    },
    'materials_cloud': {
        'name': 'Materials Cloud',
        'requires_api_key': False,
        'description': 'Swiss research database',
        'color': '#00BCD4',  # Cyan
        'icon': '🔵'
    },
    'oqmd': {
        'name': 'OQMD',
        'requires_api_key': False,
        'description': 'Northwestern database',
        'color': '#795548',  # Brown
        'icon': '🟤'
    },
    'mpds': {
        'name': 'MPDS',
        'requires_api_key': True,
        'api_key_name': 'MPDS API Key',
        'description': 'Materials Platform for Data Science',
        'color': '#E91E63',  # Pink
        'icon': '🔴'
    },
    'optimade': {
        'name': 'OPTIMADE',
        'requires_api_key': False,
        'description': 'OPTIMADE registry search',
        'color': '#607D8B',  # Blue Grey
        'icon': '🛰️',
        'default_selected': False
    }
}


class OptimadeProviderLoader(QThread):
    """Background loader for OPTIMADE providers."""

    loaded = pyqtSignal(list)
    failed = pyqtSignal(str)

    def __init__(self, registry_url: str, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.registry_url = registry_url

    def run(self) -> None:
        try:
            from mat_ret.optimade.registry import fetch_registry_links

            providers = fetch_registry_links(self.registry_url)
            self.loaded.emit(providers)
        except Exception as exc:
            self.failed.emit(str(exc))


class DatabaseSelectorWidget(QWidget):
    """Widget for selecting databases and configuring API keys."""

    # Signal emitted when database selection changes
    selection_changed = pyqtSignal(list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.db_items: Dict[str, QTreeWidgetItem] = {}
        self.api_key_inputs: Dict[str, QLineEdit] = {}
        self.optimade_item: Optional[QTreeWidgetItem] = None
        self.optimade_loader: Optional[OptimadeProviderLoader] = None
        self._tree_updating = False
        self._setup_ui()
        self._load_saved_keys()
        self._load_optimade_providers()

    def _setup_ui(self):
        """Set up the user interface."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 6, 10, 10)
        layout.setSpacing(4)

        # Title
        title_row = QHBoxLayout()
        title_row.setContentsMargins(2, 4, 2, 6)
        title = QLabel("Database Selection")
        title.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
        title.setStyleSheet("color: #1565C0;")
        title_row.addWidget(title)
        title_row.addStretch()
        layout.addLayout(title_row)

        # --- Databases Section (collapsible, expanded) ---
        db_sec = CollapsibleSection("Databases", icon="📊", expanded=True)
        db_lay = db_sec.content_layout()

        self.database_tree = QTreeWidget()
        self.database_tree.setHeaderHidden(True)
        self.database_tree.setStyleSheet("""
            QTreeWidget {
                border: 1px solid #e0e0e0;
                border-radius: 6px;
                background-color: #fafbfc;
                font-size: 11px;
            }
            QTreeWidget::item {
                padding: 4px 5px;
            }
            QTreeWidget::item:selected {
                background-color: #e3f2fd;
                color: #1976D2;
            }
        """)
        self.database_tree.itemChanged.connect(self._on_tree_item_changed)

        for db_id, config in DATABASE_CONFIG.items():
            icon = config.get('icon', '')
            name = config['name']
            item = QTreeWidgetItem([f"{icon} {name}"])
            item.setData(0, Qt.ItemDataRole.UserRole, {"type": "database", "db_id": db_id})
            flags = item.flags() | Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled
            if db_id == 'optimade':
                flags |= Qt.ItemFlag.ItemIsAutoTristate
            item.setFlags(flags)

            default_selected = config.get('default_selected', not config['requires_api_key'])
            item.setCheckState(0, Qt.CheckState.Checked if default_selected else Qt.CheckState.Unchecked)

            self.database_tree.addTopLevelItem(item)
            self.db_items[db_id] = item

            if db_id == 'optimade':
                self.optimade_item = item
                loading_item = QTreeWidgetItem(["Loading providers..."])
                loading_item.setFlags(Qt.ItemFlag.ItemIsEnabled)
                loading_item.setData(0, Qt.ItemDataRole.UserRole, {"type": "optimade_loading"})
                item.addChild(loading_item)

        db_lay.addWidget(self.database_tree)

        # Quick selection buttons — compact pill style
        btn_layout = QHBoxLayout()
        btn_layout.setContentsMargins(0, 4, 0, 0)

        _pill_green = """
            QPushButton {
                background-color: transparent; color: #2e7d32;
                border: 1.5px solid #a5d6a7; padding: 3px 12px;
                border-radius: 12px; font-size: 10px; font-weight: bold;
            }
            QPushButton:hover { background-color: #e8f5e9; border-color: #2e7d32; }
        """
        _pill_red = """
            QPushButton {
                background-color: transparent; color: #c62828;
                border: 1.5px solid #ef9a9a; padding: 3px 12px;
                border-radius: 12px; font-size: 10px; font-weight: bold;
            }
            QPushButton:hover { background-color: #ffebee; border-color: #c62828; }
        """

        select_all_btn = QPushButton("Select All")
        select_all_btn.setStyleSheet(_pill_green)
        select_all_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        select_all_btn.clicked.connect(self._select_all)
        btn_layout.addWidget(select_all_btn)

        select_none_btn = QPushButton("Clear All")
        select_none_btn.setStyleSheet(_pill_red)
        select_none_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        select_none_btn.clicked.connect(self._select_none)
        btn_layout.addWidget(select_none_btn)

        btn_layout.addStretch()
        db_lay.addLayout(btn_layout)

        layout.addWidget(db_sec)

        # --- API Keys Section (collapsible, collapsed) ---
        api_sec = CollapsibleSection("API Keys", icon="🔑", expanded=False)
        api_lay = api_sec.content_layout()

        api_form = QFormLayout()
        api_form.setSpacing(8)
        api_form.setContentsMargins(0, 0, 0, 0)

        _key_ss = """
            QLineEdit {
                padding: 6px 8px; border: 1px solid #d0d5dd;
                border-radius: 4px; font-size: 11px; background: #fafbfc;
            }
            QLineEdit:focus { border: 1.5px solid #1976D2; background: white; }
        """

        mp_key_input = QLineEdit()
        mp_key_input.setPlaceholderText("Enter Materials Project API key")
        mp_key_input.setEchoMode(QLineEdit.EchoMode.Password)
        mp_key_input.setStyleSheet(_key_ss)
        self.api_key_inputs['materials_project'] = mp_key_input
        api_form.addRow("MP Key:", mp_key_input)

        mpds_key_input = QLineEdit()
        mpds_key_input.setPlaceholderText("Enter MPDS API key")
        mpds_key_input.setEchoMode(QLineEdit.EchoMode.Password)
        mpds_key_input.setStyleSheet(_key_ss)
        self.api_key_inputs['mpds'] = mpds_key_input
        api_form.addRow("MPDS Key:", mpds_key_input)

        api_lay.addLayout(api_form)
        layout.addWidget(api_sec)

        # --- Search Settings Section (collapsible, collapsed) ---
        settings_sec = CollapsibleSection("Search Settings", icon="⚙️", expanded=False)
        settings_lay = settings_sec.content_layout()

        settings_form = QFormLayout()
        settings_form.setSpacing(8)
        settings_form.setContentsMargins(0, 0, 0, 0)

        self.limit_spinner = QSpinBox()
        self.limit_spinner.setRange(1, 100)
        self.limit_spinner.setValue(10)
        self.limit_spinner.setSuffix(" results")
        self.limit_spinner.setStyleSheet("""
            QSpinBox {
                padding: 4px 6px; border: 1px solid #d0d5dd;
                border-radius: 4px; font-size: 11px; background: #fafbfc;
            }
            QSpinBox:focus { border: 1.5px solid #1976D2; background: white; }
        """)
        settings_form.addRow("Limit per DB:", self.limit_spinner)

        settings_lay.addLayout(settings_form)
        layout.addWidget(settings_sec)

        layout.addStretch()

    def _load_saved_keys(self):
        """Load API keys from config if available."""
        try:
            from ..._config_loader import get_config_value

            mp_key = get_config_value("MP_API_KEY", "")
            mpds_key = get_config_value("MPDS_API_KEY", "")

            if mp_key:
                self.api_key_inputs['materials_project'].setText(mp_key)
            if mpds_key:
                self.api_key_inputs['mpds'].setText(mpds_key)
        except (ImportError, AttributeError):
            pass

    def _load_optimade_providers(self):
        """Fetch OPTIMADE providers in the background."""
        if not self.optimade_item:
            return

        try:
            from ..._config_loader import get_config_value
            OPTIMADE_REGISTRY_URL = get_config_value("OPTIMADE_REGISTRY_URL")
        except Exception:
            OPTIMADE_REGISTRY_URL = None

        registry_url = OPTIMADE_REGISTRY_URL or "https://providers.optimade.org"
        self.optimade_loader = OptimadeProviderLoader(registry_url, self)
        self.optimade_loader.loaded.connect(self._on_optimade_loaded)
        self.optimade_loader.failed.connect(self._on_optimade_failed)
        self.optimade_loader.start()

    def _clear_optimade_children(self):
        if not self.optimade_item:
            return
        while self.optimade_item.childCount() > 0:
            self.optimade_item.takeChild(0)

    def _on_optimade_loaded(self, providers: List[Dict[str, str]]):
        if not self.optimade_item:
            return

        self._tree_updating = True
        self._clear_optimade_children()

        if not providers:
            item = QTreeWidgetItem(["No providers found"])
            item.setFlags(Qt.ItemFlag.ItemIsEnabled)
            item.setData(0, Qt.ItemDataRole.UserRole, {"type": "optimade_empty"})
            self.optimade_item.addChild(item)
        else:
            parent_checked = self.optimade_item.checkState(0) == Qt.CheckState.Checked
            for provider in providers:
                provider_id = provider.get("id") or provider.get("base_url")
                provider_name = provider.get("name") or provider_id
                child = QTreeWidgetItem([provider_name])
                child.setData(0, Qt.ItemDataRole.UserRole, {
                    "type": "optimade_provider",
                    "provider": {
                        "id": provider_id,
                        "name": provider_name,
                        "base_url": provider.get("base_url"),
                    },
                })
                child.setFlags(child.flags() | Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled)
                child.setCheckState(0, Qt.CheckState.Checked if parent_checked else Qt.CheckState.Unchecked)
                self.optimade_item.addChild(child)

        self.database_tree.expandItem(self.optimade_item)
        self._tree_updating = False
        self.selection_changed.emit(self.get_selected_databases())

    def _on_optimade_failed(self, message: str):
        if not self.optimade_item:
            return

        self._tree_updating = True
        self._clear_optimade_children()
        item = QTreeWidgetItem(["Failed to load providers"])
        item.setFlags(Qt.ItemFlag.ItemIsEnabled)
        item.setData(0, Qt.ItemDataRole.UserRole, {"type": "optimade_error"})
        self.optimade_item.addChild(item)
        self.optimade_item.setCheckState(0, Qt.CheckState.Unchecked)
        self._tree_updating = False
        self.selection_changed.emit(self.get_selected_databases())

    def _on_tree_item_changed(self, item: QTreeWidgetItem, column: int):
        """Handle tree item check changes."""
        if self._tree_updating:
            return

        data = item.data(0, Qt.ItemDataRole.UserRole)
        if isinstance(data, dict) and data.get("type") in {"optimade_loading", "optimade_error", "optimade_empty"}:
            return

        self.selection_changed.emit(self.get_selected_databases())

    def _select_all(self):
        """Select all databases and providers."""
        self._tree_updating = True
        for i in range(self.database_tree.topLevelItemCount()):
            item = self.database_tree.topLevelItem(i)
            item.setCheckState(0, Qt.CheckState.Checked)
        self._tree_updating = False
        self.selection_changed.emit(self.get_selected_databases())

    def _select_none(self):
        """Deselect all databases and providers."""
        self._tree_updating = True
        for i in range(self.database_tree.topLevelItemCount()):
            item = self.database_tree.topLevelItem(i)
            item.setCheckState(0, Qt.CheckState.Unchecked)
        self._tree_updating = False
        self.selection_changed.emit(self.get_selected_databases())

    def get_selected_databases(self) -> list:
        """Return list of selected database IDs."""
        selected = []
        for i in range(self.database_tree.topLevelItemCount()):
            item = self.database_tree.topLevelItem(i)
            data = item.data(0, Qt.ItemDataRole.UserRole)
            if not isinstance(data, dict):
                continue
            db_id = data.get("db_id")
            if db_id == "optimade":
                if item.checkState(0) != Qt.CheckState.Unchecked:
                    selected.append("optimade")
            else:
                if item.checkState(0) == Qt.CheckState.Checked:
                    selected.append(db_id)
        return selected

    def get_selected_optimade_providers(self) -> List[Dict[str, str]]:
        """Return selected OPTIMADE providers."""
        providers: List[Dict[str, str]] = []
        if not self.optimade_item:
            return providers

        for i in range(self.optimade_item.childCount()):
            child = self.optimade_item.child(i)
            data = child.data(0, Qt.ItemDataRole.UserRole)
            if not isinstance(data, dict) or data.get("type") != "optimade_provider":
                continue
            if child.checkState(0) == Qt.CheckState.Checked:
                provider = data.get("provider")
                if isinstance(provider, dict) and provider.get("base_url"):
                    providers.append(provider)
        return providers

    def is_optimade_parent_checked(self) -> bool:
        if not self.optimade_item:
            return False
        return self.optimade_item.checkState(0) != Qt.CheckState.Unchecked

    def get_api_keys(self) -> dict:
        """Return dictionary of API keys."""
        return {
            'mp_api_key': self.api_key_inputs['materials_project'].text().strip(),
            'mpds_api_key': self.api_key_inputs['mpds'].text().strip()
        }

    def get_limit(self) -> int:
        """Return the results limit per database."""
        return self.limit_spinner.value()

    def get_database_config(self) -> dict:
        """Return the database configuration."""
        return DATABASE_CONFIG
