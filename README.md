# mat_ret

Unified retrieval and property mapping for materials databases, with a PyQt6 GUI for materials search, structure viewing, and XRD generation.

## Supported Databases

1. Materials Project
2. JARVIS
3. AFLOW
4. Alexandria
5. Materials Cloud
6. MPDS
7. OQMD
8. OPTIMADE providers (registry search)

## Installation

Install as package:

```bash
pip install .
```

Install editable for development:

```bash
pip install -e .
```

Install editable with test dependencies:

```bash
pip install -e ".[dev]"
```

## Quick Start

1. Configure API keys (`MP_API_KEY`, `MPDS_API_KEY`) via environment variables or `config.py`.
2. Run examples:

```bash
python example_fetch.py
python example_single_fetch.py
```

3. Use the Python API:

```python
from mat_ret.api import fetch_all_databases

results = fetch_all_databases(
    formula="MgO",
    limit_per_database=3,
    mp_api_key="YOUR_MP_KEY",
    mpds_api_key="YOUR_MPDS_KEY",
)
print(results["materials_project"][0])
```

## Unified Retrieval & Filtering

`fetch_all_databases` is a single entry point across every supported database.
It accepts a **formula or an element system**, a database **subset**, a shared
**`SearchFilters`** object (applied server-side where supported, post-fetch
otherwise), **parallel** fetching, opt-out **CIF writing**, a **`retrieve_all`**
mode (each database is queried up to a safety cap rather than a fixed limit), and
optional cross-database **de-duplication**.

```python
from mat_ret.api import fetch_all_databases
from mat_ret.search import SearchFilters

filters = SearchFilters(
    band_gap_min=1.0, band_gap_max=3.0,
    is_stable=True,
    include_elements=["O"],      # must contain oxygen
    exclude_elements=["Pb"],     # must not contain lead
    crystal_system="cubic",
)

# Element-system search across a subset of databases, in parallel, merged.
unified = fetch_all_databases(
    elements=["Fe", "O"],
    databases=["materials_project", "jarvis", "oqmd"],
    filters=filters,
    parallel=True,
    save_cif=False,
    merge_duplicates=True,       # returns a unified, de-duplicated envelope
    mp_api_key="YOUR_MP_KEY",
)
for material in unified["materials"]:
    print(material["formula"], material["source_databases"])
print(unified["metadata"])       # counts, databases queried, dedup totals

# retrieve_all=True fetches as many matches as each database returns (slower).
everything = fetch_all_databases(formula="MgO", retrieve_all=True)
```

Every result dict carries unified keys including `formula`, `elements`,
`num_elements`, `num_sites`, and `source_database`, so filters and storage
queries work consistently across all databases.

## Direct Client Usage

You can call specific clients from `mat_ret.databases` directly:

```python
from mat_ret.databases import MaterialsProjectClient

client = MaterialsProjectClient(api_key="YOUR_MP_KEY")
results = client.get_structures("MgO", limit=1)
if results:
    entry = results[0]
    print(entry["material_id"])
```

## OPTIMADE Search

When OPTIMADE is selected in the GUI, providers are shown as a tree.
Select the parent to toggle all providers or select individual providers.
The search filter applies to each provider, and limit is applied per provider.

## Running in a Virtual Environment

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

## GUI

mat_ret includes a PyQt6 desktop GUI.

![mat_ret GUI Screenshot](doc/Screenshot.png?raw=true)

### Launch GUI

```bash
mat-ret-gui
# or
python -m mat_ret.gui
```

### GUI Features

- Database selection and API key controls
- OPTIMADE provider tree with per-provider toggles
- Formula search (e.g., `Fe2O3`, `LiFePO4`) across selected databases
- Element-set search via periodic-table picker icon next to the search box
  - Chemsys text format: `Fe-O`, `Li-Fe-O`
  - Element mode uses contains-all semantics
  - Unsupported providers/databases are skipped with explicit status messages (e.g., OQMD)
- Search filters (electronic, energetic, structural, composition, mechanical,
  magnetic) applied across all databases, including **must-contain / exclude
  element** filters
- "Retrieve all matches" toggle to fetch as many results as each database
  returns (up to a safety cap) instead of a fixed per-database limit
- Incremental results display (each database appears as it completes) with an
  optional **Merge duplicates across databases** view
- Results table and JSON views
- Structure viewer with CIF export
- File menu exports (JSON/CSV)
- Stored-materials browser with formula / source / crystal-system / band-gap /
  element / energy-above-hull filters (SQLite, MongoDB, or file backends)
- Tools menu:
  - XRD Generator

## XRD Generator

Open `Tools -> XRD Generator...` in the GUI.

Capabilities:

- Input sources:
  - Any CIF file from disk
  - Currently selected structure from the main results window
- Radiation presets from pymatgen (including `CuKa`, `CuKa1`, `CuKa2`, etc.)
- Optional custom wavelength (Angstrom)
- Scan controls: `2theta min`, `2theta max`, `2theta step`
- Profile controls:
  - `Stick`
  - `Gaussian`
  - `Lorentzian`
  - `Pseudo-Voigt` (with `eta`)
- Peak broadening width control (`FWHM`, degrees in 2theta)
- Peak finder controls using SciPy:
  - minimum height
  - prominence
  - minimum distance
  - minimum width
  - theoretical peak match tolerance
- Interactive plot view + peak table
- Exports:
  - plot (`PNG`, `SVG`, `PDF`)
  - profile/stick CSV
  - peaks CSV

Defaults:

- Radiation: `CuKa` (`1.54184 A`)
- Scan range: `5` to `90` deg (2theta), step `0.02`
- Profile: `Pseudo-Voigt`
- FWHM: `0.15` deg
- Eta: `0.5`

Detailed XRD notes are in `doc/XRD_GENERATOR_GUIDE.md`.

## XRD API

```python
from mat_ret import XRDConfig, generate_xrd_pattern_from_cif

cfg = XRDConfig(
    radiation="CuKa",
    two_theta_min=5.0,
    two_theta_max=90.0,
    two_theta_step=0.02,
    profile="pseudo_voigt",
    fwhm=0.15,
)

result = generate_xrd_pattern_from_cif("example.cif", config=cfg)
print(result.wavelength, len(result.peaks))
```

## Tests

Run XRD tests:

```bash
pytest tests/test_xrd.py
```

Run all tests:

```bash
pytest
```

## Project Structure

```text
mat_ret/
├── src/mat_ret/
│   ├── api.py
│   ├── databases.py
│   ├── property_mapping.py
│   ├── xrd.py
│   └── gui/
│       ├── main.py
│       ├── main_window.py
│       ├── workers.py
│       ├── utils.py
│       └── widgets/
│           ├── database_selector.py
│           ├── results_view.py
│           ├── structure_viewer.py
│           └── xrd_generator_window.py
├── tests/
│   └── test_xrd.py
├── doc/
│   ├── PROPERTY_MAPPING_GUIDE.md
│   └── XRD_GENERATOR_GUIDE.md
├── README.md
├── pyproject.toml
└── requirements.txt
```

## Contributing

Issues and pull requests are welcome:
https://github.com/Aadhityan-A/mat_ret
