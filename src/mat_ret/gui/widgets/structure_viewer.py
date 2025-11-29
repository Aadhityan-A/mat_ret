"""
Structure Viewer Widget

Professional 3D crystal structure visualization using PyQtGraph with OpenGL.
Provides publication-quality rendering with proper atom spheres, bonds, and unit cells.
"""

from typing import Dict, Optional, List, Tuple
import numpy as np

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QComboBox, QFrame, QFileDialog, QMessageBox, QSizePolicy,
    QSlider, QGroupBox, QCheckBox, QSpinBox, QDoubleSpinBox,
    QToolButton, QMenu, QWidgetAction, QColorDialog
)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer
from PyQt6.QtGui import QFont, QColor, QVector3D

import pyqtgraph.opengl as gl
import pyqtgraph as pg
from OpenGL.GL import *


# CPK color scheme - standard scientific coloring for elements
CPK_COLORS = {
    'H':  (1.000, 1.000, 1.000, 1.0),  # White
    'He': (0.851, 1.000, 1.000, 1.0),  # Light cyan
    'Li': (0.800, 0.502, 1.000, 1.0),  # Violet
    'Be': (0.761, 1.000, 0.000, 1.0),  # Dark green
    'B':  (1.000, 0.710, 0.710, 1.0),  # Salmon
    'C':  (0.565, 0.565, 0.565, 1.0),  # Gray
    'N':  (0.188, 0.314, 0.973, 1.0),  # Blue
    'O':  (1.000, 0.051, 0.051, 1.0),  # Red
    'F':  (0.565, 0.878, 0.314, 1.0),  # Green
    'Ne': (0.702, 0.890, 0.961, 1.0),  # Light blue
    'Na': (0.671, 0.361, 0.949, 1.0),  # Purple
    'Mg': (0.541, 1.000, 0.000, 1.0),  # Bright green
    'Al': (0.749, 0.651, 0.651, 1.0),  # Light gray
    'Si': (0.941, 0.784, 0.627, 1.0),  # Tan
    'P':  (1.000, 0.502, 0.000, 1.0),  # Orange
    'S':  (1.000, 1.000, 0.188, 1.0),  # Yellow
    'Cl': (0.122, 0.941, 0.122, 1.0),  # Green
    'Ar': (0.502, 0.820, 0.890, 1.0),  # Cyan
    'K':  (0.561, 0.251, 0.831, 1.0),  # Purple
    'Ca': (0.239, 1.000, 0.000, 1.0),  # Green
    'Sc': (0.902, 0.902, 0.902, 1.0),  # Light gray
    'Ti': (0.749, 0.761, 0.780, 1.0),  # Gray
    'V':  (0.651, 0.651, 0.671, 1.0),  # Gray
    'Cr': (0.541, 0.600, 0.780, 1.0),  # Blue-gray
    'Mn': (0.612, 0.478, 0.780, 1.0),  # Purple-gray
    'Fe': (0.878, 0.400, 0.200, 1.0),  # Orange-brown
    'Co': (0.941, 0.565, 0.627, 1.0),  # Pink
    'Ni': (0.314, 0.816, 0.314, 1.0),  # Green
    'Cu': (0.784, 0.502, 0.200, 1.0),  # Copper
    'Zn': (0.490, 0.502, 0.690, 1.0),  # Blue-gray
    'Ga': (0.761, 0.561, 0.561, 1.0),  # Pink-gray
    'Ge': (0.400, 0.561, 0.561, 1.0),  # Gray-green
    'As': (0.741, 0.502, 0.890, 1.0),  # Purple
    'Se': (1.000, 0.631, 0.000, 1.0),  # Orange
    'Br': (0.651, 0.161, 0.161, 1.0),  # Dark red
    'Kr': (0.361, 0.722, 0.820, 1.0),  # Cyan
    'Rb': (0.439, 0.180, 0.690, 1.0),  # Purple
    'Sr': (0.000, 1.000, 0.000, 1.0),  # Green
    'Y':  (0.580, 1.000, 1.000, 1.0),  # Cyan
    'Zr': (0.580, 0.878, 0.878, 1.0),  # Light cyan
    'Nb': (0.451, 0.761, 0.788, 1.0),  # Cyan
    'Mo': (0.329, 0.710, 0.710, 1.0),  # Teal
    'Tc': (0.231, 0.620, 0.620, 1.0),  # Teal
    'Ru': (0.141, 0.561, 0.561, 1.0),  # Dark teal
    'Rh': (0.039, 0.490, 0.549, 1.0),  # Dark cyan
    'Pd': (0.000, 0.412, 0.522, 1.0),  # Dark cyan
    'Ag': (0.753, 0.753, 0.753, 1.0),  # Silver
    'Cd': (1.000, 0.851, 0.561, 1.0),  # Light orange
    'In': (0.651, 0.459, 0.451, 1.0),  # Brown
    'Sn': (0.400, 0.502, 0.502, 1.0),  # Gray
    'Sb': (0.620, 0.388, 0.710, 1.0),  # Purple
    'Te': (0.831, 0.478, 0.000, 1.0),  # Orange
    'I':  (0.580, 0.000, 0.580, 1.0),  # Purple
    'Xe': (0.259, 0.620, 0.690, 1.0),  # Cyan
    'Cs': (0.341, 0.090, 0.561, 1.0),  # Purple
    'Ba': (0.000, 0.788, 0.000, 1.0),  # Green
    'La': (0.439, 0.831, 1.000, 1.0),  # Light blue
    'Ce': (1.000, 1.000, 0.780, 1.0),  # Light yellow
    'Pr': (0.851, 1.000, 0.780, 1.0),  # Light green
    'Nd': (0.780, 1.000, 0.780, 1.0),  # Light green
    'Pm': (0.639, 1.000, 0.780, 1.0),  # Light green
    'Sm': (0.561, 1.000, 0.780, 1.0),  # Light green
    'Eu': (0.380, 1.000, 0.780, 1.0),  # Light green
    'Gd': (0.271, 1.000, 0.780, 1.0),  # Light green
    'Tb': (0.188, 1.000, 0.780, 1.0),  # Light green
    'Dy': (0.122, 1.000, 0.780, 1.0),  # Light green
    'Ho': (0.000, 1.000, 0.612, 1.0),  # Green-cyan
    'Er': (0.000, 0.902, 0.459, 1.0),  # Green
    'Tm': (0.000, 0.831, 0.322, 1.0),  # Green
    'Yb': (0.000, 0.749, 0.220, 1.0),  # Green
    'Lu': (0.000, 0.671, 0.141, 1.0),  # Green
    'Hf': (0.302, 0.761, 1.000, 1.0),  # Light blue
    'Ta': (0.302, 0.651, 1.000, 1.0),  # Blue
    'W':  (0.129, 0.580, 0.839, 1.0),  # Blue
    'Re': (0.149, 0.490, 0.671, 1.0),  # Blue
    'Os': (0.149, 0.400, 0.588, 1.0),  # Blue
    'Ir': (0.090, 0.329, 0.529, 1.0),  # Dark blue
    'Pt': (0.816, 0.816, 0.878, 1.0),  # Light gray
    'Au': (1.000, 0.820, 0.137, 1.0),  # Gold
    'Hg': (0.722, 0.722, 0.816, 1.0),  # Gray
    'Tl': (0.651, 0.329, 0.302, 1.0),  # Brown
    'Pb': (0.341, 0.349, 0.380, 1.0),  # Dark gray
    'Bi': (0.620, 0.310, 0.710, 1.0),  # Purple
    'Po': (0.671, 0.361, 0.000, 1.0),  # Orange
    'At': (0.459, 0.310, 0.271, 1.0),  # Brown
    'Rn': (0.259, 0.510, 0.588, 1.0),  # Cyan
    'Fr': (0.259, 0.000, 0.400, 1.0),  # Purple
    'Ra': (0.000, 0.490, 0.000, 1.0),  # Green
    'Ac': (0.439, 0.671, 0.980, 1.0),  # Light blue
    'Th': (0.000, 0.729, 1.000, 1.0),  # Cyan
    'Pa': (0.000, 0.631, 1.000, 1.0),  # Blue
    'U':  (0.000, 0.561, 1.000, 1.0),  # Blue
    'Np': (0.000, 0.502, 1.000, 1.0),  # Blue
    'Pu': (0.000, 0.420, 1.000, 1.0),  # Blue
    'Am': (0.329, 0.361, 0.949, 1.0),  # Blue
    'Cm': (0.471, 0.361, 0.890, 1.0),  # Purple
}

