"""
Structure Viewer Widget

Modern, publication-quality 3D crystal structure visualization using PyQtGraph
with OpenGL, styled after state-of-the-art tools such as Quantum ATK and
Materials Studio.

Highlights
----------
* Glossy ball-and-stick rendering with a custom Blinn-Phong shader (specular
  highlights + subtle fresnel rim) for that "studio" look.
* True 3D, split-colored cylinder bonds (not flat lines), batched into a single
  mesh for performance.
* Smooth icosphere atoms, also batched into a single mesh.
* Multiple representations: Ball & Stick, Space Filling (van der Waals) and
  Sticks (licorice).
* Soft vignette background and a floating element legend overlay.

Cross-platform compatible with proper OpenGL context initialization.
"""

from typing import Dict, Optional, List, Tuple
import sys
import numpy as np

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QComboBox, QFrame, QFileDialog, QMessageBox, QSizePolicy,
    QSlider, QGroupBox, QCheckBox, QSpinBox, QDoubleSpinBox,
    QToolButton, QMenu, QWidgetAction, QColorDialog
)
try:
    from PyQt6.QtOpenGLWidgets import QOpenGLWidget
except Exception:
    QOpenGLWidget = None
from PyQt6.QtCore import Qt, pyqtSignal, QTimer, QRectF, QPointF
from PyQt6.QtGui import (
    QFont, QColor, QVector3D, QPalette, QPainter, QPainterPath,
    QRadialGradient, QLinearGradient, QBrush, QPen,
)

import pyqtgraph.opengl as gl
import pyqtgraph as pg

# Safe OpenGL import with fallback
try:
    from OpenGL.GL import glClearColor, glClear, GL_COLOR_BUFFER_BIT, GL_DEPTH_BUFFER_BIT
    OPENGL_AVAILABLE = True
except ImportError:
    OPENGL_AVAILABLE = False


# Background color presets (r, g, b, a) in 0..1.  'Studio' is the modern default:
# a deep desaturated blue-charcoal paired with the vignette overlay.
BACKGROUND_PRESETS = {
    'Studio': (0.071, 0.082, 0.110, 1.0),
    'Dark': (0.12, 0.12, 0.15, 1.0),
    'Black': (0.0, 0.0, 0.0, 1.0),
    'White': (1.0, 1.0, 1.0, 1.0),
    'Gray': (0.30, 0.30, 0.34, 1.0),
}


# ---------------------------------------------------------------------------
# Custom glossy shader (Blinn-Phong, written for pyqtgraph >= 0.13 modern GL).
# Lighting is computed from the eye-space normal (headlight model) so it stays
# stable while the user orbits the camera.  Registration happens lazily; if it
# fails for any reason we transparently fall back to the built-in 'shaded'.
# ---------------------------------------------------------------------------
CRYSTAL_SHADER_NAME = 'shaded'


def _register_crystal_shader() -> str:
    global CRYSTAL_SHADER_NAME
    try:
        from pyqtgraph.opengl.shaders import ShaderProgram, VertexShader, FragmentShader
        # Already registered?
        if 'crystal' in getattr(ShaderProgram, 'names', {}):
            CRYSTAL_SHADER_NAME = 'crystal'
            return CRYSTAL_SHADER_NAME
        ShaderProgram('crystal', [
            VertexShader("""
                uniform mat4 u_mvp;
                uniform mat3 u_normal;
                attribute vec4 a_position;
                attribute vec3 a_normal;
                attribute vec4 a_color;
                varying vec4 v_color;
                varying vec3 v_normal;
                void main() {
                    v_normal = normalize(u_normal * a_normal);
                    v_color = a_color;
                    gl_Position = u_mvp * a_position;
                }
            """),
            FragmentShader("""
                #ifdef GL_ES
                precision mediump float;
                #endif
                varying vec4 v_color;
                varying vec3 v_normal;
                void main() {
                    vec3 N = normalize(v_normal);
                    vec3 V = vec3(0.0, 0.0, 1.0);
                    // two-sided shading: always light the face toward the camera
                    if (N.z < 0.0) N = -N;
                    vec3 L1 = normalize(vec3(-0.35, 0.45, 0.85));
                    vec3 L2 = normalize(vec3(0.55, -0.30, 0.55));
                    float d1 = max(dot(N, L1), 0.0);
                    float d2 = max(dot(N, L2), 0.0);
                    vec3 H1 = normalize(L1 + V);
                    float spec = pow(max(dot(N, H1), 0.0), 48.0);
                    float ambient = 0.34;
                    float diffuse = 0.70 * d1 + 0.20 * d2;
                    vec3 base = v_color.rgb;
                    vec3 color = base * (ambient + diffuse);
                    color += vec3(0.55) * spec;                 // glossy highlight
                    float rim = pow(1.0 - max(dot(N, V), 0.0), 3.0);
                    color += base * rim * 0.18;                 // subtle fresnel rim
                    gl_FragColor = vec4(clamp(color, 0.0, 1.0), v_color.a);
                }
            """),
        ])
        CRYSTAL_SHADER_NAME = 'crystal'
    except Exception:
        CRYSTAL_SHADER_NAME = 'shaded'
    return CRYSTAL_SHADER_NAME


