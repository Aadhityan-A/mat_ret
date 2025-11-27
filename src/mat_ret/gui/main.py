#!/usr/bin/env python3
"""
mat_ret GUI Application

Main entry point for the materials database retrieval GUI.

Usage:
    # After installing mat_ret:
    mat-ret-gui
    
    # Or run directly:
    python -m mat_ret.gui
    
    # Or programmatically:
    from mat_ret.gui import main
    main()
"""

import sys


def check_dependencies():
    """Check if required dependencies are installed."""
    missing = []
    
    # Check PyQt6
    try:
        from PyQt6.QtWidgets import QApplication
    except ImportError:
        missing.append("PyQt6")
    
    # Check matplotlib
    try:
        import matplotlib
    except ImportError:
        missing.append("matplotlib")
    
    # Check mat_ret
    try:
        from mat_ret import api
    except ImportError:
        missing.append("mat_ret (run: pip install -e . from project root)")
    
    if missing:
        print("Missing dependencies:")
        for dep in missing:
            print(f"  - {dep}")
        print("\nInstall with: pip install PyQt6 matplotlib")
        print("And ensure mat_ret is installed: pip install -e .")
        sys.exit(1)


def main():
    """Main entry point for the GUI application."""
    # Check dependencies first
    check_dependencies()
    
    from PyQt6.QtWidgets import QApplication
    from PyQt6.QtCore import Qt
    from PyQt6.QtGui import QIcon
    
    from mat_ret.gui.main_window import MainWindow
    
    # Enable high DPI scaling
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    
    # Create application
    app = QApplication(sys.argv)
    app.setApplicationName("mat_ret")
    app.setOrganizationName("mat_ret")
    app.setApplicationVersion("1.0.0")
    
    # Set application style
    app.setStyle("Fusion")
    
    # Create and show main window
    window = MainWindow()
    window.show()
    
    # Run event loop
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