# Covalent radii in Angstroms (for visualization scaling)
COVALENT_RADII = {
    'H': 0.31, 'He': 0.28, 'Li': 1.28, 'Be': 0.96, 'B': 0.84, 'C': 0.76,
    'N': 0.71, 'O': 0.66, 'F': 0.57, 'Ne': 0.58, 'Na': 1.66, 'Mg': 1.41,
    'Al': 1.21, 'Si': 1.11, 'P': 1.07, 'S': 1.05, 'Cl': 1.02, 'Ar': 1.06,
    'K': 2.03, 'Ca': 1.76, 'Sc': 1.70, 'Ti': 1.60, 'V': 1.53, 'Cr': 1.39,
    'Mn': 1.39, 'Fe': 1.32, 'Co': 1.26, 'Ni': 1.24, 'Cu': 1.32, 'Zn': 1.22,
    'Ga': 1.22, 'Ge': 1.20, 'As': 1.19, 'Se': 1.20, 'Br': 1.20, 'Kr': 1.16,
    'Rb': 2.20, 'Sr': 1.95, 'Y': 1.90, 'Zr': 1.75, 'Nb': 1.64, 'Mo': 1.54,
    'Tc': 1.47, 'Ru': 1.46, 'Rh': 1.42, 'Pd': 1.39, 'Ag': 1.45, 'Cd': 1.44,
    'In': 1.42, 'Sn': 1.39, 'Sb': 1.39, 'Te': 1.38, 'I': 1.39, 'Xe': 1.40,
    'Cs': 2.44, 'Ba': 2.15, 'La': 2.07, 'Ce': 2.04, 'Pr': 2.03, 'Nd': 2.01,
    'Pm': 1.99, 'Sm': 1.98, 'Eu': 1.98, 'Gd': 1.96, 'Tb': 1.94, 'Dy': 1.92,
    'Ho': 1.92, 'Er': 1.89, 'Tm': 1.90, 'Yb': 1.87, 'Lu': 1.87, 'Hf': 1.75,
    'Ta': 1.70, 'W': 1.62, 'Re': 1.51, 'Os': 1.44, 'Ir': 1.41, 'Pt': 1.36,
    'Au': 1.36, 'Hg': 1.32, 'Tl': 1.45, 'Pb': 1.46, 'Bi': 1.48, 'Po': 1.40,
    'At': 1.50, 'Rn': 1.50, 'Fr': 2.60, 'Ra': 2.21, 'Ac': 2.15, 'Th': 2.06,
    'Pa': 2.00, 'U': 1.96, 'Np': 1.90, 'Pu': 1.87, 'Am': 1.80, 'Cm': 1.69,
}


