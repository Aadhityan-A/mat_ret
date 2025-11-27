"""
Structure Viewer Widget

Displays crystal structure visualization using matplotlib and pymatgen.
Supports 2D projection and 3D rotation views.
"""

from typing import Dict, Optional, Any
import numpy as np

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QComboBox, QFrame, QFileDialog, QMessageBox, QSizePolicy,
    QSlider, QSpinBox, QGroupBox, QFormLayout, QCheckBox
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont

# Matplotlib imports for embedding in PyQt6
import matplotlib
matplotlib.use('QtAgg')
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qtagg import NavigationToolbar2QT as NavigationToolbar
from matplotlib.figure import Figure
from mpl_toolkits.mplot3d import Axes3D
import matplotlib.pyplot as plt


# Element colors for visualization (subset of common elements)
ELEMENT_COLORS = {
    'H': '#FFFFFF', 'He': '#D9FFFF', 'Li': '#CC80FF', 'Be': '#C2FF00',
    'B': '#FFB5B5', 'C': '#909090', 'N': '#3050F8', 'O': '#FF0D0D',
    'F': '#90E050', 'Ne': '#B3E3F5', 'Na': '#AB5CF2', 'Mg': '#8AFF00',
    'Al': '#BFA6A6', 'Si': '#F0C8A0', 'P': '#FF8000', 'S': '#FFFF30',
    'Cl': '#1FF01F', 'Ar': '#80D1E3', 'K': '#8F40D4', 'Ca': '#3DFF00',
    'Sc': '#E6E6E6', 'Ti': '#BFC2C7', 'V': '#A6A6AB', 'Cr': '#8A99C7',
    'Mn': '#9C7AC7', 'Fe': '#E06633', 'Co': '#F090A0', 'Ni': '#50D050',
    'Cu': '#C88033', 'Zn': '#7D80B0', 'Ga': '#C28F8F', 'Ge': '#668F8F',
    'As': '#BD80E3', 'Se': '#FFA100', 'Br': '#A62929', 'Kr': '#5CB8D1',
    'Rb': '#702EB0', 'Sr': '#00FF00', 'Y': '#94FFFF', 'Zr': '#94E0E0',
    'Nb': '#73C2C9', 'Mo': '#54B5B5', 'Tc': '#3B9E9E', 'Ru': '#248F8F',
    'Rh': '#0A7D8C', 'Pd': '#006985', 'Ag': '#C0C0C0', 'Cd': '#FFD98F',
    'In': '#A67573', 'Sn': '#668080', 'Sb': '#9E63B5', 'Te': '#D47A00',
    'I': '#940094', 'Xe': '#429EB0', 'Cs': '#57178F', 'Ba': '#00C900',
    'La': '#70D4FF', 'Ce': '#FFFFC7', 'Pr': '#D9FFC7', 'Nd': '#C7FFC7',
    'Pm': '#A3FFC7', 'Sm': '#8FFFC7', 'Eu': '#61FFC7', 'Gd': '#45FFC7',
    'Tb': '#30FFC7', 'Dy': '#1FFFC7', 'Ho': '#00FF9C', 'Er': '#00E675',
    'Tm': '#00D452', 'Yb': '#00BF38', 'Lu': '#00AB24', 'Hf': '#4DC2FF',
    'Ta': '#4DA6FF', 'W': '#2194D6', 'Re': '#267DAB', 'Os': '#266696',
    'Ir': '#175487', 'Pt': '#D0D0E0', 'Au': '#FFD123', 'Hg': '#B8B8D0',
    'Tl': '#A6544D', 'Pb': '#575961', 'Bi': '#9E4FB5', 'Po': '#AB5C00',
    'At': '#754F45', 'Rn': '#428296', 'Fr': '#420066', 'Ra': '#007D00',
    'Ac': '#70ABFA', 'Th': '#00BAFF', 'Pa': '#00A1FF', 'U': '#008FFF',
    'Np': '#0080FF', 'Pu': '#006BFF', 'Am': '#545CF2', 'Cm': '#785CE3',
}

