"""
Results View Widget

Displays search results in a hierarchical view with database grouping
and detailed material properties in a table format.
"""

import json
from typing import Dict, List, Optional, Any

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QTreeWidget, QTreeWidgetItem, QTableWidget, QTableWidgetItem,
    QLabel, QHeaderView, QAbstractItemView, QFrame,
    QPushButton, QMenu, QFileDialog, QMessageBox, QTextEdit,
    QTabWidget, QScrollArea
)
from PyQt6.QtCore import pyqtSignal, Qt, QSize
from PyQt6.QtGui import QFont, QColor, QBrush, QAction


# Define which properties to show in the summary table
SUMMARY_COLUMNS = [
    ('material_id', 'Material ID'),
    ('formula', 'Formula'),
    ('band_gap', 'Band Gap (eV)'),
    ('formation_energy_per_atom', 'Form. Energy (eV/atom)'),
    ('space_group', 'Space Group'),
    ('density', 'Density (g/cm³)'),
    ('volume', 'Volume (ų)'),
    ('functional', 'Functional'),
]


class ResultsViewWidget(QWidget):
    """Widget for displaying search results in a hierarchical table view."""
    
    # Signal emitted when a material is selected
    material_selected = pyqtSignal(dict)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.results_data = {}
        self.current_selection = None
        self._setup_ui()
    
    def _setup_ui(self):
        """Set up the user interface."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # Title bar
        title_bar = QWidget()
        title_bar.setStyleSheet("background-color: #f5f5f5; border-bottom: 1px solid #e0e0e0;")
        title_layout = QHBoxLayout(title_bar)
        title_layout.setContentsMargins(15, 10, 15, 10)
        
        title = QLabel("📋 Search Results")
        title.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        title.setStyleSheet("color: #333;")
        title_layout.addWidget(title)
        
        self.results_count_label = QLabel("No results")
        self.results_count_label.setStyleSheet("color: #666; font-size: 12px;")
        title_layout.addStretch()
        title_layout.addWidget(self.results_count_label)
        
        layout.addWidget(title_bar)
        
        # Main content area with splitter
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setStyleSheet("""
            QSplitter::handle {
                background-color: #e0e0e0;
                width: 3px;
            }
        """)
        
        # Left panel - Database tree
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(10, 10, 5, 10)
        
        db_label = QLabel("Databases")
        db_label.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        db_label.setStyleSheet("color: #555; margin-bottom: 5px;")
        left_layout.addWidget(db_label)
        
        self.database_tree = QTreeWidget()
        self.database_tree.setHeaderHidden(True)
        self.database_tree.setStyleSheet("""
            QTreeWidget {
                border: 1px solid #ddd;
                border-radius: 6px;
                background-color: white;
                font-size: 11px;
            }
            QTreeWidget::item {
                padding: 8px 5px;
                border-bottom: 1px solid #f0f0f0;
            }
            QTreeWidget::item:selected {
                background-color: #e3f2fd;
                color: #1976D2;
            }
            QTreeWidget::item:hover {
                background-color: #f5f5f5;
            }
        """)
        self.database_tree.itemClicked.connect(self._on_database_item_clicked)
        left_layout.addWidget(self.database_tree)
        
        splitter.addWidget(left_panel)
        
        # Right panel - Results tabs
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(5, 10, 10, 10)
        
        # Tab widget for different views
        self.tabs = QTabWidget()
        self.tabs.setStyleSheet("""
            QTabWidget::pane {
                border: 1px solid #ddd;
                border-radius: 6px;
                background-color: white;
            }
            QTabBar::tab {
                background-color: #f0f0f0;
                padding: 8px 20px;
                margin-right: 2px;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
                font-size: 11px;
            }
            QTabBar::tab:selected {
                background-color: white;
                border-bottom: 2px solid #1976D2;
            }
        """)
        
        # Table tab
        table_widget = QWidget()
        table_layout = QVBoxLayout(table_widget)
        table_layout.setContentsMargins(5, 5, 5, 5)
        
        self.results_table = QTableWidget()
        self.results_table.setAlternatingRowColors(True)
        self.results_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.results_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.results_table.horizontalHeader().setStretchLastSection(True)
        self.results_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.results_table.verticalHeader().setVisible(False)
        self.results_table.setStyleSheet("""
            QTableWidget {
                border: none;
                gridline-color: #e0e0e0;
                font-size: 11px;
            }
            QTableWidget::item {
                padding: 8px;
            }
            QTableWidget::item:selected {
                background-color: #e3f2fd;
                color: #1976D2;
            }
            QHeaderView::section {
                background-color: #f5f5f5;
                padding: 10px;
                border: none;
                border-bottom: 2px solid #1976D2;
                font-weight: bold;
                font-size: 11px;
            }
        """)
        self.results_table.cellClicked.connect(self._on_table_cell_clicked)
        table_layout.addWidget(self.results_table)
        
        self.tabs.addTab(table_widget, "📊 Table View")
        
        # JSON tab
        json_widget = QWidget()
        json_layout = QVBoxLayout(json_widget)
        json_layout.setContentsMargins(5, 5, 5, 5)
        
        self.json_view = QTextEdit()
        self.json_view.setReadOnly(True)
        self.json_view.setFont(QFont("Consolas", 10))
        self.json_view.setStyleSheet("""
            QTextEdit {
                border: none;
                background-color: #1e1e1e;
                color: #d4d4d4;
                padding: 10px;
            }
        """)
        json_layout.addWidget(self.json_view)
        
        self.tabs.addTab(json_widget, "📝 JSON View")
        
        right_layout.addWidget(self.tabs)
        
        # Export buttons
        export_layout = QHBoxLayout()
        export_layout.setSpacing(10)
        
        self.export_json_btn = QPushButton("💾 Export JSON")
        self.export_json_btn.setStyleSheet("""
            QPushButton {
                background-color: #2196F3;
                color: white;
                border: none;
                padding: 8px 20px;
                border-radius: 4px;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: #1976D2;
            }
            QPushButton:disabled {
                background-color: #ccc;
            }
        """)
        self.export_json_btn.clicked.connect(self._export_json)
        self.export_json_btn.setEnabled(False)
        export_layout.addWidget(self.export_json_btn)
        
        self.export_csv_btn = QPushButton("📄 Export CSV")
        self.export_csv_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border: none;
                padding: 8px 20px;
                border-radius: 4px;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
            QPushButton:disabled {
                background-color: #ccc;
            }
        """)
        self.export_csv_btn.clicked.connect(self._export_csv)
        self.export_csv_btn.setEnabled(False)
        export_layout.addWidget(self.export_csv_btn)
        
        export_layout.addStretch()
        right_layout.addLayout(export_layout)
        
        splitter.addWidget(right_panel)
        
        # Set splitter proportions
        splitter.setSizes([200, 600])
        
        layout.addWidget(splitter)
    
    def set_results(self, results: Dict[str, List[Dict]]):
        """Set the search results data."""
        self.results_data = results
        self._populate_database_tree()
        self._update_results_count()
        
        # Enable/disable export buttons
        has_results = any(len(v) > 0 for v in results.values())
        self.export_json_btn.setEnabled(has_results)
        self.export_csv_btn.setEnabled(has_results)
    
    def clear_results(self):
        """Clear all results."""
        self.results_data = {}
        self.database_tree.clear()
        self.results_table.setRowCount(0)
        self.results_table.setColumnCount(0)
        self.json_view.clear()
        self.results_count_label.setText("No results")
        self.export_json_btn.setEnabled(False)
        self.export_csv_btn.setEnabled(False)
    
    def _populate_database_tree(self):
        """Populate the database tree with results."""
        self.database_tree.clear()
        
        # Database icons and colors
        db_colors = {
            'materials_project': ('#2196F3', '🔷'),
            'jarvis': ('#4CAF50', '🟢'),
            'aflow': ('#FF9800', '🟠'),
            'alexandria': ('#9C27B0', '🟣'),
            'materials_cloud': ('#00BCD4', '🔵'),
            'oqmd': ('#795548', '🟤'),
            'mpds': ('#E91E63', '🔴'),
        }
        
        # Add "All Results" item
        total_count = sum(len(v) for v in self.results_data.values())
        all_item = QTreeWidgetItem(["📁 All Results ({})".format(total_count)])
        all_item.setData(0, Qt.ItemDataRole.UserRole, 'all')
        self.database_tree.addTopLevelItem(all_item)
        
        # Add database items
        for db_id, materials in self.results_data.items():
            if len(materials) > 0:
                color, icon = db_colors.get(db_id, ('#666', '⚪'))
                db_name = self._format_db_name(db_id)
                
                item = QTreeWidgetItem([f"{icon} {db_name} ({len(materials)})"])
                item.setData(0, Qt.ItemDataRole.UserRole, db_id)
                item.setForeground(0, QBrush(QColor(color)))
                self.database_tree.addTopLevelItem(item)
                
                # Add material sub-items
                for i, material in enumerate(materials):
                    mat_id = material.get('material_id', f'Entry {i+1}')
                    formula = material.get('formula', 'Unknown')
                    
                    child_item = QTreeWidgetItem([f"  {formula} ({mat_id})"])
                    child_item.setData(0, Qt.ItemDataRole.UserRole, ('material', db_id, i))
                    item.addChild(child_item)
        
        # Expand all items
        self.database_tree.expandAll()
        
        # Select "All Results" by default
        if total_count > 0:
            self.database_tree.setCurrentItem(all_item)
            self._show_all_results()
    
    def _format_db_name(self, db_id: str) -> str:
        """Format database ID to display name."""
        names = {
            'materials_project': 'Materials Project',
            'jarvis': 'JARVIS',
            'aflow': 'AFLOW',
            'alexandria': 'Alexandria',
            'materials_cloud': 'Materials Cloud',
            'oqmd': 'OQMD',
            'mpds': 'MPDS',
        }
        return names.get(db_id, db_id)
    
    def _update_results_count(self):
        """Update the results count label."""
        total = sum(len(v) for v in self.results_data.values())
        db_count = sum(1 for v in self.results_data.values() if len(v) > 0)
        
        if total == 0:
            self.results_count_label.setText("No results")
        else:
            self.results_count_label.setText(f"{total} materials from {db_count} database(s)")
    
    def _on_database_item_clicked(self, item: QTreeWidgetItem, column: int):
        """Handle click on database tree item."""
        data = item.data(0, Qt.ItemDataRole.UserRole)
        
        if data == 'all':
            self._show_all_results()
        elif isinstance(data, tuple) and data[0] == 'material':
            _, db_id, index = data
            self._show_material_details(db_id, index)
        elif isinstance(data, str):
            self._show_database_results(data)
    
    def _show_all_results(self):
        """Show all results in the table."""
        all_materials = []
        for db_id, materials in self.results_data.items():
            for mat in materials:
                mat_copy = mat.copy()
                mat_copy['_db_id'] = db_id
                all_materials.append(mat_copy)
        
        self._populate_table(all_materials)
        self._update_json_view(self.results_data)
    
    def _show_database_results(self, db_id: str):
        """Show results for a specific database."""
        materials = self.results_data.get(db_id, [])
        for mat in materials:
            mat['_db_id'] = db_id
        self._populate_table(materials)
        self._update_json_view({db_id: materials})
    
    def _show_material_details(self, db_id: str, index: int):
        """Show details for a specific material."""
        materials = self.results_data.get(db_id, [])
        if 0 <= index < len(materials):
            material = materials[index]
            material['_db_id'] = db_id
            self._populate_table([material])
            self._update_json_view(material)
            self.current_selection = material
            self.material_selected.emit(material)
    
    def _populate_table(self, materials: List[Dict]):
        """Populate the results table with materials."""
        if not materials:
            self.results_table.setRowCount(0)
            return
        
        # Set up columns
        columns = [col[1] for col in SUMMARY_COLUMNS]
        columns.insert(0, 'Database')  # Add database column first
        
        self.results_table.setColumnCount(len(columns))
        self.results_table.setHorizontalHeaderLabels(columns)
        self.results_table.setRowCount(len(materials))
        
        # Populate rows
        for row, material in enumerate(materials):
            # Database column
            db_id = material.get('_db_id', material.get('source_database', 'Unknown'))
            db_name = self._format_db_name(db_id)
            db_item = QTableWidgetItem(db_name)
            db_item.setData(Qt.ItemDataRole.UserRole, material)
            self.results_table.setItem(row, 0, db_item)
            
            # Property columns
            for col, (prop_key, _) in enumerate(SUMMARY_COLUMNS, start=1):
                value = material.get(prop_key, '')
                
                # Format numeric values
                if isinstance(value, float):
                    if abs(value) < 0.001 and value != 0:
                        display = f"{value:.2e}"
                    else:
                        display = f"{value:.4f}"
                elif value is None:
                    display = "—"
                else:
                    display = str(value)
                
                item = QTableWidgetItem(display)
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.results_table.setItem(row, col, item)
        
        # Resize columns to content
        self.results_table.resizeColumnsToContents()
    
    def _on_table_cell_clicked(self, row: int, column: int):
        """Handle click on table cell."""
        item = self.results_table.item(row, 0)
        if item:
            material = item.data(Qt.ItemDataRole.UserRole)
            if material:
                self.current_selection = material
                self._update_json_view(material)
                self.material_selected.emit(material)
    
    def _update_json_view(self, data: Any):
        """Update the JSON view with data."""
        # Remove structure objects for display (they're not JSON serializable)
        def clean_for_json(obj):
            if isinstance(obj, dict):
                return {k: clean_for_json(v) for k, v in obj.items() 
                        if k not in ('structure', '_db_id') and not k.startswith('_')}
            elif isinstance(obj, list):
                return [clean_for_json(item) for item in obj]
            elif hasattr(obj, '__dict__'):
                return str(obj)
            else:
                return obj
        
        cleaned = clean_for_json(data)
        formatted = json.dumps(cleaned, indent=2, default=str)
        
        # Syntax highlighting for JSON
        highlighted = self._highlight_json(formatted)
        self.json_view.setHtml(highlighted)
    
    def _highlight_json(self, json_str: str) -> str:
        """Apply syntax highlighting to JSON string."""
        import re
        
        # Escape HTML
        json_str = json_str.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
        
        # Color scheme
        json_str = re.sub(r'"([^"]+)":', r'<span style="color: #9cdcfe;">"\1"</span>:', json_str)
        json_str = re.sub(r': "([^"]*)"', r': <span style="color: #ce9178;">"\1"</span>', json_str)
        json_str = re.sub(r': (-?\d+\.?\d*)', r': <span style="color: #b5cea8;">\1</span>', json_str)
        json_str = re.sub(r': (true|false|null)', r': <span style="color: #569cd6;">\1</span>', json_str)
        
        return f'<pre style="font-family: Consolas, monospace; margin: 0;">{json_str}</pre>'
    
    def _export_json(self):
        """Export results to JSON file."""
        if not self.results_data:
            return
        
        filename, _ = QFileDialog.getSaveFileName(
            self, "Export JSON", "", "JSON Files (*.json)"
        )
        
        if filename:
            if not filename.endswith('.json'):
                filename += '.json'
            
            try:
                # Clean data for export
                def clean_for_export(obj):
                    if isinstance(obj, dict):
                        return {k: clean_for_export(v) for k, v in obj.items() 
                                if k not in ('structure', '_db_id')}
                    elif isinstance(obj, list):
                        return [clean_for_export(item) for item in obj]
                    elif hasattr(obj, 'as_dict'):
                        return obj.as_dict()
                    elif hasattr(obj, '__dict__'):
                        return str(obj)
                    else:
                        return obj
                
                cleaned = clean_for_export(self.results_data)
                
                with open(filename, 'w') as f:
                    json.dump(cleaned, f, indent=2, default=str)
                
                QMessageBox.information(self, "Export Successful", 
                                        f"Results exported to:\n{filename}")
            except Exception as e:
                QMessageBox.critical(self, "Export Error", f"Failed to export: {str(e)}")
    
    def _export_csv(self):
        """Export results to CSV file."""
        if not self.results_data:
            return
        
        filename, _ = QFileDialog.getSaveFileName(
            self, "Export CSV", "", "CSV Files (*.csv)"
        )
        
        if filename:
            if not filename.endswith('.csv'):
                filename += '.csv'
            
            try:
                import csv
                
                # Gather all materials
                all_materials = []
                for db_id, materials in self.results_data.items():
                    for mat in materials:
                        row = {'database': self._format_db_name(db_id)}
                        for prop_key, _ in SUMMARY_COLUMNS:
                            row[prop_key] = mat.get(prop_key, '')
                        all_materials.append(row)
                
                if all_materials:
                    headers = ['database'] + [col[0] for col in SUMMARY_COLUMNS]
                    
                    with open(filename, 'w', newline='') as f:
                        writer = csv.DictWriter(f, fieldnames=headers)
                        writer.writeheader()
                        writer.writerows(all_materials)
                    
                    QMessageBox.information(self, "Export Successful",
                                            f"Results exported to:\n{filename}")
            except Exception as e:
                QMessageBox.critical(self, "Export Error", f"Failed to export: {str(e)}")
    
    def get_current_selection(self) -> Optional[Dict]:
        """Return the currently selected material."""
        return self.current_selection