def create_sphere_mesh(radius: float = 1.0, rows: int = 16, cols: int = 16) -> gl.MeshData:
    """Create a high-quality sphere mesh."""
    verts = []
    faces = []
    
    for i in range(rows + 1):
        phi = np.pi * i / rows
        for j in range(cols):
            theta = 2 * np.pi * j / cols
            x = radius * np.sin(phi) * np.cos(theta)
            y = radius * np.sin(phi) * np.sin(theta)
            z = radius * np.cos(phi)
            verts.append([x, y, z])
    
    for i in range(rows):
        for j in range(cols):
            p1 = i * cols + j
            p2 = i * cols + (j + 1) % cols
            p3 = (i + 1) * cols + j
            p4 = (i + 1) * cols + (j + 1) % cols
            
            if i > 0:
                faces.append([p1, p2, p3])
            if i < rows - 1:
                faces.append([p2, p4, p3])
    
    return gl.MeshData(vertexes=np.array(verts), faces=np.array(faces))


def create_cylinder_mesh(radius: float = 0.1, length: float = 1.0, segments: int = 12) -> gl.MeshData:
    """Create a cylinder mesh for bonds."""
    verts = []
    faces = []
    
    # Create vertices for two circles
    for z in [0, length]:
        for i in range(segments):
            theta = 2 * np.pi * i / segments
            x = radius * np.cos(theta)
            y = radius * np.sin(theta)
            verts.append([x, y, z])
    
    # Create faces
    for i in range(segments):
        next_i = (i + 1) % segments
        # Bottom circle index: i, Top circle index: i + segments
        faces.append([i, next_i, next_i + segments])
        faces.append([i, next_i + segments, i + segments])
    
    return gl.MeshData(vertexes=np.array(verts), faces=np.array(faces))


