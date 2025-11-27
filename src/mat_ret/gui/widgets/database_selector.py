"""
Database Selector Widget

Provides checkboxes for selecting which materials databases to query.
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, 
    QCheckBox, QLabel, QLineEdit, QSpinBox, QPushButton,
    QFrame, QFormLayout
)
from PyQt6.QtCore import pyqtSignal, Qt
from PyQt6.QtGui import QFont, QIcon


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
    }
}


class DatabaseSelectorWidget(QWidget):
    """Widget for selecting databases and configuring API keys."""
    
    # Signal emitted when database selection changes
    selection_changed = pyqtSignal(list)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.checkboxes = {}
        self.api_key_inputs = {}
        self._setup_ui()
        self._load_saved_keys()
    
    def _setup_ui(self):
        """Set up the user interface."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(15)
        
        # Title
        title = QLabel("📊 Database Selection")
        title.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        title.setStyleSheet("color: #1976D2; margin-bottom: 10px;")
        layout.addWidget(title)
        
        # Databases Group
        db_group = QGroupBox("Select Databases")
        db_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                font-size: 12px;
                border: 2px solid #e0e0e0;
                border-radius: 8px;
                margin-top: 10px;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }
        """)
        db_layout = QVBoxLayout(db_group)
        db_layout.setSpacing(8)
        
        # Create checkboxes for each database
        for db_id, config in DATABASE_CONFIG.items():
            cb_layout = QHBoxLayout()
            
            checkbox = QCheckBox(f"{config['icon']} {config['name']}")
            checkbox.setToolTip(config['description'])
            checkbox.setChecked(not config['requires_api_key'])  # Pre-select non-API databases
            checkbox.setStyleSheet(f"""
                QCheckBox {{
                    font-size: 11px;
                    padding: 5px;
                }}
                QCheckBox::indicator {{
                    width: 18px;
                    height: 18px;
                }}
                QCheckBox::indicator:checked {{
                    background-color: {config['color']};
                    border: 2px solid {config['color']};
                    border-radius: 3px;
                }}
            """)
            checkbox.stateChanged.connect(self._on_selection_changed)
            self.checkboxes[db_id] = checkbox
            cb_layout.addWidget(checkbox)
            
            # Add API key indicator
            if config['requires_api_key']:
                key_label = QLabel("🔑")
                key_label.setToolTip("Requires API key")
                key_label.setStyleSheet("font-size: 10px;")
                cb_layout.addWidget(key_label)
            
            cb_layout.addStretch()
            db_layout.addLayout(cb_layout)
        
        layout.addWidget(db_group)
        
        # Quick selection buttons
        btn_layout = QHBoxLayout()
        
        select_all_btn = QPushButton("Select All")
        select_all_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border: none;
                padding: 5px 15px;
                border-radius: 4px;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
        """)
        select_all_btn.clicked.connect(self._select_all)
        btn_layout.addWidget(select_all_btn)
        
        select_none_btn = QPushButton("Clear All")
        select_none_btn.setStyleSheet("""
            QPushButton {
                background-color: #f44336;
                color: white;
                border: none;
                padding: 5px 15px;
                border-radius: 4px;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: #da190b;
            }
        """)
        select_none_btn.clicked.connect(self._select_none)
        btn_layout.addWidget(select_none_btn)
        
        layout.addLayout(btn_layout)
        
        # Separator
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setStyleSheet("background-color: #e0e0e0;")
        layout.addWidget(separator)
        
        # API Keys Group
        api_group = QGroupBox("🔑 API Keys")
        api_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                font-size: 12px;
                border: 2px solid #e0e0e0;
                border-radius: 8px;
                margin-top: 10px;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }
        """)
        api_layout = QFormLayout(api_group)
        api_layout.setSpacing(10)
        
        # Materials Project API Key
        mp_key_input = QLineEdit()
        mp_key_input.setPlaceholderText("Enter Materials Project API key")
        mp_key_input.setEchoMode(QLineEdit.EchoMode.Password)
        mp_key_input.setStyleSheet("""
            QLineEdit {
                padding: 8px;
                border: 1px solid #ccc;
                border-radius: 4px;
                font-size: 11px;
            }
            QLineEdit:focus {
                border: 2px solid #2196F3;
            }
        """)
        self.api_key_inputs['materials_project'] = mp_key_input
        api_layout.addRow("MP Key:", mp_key_input)
        
        # MPDS API Key
        mpds_key_input = QLineEdit()
        mpds_key_input.setPlaceholderText("Enter MPDS API key")
        mpds_key_input.setEchoMode(QLineEdit.EchoMode.Password)
        mpds_key_input.setStyleSheet("""
            QLineEdit {
                padding: 8px;
                border: 1px solid #ccc;
                border-radius: 4px;
                font-size: 11px;
            }
            QLineEdit:focus {
                border: 2px solid #E91E63;
            }
        """)
        self.api_key_inputs['mpds'] = mpds_key_input
        api_layout.addRow("MPDS Key:", mpds_key_input)
        
        layout.addWidget(api_group)
        
        # Search Settings Group
        settings_group = QGroupBox("⚙️ Search Settings")
        settings_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                font-size: 12px;
                border: 2px solid #e0e0e0;
                border-radius: 8px;
                margin-top: 10px;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }
        """)
        settings_layout = QFormLayout(settings_group)
        settings_layout.setSpacing(10)
        
        # Results limit spinner
        self.limit_spinner = QSpinBox()
        self.limit_spinner.setRange(1, 100)
        self.limit_spinner.setValue(10)
        self.limit_spinner.setSuffix(" results")
        self.limit_spinner.setStyleSheet("""
            QSpinBox {
                padding: 5px;
                border: 1px solid #ccc;
                border-radius: 4px;
                font-size: 11px;
            }
        """)
        settings_layout.addRow("Limit per DB:", self.limit_spinner)
        
        layout.addWidget(settings_group)
        
        # Add stretch at the bottom
        layout.addStretch()
    
    def _load_saved_keys(self):
        """Load API keys from config if available."""
        try:
            import sys
            sys.path.insert(0, str(__file__).rsplit('/gui', 1)[0])
            from config import MP_API_KEY, MPDS_API_KEY
            
            if MP_API_KEY:
                self.api_key_inputs['materials_project'].setText(MP_API_KEY)
            if MPDS_API_KEY:
                self.api_key_inputs['mpds'].setText(MPDS_API_KEY)
        except (ImportError, AttributeError):
            pass
    
    def _on_selection_changed(self):
        """Handle database selection change."""
        selected = self.get_selected_databases()
        self.selection_changed.emit(selected)
    
    def _select_all(self):
        """Select all databases."""
        for checkbox in self.checkboxes.values():
            checkbox.setChecked(True)
    
    def _select_none(self):
        """Deselect all databases."""
        for checkbox in self.checkboxes.values():
            checkbox.setChecked(False)
    
    def get_selected_databases(self) -> list:
        """Return list of selected database IDs."""
        return [db_id for db_id, cb in self.checkboxes.items() if cb.isChecked()]
    
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
