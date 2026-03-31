"""Centralised, platform-safe loader for the optional user ``config`` module.

Every place in the package that previously did a bare ``import config`` now
calls :func:`get_config_value` instead.  The loader tries, in order:

1. The ``config`` module already on ``sys.modules`` (e.g. when the user has
   imported it at the top of their script).
2. ``importlib.import_module("config")`` – works when the project root (or any
   directory containing ``config.py``) is on ``sys.path``.

If the config module cannot be found, every call silently returns *default*.
No ``sys.path`` mutation is performed, so the approach is safe against
accidental name collisions on different platforms.
"""

from __future__ import annotations

import importlib
import sys
from typing import Any

_SENTINEL = object()
_config_module: Any = _SENTINEL


def _load_config() -> Any:
    """Return the ``config`` module or ``None`` on failure."""
    global _config_module
    if _config_module is not _SENTINEL:
        return _config_module
    try:
        _config_module = importlib.import_module("config")
    except Exception:
        _config_module = None
    return _config_module


def get_config_value(name: str, default: Any = None) -> Any:
    """Return ``config.<name>`` if available, otherwise *default*."""
    mod = _load_config()
    if mod is None:
        return default
    return getattr(mod, name, default)