class OpaqueGLViewWidget(gl.GLViewWidget):
    """
    A GLViewWidget subclass that ensures opaque background rendering and hosts
    floating Qt overlays (vignette + legend) drawn on top of the 3D scene.

    This also fixes transparency/bleed-through issues on various platforms by
    properly initializing the OpenGL context and paint events.
    """

    def __init__(self, *args, **kwargs):
        self._bg_color = BACKGROUND_PRESETS['Studio']
        self._initialized = False
        # Overlay widgets (assigned by the parent viewer after construction)
        self.vignette = None
        self.legend = None
        super().__init__(*args, **kwargs)

    def setBackgroundColor(self, color):
        """Set background color and update palette."""
        if color is None:
            return

        if isinstance(color, QColor):
            self._bg_color = (color.redF(), color.greenF(), color.blueF(), color.alphaF())
        elif isinstance(color, str):
            qc = QColor(color)
            if qc.isValid():
                self._bg_color = (qc.redF(), qc.greenF(), qc.blueF(), qc.alphaF())
            else:
                self._bg_color = BACKGROUND_PRESETS['Studio']
        elif isinstance(color, (tuple, list)):
            if len(color) == 3:
                self._bg_color = (float(color[0]), float(color[1]), float(color[2]), 1.0)
            elif len(color) >= 4:
                self._bg_color = tuple(float(c) for c in color[:4])
        else:
            try:
                qc = pg.mkColor(color)
                self._bg_color = (qc.redF(), qc.greenF(), qc.blueF(), qc.alphaF())
            except Exception:
                self._bg_color = BACKGROUND_PRESETS['Studio']

        palette = self.palette()
        bg_qcolor = QColor(
            int(self._bg_color[0] * 255),
            int(self._bg_color[1] * 255),
            int(self._bg_color[2] * 255),
        )
        palette.setColor(QPalette.ColorRole.Window, bg_qcolor)
        palette.setColor(QPalette.ColorRole.Base, bg_qcolor)
        self.setPalette(palette)

        try:
            super().setBackgroundColor(bg_qcolor)
        except Exception:
            pass

        self.update()

    def initializeGL(self):
        """Initialize OpenGL with proper background color."""
        super().initializeGL()
        self._initialized = True
        if OPENGL_AVAILABLE:
            glClearColor(self._bg_color[0], self._bg_color[1],
                         self._bg_color[2], self._bg_color[3])

    def paintGL(self, *args, **kwargs):
        """Paint with explicit background clear."""
        if OPENGL_AVAILABLE and self._initialized:
            glClearColor(self._bg_color[0], self._bg_color[1],
                         self._bg_color[2], self._bg_color[3])
            glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
        super().paintGL(*args, **kwargs)

    def resizeEvent(self, ev):
        super().resizeEvent(ev)
        self.reposition_overlays()

    def reposition_overlays(self):
        """Keep the vignette full-bleed and the legend pinned to the top-left."""
        rect = self.rect()
        if self.vignette is not None:
            self.vignette.setGeometry(rect)
            self.vignette.raise_()
        if self.legend is not None:
            self.legend.adjustSize()
            self.legend.move(14, 14)
            self.legend.raise_()


class VignetteOverlay(QWidget):
    """A mouse-transparent radial vignette painted over the GL scene for depth."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self._edge_alpha = 90  # 0..255, strength of the darkening at the corners

    def set_edge_alpha(self, alpha: int):
        self._edge_alpha = max(0, min(255, int(alpha)))
        self.update()

    def paintEvent(self, ev):
        if self._edge_alpha <= 0:
            return
        w, h = self.width(), self.height()
        if w <= 0 or h <= 0:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        cx, cy = w / 2.0, h / 2.0
        radius = max(w, h) * 0.72
        grad = QRadialGradient(cx, cy, radius)
        grad.setColorAt(0.0, QColor(0, 0, 0, 0))
        grad.setColorAt(0.62, QColor(0, 0, 0, 0))
        grad.setColorAt(1.0, QColor(0, 0, 0, self._edge_alpha))
        painter.fillRect(self.rect(), QBrush(grad))
        painter.end()


class LegendOverlay(QWidget):
    """A floating, semi-transparent element legend (color swatch + symbol)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self._entries: List[Tuple[str, QColor]] = []
        self._row_h = 20
        self._pad = 10
        self._swatch = 12
        self._font = QFont("Segoe UI", 10, QFont.Weight.DemiBold)

    def set_entries(self, entries: List[Tuple[str, QColor]]):
        self._entries = entries
        self.adjustSize()
        self.update()

    def sizeHint(self):
        from PyQt6.QtCore import QSize
        if not self._entries:
            return QSize(0, 0)
        metrics_w = 0
        try:
            from PyQt6.QtGui import QFontMetrics
            fm = QFontMetrics(self._font)
            metrics_w = max(fm.horizontalAdvance(sym) for sym, _ in self._entries)
        except Exception:
            metrics_w = 24
        w = self._pad * 2 + self._swatch + 8 + metrics_w + 6
        h = self._pad * 2 + self._row_h * len(self._entries)
        return QSize(int(w), int(h))

    def paintEvent(self, ev):
        if not self._entries:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        # Rounded translucent panel
        panel = QRectF(0.5, 0.5, self.width() - 1, self.height() - 1)
        path = QPainterPath()
        path.addRoundedRect(panel, 8, 8)
        painter.fillPath(path, QColor(18, 20, 28, 165))
        painter.setPen(QPen(QColor(255, 255, 255, 30), 1))
        painter.drawPath(path)

        painter.setFont(self._font)
        x = self._pad
        y = self._pad
        for sym, color in self._entries:
            cy = y + self._row_h / 2.0
            # Swatch with a soft highlight to echo the glossy spheres
            sw_rect = QRectF(x, cy - self._swatch / 2.0, self._swatch, self._swatch)
            grad = QRadialGradient(
                sw_rect.center().x() - 2, sw_rect.center().y() - 2, self._swatch
            )
            grad.setColorAt(0.0, color.lighter(150))
            grad.setColorAt(1.0, color)
            painter.setBrush(QBrush(grad))
            painter.setPen(QPen(QColor(0, 0, 0, 90), 0.8))
            painter.drawEllipse(sw_rect)
            # Symbol text
            painter.setPen(QColor(235, 238, 245))
            painter.drawText(
                QRectF(x + self._swatch + 8, y, self.width(), self._row_h),
                int(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft),
                sym,
            )
            y += self._row_h
        painter.end()


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

