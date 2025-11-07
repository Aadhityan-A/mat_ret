# PROPERTY MAPPING GUIDE

This guide explains how the `mat_rev` library unifies material properties from multiple databases into a consistent schema.

## 1. Introduction

The `mat_rev` package retrieves raw data from various materials databases, applies standardized property names via mapping configurations, and exports both CIF files and metadata JSON. Central to this process is a property mapping system that ensures every database uses the same internal keys.

## 2. Standard Properties

All supported properties are defined in `STANDARD_PROPERTIES` (in `src/mat_rev/property_mapping.py`). Below is a complete table of properties, their internal keys, and units:

| Property                  | Key                         | Unit            |
|---------------------------|-----------------------------|-----------------|
| Material ID               | `material_id`               | identifier      |
| Formula                   | `formula`                   | —               |
| Space group               | `space_group`               | —               |
| Space group number        | `space_group_number`        | —               |
| Density                   | `density`                   | g/cm³           |
| Volume                    | `volume`                    | Å³              |
| Lattice parameters        | `lattice_parameters`        | Å               |
| Crystal system            | `crystal_system`            | categorical     |
| Band gap                  | `band_gap`                  | eV              |
| Direct band gap           | `band_gap_direct`           | eV              |
| Indirect band gap         | `band_gap_indirect`         | eV              |
| Is metallic               | `is_metallic`               | boolean         |
| Electronic type           | `electronic_type`           | categorical     |
| Formation energy          | `formation_energy`          | eV              |
| Formation energy per atom | `formation_energy_per_atom` | eV/atom         |
| Energy per atom           | `energy_per_atom`           | eV/atom         |
| Total energy              | `total_energy`              | eV              |
| Energy above hull         | `energy_above_hull`         | eV/atom         |
| Bulk modulus              | `bulk_modulus`              | GPa             |
| Shear modulus             | `shear_modulus`             | GPa             |
| Elastic modulus           | `elastic_modulus`           | GPa             |
| Poisson ratio             | `poisson_ratio`             | —               |
| Elastic tensor            | `elastic_tensor`            | GPa             |
| Hardness                  | `hardness`                  | GPa             |
| Thermal expansion         | `thermal_expansion`         | 10⁻⁶/K          |
| Thermal conductivity      | `thermal_conductivity`      | W/m·K           |
| Heat capacity             | `heat_capacity`             | J/mol·K         |
| Debye temperature         | `debye_temperature`         | K               |
| Magnetic moment           | `magnetic_moment`           | μ_B             |
| Magnetic ordering         | `magnetic_ordering`         | categorical     |
| Is magnetic               | `is_magnetic`               | boolean         |
| Refractive index          | `refractive_index`          | —               |
| Dielectric constant       | `dielectric_constant`       | —               |
| Optical absorption        | `optical_absorption`        | cm⁻¹            |
| Functional                | `functional`                | —               |
| Calculation method        | `calculation_method`        | text            |
| Calculation date          | `calculation_date`          | date            |
| Source database           | `source_database`           | —               |
| Last modified             | `last_modified`             | date            |
| Entry ID                  | `entry_id`                  | text            |

## 3. Database-Specific Mappings

Mappings between raw database fields and standard keys live in `DATABASE_PROPERTY_MAPPINGS`. To view current mappings, inspect `src/mat_rev/property_mapping.py`. Example for Materials Project:

```python
DATABASE_PROPERTY_MAPPINGS['materials_project'] = {
    'material_id': 'material_id',
    'formula': 'formula_pretty',
    'space_group': 'symmetry.symbol',
    # ...
}
```

### Customizing or Adding Mappings
1. Open `DATABASE_PROPERTY_MAPPINGS` in `property_mapping.py`.
2. Add or update the mapping for your database and property.
3. Use `export_property_mappings(path)` to write updates to `property_mappings.json`.

## 4. Helper Functions

- `get_available_properties(database: str) -> List[str]`  
  Returns all standard keys supported by a database.
- `get_property_value(raw: dict, database: str, key: str) -> Any`  
  Extracts and converts the raw field for a single property.
- `standardize_properties(raw: dict, database: str) -> dict`  
  Builds a complete dict of all standard properties for one record.
- `export_property_mappings(path: str) -> None`  
  Exports current mapping definitions to a JSON file.

## 5. Extending the System

**Adding a new property**:
1. In `STANDARD_PROPERTIES`, add your new key and default name.
2. Define its unit in `PROPERTY_UNITS`.
3. In each database map, add the raw field path under `DATABASE_PROPERTY_MAPPINGS`.
4. Call `standardize_properties` to test extraction.

**Adding a new database**:
1. Subclass `MaterialsDatabaseClient` in `src/mat_rev/databases.py`.
2. Register your client in `MaterialsDatabaseRetriever._initialize_clients()`.

## 6. Examples

```python
from mat_rev.property_mapping import standardize_properties
from mat_rev.api import fetch_jarvis

# Fetch raw entries
entry = fetch_jarvis('MgO', limit=1)[0]
# Standardize properties
std = standardize_properties(entry, 'jarvis')
print(std)
```

## Appendix

- **Full JSON Mapping**: `property_mappings.json`
- **Source Code**: `src/mat_rev/property_mapping.py`
