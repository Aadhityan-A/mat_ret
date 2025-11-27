"""
Utility functions for the mat_ret GUI.

Provides helper functions for file export, data conversion, and styling.
"""

import json
import csv
from typing import Dict, List, Any, Optional
from pathlib import Path


def clean_material_for_export(material: Dict) -> Dict:
    """
    Clean a material dictionary for export by removing non-serializable objects.
    
    Args:
        material: Material data dictionary
        
    Returns:
        Cleaned dictionary suitable for JSON export
    """
    cleaned = {}
    
    for key, value in material.items():
        # Skip internal keys and structure objects
        if key.startswith('_'):
            continue
        if key == 'structure':
            # Convert structure to serializable format if possible
            if hasattr(value, 'as_dict'):
                cleaned['structure_dict'] = value.as_dict()
            elif hasattr(value, 'to_json'):
                cleaned['structure_json'] = value.to_json()
            continue
        
        # Handle various types
        if hasattr(value, 'as_dict'):
            cleaned[key] = value.as_dict()
        elif hasattr(value, '__dict__'):
            cleaned[key] = str(value)
        else:
            cleaned[key] = value
    
    return cleaned


def export_results_to_json(results: Dict[str, List[Dict]], 
                           filepath: str,
                           include_structures: bool = False) -> bool:
    """
    Export search results to a JSON file.
    
    Args:
        results: Dictionary of database -> materials list
        filepath: Output file path
        include_structures: Whether to include structure data
        
    Returns:
        True if successful, False otherwise
    """
    try:
        export_data = {}
        
        for db_id, materials in results.items():
            export_data[db_id] = []
            for mat in materials:
                cleaned = clean_material_for_export(mat)
                if not include_structures and 'structure_dict' in cleaned:
                    del cleaned['structure_dict']
                if not include_structures and 'structure_json' in cleaned:
                    del cleaned['structure_json']
                export_data[db_id].append(cleaned)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(export_data, f, indent=2, default=str)
        
        return True
        
    except Exception as e:
        print(f"Error exporting to JSON: {e}")
        return False


def export_results_to_csv(results: Dict[str, List[Dict]], 
                          filepath: str,
                          columns: Optional[List[str]] = None) -> bool:
    """
    Export search results to a CSV file.
    
    Args:
        results: Dictionary of database -> materials list
        filepath: Output file path
        columns: Optional list of column names to include
        
    Returns:
        True if successful, False otherwise
    """
    default_columns = [
        'database', 'material_id', 'formula', 'band_gap',
        'formation_energy_per_atom', 'space_group', 'density',
        'volume', 'functional'
    ]
    
    columns = columns or default_columns
    
    try:
        all_rows = []
        
        for db_id, materials in results.items():
            db_name = format_database_name(db_id)
            
            for mat in materials:
                row = {'database': db_name}
                for col in columns:
                    if col != 'database':
                        row[col] = mat.get(col, '')
                all_rows.append(row)
        
        if all_rows:
            with open(filepath, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=columns)
                writer.writeheader()
                writer.writerows(all_rows)
        
        return True
        
    except Exception as e:
        print(f"Error exporting to CSV: {e}")
        return False


def export_structure_to_cif(structure, filepath: str, 
                            material_info: Optional[Dict] = None) -> bool:
    """
    Export a pymatgen structure to CIF format.
    
    Args:
        structure: Pymatgen Structure object
        filepath: Output file path
        material_info: Optional material metadata to include
        
    Returns:
        True if successful, False otherwise
    """
    try:
        from pymatgen.io.cif import CifWriter
        
        cif_writer = CifWriter(structure)
        cif_writer.write_file(filepath)
        
        # Optionally save metadata alongside
        if material_info:
            metadata_path = Path(filepath).with_suffix('.json')
            cleaned = clean_material_for_export(material_info)
            with open(metadata_path, 'w', encoding='utf-8') as f:
                json.dump(cleaned, f, indent=2, default=str)
        
        return True
        
    except Exception as e:
        print(f"Error exporting to CIF: {e}")
        return False


def format_database_name(db_id: str) -> str:
    """
    Format a database ID to a display name.
    
    Args:
        db_id: Database identifier
        
    Returns:
        Formatted display name
    """
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