# Covalent radii in Angstroms (used for ball-and-stick scaling and bonding)
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

# Van der Waals radii in Angstroms (used for the Space-Filling representation).
# Missing elements fall back to a scaled covalent radius.
VDW_RADII = {
    'H': 1.20, 'He': 1.40, 'Li': 1.82, 'Be': 1.53, 'B': 1.92, 'C': 1.70,
    'N': 1.55, 'O': 1.52, 'F': 1.47, 'Ne': 1.54, 'Na': 2.27, 'Mg': 1.73,
    'Al': 1.84, 'Si': 2.10, 'P': 1.80, 'S': 1.80, 'Cl': 1.75, 'Ar': 1.88,
    'K': 2.75, 'Ca': 2.31, 'Ni': 1.63, 'Cu': 1.40, 'Zn': 1.39, 'Ga': 1.87,
    'Ge': 2.11, 'As': 1.85, 'Se': 1.90, 'Br': 1.85, 'Kr': 2.02, 'Rb': 3.03,
    'Sr': 2.49, 'Pd': 1.63, 'Ag': 1.72, 'Cd': 1.58, 'In': 1.93, 'Sn': 2.17,
    'Sb': 2.06, 'Te': 2.06, 'I': 1.98, 'Xe': 2.16, 'Cs': 3.43, 'Ba': 2.68,
    'Pt': 1.75, 'Au': 1.66, 'Hg': 1.55, 'Tl': 1.96, 'Pb': 2.02, 'Bi': 2.07,
    'Po': 1.97, 'At': 2.02, 'Rn': 2.20, 'Fr': 3.48, 'Ra': 2.83, 'U': 1.86,
}


def vdw_radius(elem: str) -> float:
    """Return a van der Waals radius, falling back to scaled covalent radius."""
    if elem in VDW_RADII:
        return VDW_RADII[elem]
    return COVALENT_RADII.get(elem, 1.0) * 1.8


def site_symbol(site) -> str:
    """Robustly extract an element symbol from a pymatgen site.

    Handles ordered sites and disordered/partial-occupancy sites (where
    ``site.specie`` raises) by using the dominant species.
    """
    try:
        sp = site.specie
        return getattr(sp, "symbol", str(sp))
    except Exception:
        pass
    try:
        comp = site.species
        el = max(comp, key=comp.get)
        return getattr(el, "symbol", str(el))
    except Exception:
        return "X"


# Metallic elements - used to suppress spurious metal-metal "bonds", which keeps
# coordination polyhedra (e.g. TiO6 octahedra) clean as in professional viewers.
METALS = {
    'Li', 'Be', 'Na', 'Mg', 'Al', 'K', 'Ca', 'Sc', 'Ti', 'V', 'Cr', 'Mn',
    'Fe', 'Co', 'Ni', 'Cu', 'Zn', 'Ga', 'Rb', 'Sr', 'Y', 'Zr', 'Nb', 'Mo',
    'Tc', 'Ru', 'Rh', 'Pd', 'Ag', 'Cd', 'In', 'Sn', 'Cs', 'Ba', 'La', 'Ce',
    'Pr', 'Nd', 'Pm', 'Sm', 'Eu', 'Gd', 'Tb', 'Dy', 'Ho', 'Er', 'Tm', 'Yb',
    'Lu', 'Hf', 'Ta', 'W', 'Re', 'Os', 'Ir', 'Pt', 'Au', 'Hg', 'Tl', 'Pb',
    'Bi', 'Po', 'Fr', 'Ra', 'Ac', 'Th', 'Pa', 'U', 'Np', 'Pu', 'Am', 'Cm',
}


# ---------------------------------------------------------------------------
# Geometry helpers - unit primitives reused (instanced) across the structure.
# ---------------------------------------------------------------------------
def create_icosphere(subdivisions: int = 2) -> Tuple[np.ndarray, np.ndarray]:
    """Create a smooth, evenly-tessellated unit sphere (icosphere).

    Returns (vertices, faces).  Vertices lie on the unit sphere, so they double
    as outward normals.  Icospheres avoid the pole-pinching of UV spheres and
    give noticeably rounder atoms.
    """
    t = (1.0 + 5.0 ** 0.5) / 2.0
    verts = [
        (-1, t, 0), (1, t, 0), (-1, -t, 0), (1, -t, 0),
        (0, -1, t), (0, 1, t), (0, -1, -t), (0, 1, -t),
        (t, 0, -1), (t, 0, 1), (-t, 0, -1), (-t, 0, 1),
    ]
    verts = [np.array(v, dtype=float) for v in verts]
    verts = [v / np.linalg.norm(v) for v in verts]

    faces = [
        (0, 11, 5), (0, 5, 1), (0, 1, 7), (0, 7, 10), (0, 10, 11),
        (1, 5, 9), (5, 11, 4), (11, 10, 2), (10, 7, 6), (7, 1, 8),
        (3, 9, 4), (3, 4, 2), (3, 2, 6), (3, 6, 8), (3, 8, 9),
        (4, 9, 5), (2, 4, 11), (6, 2, 10), (8, 6, 7), (9, 8, 1),
    ]

    midpoint_cache: Dict[Tuple[int, int], int] = {}

    def midpoint(i: int, j: int) -> int:
        key = (i, j) if i < j else (j, i)
        if key in midpoint_cache:
            return midpoint_cache[key]
        mid = (verts[i] + verts[j]) / 2.0
        mid = mid / np.linalg.norm(mid)
        verts.append(mid)
        idx = len(verts) - 1
        midpoint_cache[key] = idx
        return idx

    for _ in range(max(0, subdivisions)):
        new_faces = []
        for a, b, c in faces:
            ab = midpoint(a, b)
            bc = midpoint(b, c)
            ca = midpoint(c, a)
            new_faces.extend([
                (a, ab, ca), (b, bc, ab), (c, ca, bc), (ab, bc, ca),
            ])
        faces = new_faces

    return np.array(verts, dtype=float), np.array(faces, dtype=np.int32)


