"""
mat_ret GUI Package

A PyQt6-based graphical interface for searching, retrieving, 
and visualizing materials data from multiple databases.

Usage:
    # From command line (after installing mat_ret):
    mat-ret-gui
    
    # Or programmatically:
    from mat_ret.gui import main
    main()

Requires the ``gui`` extra: ``pip install mat_ret[gui]``
"""

__version__ = "1.0.0"


def main():
    """Launch the GUI application (lazy import to avoid hard PyQt6 dependency)."""
    from .main import main as _main
    return _main()


__all__ = ["main"]
