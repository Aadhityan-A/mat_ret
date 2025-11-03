"""Configuration helpers for the mat_rev package.

Environment variables are preferred for secrets. Provide fallbacks here only for
local development.
"""

from __future__ import annotations

import os
from pathlib import Path


# Materials Project API key (https://materialsproject.org/api)
# MP_API_KEY = os.getenv("MP_API_KEY")
MP_API_KEY= "" # Provide your Materials Project API key here
# MPDS API key (https://developer.mpds.io/)
MPDS_API_KEY = "" # Provide your MPDS API key here
# MPDS_API_KEY = os.getenv("MPDS_API_KEY")
# AFLOW settings (no key required)
AFLOW_BASE_URL = "http://aflowlib.duke.edu/search/API/"

# Download settings
DOWNLOAD_LIMIT_PER_DB = int(os.getenv("MAT_REV_DOWNLOAD_LIMIT", "10"))

_output_dir_env = os.getenv("MAT_REV_OUTPUT_DIR")
if _output_dir_env:
    OUTPUT_DIRECTORY = Path(_output_dir_env).expanduser()
else:
    OUTPUT_DIRECTORY = Path.cwd() / "downloaded_materials"

# Structure matching tolerances for deduplication (for future use)
STRUCTURE_MATCHING = {
    "ltol": 0.2,        # Length tolerance
    "stol": 0.3,        # Site tolerance
    "angle_tol": 5,     # Angle tolerance (degrees)
    "primitive_cell": True,
    "scale": True,
    "attempt_supercell": False
}