class StructureViewerWidget(QWidget):
    """Professional 3D crystal structure viewer using OpenGL."""
    
    structure_exported = pyqtSignal(str)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_structure = None
        self.current_material = None
        self.atom_meshes = []
        self.bond_meshes = []
        self.cell_lines = None
        self.axis_items = []
        
        # Default settings
        self.atom_scale = 0.4
        self.bond_radius = 0.08
        self.bond_cutoff = 3.0
        self.show_bonds = True
        self.show_unit_cell = True
        self.show_axes = True
        self.background_color = (0.15, 0.15, 0.18, 1.0)
        
        self._setup_ui()
    
    def _setup_ui(self):
        """Set up the user interface."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # Title bar
        title_bar = self._create_title_bar()
        layout.addWidget(title_bar)
        
        # Main 3D view
        self.gl_widget = gl.GLViewWidget()
        self.gl_widget.setBackgroundColor(self.background_color)
        self.gl_widget.setCameraPosition(distance=20, elevation=30, azimuth=45)
        self.gl_widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        layout.addWidget(self.gl_widget, stretch=1)
        
        # Controls panel
        controls = self._create_controls()
        layout.addWidget(controls)
        
        # Show placeholder
        self._show_placeholder()
    
    def _create_title_bar(self) -> QWidget:
        """Create the title bar."""
        title_bar = QFrame()
        title_bar.setStyleSheet("""
            QFrame {
                background-color: #1a1a2e;
                border-bottom: 2px solid #16213e;
            }
        """)
        title_layout = QHBoxLayout(title_bar)
        title_layout.setContentsMargins(15, 10, 15, 10)
        
        title = QLabel("🔬 Structure Viewer")
        title.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        title.setStyleSheet("color: #e0e0e0;")
        title_layout.addWidget(title)
        
        self.structure_info_label = QLabel("No structure loaded")
        self.structure_info_label.setStyleSheet("color: #888; font-size: 12px;")
        title_layout.addStretch()
        title_layout.addWidget(self.structure_info_label)
        
        return title_bar
    
    def _create_controls(self) -> QWidget:
        """Create the controls panel."""
        controls = QFrame()
        controls.setStyleSheet("""
            QFrame {
                background-color: #1a1a2e;
                border-top: 1px solid #16213e;
            }
            QGroupBox {
                color: #e0e0e0;
                font-weight: bold;
                font-size: 11px;
                border: 1px solid #2d2d44;
                border-radius: 6px;
                margin-top: 8px;
                padding-top: 8px;
                background-color: #252538;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }
            QLabel {
                color: #b0b0b0;
                font-size: 11px;
            }
            QCheckBox {
                color: #b0b0b0;
                font-size: 11px;
            }
            QCheckBox::indicator {
                width: 16px;
                height: 16px;
            }
            QSlider::groove:horizontal {
                height: 6px;
                background: #2d2d44;
                border-radius: 3px;
            }
            QSlider::handle:horizontal {
                width: 16px;
                margin: -5px 0;
                background: #4fc3f7;
                border-radius: 8px;
            }
            QSlider::handle:horizontal:hover {
                background: #81d4fa;
            }
            QPushButton {
                background-color: #3d5a80;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-size: 11px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #4a6fa5;
            }
            QPushButton:disabled {
                background-color: #2d2d44;
                color: #666;
            }
        """)
        
        controls_layout = QHBoxLayout(controls)
        controls_layout.setContentsMargins(15, 10, 15, 10)
        controls_layout.setSpacing(15)
        
        # Display options group
        display_group = QGroupBox("Display")
        display_layout = QHBoxLayout(display_group)
        display_layout.setSpacing(15)
        
        self.show_bonds_cb = QCheckBox("Bonds")
        self.show_bonds_cb.setChecked(True)
        self.show_bonds_cb.stateChanged.connect(self._toggle_bonds)
        display_layout.addWidget(self.show_bonds_cb)
        
        self.show_cell_cb = QCheckBox("Unit Cell")
        self.show_cell_cb.setChecked(True)
        self.show_cell_cb.stateChanged.connect(self._toggle_unit_cell)
        display_layout.addWidget(self.show_cell_cb)
        
        self.show_axes_cb = QCheckBox("Axes")
        self.show_axes_cb.setChecked(True)
        self.show_axes_cb.stateChanged.connect(self._toggle_axes)
        display_layout.addWidget(self.show_axes_cb)
        
        controls_layout.addWidget(display_group)
        
        # Atom size group
        size_group = QGroupBox("Atom Size")
        size_layout = QHBoxLayout(size_group)
        
        self.size_slider = QSlider(Qt.Orientation.Horizontal)
        self.size_slider.setRange(10, 100)
        self.size_slider.setValue(40)
        self.size_slider.setMinimumWidth(100)
        self.size_slider.valueChanged.connect(self._update_atom_size)
        size_layout.addWidget(self.size_slider)
        
        self.size_label = QLabel("40%")
        self.size_label.setMinimumWidth(35)
        size_layout.addWidget(self.size_label)
        
        controls_layout.addWidget(size_group)
        
        # Bond cutoff group
        bond_group = QGroupBox("Bond Cutoff")
        bond_layout = QHBoxLayout(bond_group)
        
        self.bond_slider = QSlider(Qt.Orientation.Horizontal)
        self.bond_slider.setRange(15, 50)
        self.bond_slider.setValue(30)
        self.bond_slider.setMinimumWidth(80)
        self.bond_slider.valueChanged.connect(self._update_bond_cutoff)
        bond_layout.addWidget(self.bond_slider)
        
        self.bond_label = QLabel("3.0 Å")
        self.bond_label.setMinimumWidth(40)
        bond_layout.addWidget(self.bond_label)
        
        controls_layout.addWidget(bond_group)
        
        controls_layout.addStretch()
        
        # View buttons
        self.reset_view_btn = QPushButton("⟳ Reset View")
        self.reset_view_btn.clicked.connect(self._reset_view)
        controls_layout.addWidget(self.reset_view_btn)
        
        self.export_btn = QPushButton("💾 Export CIF")
        self.export_btn.setStyleSheet("""
            QPushButton {
                background-color: #e65100;
                color: white;
            }
            QPushButton:hover {
                background-color: #f57c00;
            }
            QPushButton:disabled {
                background-color: #2d2d44;
                color: #666;
            }
        """)
        self.export_btn.clicked.connect(self._export_cif)
        self.export_btn.setEnabled(False)
        controls_layout.addWidget(self.export_btn)
        
        return controls
    
    def _show_placeholder(self):
        """Show placeholder when no structure is loaded."""
        # Add a simple text indicator (axes will show it's active)
        self._add_axes()
    
    def _add_axes(self):
        """Add coordinate axes to the scene."""
        # Remove existing axes
        for item in self.axis_items:
            self.gl_widget.removeItem(item)
        self.axis_items.clear()
        
        if not self.show_axes:
            return
        
        axis_length = 3.0
        axis_width = 2.0
        
        # X axis (red)
        x_axis = gl.GLLinePlotItem(
            pos=np.array([[0, 0, 0], [axis_length, 0, 0]]),
            color=(1, 0.3, 0.3, 1),
            width=axis_width,
            antialias=True
        )
        self.gl_widget.addItem(x_axis)
        self.axis_items.append(x_axis)
        
        # Y axis (green)
        y_axis = gl.GLLinePlotItem(
            pos=np.array([[0, 0, 0], [0, axis_length, 0]]),
            color=(0.3, 1, 0.3, 1),
            width=axis_width,
            antialias=True
        )
        self.gl_widget.addItem(y_axis)
        self.axis_items.append(y_axis)
        
        # Z axis (blue)
        z_axis = gl.GLLinePlotItem(
            pos=np.array([[0, 0, 0], [0, 0, axis_length]]),
            color=(0.3, 0.6, 1, 1),
            width=axis_width,
            antialias=True
        )
        self.gl_widget.addItem(z_axis)
        self.axis_items.append(z_axis)
    
    def set_structure(self, material: Dict):
        """Set the structure to display from material data."""
        self.current_material = material
        structure = material.get('structure')
        
        if structure is None:
            self.structure_info_label.setText("No structure available")
            self.export_btn.setEnabled(False)
            return
        
        self.current_structure = structure
        
        # Update info label
        formula = material.get('formula', 'Unknown')
        mat_id = material.get('material_id', '')
        space_group = material.get('space_group', '')
        
        info_parts = [formula]
        if mat_id:
            info_parts.append(f"({mat_id})")
        if space_group:
            info_parts.append(f"• {space_group}")
        
        self.structure_info_label.setText(" ".join(info_parts))
        self.structure_info_label.setStyleSheet("color: #4fc3f7; font-size: 12px;")
        self.export_btn.setEnabled(True)
        
        # Render the structure
        self._render_structure()
    
    def clear_structure(self):
        """Clear the current structure display."""
        self.current_structure = None
        self.current_material = None
        self._clear_scene()
        self._show_placeholder()
        self.structure_info_label.setText("No structure loaded")
        self.structure_info_label.setStyleSheet("color: #888; font-size: 12px;")
        self.export_btn.setEnabled(False)
    
    def _clear_scene(self):
        """Clear all items from the scene."""
        for mesh in self.atom_meshes:
            self.gl_widget.removeItem(mesh)
        self.atom_meshes.clear()
        
        for mesh in self.bond_meshes:
            self.gl_widget.removeItem(mesh)
        self.bond_meshes.clear()
        
        if self.cell_lines is not None:
            self.gl_widget.removeItem(self.cell_lines)
            self.cell_lines = None
        
        for item in self.axis_items:
            self.gl_widget.removeItem(item)
        self.axis_items.clear()
    
    def _render_structure(self):
        """Render the crystal structure."""
        if self.current_structure is None:
            return
        
        self._clear_scene()
        
        structure = self.current_structure
        coords = structure.cart_coords
        species = [str(site.specie) for site in structure.sites]
        
        # Calculate center of mass for centering
        center = coords.mean(axis=0)
        coords_centered = coords - center
        
        # Render atoms as spheres
        self._render_atoms(coords_centered, species)
        
        # Render bonds
        if self.show_bonds:
            self._render_bonds(coords_centered, species)
        
        # Render unit cell
        if self.show_unit_cell:
            self._render_unit_cell(structure.lattice.matrix, center)
        
        # Add axes
        self._add_axes()
        
        # Adjust camera to fit structure
        max_extent = np.max(np.abs(coords_centered)) * 2.5
        self.gl_widget.setCameraPosition(distance=max(max_extent, 15))
    
    def _render_atoms(self, coords: np.ndarray, species: List[str]):
        """Render atoms as 3D spheres."""
        sphere_mesh = create_sphere_mesh(radius=1.0, rows=20, cols=20)
        
        for coord, elem in zip(coords, species):
            # Get element color and radius
            color = CPK_COLORS.get(elem, (0.5, 0.5, 0.5, 1.0))
            radius = COVALENT_RADII.get(elem, 1.0) * self.atom_scale
            
            # Create colored mesh
            colors = np.ones((len(sphere_mesh.faces()), 3, 4)) * np.array(color)
            
            mesh_item = gl.GLMeshItem(
                meshdata=sphere_mesh,
                color=color,
                smooth=True,
                shader='shaded',
                glOptions='opaque'
            )
            
            # Transform: scale and translate
            mesh_item.scale(radius, radius, radius)
            mesh_item.translate(coord[0], coord[1], coord[2])
            
            self.gl_widget.addItem(mesh_item)
            self.atom_meshes.append(mesh_item)
    
    def _render_bonds(self, coords: np.ndarray, species: List[str]):
        """Render bonds as cylinders between nearby atoms."""
        n_atoms = len(coords)
        bond_pairs = []
        
        # Find bonded pairs
        for i in range(n_atoms):
            for j in range(i + 1, n_atoms):
                dist = np.linalg.norm(coords[i] - coords[j])
                if dist < self.bond_cutoff:
                    bond_pairs.append((i, j, dist))
        
        # Render each bond as a line (faster than cylinders for many bonds)
        if bond_pairs:
            lines = []
            colors = []
            
            for i, j, dist in bond_pairs:
                pos1 = coords[i]
                pos2 = coords[j]
                mid = (pos1 + pos2) / 2
                
                # Get colors for both atoms
                color1 = CPK_COLORS.get(species[i], (0.5, 0.5, 0.5, 1.0))
                color2 = CPK_COLORS.get(species[j], (0.5, 0.5, 0.5, 1.0))
                
                # First half of bond (color of first atom)
                lines.append([pos1, mid])
                colors.append([color1, color1])
                
                # Second half of bond (color of second atom)
                lines.append([mid, pos2])
                colors.append([color2, color2])
            
            for line_pts, line_colors in zip(lines, colors):
                bond_line = gl.GLLinePlotItem(
                    pos=np.array(line_pts),
                    color=np.array(line_colors),
                    width=3.0,
                    antialias=True
                )
                self.gl_widget.addItem(bond_line)
                self.bond_meshes.append(bond_line)
    
    def _render_unit_cell(self, lattice_matrix: np.ndarray, center: np.ndarray):
        """Render the unit cell as lines."""
        origin = -center
        a, b, c = lattice_matrix
        
        # Define the 12 edges of the unit cell
        vertices = np.array([
            origin,                    # 0
            origin + a,                # 1
            origin + b,                # 2
            origin + c,                # 3
            origin + a + b,            # 4
            origin + a + c,            # 5
            origin + b + c,            # 6
            origin + a + b + c,        # 7
        ])
        
        edges = [
            (0, 1), (0, 2), (0, 3),
            (1, 4), (1, 5),
            (2, 4), (2, 6),
            (3, 5), (3, 6),
            (4, 7), (5, 7), (6, 7)
        ]
        
        # Create line data
        lines = []
        for i, j in edges:
            lines.append([vertices[i], vertices[j]])
        
        for line_pts in lines:
            cell_line = gl.GLLinePlotItem(
                pos=np.array(line_pts),
                color=(0.6, 0.8, 1.0, 0.6),
                width=1.5,
                antialias=True
            )
            self.gl_widget.addItem(cell_line)
            self.bond_meshes.append(cell_line)  # Reuse bond_meshes for cleanup
    
    def _toggle_bonds(self, state):
        """Toggle bond visibility."""
        self.show_bonds = bool(state)
        if self.current_structure:
            self._render_structure()
    
    def _toggle_unit_cell(self, state):
        """Toggle unit cell visibility."""
        self.show_unit_cell = bool(state)
        if self.current_structure:
            self._render_structure()
    
    def _toggle_axes(self, state):
        """Toggle axes visibility."""
        self.show_axes = bool(state)
        self._add_axes()
    
    def _update_atom_size(self, value):
        """Update atom size scaling."""
        self.atom_scale = value / 100.0
        self.size_label.setText(f"{value}%")
        if self.current_structure:
            self._render_structure()
    
    def _update_bond_cutoff(self, value):
        """Update bond cutoff distance."""
        self.bond_cutoff = value / 10.0
        self.bond_label.setText(f"{self.bond_cutoff:.1f} Å")
        if self.current_structure:
            self._render_structure()
    
    def _reset_view(self):
        """Reset the camera view."""
        if self.current_structure:
            coords = self.current_structure.cart_coords
            max_extent = np.max(np.ptp(coords, axis=0)) * 1.5
            self.gl_widget.setCameraPosition(
                distance=max(max_extent, 15),
                elevation=30,
                azimuth=45
            )
        else:
            self.gl_widget.setCameraPosition(distance=20, elevation=30, azimuth=45)
    
    def _export_cif(self):
        """Export the current structure to a CIF file."""
        if self.current_structure is None:
            return
        
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
                
                QMessageBox.information(
                    self, "Export Successful",
                    f"Structure exported to:\n{filename}"
                )
                self.structure_exported.emit(filename)
                
            except Exception as e:
                QMessageBox.critical(self, "Export Error", f"Failed to export: {str(e)}")
