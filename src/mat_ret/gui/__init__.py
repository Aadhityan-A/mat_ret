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
"""

__version__ = "1.0.0"

from .main import main

__all__ = ["main"]
