"""
Main Window for mat_ret GUI

The central window combining all widgets for materials database retrieval.
"""

from typing import Optional
import sys

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QLabel, QLineEdit, QPushButton, QStatusBar, QProgressBar,
    QFrame, QMessageBox, QApplication, QToolBar, QMenuBar, QMenu,
    QFileDialog, QSizePolicy
)
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QFont, QAction, QIcon, QKeySequence

from .widgets import DatabaseSelectorWidget, ResultsViewWidget, StructureViewerWidget
from .workers import FetchWorker
from .utils import APP_STYLESHEET, validate_composition


class MainWindow(QMainWindow):
    """Main application window for mat_ret GUI."""
    
    def __init__(self):
        super().__init__()
        self.fetch_worker = None
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
        
        # Left panel - Database selector
        left_panel = QFrame()
        left_panel.setMinimumWidth(280)
        left_panel.setMaximumWidth(400)
        left_panel.setStyleSheet("""
            QFrame {
                background-color: white;
                border-right: 1px solid #e0e0e0;
            }
        """)
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)
        
        self.database_selector = DatabaseSelectorWidget()
        left_layout.addWidget(self.database_selector)
        
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
        
        # Set initial splitter sizes (60% results, 40% structure)
        right_splitter.setSizes([500, 400])
        
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
        self.search_input.setPlaceholderText("Enter composition (e.g., MgO, Fe2O3, LiFePO4)")
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
        search_layout.addWidget(self.search_input)
        
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
        
        self.stats_label = QLabel("7 Databases Available")
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
        self.status_bar.showMessage("Ready. Enter a composition and click Search.")
    
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
    
    def _on_search(self):
        """Handle search button click."""
        formula = self.search_input.text().strip()
        
        # Validate composition
        is_valid, result = validate_composition(formula)
        if not is_valid:
            QMessageBox.warning(self, "Invalid Composition", result)
            return
        
        # Get selected databases
        selected_dbs = self.database_selector.get_selected_databases()
        if not selected_dbs:
            QMessageBox.warning(self, "No Databases Selected",
                              "Please select at least one database to search.")
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
        self._start_fetch(formula, selected_dbs, limit, api_keys)
    
    def _start_fetch(self, formula: str, databases: list, limit: int, api_keys: dict):
        """Start the fetch worker."""
        # Update UI
        self.search_button.setEnabled(False)
        self.search_button.setVisible(False)
        self.cancel_button.setVisible(True)
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 0)  # Indeterminate
        
        self.status_bar.showMessage(f"Searching for {formula}...")
        
        # Create and start worker
        self.fetch_worker = FetchWorker(
            formula=formula,
            databases=databases,
            limit=limit,
            mp_api_key=api_keys.get('mp_api_key'),
            mpds_api_key=api_keys.get('mpds_api_key')
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
    
    def _on_material_selected(self, material: dict):
        """Handle material selection for structure viewing."""
        self.structure_viewer.set_structure(material)
    
    def _clear_results(self):
        """Clear all results."""
        self.results_view.clear_results()
        self.structure_viewer.clear_structure()
        self.status_bar.showMessage("Results cleared. Enter a new composition to search.")
    
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
        
        event.accept()
