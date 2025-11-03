# mat_ret

**Unified retrieval and property mapping for materials databases**
This project is intended to extract materials data from various databases (see the supported databases section) and have a single property identifier for clear and unambiguous understanding.

***Supported databases:***
  1. MATERIALS PROJECT
  2. JARVIS
  3. AFLOW
  4. ALEXANDRIA
  5. MATERIALS CLOUD
  6. MPDS
  7. OQMD

## Installation

Install in development mode:

```bash
pip install -e .
```

Or install as a package:

```bash
pip install .
```

## Quick Start

1. **Configure API keys**
   - Set `MP_API_KEY` and `MPDS_API_KEY` as environment variables or in `config.py`.

2. **Run tests and examples**
   - Full test suite:
     ```bash
     python comprehensive_database_test.py --formula Al2O3 --limit 2
     ```
   - Demo fetch:
     ```bash
     python example_fetch.py
     ```

3. **Library usage**
   - High-level fetch helper:
     ```python
     from mat_ret.api import fetch_all_databases

     results = fetch_all_databases(
         formula='MgO',
         limit_per_database=3,
         mp_api_key='YOUR_MP_KEY',
         mpds_api_key='YOUR_MPDS_KEY'
     )
     print(results['materials_project'][0])
     ```

## Direct Client Usage

Look into the example_single_fetch.py file to retive from a single database then save the information in json format and the sturcture in cif format.
You can bypass the high-level helpers and use specific client classes from `mat_ret.databases`. For example, to fetch from Materials Project:

```python
from mat_ret.databases import MaterialsProjectClient

# Initialize client with your API key
client = MaterialsProjectClient(api_key='YOUR_MP_KEY')
# Retrieve a single structure for MgO
results = client.get_structures('MgO', limit=1)
if results:
    entry = results[0]
    print(f"Material ID: {entry['material_id']}")
    for key, value in entry.items():
        if key != 'structure':
            print(f"{key}: {value}")
``` 

## Running in a Virtual Environment (.venv)

To isolate dependencies, create and activate a Python virtual environment in your project root:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

Then run scripts using the environment's Python interpreter:

```bash
.venv/bin/python example_single_fetch.py
.venv/bin/python example_fetch.py
.venv/bin/python comprehensive_database_test.py --formula Al2O3 --limit 2
```

## Project Structure

```
mat_ret/
├── src/mat_ret/                # Core package code
│   ├── api.py                  # High-level fetch helpers
│   ├── property_mapping.py     # Mapping config and helpers
│   └── databases.py            # Database client implementations
├── doc/                        # Documentation assets (CSV, guides)
├── example_fetch.py            # Demo script intended to retirive information from all the above mentioned database
├── example_single_fetch.py            # Demo script intended to retirive information from anyone of the above mentioned database
├── README                      # Project overview
├── requirements.txt            # Python dependencies
└── LICENSE                     # CeCILL license
```

## Contributing

Keep in touch to contribute !!!
We welcome others to develop/fix the functionalities of this python library with these existing databases and/or provide new databases.
https://github.com/Aadhityan-A/mat_ret

*Note:* It's still in the developing phase. If you face any issues let us know through github issues. Also there are some lines of code not in use are present for future development purpose.