def create_unit_cylinder(segments: int = 18) -> Tuple[np.ndarray, np.ndarray]:
    """Create a unit cylinder (radius 1, height 1) along +Z, side faces only.

    Caps are omitted because cylinder ends are always hidden inside atom spheres
    (ball-and-stick / licorice).  Returns (vertices, faces).
    """
    verts = []
    for z in (0.0, 1.0):
        for i in range(segments):
            theta = 2.0 * np.pi * i / segments
            verts.append((np.cos(theta), np.sin(theta), z))
    faces = []
    for i in range(segments):
        nxt = (i + 1) % segments
        bottom_i, bottom_n = i, nxt
        top_i, top_n = i + segments, nxt + segments
        faces.append((bottom_i, bottom_n, top_n))
        faces.append((bottom_i, top_n, top_i))
    return np.array(verts, dtype=float), np.array(faces, dtype=np.int32)


class StructureViewerWidget(QWidget):
    """Modern 3D crystal structure viewer using OpenGL.

    Cross-platform compatible with proper OpenGL initialization and support for
    multiple representations, glossy shading and 3D cylinder bonds.
    """

    structure_exported = pyqtSignal(str)
    background_changed = pyqtSignal(str)  # Emits background preset name

    REPRESENTATIONS = ('Ball & Stick', 'Space Filling', 'Sticks')

    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_structure = None
        self.current_material = None
        self.atom_mesh = None
        self.bond_mesh = None
        self.cell_lines = None
        self.axis_items = []

        # Default settings
        self.representation = 'Ball & Stick'
        self.atom_scale = 0.40
        self.bond_radius = 0.14
        self.bond_cutoff = 3.0
        self.bond_tol = 1.25  # covalent-radii-sum tolerance for bond detection
        self._last_coords = None
        self._last_radii = None
        self.show_bonds = True
        self.show_unit_cell = True
        self.show_axes = True
        self.show_legend = True
        self.background_preset = 'Studio'
        self.background_color = BACKGROUND_PRESETS['Studio']

        # Platform-specific settings
        self._is_linux = sys.platform.startswith('linux')
        self._is_macos = sys.platform == 'darwin'
        self._is_windows = sys.platform.startswith('win')

        # Register the glossy shader (falls back to 'shaded' if unavailable)
        self._shader = _register_crystal_shader()

        # Precompute unit primitives at a couple of detail levels
        self._ico_high = create_icosphere(subdivisions=2)   # 320 faces / atom
        self._ico_low = create_icosphere(subdivisions=1)    # 80 faces / atom
        self._cyl_high = create_unit_cylinder(segments=18)
        self._cyl_low = create_unit_cylinder(segments=10)
        self._low_detail_threshold = 200
        self._scatter_threshold = 1500

        self._setup_ui()

    # ------------------------------------------------------------------ UI
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        title_bar = self._create_title_bar()
        layout.addWidget(title_bar)

        # Main 3D view using our custom opaque widget
        self.gl_widget = OpaqueGLViewWidget()
        self._configure_gl_widget()
        layout.addWidget(self.gl_widget, stretch=1)

        # Floating overlays (children of the GL widget so they composite on top)
        self.vignette = VignetteOverlay(self.gl_widget)
        self.legend = LegendOverlay(self.gl_widget)
        self.gl_widget.vignette = self.vignette
        self.gl_widget.legend = self.legend
        self.vignette.show()
        self._update_vignette_strength()
        self.gl_widget.reposition_overlays()

        controls = self._create_controls()
        layout.addWidget(controls)

        QTimer.singleShot(100, self._show_placeholder)

    def _configure_gl_widget(self):
        self._apply_background_color()
        self.gl_widget.setCameraPosition(distance=20, elevation=22, azimuth=40)
        self.gl_widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.gl_widget.setMinimumSize(200, 200)

    def _apply_background_color(self):
        self.gl_widget.setBackgroundColor(self.background_color)

    def _create_title_bar(self) -> QWidget:
        title_bar = QFrame()
        title_bar.setStyleSheet("""
            QFrame {
                background-color: #14161c;
                border-bottom: 1px solid #232733;
            }
        """)
        title_layout = QHBoxLayout(title_bar)
        title_layout.setContentsMargins(15, 10, 15, 10)

        title = QLabel("🔬 Structure Viewer")
        title.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        title.setStyleSheet("color: #e8eaf0;")
        title_layout.addWidget(title)

        self.structure_info_label = QLabel("No structure loaded")
        self.structure_info_label.setStyleSheet("color: #8b91a3; font-size: 12px;")
        title_layout.addStretch()
        title_layout.addWidget(self.structure_info_label)

        return title_bar

    def _create_controls(self) -> QWidget:
        controls = QFrame()
        controls.setStyleSheet("""
            QFrame {
                background-color: #14161c;
                border-top: 1px solid #232733;
            }
            QGroupBox {
                color: #e8eaf0;
                font-weight: bold;
                font-size: 11px;
                border: 1px solid #2a2f3d;
                border-radius: 8px;
                margin-top: 8px;
                padding-top: 8px;
                background-color: #1b1e27;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }
            QLabel { color: #aab1c4; font-size: 11px; }
            QCheckBox { color: #aab1c4; font-size: 11px; }
            QCheckBox::indicator { width: 16px; height: 16px; }
            QSlider::groove:horizontal {
                height: 6px; background: #2a2f3d; border-radius: 3px;
            }
            QSlider::handle:horizontal {
                width: 16px; margin: -5px 0; background: #4fc3f7; border-radius: 8px;
            }
            QSlider::handle:horizontal:hover { background: #81d4fa; }
            QComboBox {
                background-color: #232733; color: #e8eaf0;
                border: 1px solid #323848; border-radius: 6px;
                padding: 4px 8px; font-size: 11px;
            }
            QComboBox:hover { border-color: #4fc3f7; }
            QComboBox::drop-down { border: none; width: 20px; }
            QComboBox::down-arrow {
                image: none; border-left: 4px solid transparent;
                border-right: 4px solid transparent; border-top: 6px solid #aab1c4;
                margin-right: 6px;
            }
            QComboBox QAbstractItemView {
                background-color: #232733; color: #e8eaf0;
                selection-background-color: #4fc3f7; selection-color: #14161c;
                border: 1px solid #323848;
            }
            QPushButton {
                background-color: #2f4a6b; color: white; border: none;
                padding: 8px 16px; border-radius: 6px; font-size: 11px; font-weight: bold;
            }
            QPushButton:hover { background-color: #3d5f87; }
            QPushButton:disabled { background-color: #2a2f3d; color: #5b6172; }
        """)

        controls_layout = QHBoxLayout(controls)
        controls_layout.setContentsMargins(15, 10, 15, 10)
        controls_layout.setSpacing(12)

        # Representation / Style group
        style_group = QGroupBox("Style")
        style_layout = QHBoxLayout(style_group)
        self.repr_combo = QComboBox()
        self.repr_combo.addItems(self.REPRESENTATIONS)
        self.repr_combo.setCurrentText(self.representation)
        self.repr_combo.setMinimumWidth(120)
        self.repr_combo.currentTextChanged.connect(self._change_representation)
        style_layout.addWidget(self.repr_combo)
        controls_layout.addWidget(style_group)

        # Display options group
        display_group = QGroupBox("Display")
        display_layout = QHBoxLayout(display_group)
        display_layout.setSpacing(12)

        self.show_bonds_cb = QCheckBox("Bonds")
        self.show_bonds_cb.setChecked(True)
        self.show_bonds_cb.stateChanged.connect(self._toggle_bonds)
        display_layout.addWidget(self.show_bonds_cb)

        self.show_cell_cb = QCheckBox("Cell")
        self.show_cell_cb.setChecked(True)
        self.show_cell_cb.stateChanged.connect(self._toggle_unit_cell)
        display_layout.addWidget(self.show_cell_cb)

        self.show_axes_cb = QCheckBox("Axes")
        self.show_axes_cb.setChecked(True)
        self.show_axes_cb.stateChanged.connect(self._toggle_axes)
        display_layout.addWidget(self.show_axes_cb)

        self.show_legend_cb = QCheckBox("Legend")
        self.show_legend_cb.setChecked(True)
        self.show_legend_cb.stateChanged.connect(self._toggle_legend)
        display_layout.addWidget(self.show_legend_cb)

        controls_layout.addWidget(display_group)

        # Atom size group
        size_group = QGroupBox("Atom Size")
        size_layout = QHBoxLayout(size_group)
        self.size_slider = QSlider(Qt.Orientation.Horizontal)
        self.size_slider.setRange(10, 100)
        self.size_slider.setValue(40)
        self.size_slider.setMinimumWidth(90)
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

        # Background group
        bg_group = QGroupBox("Background")
        bg_layout = QHBoxLayout(bg_group)
        self.bg_combo = QComboBox()
        self.bg_combo.addItems(list(BACKGROUND_PRESETS.keys()))
        self.bg_combo.setCurrentText(self.background_preset)
        self.bg_combo.currentTextChanged.connect(self._change_background)
        self.bg_combo.setMinimumWidth(80)
        bg_layout.addWidget(self.bg_combo)
        controls_layout.addWidget(bg_group)

        controls_layout.addStretch()

        self.reset_view_btn = QPushButton("⟳ Reset View")
        self.reset_view_btn.clicked.connect(self._reset_view)
        controls_layout.addWidget(self.reset_view_btn)

        self.export_btn = QPushButton("💾 Export CIF")
        self.export_btn.setStyleSheet("""
            QPushButton { background-color: #c2410c; color: white; }
            QPushButton:hover { background-color: #ea580c; }
            QPushButton:disabled { background-color: #2a2f3d; color: #5b6172; }
        """)
        self.export_btn.clicked.connect(self._export_cif)
        self.export_btn.setEnabled(False)
        controls_layout.addWidget(self.export_btn)

        return controls

    # ------------------------------------------------------------- scene/axes
    def _show_placeholder(self):
        self._add_axes()

    def _add_axes(self):
        for item in self.axis_items:
            try:
                self.gl_widget.removeItem(item)
            except Exception:
                pass
        self.axis_items.clear()

        if not self.show_axes:
            return

        axis_length = 3.0
        axis_width = 2.5
        is_light_bg = sum(self.background_color[:3]) / 3 > 0.5

        if is_light_bg:
            x_color = (0.85, 0.18, 0.18, 1.0)
            y_color = (0.16, 0.62, 0.20, 1.0)
            z_color = (0.16, 0.34, 0.85, 1.0)
        else:
            x_color = (1.0, 0.42, 0.42, 1.0)
            y_color = (0.42, 1.0, 0.45, 1.0)
            z_color = (0.45, 0.68, 1.0, 1.0)

        for vec, color in (
            ([axis_length, 0, 0], x_color),
            ([0, axis_length, 0], y_color),
            ([0, 0, axis_length], z_color),
        ):
            axis = gl.GLLinePlotItem(
                pos=np.array([[0, 0, 0], vec]),
                color=color, width=axis_width, antialias=True,
            )
            axis.setGLOptions('translucent')
            self.gl_widget.addItem(axis)
            self.axis_items.append(axis)

    # ------------------------------------------------------------- public API
    def set_structure(self, material: Dict):
        """Set the structure to display from material data."""
        self.current_material = material
        structure = material.get('structure')

        if structure is None:
            self.structure_info_label.setText("No structure available")
            self.structure_info_label.setStyleSheet("color: #8b91a3; font-size: 12px;")
            self.export_btn.setEnabled(False)
            return

        self.current_structure = structure

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

        self._render_structure()

    def clear_structure(self):
        """Clear the current structure display."""
        self.current_structure = None
        self.current_material = None
        self._clear_scene()
        self._show_placeholder()
        if self.legend is not None:
            self.legend.set_entries([])
        self.structure_info_label.setText("No structure loaded")
        self.structure_info_label.setStyleSheet("color: #8b91a3; font-size: 12px;")
        self.export_btn.setEnabled(False)

    # --------------------------------------------------------------- rendering
    def _clear_scene(self):
        for mesh in (self.atom_mesh, self.bond_mesh, self.cell_lines):
            if mesh is not None:
                try:
                    self.gl_widget.removeItem(mesh)
                except Exception:
                    pass
        self.atom_mesh = None
        self.bond_mesh = None
        self.cell_lines = None

        for item in self.axis_items:
            try:
                self.gl_widget.removeItem(item)
            except Exception:
                pass
        self.axis_items.clear()

    def _atom_radii(self, species: List[str]) -> np.ndarray:
        """Per-atom display radius for the current representation."""
        if self.representation == 'Space Filling':
            base = np.array([vdw_radius(e) for e in species], dtype=float)
            return base * self.atom_scale
        if self.representation == 'Sticks':
            return np.full(len(species), self.bond_radius, dtype=float)
        # Ball & Stick
        base = np.array([COVALENT_RADII.get(e, 1.0) for e in species], dtype=float)
        return base * self.atom_scale

    def _bonds_enabled(self) -> bool:
        if self.representation == 'Space Filling':
            return False
        return self.show_bonds

    def _render_structure(self):
        if self.current_structure is None:
            return

        self._clear_scene()

        structure = self.current_structure
        coords = np.asarray(structure.cart_coords, dtype=float)
        species = [site_symbol(site) for site in structure.sites]

        if coords.size == 0:
            self._add_axes()
            if self.legend is not None:
                self.legend.set_entries([])
            return

        center = coords.mean(axis=0)
        coords_centered = coords - center

        atom_colors = np.array(
            [CPK_COLORS.get(elem, (0.5, 0.5, 0.5, 1.0)) for elem in species],
            dtype=float,
        )
        atom_radii = self._atom_radii(species)
        self._last_coords = coords_centered
        self._last_radii = atom_radii

        self._render_atoms(coords_centered, atom_colors, atom_radii)

        if self._bonds_enabled():
            self._render_bonds(coords_centered, atom_colors, species)

        if self.show_unit_cell:
            self._render_unit_cell(structure.lattice.matrix, center)

        self._add_axes()
        self._update_legend(species, atom_colors)

        self._frame_camera(coords_centered, atom_radii)

    def _frame_camera(self, coords: np.ndarray, radii: np.ndarray, reset_angle: bool = False):
        """Position the camera so the whole structure (incl. atom radii) fits."""
        if coords is not None and len(coords):
            bounding = float(np.max(np.linalg.norm(coords, axis=1) + radii))
        else:
            bounding = 6.0
        # fov is ~60deg; distance ~= 2 * bounding_radius to fit, plus margin
        distance = max(bounding * 2.4, 9.0)
        if reset_angle:
            self.gl_widget.setCameraPosition(distance=distance, elevation=22, azimuth=40)
        else:
            self.gl_widget.setCameraPosition(distance=distance)

    def _render_atoms(self, coords: np.ndarray, colors: np.ndarray, radii: np.ndarray):
        """Render every atom as part of a single batched, glossy sphere mesh."""
        n_atoms = len(coords)
        if n_atoms == 0:
            return

        # Fast path for very large structures: point sprites
        if n_atoms >= self._scatter_threshold:
            sizes = np.clip(radii * 2.0, 0.05, None)
            scatter = gl.GLScatterPlotItem(
                pos=coords, size=sizes, color=colors, pxMode=False
            )
            scatter.setGLOptions('opaque')
            self.gl_widget.addItem(scatter)
            self.atom_mesh = scatter
            return

        base_v, base_f = self._ico_low if n_atoms >= self._low_detail_threshold else self._ico_high
        m = len(base_v)

        verts = (base_v[None, :, :] * radii[:, None, None] + coords[:, None, :]).reshape(-1, 3)
        faces = (base_f[None, :, :] + (np.arange(n_atoms) * m)[:, None, None]).reshape(-1, 3)
        vcolors = np.repeat(colors, m, axis=0)

        mesh = gl.GLMeshItem(
            meshdata=gl.MeshData(vertexes=verts, faces=faces, vertexColors=vcolors),
            smooth=True, shader=self._shader, glOptions='opaque',
        )
        self.gl_widget.addItem(mesh)
        self.atom_mesh = mesh

    def _render_bonds(self, coords: np.ndarray, colors: np.ndarray, species: List[str]):
        """Render bonds as batched, split-colored 3D cylinders."""
        n_atoms = len(coords)
        if n_atoms < 2:
            return

        pairs = self._find_bond_pairs(coords, species)
        if pairs is None or len(pairs) == 0:
            return

        # For very dense bonding, fall back to lines to keep things responsive.
        if len(pairs) > 6000:
            self._render_bond_lines(coords, colors, pairs)
            return

        pos_i = coords[pairs[:, 0]]
        pos_j = coords[pairs[:, 1]]
        mid = (pos_i + pos_j) / 2.0

        starts = np.concatenate([pos_i, mid], axis=0)
        ends = np.concatenate([mid, pos_j], axis=0)
        seg_colors = np.concatenate([colors[pairs[:, 0]], colors[pairs[:, 1]]], axis=0)

        vec = ends - starts
        lengths = np.linalg.norm(vec, axis=1)
        valid = lengths > 1e-6
        if not np.any(valid):
            return
        starts, ends, seg_colors = starts[valid], ends[valid], seg_colors[valid]
        vec, lengths = vec[valid], lengths[valid]
        dirs = vec / lengths[:, None]
        s = len(dirs)

        # Orthonormal basis (u, v, dir) per segment - singularity-free.
        helper = np.tile(np.array([0.0, 0.0, 1.0]), (s, 1))
        near_z = np.abs(dirs[:, 2]) > 0.9
        helper[near_z] = np.array([0.0, 1.0, 0.0])
        u = np.cross(helper, dirs)
        u /= np.linalg.norm(u, axis=1)[:, None]
        v = np.cross(dirs, u)
        rot = np.stack([u, v, dirs], axis=2)  # (s, 3, 3), columns = u, v, dir

        base_v, base_f = self._cyl_low if s >= 2 * self._low_detail_threshold else self._cyl_high
        k = len(base_v)

        scale = np.empty((s, 3))
        scale[:, 0] = self.bond_radius
        scale[:, 1] = self.bond_radius
        scale[:, 2] = lengths
        scaled = base_v[None, :, :] * scale[:, None, :]          # (s, k, 3)
        world = starts[:, None, :] + np.einsum('sij,skj->ski', rot, scaled)

        verts = world.reshape(-1, 3)
        faces = (base_f[None, :, :] + (np.arange(s) * k)[:, None, None]).reshape(-1, 3)
        vcolors = np.repeat(seg_colors, k, axis=0)

        mesh = gl.GLMeshItem(
            meshdata=gl.MeshData(vertexes=verts, faces=faces, vertexColors=vcolors),
            smooth=True, shader=self._shader, glOptions='opaque',
        )
        self.gl_widget.addItem(mesh)
        self.bond_mesh = mesh

    def _find_bond_pairs(self, coords: np.ndarray, species: List[str]) -> Optional[np.ndarray]:
        """Chemically-aware bonding.

        A pair is bonded when their separation is below both the covalent-radii
        sum (scaled by a tolerance) and the user's absolute cutoff, and they are
        not both metals.  This yields clean coordination polyhedra instead of a
        dense distance-only web.
        """
        n_atoms = len(coords)
        cov = np.array([COVALENT_RADII.get(e, 1.0) for e in species], dtype=float)
        is_metal = np.array([e in METALS for e in species], dtype=bool)
        tol = self.bond_tol
        # Candidate search radius: generous, then filtered per-pair below.
        search_r = min(float((cov.max() * 2.0) * tol), self.bond_cutoff)

        candidates = None
        try:
            from scipy.spatial import cKDTree
            tree = cKDTree(coords)
            candidates = np.array(list(tree.query_pairs(r=search_r)), dtype=int)
        except Exception:
            pair_list = []
            for i in range(n_atoms):
                for j in range(i + 1, n_atoms):
                    if np.linalg.norm(coords[i] - coords[j]) < search_r:
                        pair_list.append((i, j))
            candidates = np.array(pair_list, dtype=int) if pair_list else None

        if candidates is None or len(candidates) == 0:
            return None

        i_idx = candidates[:, 0]
        j_idx = candidates[:, 1]
        dists = np.linalg.norm(coords[i_idx] - coords[j_idx], axis=1)
        max_allowed = np.minimum((cov[i_idx] + cov[j_idx]) * tol, self.bond_cutoff)
        keep = (dists > 0.4) & (dists < max_allowed) & ~(is_metal[i_idx] & is_metal[j_idx])
        result = candidates[keep]
        return result if len(result) else None

    def _render_bond_lines(self, coords: np.ndarray, colors: np.ndarray, pairs: np.ndarray):
        """Line-based bond fallback for very dense structures."""
        pos1 = coords[pairs[:, 0]]
        pos2 = coords[pairs[:, 1]]
        mid = (pos1 + pos2) / 2.0
        line_positions = np.empty((len(pairs) * 4, 3), dtype=float)
        line_colors = np.empty((len(pairs) * 4, 4), dtype=float)
        c1 = colors[pairs[:, 0]]
        c2 = colors[pairs[:, 1]]
        line_positions[0::4], line_positions[1::4] = pos1, mid
        line_positions[2::4], line_positions[3::4] = mid, pos2
        line_colors[0::4], line_colors[1::4] = c1, c1
        line_colors[2::4], line_colors[3::4] = c2, c2
        bond_line = gl.GLLinePlotItem(
            pos=line_positions, color=line_colors, width=2.5,
            antialias=False, mode='lines',
        )
        self.gl_widget.addItem(bond_line)
        self.bond_mesh = bond_line

    def _render_unit_cell(self, lattice_matrix: np.ndarray, center: np.ndarray):
        origin = -center
        a, b, c = lattice_matrix

        vertices = np.array([
            origin, origin + a, origin + b, origin + c,
            origin + a + b, origin + a + c, origin + b + c, origin + a + b + c,
        ])
        edges = [
            (0, 1), (0, 2), (0, 3), (1, 4), (1, 5),
            (2, 4), (2, 6), (3, 5), (3, 6), (4, 7), (5, 7), (6, 7),
        ]

        line_positions = np.empty((len(edges) * 2, 3), dtype=float)
        line_colors = np.empty((len(edges) * 2, 4), dtype=float)

        is_light_bg = sum(self.background_color[:3]) / 3 > 0.5
        if is_light_bg:
            cell_color = np.array((0.30, 0.42, 0.62, 0.85), dtype=float)
        else:
            cell_color = np.array((0.62, 0.74, 0.95, 0.85), dtype=float)

        for idx, (i, j) in enumerate(edges):
            line_positions[idx * 2] = vertices[i]
            line_positions[idx * 2 + 1] = vertices[j]
            line_colors[idx * 2] = cell_color
            line_colors[idx * 2 + 1] = cell_color

        cell_line = gl.GLLinePlotItem(
            pos=line_positions, color=line_colors, width=1.6,
            antialias=True, mode='lines',
        )
        cell_line.setGLOptions('translucent')
        self.gl_widget.addItem(cell_line)
        self.cell_lines = cell_line

    def _update_legend(self, species: List[str], colors: np.ndarray):
        if self.legend is None:
            return
        seen = {}
        for elem in species:
            if elem not in seen:
                rgba = CPK_COLORS.get(elem, (0.5, 0.5, 0.5, 1.0))
                seen[elem] = QColor(
                    int(rgba[0] * 255), int(rgba[1] * 255), int(rgba[2] * 255)
                )
        entries = list(seen.items())
        self.legend.set_entries(entries)
        self.legend.setVisible(self.show_legend and bool(entries))
        self.gl_widget.reposition_overlays()

    def _update_vignette_strength(self):
        if self.vignette is None:
            return
        is_light_bg = sum(self.background_color[:3]) / 3 > 0.5
        if self.background_preset == 'Black':
            self.vignette.set_edge_alpha(0)
        elif is_light_bg:
            self.vignette.set_edge_alpha(28)
        else:
            self.vignette.set_edge_alpha(95)

    # ----------------------------------------------------------- control slots
    def _change_representation(self, name: str):
        if name not in self.REPRESENTATIONS:
            return
        self.representation = name
        # Pick sensible defaults per representation
        if name == 'Space Filling':
            self.size_slider.blockSignals(True)
            self.size_slider.setValue(100)
            self.size_slider.blockSignals(False)
            self.atom_scale = 1.0
            self.size_label.setText("100%")
            self.show_bonds_cb.setEnabled(False)
        elif name == 'Sticks':
            self.show_bonds_cb.setEnabled(True)
            self.show_bonds_cb.setChecked(True)
            self.show_bonds = True
        else:  # Ball & Stick
            self.size_slider.blockSignals(True)
            self.size_slider.setValue(40)
            self.size_slider.blockSignals(False)
            self.atom_scale = 0.40
            self.size_label.setText("40%")
            self.show_bonds_cb.setEnabled(True)
        if self.current_structure:
            self._render_structure()

    def _toggle_bonds(self, state):
        self.show_bonds = bool(state)
        if self.current_structure:
            self._render_structure()

    def _toggle_unit_cell(self, state):
        self.show_unit_cell = bool(state)
        if self.current_structure:
            self._render_structure()

    def _toggle_axes(self, state):
        self.show_axes = bool(state)
        self._add_axes()

    def _toggle_legend(self, state):
        self.show_legend = bool(state)
        if self.legend is not None:
            self.legend.setVisible(self.show_legend and bool(self.legend._entries))

    def _change_background(self, preset_name: str):
        if preset_name in BACKGROUND_PRESETS:
            self.background_preset = preset_name
            self.background_color = BACKGROUND_PRESETS[preset_name]
            self._apply_background_color()
            self._update_vignette_strength()
            self.gl_widget.update()
            if self.current_structure:
                self._render_structure()
            elif self.show_axes:
                self._add_axes()
            self.background_changed.emit(preset_name)

    def set_background_color(self, r: float, g: float, b: float, a: float = 1.0):
        """Set a custom background color (RGBA components in 0.0-1.0)."""
        self.background_color = (r, g, b, a)
        self.background_preset = 'Custom'
        self._apply_background_color()
        self._update_vignette_strength()
        self.gl_widget.update()

    def _update_atom_size(self, value):
        self.atom_scale = value / 100.0
        self.size_label.setText(f"{value}%")
        if self.current_structure:
            self._render_structure()

    def _update_bond_cutoff(self, value):
        self.bond_cutoff = value / 10.0
        self.bond_label.setText(f"{self.bond_cutoff:.1f} Å")
        if self.current_structure:
            self._render_structure()

    def _reset_view(self):
        if self.current_structure is not None and self._last_coords is not None:
            self._frame_camera(self._last_coords, self._last_radii, reset_angle=True)
        else:
            self.gl_widget.setCameraPosition(distance=20, elevation=22, azimuth=40)

    def _export_cif(self):
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
                CifWriter(self.current_structure).write_file(filename)
                QMessageBox.information(
                    self, "Export Successful", f"Structure exported to:\n{filename}"
                )
                self.structure_exported.emit(filename)
            except Exception as e:
                QMessageBox.critical(self, "Export Error", f"Failed to export: {str(e)}")
