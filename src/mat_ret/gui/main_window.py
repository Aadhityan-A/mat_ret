"""
Main Window for mat_ret GUI

The central window combining all widgets for materials database retrieval.
"""

from typing import List, Optional

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QLabel, QLineEdit, QPushButton, QStatusBar, QProgressBar,
    QFrame, QMessageBox, QApplication, QToolBar, QMenuBar, QMenu,
    QFileDialog, QSizePolicy, QToolButton, QDialog, QScrollArea,
)
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QFont, QAction, QIcon, QKeySequence, QPixmap, QPainter, QPen, QColor

from .widgets import (
    DatabaseSelectorWidget,
    PeriodicTableDialog,
    ResultsViewWidget,
    SearchFiltersWidget,
    StructureViewerWidget,
    XRDGeneratorWindow,
)
from .widgets.storage_config_dialog import StorageConfigDialog
from .widgets.storage_browser_dialog import StorageBrowserDialog
from .workers import FetchWorker
from .utils import APP_STYLESHEET
from ..search import SearchQuery, format_chemsys, parse_search_text
from ..storage import get_storage, StorageType


class MainWindow(QMainWindow):
    """Main application window for mat_ret GUI."""
    
    def __init__(self):
        super().__init__()
        self.fetch_worker = None
        self.current_material = None
        self.xrd_window = None
        self._selected_elements: List[str] = []
        self._updating_search_text = False
        # Storage backend state
        self._storage_backend_type = StorageType.FILE
        self._storage_config: dict = {}
        self._storage = None  # active StorageBackend instance (None = file-only default)
        self._setup_ui()
        self._setup_menu()
        self._setup_connections()
    
    def _setup_ui(self):
        """Set up the main user interface."""
        self.setWindowTitle("mat_ret - Materials Database Retrieval")
        self.setMinimumSize(1400, 900)
        self.resize(1600, 1000)
        
        # Apply stylesheet
        self.setStyleSheet(APP_STYLESHEET)
        
        # Central widget
        central = QWidget()
        self.setCentralWidget(central)
        
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # Header bar
        header = self._create_header()
        main_layout.addWidget(header)
        
        # Main content with splitter
        content_splitter = QSplitter(Qt.Orientation.Horizontal)
        content_splitter.setStyleSheet("""
            QSplitter::handle {
                background-color: #e0e0e0;
                width: 4px;
            }
            QSplitter::handle:hover {
                background-color: #1976D2;
            }
        """)
        
        # Left panel - Database selector + Search filters (scrollable)
        left_panel = QFrame()
        left_panel.setMinimumWidth(300)
        left_panel.setMaximumWidth(420)
        left_panel.setStyleSheet("""
            QFrame#leftPanel {
                background-color: #f8f9fb;
                border-right: 1px solid #e0e0e0;
            }
        """)
        left_panel.setObjectName("leftPanel")
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(0)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll_area.verticalScrollBar().setSingleStep(20)

        scroll_content = QWidget()
        scroll_content.setStyleSheet("background-color: #f8f9fb;")
        scroll_layout = QVBoxLayout(scroll_content)
        scroll_layout.setContentsMargins(4, 8, 4, 8)
        scroll_layout.setSpacing(2)

        self.database_selector = DatabaseSelectorWidget()
        scroll_layout.addWidget(self.database_selector)

        # Thin separator
        sep = QFrame()
        sep.setFixedHeight(1)
        sep.setStyleSheet("background-color: #e0e0e0; margin: 4px 12px;")
        scroll_layout.addWidget(sep)

        self.search_filters = SearchFiltersWidget()
        scroll_layout.addWidget(self.search_filters)

        scroll_layout.addStretch()
        scroll_area.setWidget(scroll_content)
        left_layout.addWidget(scroll_area)
        
        content_splitter.addWidget(left_panel)
        
        # Right panel - Results and structure viewer
        right_splitter = QSplitter(Qt.Orientation.Vertical)
        right_splitter.setStyleSheet("""
            QSplitter::handle {
                background-color: #e0e0e0;
                height: 4px;
            }
            QSplitter::handle:hover {
                background-color: #1976D2;
            }
        """)
        
        # Results view
        self.results_view = ResultsViewWidget()
        right_splitter.addWidget(self.results_view)
        
        # Structure viewer
        self.structure_viewer = StructureViewerWidget()
        right_splitter.addWidget(self.structure_viewer)
        
        # Set initial splitter sizes (40% results, 60% structure viewer)
        right_splitter.setSizes([350, 550])
        
        content_splitter.addWidget(right_splitter)
        
        # Set content splitter sizes (left panel smaller)
        content_splitter.setSizes([280, 1000])
        
        main_layout.addWidget(content_splitter, stretch=1)
        
        # Status bar
        self._create_status_bar()
    
    def _create_header(self) -> QWidget:
        """Create the header bar with search controls."""
        header = QFrame()
        header.setFixedHeight(80)
        header.setStyleSheet("""
            QFrame {
                background-color: #1976D2;
                border-bottom: 2px solid #1565C0;
            }
        """)
        
        layout = QHBoxLayout(header)
        layout.setContentsMargins(20, 15, 20, 15)
        layout.setSpacing(20)
        
        # Logo/Title
        title_layout = QVBoxLayout()
        title_layout.setSpacing(2)
        
        title = QLabel("🔬 mat_ret")
        title.setFont(QFont("Segoe UI", 18, QFont.Weight.Bold))
        title.setStyleSheet("color: white;")
        title_layout.addWidget(title)
        
        subtitle = QLabel("Unified Materials Database Retrieval")
        subtitle.setFont(QFont("Segoe UI", 10))
        subtitle.setStyleSheet("color: rgba(255, 255, 255, 0.8);")
        title_layout.addWidget(subtitle)
        
        layout.addLayout(title_layout)
        
        # Spacer
        layout.addStretch()
        
        # Search box
        search_container = QFrame()
        search_container.setStyleSheet("""
            QFrame {
                background-color: white;
                border-radius: 6px;
                border: none;
            }
        """)
        search_layout = QHBoxLayout(search_container)
        search_layout.setContentsMargins(15, 0, 5, 0)
        search_layout.setSpacing(10)
        
        search_icon = QLabel("🔍")
        search_icon.setStyleSheet("font-size: 16px;")
        search_layout.addWidget(search_icon)
        
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Enter composition or element system (e.g., MgO or Fe-O)")
        self.search_input.setMinimumWidth(350)
        self.search_input.setStyleSheet("""
            QLineEdit {
                border: none;
                font-size: 14px;
                padding: 10px 0;
                background: transparent;
            }
        """)
        self.search_input.returnPressed.connect(self._on_search)
        self.search_input.textEdited.connect(self._on_search_text_edited)
        search_layout.addWidget(self.search_input)

        self.periodic_button = QToolButton()
        self.periodic_button.setIcon(self._create_periodic_table_icon())
        self.periodic_button.setIconSize(QSize(18, 18))
        self.periodic_button.setToolTip("Select elements from periodic table")
        self.periodic_button.setStyleSheet("""
            QToolButton {
                border: 1px solid #d0d7de;
                border-radius: 4px;
                background: #f8fafc;
                padding: 6px;
            }
            QToolButton:hover {
                border-color: #1976D2;
                background: #eef4fb;
            }
            QToolButton:pressed {
                background: #e3edf9;
            }
        """)
        self.periodic_button.clicked.connect(self._open_periodic_table_dialog)
        search_layout.addWidget(self.periodic_button)
        
        self.search_button = QPushButton("Search")
        self.search_button.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border: none;
                padding: 10px 25px;
                border-radius: 4px;
                font-size: 13px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
            QPushButton:pressed {
                background-color: #3d8b40;
            }
            QPushButton:disabled {
                background-color: #ccc;
            }
        """)
        self.search_button.clicked.connect(self._on_search)
        search_layout.addWidget(self.search_button)
        
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.setStyleSheet("""
            QPushButton {
                background-color: #f44336;
                color: white;
                border: none;
                padding: 10px 20px;
                border-radius: 4px;
                font-size: 13px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #da190b;
            }
        """)
        self.cancel_button.clicked.connect(self._on_cancel)
        self.cancel_button.setVisible(False)
        search_layout.addWidget(self.cancel_button)
        
        layout.addWidget(search_container)
        
        layout.addStretch()
        
        # Quick stats
        stats_layout = QVBoxLayout()
        stats_layout.setSpacing(2)
        
        self.stats_label = QLabel("8 Databases Available")
        self.stats_label.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        self.stats_label.setStyleSheet("color: white;")
        stats_layout.addWidget(self.stats_label)
        
        self.selected_label = QLabel("5 selected")
        self.selected_label.setFont(QFont("Segoe UI", 9))
        self.selected_label.setStyleSheet("color: rgba(255, 255, 255, 0.8);")
        stats_layout.addWidget(self.selected_label)
        
        layout.addLayout(stats_layout)
        
        return header
    
    def _create_status_bar(self):
        """Create the status bar."""
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        
        # Progress bar (hidden by default)
        self.progress_bar = QProgressBar()
        self.progress_bar.setMaximumWidth(200)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                border: 1px solid #ddd;
                border-radius: 4px;
                background-color: #f0f0f0;
                height: 16px;
            }
            QProgressBar::chunk {
                background-color: #1976D2;
                border-radius: 3px;
            }
        """)
        self.progress_bar.setVisible(False)
        self.status_bar.addPermanentWidget(self.progress_bar)
        
        # Status message
        self.status_bar.showMessage("Ready. Enter a composition or element system and click Search.")
    
    def _setup_menu(self):
        """Set up the menu bar."""
        menubar = self.menuBar()
        
        # File menu
        file_menu = menubar.addMenu("&File")
        
        export_json_action = QAction("Export Results as JSON...", self)
        export_json_action.setShortcut(QKeySequence.StandardKey.Save)
        export_json_action.triggered.connect(self._export_json)
        file_menu.addAction(export_json_action)
        
        export_csv_action = QAction("Export Results as CSV...", self)
        export_csv_action.triggered.connect(self._export_csv)
        file_menu.addAction(export_csv_action)
        
        file_menu.addSeparator()
        
        exit_action = QAction("E&xit", self)
        exit_action.setShortcut(QKeySequence.StandardKey.Quit)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)
        
        # View menu
        view_menu = menubar.addMenu("&View")
        
        clear_action = QAction("Clear Results", self)
        clear_action.triggered.connect(self._clear_results)
        view_menu.addAction(clear_action)

        # Tools menu
        tools_menu = menubar.addMenu("&Tools")

        xrd_action = QAction("XRD Generator...", self)
        xrd_action.setShortcut("Ctrl+Shift+X")
        xrd_action.triggered.connect(self._open_xrd_generator)
        tools_menu.addAction(xrd_action)

        # Database (storage) menu
        db_menu = menubar.addMenu("&Database")

        # Storage Backend submenu (radio group)
        backend_menu = db_menu.addMenu("Storage Backend")
        self._backend_actions = {}
        for st in StorageType:
            action = QAction(st.value.capitalize(), self, checkable=True)
            action.setData(st)
            action.triggered.connect(lambda checked, s=st: self._set_storage_backend(s))
            backend_menu.addAction(action)
            self._backend_actions[st] = action
        self._backend_actions[StorageType.FILE].setChecked(True)

        db_menu.addSeparator()

        configure_action = QAction("Configure Storage…", self)
        configure_action.triggered.connect(self._open_storage_config)
        db_menu.addAction(configure_action)

        browse_action = QAction("Browse Stored Materials…", self)
        browse_action.setShortcut("Ctrl+Shift+B")
        browse_action.triggered.connect(self._open_storage_browser)
        db_menu.addAction(browse_action)

        db_menu.addSeparator()

        import_action = QAction("Import Current Results to Storage", self)
        import_action.triggered.connect(self._import_results_to_storage)
        db_menu.addAction(import_action)

        stats_action = QAction("Storage Statistics", self)
        stats_action.triggered.connect(self._show_storage_stats)
        db_menu.addAction(stats_action)

        # Help menu
        help_menu = menubar.addMenu("&Help")
        
        about_action = QAction("&About", self)
        about_action.triggered.connect(self._show_about)
        help_menu.addAction(about_action)
    
    def _setup_connections(self):
        """Set up signal connections."""
        # Database selection changes
        self.database_selector.selection_changed.connect(self._on_selection_changed)
        
        # Material selection for structure viewing
        self.results_view.material_selected.connect(self._on_material_selected)
    
    def _on_selection_changed(self, selected: list):
        """Handle database selection changes."""
        count = len(selected)
        self.selected_label.setText(f"{count} selected")

    def _create_periodic_table_icon(self) -> QIcon:
        """Create a lightweight periodic-table style icon."""
        pixmap = QPixmap(18, 18)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        pen = QPen(QColor("#2F4F6F"))
        pen.setWidth(1)
        painter.setPen(pen)

        cell = 5
        offsets = [
            (1, 1), (7, 1), (13, 1),
            (1, 7), (7, 7), (13, 7),
            (1, 13), (7, 13), (13, 13),
        ]
        for x, y in offsets:
            painter.drawRect(x, y, cell, cell)
        painter.end()
        return QIcon(pixmap)

    def _set_search_text(self, text: str) -> None:
        """Set search box text without treating it as manual user edits."""
        self._updating_search_text = True
        self.search_input.setText(text)
        self._updating_search_text = False

    def _on_search_text_edited(self, text: str) -> None:
        """Clear periodic-table state when user manually diverges from selected chemsys."""
        if self._updating_search_text or not self._selected_elements:
            return
        if text.strip() != format_chemsys(self._selected_elements):
            self._selected_elements = []

    def _open_periodic_table_dialog(self) -> None:
        """Open periodic table picker and write selected chemsys into search input."""
        dialog = PeriodicTableDialog(self, selected_elements=self._selected_elements)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        self._selected_elements = dialog.selected_elements()
        if self._selected_elements:
            self._set_search_text(format_chemsys(self._selected_elements))
        else:
            self._set_search_text("")
    
    def _on_search(self):
        """Handle search button click."""
        query_text = self.search_input.text().strip()

        try:
            query = parse_search_text(query_text)
        except ValueError as exc:
            QMessageBox.warning(self, "Invalid Query", str(exc))
            return

        selected_chemsys = format_chemsys(self._selected_elements) if self._selected_elements else ""
        if self._selected_elements and query_text == selected_chemsys:
            query = SearchQuery(
                mode="elements_all",
                formula=None,
                elements=list(self._selected_elements),
                display_text=selected_chemsys,
            )
        
        # Get selected databases
        selected_dbs = self.database_selector.get_selected_databases()
        if not selected_dbs:
            QMessageBox.warning(self, "No Databases Selected",
                              "Please select at least one database to search.")
            return

        optimade_providers = self.database_selector.get_selected_optimade_providers()
        if 'optimade' in selected_dbs and not optimade_providers:
            QMessageBox.warning(
                self,
                "No OPTIMADE Providers Selected",
                "Please select at least one OPTIMADE provider.",
            )
            return
        
        # Get API keys and limit
        api_keys = self.database_selector.get_api_keys()
        limit = self.database_selector.get_limit()
        
        # Check if required API keys are provided
        if 'materials_project' in selected_dbs and not api_keys.get('mp_api_key'):
            reply = QMessageBox.question(
                self, "Missing API Key",
                "Materials Project requires an API key. Continue without it?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.No:
                return
            selected_dbs.remove('materials_project')
        
        if 'mpds' in selected_dbs and not api_keys.get('mpds_api_key'):
            reply = QMessageBox.question(
                self, "Missing API Key",
                "MPDS requires an API key. Continue without it?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.No:
                return
            selected_dbs.remove('mpds')
        
        if not selected_dbs:
            QMessageBox.warning(self, "No Valid Databases",
                              "No databases available to search with current settings.")
            return
        
        # Clear previous results
        self.results_view.clear_results()
        self.structure_viewer.clear_structure()
        
        # Start fetch
        self._start_fetch(
            query=query,
            databases=selected_dbs,
            limit=limit,
            api_keys=api_keys,
            optimade_providers=optimade_providers,
            filters=self.search_filters.get_filters(),
        )
    
    def _start_fetch(self, query: SearchQuery, databases: list, limit: int, api_keys: dict, optimade_providers: list, filters=None):
        """Start the fetch worker."""
        # Update UI
        self.search_button.setEnabled(False)
        self.search_button.setVisible(False)
        self.cancel_button.setVisible(True)
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 0)  # Indeterminate
        
        self.status_bar.showMessage(f"Searching for {query.display_text}...")
        
        # Create and start worker
        self.fetch_worker = FetchWorker(
            formula=query.formula or query.display_text,
            query_mode=query.mode,
            elements=query.elements,
            databases=databases,
            limit=limit,
            mp_api_key=api_keys.get('mp_api_key'),
            mpds_api_key=api_keys.get('mpds_api_key'),
            optimade_providers=optimade_providers,
            filters=filters,
        )
        
        self.fetch_worker.status_update.connect(self._on_status_update)
        self.fetch_worker.database_complete.connect(self._on_database_complete)
        self.fetch_worker.error.connect(self._on_fetch_error)
        self.fetch_worker.finished_all.connect(self._on_fetch_complete)
        
        self.fetch_worker.start()
    
    def _on_cancel(self):
        """Handle cancel button click."""
        if self.fetch_worker and self.fetch_worker.isRunning():
            self.fetch_worker.cancel()
            self.status_bar.showMessage("Cancelling...")
    
    def _on_status_update(self, message: str):
        """Handle status update from worker."""
        self.status_bar.showMessage(message)
    
    def _on_database_complete(self, db_id: str, results: list):
        """Handle completion of a single database fetch."""
        # Could update UI incrementally here if desired
        pass
    
    def _on_fetch_error(self, db_id: str, error: str):
        """Handle fetch error."""
        self.status_bar.showMessage(f"Error from {db_id}: {error[:50]}...")
    
    def _on_fetch_complete(self, results: dict):
        """Handle completion of all fetches."""
        # Reset UI
        self.search_button.setEnabled(True)
        self.search_button.setVisible(True)
        self.cancel_button.setVisible(False)
        self.progress_bar.setVisible(False)
        
        # Update results view
        self.results_view.set_results(results)
        
        # Update status
        total = sum(len(v) for v in results.values())
        db_count = sum(1 for v in results.values() if len(v) > 0)
        
        if total > 0:
            self.status_bar.showMessage(
                f"Found {total} materials from {db_count} database(s). "
                "Click on a material to view its structure."
            )
        else:
            self.status_bar.showMessage("No results found. Try a different composition.")

        # Auto-save to storage backend (if not file-mode)
        if total > 0:
            self._auto_save_to_storage(results)

    def _on_material_selected(self, material: dict):
        """Handle material selection for structure viewing."""
        self.current_material = material
        self.structure_viewer.set_structure(material)
        if self.xrd_window is not None:
            self.xrd_window.set_current_material(material)

    def _clear_results(self):
        """Clear all results."""
        self.current_material = None
        self.results_view.clear_results()
        self.structure_viewer.clear_structure()
        if self.xrd_window is not None:
            self.xrd_window.set_current_material(None)
        self.status_bar.showMessage("Results cleared. Enter a new composition or element system to search.")

    def _open_xrd_generator(self):
        """Open or focus the XRD Generator window."""
        if self.xrd_window is None:
            self.xrd_window = XRDGeneratorWindow(self)

        self.xrd_window.set_current_material(self.current_material)
        self.xrd_window.show()
        self.xrd_window.raise_()
        self.xrd_window.activateWindow()

    # -- Storage menu handlers -------------------------------------------------

    def _set_storage_backend(self, backend_type: "StorageType") -> None:
        """Switch the active storage backend."""
        # Uncheck all, then check selected
        for st, act in self._backend_actions.items():
            act.setChecked(st == backend_type)

        if backend_type == self._storage_backend_type and self._storage is not None:
            return  # already active

        # Close previous backend
        if self._storage is not None:
            try:
                self._storage.close()
            except Exception:
                pass
            self._storage = None

        self._storage_backend_type = backend_type

        if backend_type == StorageType.FILE:
            # File backend — storage is None; save_cif already handles file writes
            self._storage = None
            self.status_bar.showMessage("Storage: File mode (JSON + CIF)")
            return

        try:
            self._storage = get_storage(
                backend_type,
                sqlite_path=self._storage_config.get("sqlite_path") or None,
                mongodb_uri=self._storage_config.get("mongodb_uri") or None,
                mongodb_db_name=self._storage_config.get("mongodb_db_name") or None,
            )
            self.status_bar.showMessage(f"Storage: {backend_type.value.capitalize()} backend active")
        except ImportError as exc:
            QMessageBox.warning(self, "Missing Dependency", str(exc))
            self._set_storage_backend(StorageType.FILE)
        except Exception as exc:
            QMessageBox.critical(self, "Storage Error", f"Failed to initialize storage:\n{exc}")
            self._set_storage_backend(StorageType.FILE)

    def _open_storage_config(self) -> None:
        """Open the storage configuration dialog."""
        dialog = StorageConfigDialog(self, current_config=self._storage_config)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self._storage_config = dialog.get_config()
            # Re-initialize active backend with new config
            self._set_storage_backend(self._storage_backend_type)

    def _open_storage_browser(self) -> None:
        """Open the stored materials browser."""
        storage = self._storage
        if storage is None:
            # For file mode, create a temporary FileStorage for browsing
            from ..storage import FileStorage
            output_dir = self._storage_config.get("output_directory") or None
            storage = FileStorage(output_directory=output_dir)
        dialog = StorageBrowserDialog(storage, parent=self)
        dialog.exec()

    def _import_results_to_storage(self) -> None:
        """Import current search results into the active storage backend."""
        results = self.results_view.results_data
        if not results or not any(len(v) > 0 for v in results.values()):
            QMessageBox.information(self, "No Results", "No results to import.")
            return

        storage = self._storage
        if storage is None:
            from ..storage import FileStorage
            output_dir = self._storage_config.get("output_directory") or None
            storage = FileStorage(output_directory=output_dir)

        count = 0
        from .utils import clean_material_for_export
        for db_id, materials in results.items():
            for mat in materials:
                try:
                    cleaned = clean_material_for_export(mat)
                    cleaned["source_database"] = db_id
                    storage.save_material(cleaned, search_query="manual_import")
                    count += 1
                except Exception as exc:
                    import logging
                    logging.getLogger(__name__).warning(f"Import failed for material: {exc}")

        QMessageBox.information(
            self, "Import Complete",
            f"Imported {count} material(s) into {self._storage_backend_type.value} storage."
        )

    def _show_storage_stats(self) -> None:
        """Show storage statistics dialog."""
        storage = self._storage
        if storage is None:
            from ..storage import FileStorage
            output_dir = self._storage_config.get("output_directory") or None
            storage = FileStorage(output_directory=output_dir)

        try:
            total = storage.count_materials()
            sources = {}
            for name in ["Materials Project", "JARVIS", "AFLOW", "Alexandria",
                         "Materials Cloud", "OQMD", "MPDS", "OPTIMADE"]:
                c = storage.count_materials(source_database=name)
                if c > 0:
                    sources[name] = c

            lines = [
                f"<b>Backend:</b> {self._storage_backend_type.value.capitalize()}",
                f"<b>Total materials:</b> {total}",
                "",
                "<b>By source database:</b>",
            ]
            if sources:
                for name, c in sorted(sources.items(), key=lambda x: -x[1]):
                    lines.append(f"  • {name}: {c}")
            else:
                lines.append("  (none)")

            QMessageBox.information(self, "Storage Statistics", "<br>".join(lines))
        except Exception as exc:
            QMessageBox.critical(self, "Error", f"Could not retrieve statistics:\n{exc}")

    def _auto_save_to_storage(self, results: dict) -> None:
        """Persist fetched results into the active storage backend."""
        if self._storage is None:
            return
        from .utils import clean_material_for_export
        count = 0
        for db_id, materials in results.items():
            for mat in materials:
                try:
                    cleaned = clean_material_for_export(mat)
                    cleaned["source_database"] = db_id
                    self._storage.save_material(cleaned, search_query=self.search_input.text().strip())
                    count += 1
                except Exception:
                    pass
        if count:
            self.status_bar.showMessage(
                self.status_bar.currentMessage() + f" | {count} saved to {self._storage_backend_type.value} storage."
            )
    
    def _export_json(self):
        """Export results to JSON."""
        results = self.results_view.results_data
        if not results or not any(len(v) > 0 for v in results.values()):
            QMessageBox.information(self, "No Results", "No results to export.")
            return
        
        filename, _ = QFileDialog.getSaveFileName(
            self, "Export JSON", "", "JSON Files (*.json)"
        )
        
        if filename:
            from .utils import export_results_to_json
            if export_results_to_json(results, filename):
                QMessageBox.information(self, "Export Successful",
                                       f"Results exported to:\n{filename}")
            else:
                QMessageBox.critical(self, "Export Failed",
                                    "Failed to export results.")
    
    def _export_csv(self):
        """Export results to CSV."""
        results = self.results_view.results_data
        if not results or not any(len(v) > 0 for v in results.values()):
            QMessageBox.information(self, "No Results", "No results to export.")
            return
        
        filename, _ = QFileDialog.getSaveFileName(
            self, "Export CSV", "", "CSV Files (*.csv)"
        )
        
        if filename:
            from .utils import export_results_to_csv
            if export_results_to_csv(results, filename):
                QMessageBox.information(self, "Export Successful",
                                       f"Results exported to:\n{filename}")
            else:
                QMessageBox.critical(self, "Export Failed",
                                    "Failed to export results.")
    
    def _show_about(self):
        """Show about dialog."""
        QMessageBox.about(
            self,
            "About mat_ret",
            """<h2>mat_ret</h2>
            <p><b>Unified retrieval and property mapping for materials databases</b></p>
            <p>Version 1.0.0</p>
            <p>Supported databases:</p>
            <ul>
                <li>Materials Project</li>
                <li>JARVIS</li>
                <li>AFLOW</li>
                <li>Alexandria</li>
                <li>Materials Cloud</li>
                <li>OQMD</li>
                <li>MPDS</li>
                <li>OPTIMADE providers</li>
            </ul>
            <p>
                <a href="https://github.com/Aadhityan-A/mat_ret">GitHub Repository</a>
            </p>
            """
        )
    
    def closeEvent(self, event):
        """Handle window close event."""
        if self.fetch_worker and self.fetch_worker.isRunning():
            reply = QMessageBox.question(
                self, "Confirm Exit",
                "A search is in progress. Are you sure you want to exit?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            
            if reply == QMessageBox.StandardButton.No:
                event.ignore()
                return
            
            self.fetch_worker.cancel()
            self.fetch_worker.wait()

        # Close storage backend
        if self._storage is not None:
            try:
                self._storage.close()
            except Exception:
                pass

        event.accept()