def format_property_value(value: Any, precision: int = 4) -> str:
    """
    Format a property value for display.
    
    Args:
        value: The value to format
        precision: Number of decimal places for floats
        
    Returns:
        Formatted string
    """
    if value is None:
        return "—"
    elif isinstance(value, bool):
        return "Yes" if value else "No"
    elif isinstance(value, float):
        if abs(value) < 0.001 and value != 0:
            return f"{value:.2e}"
        else:
            return f"{value:.{precision}f}"
    elif isinstance(value, (list, tuple)):
        return ", ".join(str(v) for v in value)
    else:
        return str(value)


def validate_composition(formula: str) -> tuple:
    """
    Validate a chemical composition formula.
    
    Args:
        formula: Chemical formula string
        
    Returns:
        Tuple of (is_valid, error_message or parsed_formula)
    """
    if not formula or not formula.strip():
        return False, "Please enter a composition formula"
    
    formula = formula.strip()
    
    try:
        from pymatgen.core.composition import Composition
        comp = Composition(formula)
        return True, comp.reduced_formula
    except Exception as e:
        return False, f"Invalid formula: {str(e)}"


# Application stylesheet
APP_STYLESHEET = """
QMainWindow {
    background-color: #f5f5f5;
}

QWidget {
    font-family: "Segoe UI", Arial, sans-serif;
}

QGroupBox {
    font-weight: bold;
    border: 2px solid #e0e0e0;
    border-radius: 8px;
    margin-top: 12px;
    padding-top: 12px;
    background-color: white;
}

QGroupBox::title {
    subcontrol-origin: margin;
    left: 12px;
    padding: 0 8px;
    color: #1976D2;
}

QPushButton {
    font-size: 12px;
    padding: 8px 16px;
    border-radius: 4px;
    border: none;
}

QPushButton:disabled {
    background-color: #cccccc;
    color: #888888;
}

QLineEdit {
    padding: 8px 12px;
    border: 1px solid #ccc;
    border-radius: 4px;
    font-size: 12px;
    background-color: white;
}

QLineEdit:focus {
    border: 2px solid #1976D2;
}

QComboBox {
    padding: 6px 12px;
    border: 1px solid #ccc;
    border-radius: 4px;
    font-size: 12px;
    background-color: white;
}

QSpinBox {
    padding: 6px;
    border: 1px solid #ccc;
    border-radius: 4px;
    font-size: 12px;
}

QTableWidget {
    gridline-color: #e0e0e0;
    background-color: white;
    alternate-background-color: #f9f9f9;
}

QTableWidget::item:selected {
    background-color: #e3f2fd;
    color: #1976D2;
}

QHeaderView::section {
    background-color: #f5f5f5;
    padding: 8px;
    border: none;
    border-bottom: 2px solid #1976D2;
    font-weight: bold;
}

QTreeWidget {
    border: 1px solid #ddd;
    border-radius: 6px;
    background-color: white;
}

QTreeWidget::item {
    padding: 6px;
}

QTreeWidget::item:selected {
    background-color: #e3f2fd;
    color: #1976D2;
}

QScrollBar:vertical {
    background-color: #f0f0f0;
    width: 12px;
    border-radius: 6px;
}

QScrollBar::handle:vertical {
    background-color: #c0c0c0;
    border-radius: 6px;
    min-height: 20px;
}

QScrollBar::handle:vertical:hover {
    background-color: #a0a0a0;
}

QStatusBar {
    background-color: #f5f5f5;
    border-top: 1px solid #e0e0e0;
}

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
}

QTabBar::tab:selected {
    background-color: white;
    border-bottom: 2px solid #1976D2;
}

QProgressBar {
    border: 1px solid #ddd;
    border-radius: 4px;
    text-align: center;
    background-color: #f0f0f0;
}

QProgressBar::chunk {
    background-color: #1976D2;
    border-radius: 3px;
}

QMessageBox {
    background-color: white;
}

QToolTip {
    background-color: #333;
    color: white;
    border: none;
    padding: 6px;
    border-radius: 4px;
}
"""


# Color schemes for different databases
DATABASE_COLORS = {
    'materials_project': '#2196F3',
    'jarvis': '#4CAF50',
    'aflow': '#FF9800',
    'alexandria': '#9C27B0',
    'materials_cloud': '#00BCD4',
    'oqmd': '#795548',
    'mpds': '#E91E63',
}


def get_database_color(db_id: str) -> str:
    """Get the color associated with a database."""
    return DATABASE_COLORS.get(db_id, '#666666')
