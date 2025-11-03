#!/usr/bin/env python3
"""Example: Fetch a single entry from a specific database using a client class"""

import os
from mat_ret.databases import MaterialsProjectClient#, JARVISClient, AFLOWClient
from pathlib import Path
import json
from pymatgen.io.cif import CifWriter

# Choose your database client:
# client = JARVISClient(output_directory=None)
# client = AFLOWClient(output_directory=None)

# Example: Materials Project
try:
    import config
    mp_api_key = os.getenv('MP_API_KEY') or config.MP_API_KEY
except ImportError:
    mp_api_key = os.getenv('MP_API_KEY')

client = MaterialsProjectClient(api_key=mp_api_key)

# Define the target formula
MATERIAL = 'MgO'

# Fetch a single structure for MgO
results = client.get_structures('MgO', limit=1)

if not results:
    print("No structures returned.")
    exit(1)

entry = results[0]
print("Fetched entry metadata:")
for key, value in entry.items():
    if key == 'structure':
        continue
    print(f"- {key}: {value}")

# After fetching entry
out_root = Path.cwd() / "example_single_downloads" / client.database_name
out_root.mkdir(parents=True, exist_ok=True)
filename_base = f"{client.database_name}_{MATERIAL}_1"

# Save metadata JSON
meta = {k: v for k, v in entry.items() if k != 'structure'}
with open(out_root / f"{filename_base}_metadata.json", 'w') as jf:
    json.dump(meta, jf, indent=2, default=str)
print(f"Metadata saved to {out_root / (filename_base + '_metadata.json')}")

# Save CIF file
structure = entry.get('structure')
if structure:
    cif_path = out_root / f"{filename_base}.cif"
    CifWriter(structure).write_file(str(cif_path))
    print(f"Structure CIF saved to {cif_path}")
else:
    print("No structure available to save CIF.")