# Element radii for visualization
ELEMENT_RADII = {
    'H': 0.31, 'He': 0.28, 'Li': 1.28, 'Be': 0.96, 'B': 0.84, 'C': 0.76,
    'N': 0.71, 'O': 0.66, 'F': 0.57, 'Ne': 0.58, 'Na': 1.66, 'Mg': 1.41,
    'Al': 1.21, 'Si': 1.11, 'P': 1.07, 'S': 1.05, 'Cl': 1.02, 'Ar': 1.06,
    'K': 2.03, 'Ca': 1.76, 'Sc': 1.70, 'Ti': 1.60, 'V': 1.53, 'Cr': 1.39,
    'Mn': 1.39, 'Fe': 1.32, 'Co': 1.26, 'Ni': 1.24, 'Cu': 1.32, 'Zn': 1.22,
    'Ga': 1.22, 'Ge': 1.20, 'As': 1.19, 'Se': 1.20, 'Br': 1.20, 'Kr': 1.16,
}


class StructureViewerWidget(QWidget):
    """Widget for 3D crystal structure visualization."""
    
    # Signal emitted when structure is exported
    structure_exported = pyqtSignal(str)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_structure = None
        self.current_material = None
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
        
        title = QLabel("🔬 Structure Viewer")
        title.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        title.setStyleSheet("color: #333;")
        title_layout.addWidget(title)
        
        self.structure_info_label = QLabel("No structure loaded")
        self.structure_info_label.setStyleSheet("color: #666; font-size: 12px;")
        title_layout.addStretch()
        title_layout.addWidget(self.structure_info_label)
        
        layout.addWidget(title_bar)
        
        # Main content
        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(10, 10, 10, 10)
        content_layout.setSpacing(10)
        
        # Matplotlib figure
        self.figure = Figure(figsize=(8, 6), dpi=100, facecolor='white')
        self.canvas = FigureCanvas(self.figure)
        self.canvas.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.canvas.setStyleSheet("border: 1px solid #ddd; border-radius: 6px;")
        
        # Navigation toolbar
        self.toolbar = NavigationToolbar(self.canvas, self)
        self.toolbar.setStyleSheet("""
            QToolBar {
                background-color: #f5f5f5;
                border: 1px solid #ddd;
                border-radius: 4px;
                padding: 2px;
            }
        """)
        
        content_layout.addWidget(self.toolbar)
        content_layout.addWidget(self.canvas, stretch=1)
        
        # Controls panel
        controls = QWidget()
        controls_layout = QHBoxLayout(controls)
        controls_layout.setContentsMargins(0, 5, 0, 0)
        controls_layout.setSpacing(15)
        
        # View options
        view_group = QGroupBox("View Options")
        view_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                font-size: 11px;
                border: 1px solid #ddd;
                border-radius: 6px;
                margin-top: 8px;
                padding-top: 8px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }
        """)
        view_layout = QHBoxLayout(view_group)
        view_layout.setSpacing(10)
        
        # View type selector
        view_label = QLabel("View:")
        view_label.setStyleSheet("font-size: 11px;")
        view_layout.addWidget(view_label)
        
        self.view_combo = QComboBox()
        self.view_combo.addItems(["3D Perspective", "XY Plane", "XZ Plane", "YZ Plane"])
        self.view_combo.setStyleSheet("""
            QComboBox {
                padding: 5px;
                border: 1px solid #ccc;
                border-radius: 4px;
                font-size: 11px;
                min-width: 100px;
            }
        """)
        self.view_combo.currentIndexChanged.connect(self._update_view)
        view_layout.addWidget(self.view_combo)
        
        # Show bonds checkbox
        self.show_bonds_cb = QCheckBox("Show Bonds")
        self.show_bonds_cb.setChecked(True)
        self.show_bonds_cb.setStyleSheet("font-size: 11px;")
        self.show_bonds_cb.stateChanged.connect(self._refresh_plot)
        view_layout.addWidget(self.show_bonds_cb)
        
        # Show unit cell checkbox
        self.show_cell_cb = QCheckBox("Show Unit Cell")
        self.show_cell_cb.setChecked(True)
        self.show_cell_cb.setStyleSheet("font-size: 11px;")
        self.show_cell_cb.stateChanged.connect(self._refresh_plot)
        view_layout.addWidget(self.show_cell_cb)
        
        controls_layout.addWidget(view_group)
        
        # Atom size control
        size_group = QGroupBox("Atom Size")
        size_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                font-size: 11px;
                border: 1px solid #ddd;
                border-radius: 6px;
                margin-top: 8px;
                padding-top: 8px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }
        """)
        size_layout = QHBoxLayout(size_group)
        
        self.size_slider = QSlider(Qt.Orientation.Horizontal)
        self.size_slider.setRange(50, 300)
        self.size_slider.setValue(150)
        self.size_slider.setStyleSheet("""
            QSlider::groove:horizontal {
                height: 6px;
                background: #ddd;
                border-radius: 3px;
            }
            QSlider::handle:horizontal {
                width: 16px;
                margin: -5px 0;
                background: #1976D2;
                border-radius: 8px;
            }
        """)
        self.size_slider.valueChanged.connect(self._refresh_plot)
        size_layout.addWidget(self.size_slider)
        
        controls_layout.addWidget(size_group)
        
        controls_layout.addStretch()
        
        # Export button
        self.export_cif_btn = QPushButton("💾 Export CIF")
        self.export_cif_btn.setStyleSheet("""
            QPushButton {
                background-color: #FF9800;
                color: white;
                border: none;
                padding: 8px 20px;
                border-radius: 4px;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: #F57C00;
            }
            QPushButton:disabled {
                background-color: #ccc;
            }
        """)
        self.export_cif_btn.clicked.connect(self._export_cif)
        self.export_cif_btn.setEnabled(False)
        controls_layout.addWidget(self.export_cif_btn)
        
        content_layout.addWidget(controls)
        
        layout.addWidget(content)
        
        # Show placeholder message
        self._show_placeholder()
    
    def _show_placeholder(self):
        """Show a placeholder message when no structure is loaded."""
        self.figure.clear()
        ax = self.figure.add_subplot(111)
        ax.text(0.5, 0.5, "Select a material to view its structure",
                ha='center', va='center', fontsize=14, color='#999',
                transform=ax.transAxes)
        ax.set_xlim(0, 1)
        ax.set_ylim(0, 1)
        ax.axis('off')
        self.canvas.draw()
    
    def set_structure(self, material: Dict):
        """Set the structure to display from material data."""
        self.current_material = material
        structure = material.get('structure')
        
        if structure is None:
            self._show_placeholder()
            self.structure_info_label.setText("No structure available")
            self.export_cif_btn.setEnabled(False)
            return
        
        self.current_structure = structure
        
        # Update info label
        formula = material.get('formula', 'Unknown')
        mat_id = material.get('material_id', '')
        space_group = material.get('space_group', '')
        
        info_text = f"{formula}"
        if mat_id:
            info_text += f" ({mat_id})"
        if space_group:
            info_text += f" • {space_group}"
        
        self.structure_info_label.setText(info_text)
        self.export_cif_btn.setEnabled(True)
        
        # Plot the structure
        self._plot_structure()
    
    def clear_structure(self):
        """Clear the current structure display."""
        self.current_structure = None
        self.current_material = None
        self._show_placeholder()
        self.structure_info_label.setText("No structure loaded")
        self.export_cif_btn.setEnabled(False)
    
    def _plot_structure(self):
        """Plot the crystal structure."""
        if self.current_structure is None:
            return
        
        self.figure.clear()
        
        view_type = self.view_combo.currentText()
        
        if view_type == "3D Perspective":
            self._plot_3d()
        else:
            self._plot_2d(view_type)
        
        self.canvas.draw()
    
    def _plot_3d(self):
        """Create a 3D plot of the structure."""
        ax = self.figure.add_subplot(111, projection='3d')
        
        structure = self.current_structure
        
        # Get atom positions and species
        coords = structure.cart_coords
        species = [str(site.specie) for site in structure.sites]
        
        # Plot atoms
        size_scale = self.size_slider.value() / 100.0
        
        for i, (coord, elem) in enumerate(zip(coords, species)):
            color = ELEMENT_COLORS.get(elem, '#808080')
            radius = ELEMENT_RADII.get(elem, 1.0) * size_scale * 50
            ax.scatter(coord[0], coord[1], coord[2], 
                      c=color, s=radius, alpha=0.9, edgecolors='black', linewidths=0.5)
        
        # Plot unit cell
        if self.show_cell_cb.isChecked():
            self._plot_unit_cell_3d(ax, structure.lattice.matrix)
        
        # Plot bonds
        if self.show_bonds_cb.isChecked():
            self._plot_bonds_3d(ax, coords, species)
        
        # Set labels and style
        ax.set_xlabel('X (Å)', fontsize=10)
        ax.set_ylabel('Y (Å)', fontsize=10)
        ax.set_zlabel('Z (Å)', fontsize=10)
        
        # Set equal aspect ratio
        max_range = np.max([coords.max() - coords.min()]) * 0.5
        mid = coords.mean(axis=0)
        ax.set_xlim(mid[0] - max_range, mid[0] + max_range)
        ax.set_ylim(mid[1] - max_range, mid[1] + max_range)
        ax.set_zlim(mid[2] - max_range, mid[2] + max_range)
        
        ax.set_box_aspect([1, 1, 1])
        
        # Add legend
        unique_species = list(set(species))
        for elem in unique_species:
            color = ELEMENT_COLORS.get(elem, '#808080')
            ax.scatter([], [], [], c=color, s=50, label=elem)
        ax.legend(loc='upper left', fontsize=9)
        
        self.figure.tight_layout()
    
    def _plot_2d(self, view_type: str):
        """Create a 2D projection plot."""
        ax = self.figure.add_subplot(111)
        
        structure = self.current_structure
        coords = structure.cart_coords
        species = [str(site.specie) for site in structure.sites]
        
        # Determine projection axes
        if view_type == "XY Plane":
            x_idx, y_idx = 0, 1
            xlabel, ylabel = 'X (Å)', 'Y (Å)'
        elif view_type == "XZ Plane":
            x_idx, y_idx = 0, 2
            xlabel, ylabel = 'X (Å)', 'Z (Å)'
        else:  # YZ Plane
            x_idx, y_idx = 1, 2
            xlabel, ylabel = 'Y (Å)', 'Z (Å)'
        
        # Plot atoms
        size_scale = self.size_slider.value() / 100.0
        
        for coord, elem in zip(coords, species):
            color = ELEMENT_COLORS.get(elem, '#808080')
            radius = ELEMENT_RADII.get(elem, 1.0) * size_scale * 200
            ax.scatter(coord[x_idx], coord[y_idx], 
                      c=color, s=radius, alpha=0.9, edgecolors='black', linewidths=0.5, zorder=2)
        
        # Plot unit cell
        if self.show_cell_cb.isChecked():
            self._plot_unit_cell_2d(ax, structure.lattice.matrix, x_idx, y_idx)
        
        # Plot bonds
        if self.show_bonds_cb.isChecked():
            self._plot_bonds_2d(ax, coords, species, x_idx, y_idx)
        
        ax.set_xlabel(xlabel, fontsize=11)
        ax.set_ylabel(ylabel, fontsize=11)
        ax.set_aspect('equal')
        ax.grid(True, alpha=0.3)
        
        # Add legend
        unique_species = list(set(species))
        for elem in unique_species:
            color = ELEMENT_COLORS.get(elem, '#808080')
            ax.scatter([], [], c=color, s=100, label=elem)
        ax.legend(loc='upper right', fontsize=9)
        
        self.figure.tight_layout()
    
    def _plot_unit_cell_3d(self, ax, lattice_matrix):
        """Plot unit cell edges in 3D."""
        origin = np.array([0, 0, 0])
        a, b, c = lattice_matrix
        
        # Define the 12 edges of the unit cell
        edges = [
            (origin, a), (origin, b), (origin, c),
            (a, a + b), (a, a + c),
            (b, b + a), (b, b + c),
            (c, c + a), (c, c + b),
            (a + b, a + b + c), (a + c, a + b + c), (b + c, a + b + c)
        ]
        
        for start, end in edges:
            ax.plot3D([start[0], end[0]], [start[1], end[1]], [start[2], end[2]],
                     'k-', alpha=0.4, linewidth=1)
    
    def _plot_unit_cell_2d(self, ax, lattice_matrix, x_idx, y_idx):
        """Plot unit cell edges in 2D."""
        origin = np.array([0, 0, 0])
        a, b, c = lattice_matrix
        
        # Get 2D projections
        vertices_2d = [
            (origin[x_idx], origin[y_idx]),
            (a[x_idx], a[y_idx]),
            ((a + b)[x_idx], (a + b)[y_idx]),
            (b[x_idx], b[y_idx]),
        ]
        vertices_2d.append(vertices_2d[0])  # Close the rectangle
        
        xs, ys = zip(*vertices_2d)
        ax.plot(xs, ys, 'k-', alpha=0.4, linewidth=1.5, zorder=1)
    
    def _plot_bonds_3d(self, ax, coords, species, max_bond_length=3.0):
        """Plot bonds between atoms in 3D."""
        n_atoms = len(coords)
        
        for i in range(n_atoms):
            for j in range(i + 1, n_atoms):
                dist = np.linalg.norm(coords[i] - coords[j])
                if dist < max_bond_length:
                    ax.plot3D([coords[i][0], coords[j][0]],
                             [coords[i][1], coords[j][1]],
                             [coords[i][2], coords[j][2]],
                             'gray', alpha=0.5, linewidth=1)
    
    def _plot_bonds_2d(self, ax, coords, species, x_idx, y_idx, max_bond_length=3.0):
        """Plot bonds between atoms in 2D."""
        n_atoms = len(coords)
        
        for i in range(n_atoms):
            for j in range(i + 1, n_atoms):
                dist = np.linalg.norm(coords[i] - coords[j])
                if dist < max_bond_length:
                    ax.plot([coords[i][x_idx], coords[j][x_idx]],
                           [coords[i][y_idx], coords[j][y_idx]],
                           'gray', alpha=0.5, linewidth=1, zorder=1)
    
    def _update_view(self):
        """Update the view based on combo box selection."""
        if self.current_structure is not None:
            self._plot_structure()
    
    def _refresh_plot(self):
        """Refresh the current plot."""
        if self.current_structure is not None:
            self._plot_structure()
    
    def _export_cif(self):
        """Export the current structure to a CIF file."""
        if self.current_structure is None:
            return
        
        # Suggest filename based on material info
        formula = self.current_material.get('formula', 'structure') if self.current_material else 'structure'
        mat_id = self.current_material.get('material_id', '') if self.current_material else ''
        
        suggested_name = f"{formula}_{mat_id}" if mat_id else formula
        suggested_name = suggested_name.replace('/', '-').replace('\\', '-')
        
        filename, _ = QFileDialog.getSaveFileName(
            self, "Export CIF", f"{suggested_name}.cif", "CIF Files (*.cif)"
        )
        
        if filename:
            if not filename.endswith('.cif'):
                filename += '.cif'
            
            try:
                from pymatgen.io.cif import CifWriter
                
                cif_writer = CifWriter(self.current_structure)
                cif_writer.write_file(filename)
                
                QMessageBox.information(self, "Export Successful",
                                        f"Structure exported to:\n{filename}")
                self.structure_exported.emit(filename)
                
            except Exception as e:
                QMessageBox.critical(self, "Export Error", f"Failed to export: {str(e)}")
