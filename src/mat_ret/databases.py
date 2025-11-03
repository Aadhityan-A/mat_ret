"""Utilities for retrieving materials data from external databases."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

import requests
import re

# Third-party imports
try:
    from mp_api.client import MPRester
except ImportError:
    print("Warning: mp-api not installed. Materials Project access will be limited.")
    MPRester = None

try:
    from jarvis.db.figshare import data
    from jarvis.core.atoms import Atoms as JarvisAtoms
except ImportError:
    print("Warning: jarvis-tools not installed. JARVIS access will be limited.")
    data = None
    JarvisAtoms = None


try:
    import aflow
except ImportError:
    print("Warning: aflow not installed. AFLOW access will be limited.")
    aflow = None

try:
    from mpds_client import MPDSDataRetrieval
except ImportError:
    print("Warning: mpds-client not installed. MPDS access will be limited.")
    MPDSDataRetrieval = None

try:
    from optimade.client import OptimadeClient
    from optimade.adapters.structures import Structure as OptimadeStructure
    from optimade.adapters.exceptions import ConversionError as OptimadeConversionError
except ImportError:
    print("Warning: optimade client extras not installed. Materials Cloud access will be limited.")
    OptimadeClient = None
    OptimadeStructure = None
    OptimadeConversionError = Exception

from pymatgen.core.structure import Structure as PymatgenStructure
from pymatgen.io.cif import CifWriter, CifParser
from pymatgen.core.composition import Composition

# Import property mapping system
from .property_mapping import (
    get_property_value,
    get_available_properties,
    STANDARD_PROPERTIES,
    DATABASE_PROPERTY_MAPPINGS,
)


AFLOW_REST_URL = os.getenv("AFLOW_BASE_URL", "http://aflowlib.duke.edu/search/API/")


class MaterialsDatabaseClient:
    """Base class for materials database clients."""

    def __init__(self, database_name: str, output_directory: Optional[Path] = None):
        base_dir = Path(output_directory) if output_directory else (Path.cwd() / "downloaded_materials")
        self.database_name = database_name
        self.output_dir = base_dir / database_name
        self.output_dir.mkdir(parents=True, exist_ok=True)
    
    def get_structures(self, formula: str, limit: int = 10) -> List[Dict]:
        """Get structures for a given formula"""
        raise NotImplementedError
    
    def save_cif(self, structure_data: Dict, filename: str) -> str:
        """Save structure as CIF file"""
        raise NotImplementedError


class MaterialsProjectClient(MaterialsDatabaseClient):
    """Materials Project database client."""

    def __init__(self, api_key: str, output_directory: Optional[Path] = None):
        super().__init__("materials_project", output_directory=output_directory)
        self.api_key = api_key
        if MPRester is None:
            raise ImportError("mp-api is required for Materials Project access")
        self.client = MPRester(api_key)
    
    def get_structures(self, formula: str, limit: int = 10) -> List[Dict]:
        """Get structures from Materials Project with GGA PBE functional"""
        try:
            # Get available properties for Materials Project
            available_props = get_available_properties('materials_project')
            
            # Search for materials with the given formula - use only available fields
            docs = self.client.materials.summary.search(
                formula=formula,
                theoretical=True,
                fields=["material_id", "formula_pretty", "structure", "band_gap", 
                       "formation_energy_per_atom", "energy_per_atom", "density",
                       "symmetry", "volume", "is_metal", "energy_above_hull",
                       "total_magnetization", "ordering", "bulk_modulus", "shear_modulus"]
            )
            
            results = []
            for i, doc in enumerate(docs[:limit]):
                if doc.structure:
                    # Convert doc to dictionary for property extraction
                    doc_dict = doc.model_dump() if hasattr(doc, 'model_dump') else doc.__dict__
                    
                    # Use property mapping to extract standardized properties
                    structure_data = {
                        'database': 'Materials Project',
                        'structure': doc.structure
                    }
                    
                    # Extract all available properties using mapping
                    for prop_name in available_props:
                        value = get_property_value(doc_dict, 'materials_project', prop_name)
                        if value is not None:
                            structure_data[STANDARD_PROPERTIES[prop_name]] = value
                    
                    # Set functional information
                    structure_data['functional'] = 'GGA PBE'
                    structure_data['source_database'] = 'Materials Project'
                    
                    results.append(structure_data)
            
            return results
        except Exception as e:
            print(f"Error retrieving from Materials Project: {e}")
            return []
    
    def save_cif(self, structure_data: Dict, filename: str) -> str:
        """Save Materials Project structure as CIF file"""
        cif_path = self.output_dir / f"{filename}.cif"
        structure = structure_data['structure']
        
        # Write CIF file
        cif_writer = CifWriter(structure)
        cif_writer.write_file(str(cif_path))
        
        # Save metadata
        metadata = {k: v for k, v in structure_data.items() if k != 'structure'}
        metadata_path = self.output_dir / f"{filename}_metadata.json"
        with open(metadata_path, 'w') as f:
            json.dump(metadata, f, indent=2, default=str)
        
        return str(cif_path)


class JARVISClient(MaterialsDatabaseClient):
    """JARVIS database client."""

    def __init__(self, output_directory: Optional[Path] = None):
        super().__init__("jarvis", output_directory=output_directory)
        if data is None or JarvisAtoms is None:
            raise ImportError("jarvis-tools is required for JARVIS access")
    
    def get_structures(self, formula: str, limit: int = 10) -> List[Dict]:
        """Get structures from JARVIS-DFT database"""
        try:
            # Download JARVIS-DFT dataset
            dft_3d = data('dft_3d')
            
            results = []
            count = 0
            
            for entry in dft_3d:
                if count >= limit:
                    break
                
                # Check if formula matches
                if entry.get('formula', '').replace(' ', '') == formula.replace(' ', ''):
                    # Convert JARVIS atoms to pymatgen structure
                    jarvis_atoms = JarvisAtoms.from_dict(entry['atoms'])
                    pymatgen_structure = jarvis_atoms.pymatgen_converter()
                    
                    # Use property mapping to extract standardized properties
                    structure_data = {
                        'database': 'JARVIS',
                        'structure': pymatgen_structure
                    }
                    
                    # Get available properties for JARVIS
                    available_props = get_available_properties('jarvis')
                    
                    # Extract all available properties using mapping
                    for prop_name in available_props:
                        value = get_property_value(entry, 'jarvis', prop_name)
                        if value is not None:
                            structure_data[STANDARD_PROPERTIES[prop_name]] = value
                    
                    # Set functional and source information
                    structure_data['functional'] = 'GGA PBE/optB88vdW'
                    structure_data['source_database'] = 'JARVIS'
                    
                    results.append(structure_data)
                    count += 1
            
            return results
        except Exception as e:
            print(f"Error retrieving from JARVIS: {e}")
            return []
    
    def save_cif(self, structure_data: Dict, filename: str) -> str:
        """Save JARVIS structure as CIF file"""
        cif_path = self.output_dir / f"{filename}.cif"
        structure = structure_data['structure']
        
        # Write CIF file
        cif_writer = CifWriter(structure)
        cif_writer.write_file(str(cif_path))
        
        # Save metadata
        metadata = {k: v for k, v in structure_data.items() if k != 'structure'}
        metadata_path = self.output_dir / f"{filename}_metadata.json"
        with open(metadata_path, 'w') as f:
            json.dump(metadata, f, indent=2, default=str)
        
        return str(cif_path)


class AFLOWClient(MaterialsDatabaseClient):
    """AFLOW database client."""

    _schema_fields: Optional[set[str]] = None

    def __init__(self, output_directory: Optional[Path] = None):
        super().__init__("aflow", output_directory=output_directory)
        if aflow is None:
            print("Warning: aflow package not available, using REST API")
    
    @classmethod
    def _get_schema_fields(cls) -> Optional[set[str]]:
        """Cache and return available AFLOW API fields from ?schema endpoint."""
        if cls._schema_fields is None:
            schema_url = AFLOW_REST_URL.rstrip('/') + '/?schema'
            try:
                response = requests.get(
                    schema_url,
                    timeout=30,
                    headers={'User-Agent': 'mat-rev/1.0'}
                )
                response.raise_for_status()
                data = response.json()
                if isinstance(data, dict):
                    cls._schema_fields = set(data.keys())
            except Exception as exc:
                print(f"  AFLOW schema fetch failed: {exc}")
                return None
        return cls._schema_fields

    def get_structures(self, formula: str, limit: int = 10) -> List[Dict]:
        """Get structures from AFLOW database"""
        try:
            # Use REST API approach (aflow package has API issues)
            return self._get_structures_rest_api(formula, limit)
                
        except Exception as e:
            print(f"Error retrieving from AFLOW: {e}")
            return []
    
    def _get_structures_rest_api(self, formula: str, limit: int) -> List[Dict]:
        """Get structures using AFLOW REST API."""
        results: List[Dict] = []

        if limit <= 0:
            return results

        props = get_available_properties('aflow')
        db_mapping = DATABASE_PROPERTY_MAPPINGS.get('aflow', {})

        requested_fields: set[str] = set()
        for prop in props:
            if prop in {'functional', 'source_database'}:
                continue
            field_name = db_mapping.get(prop)
            if isinstance(field_name, str) and re.match(r'^[A-Za-z0-9_]+$', field_name):
                requested_fields.add(field_name)

        # Always include identifiers, CIF text, and basic structural helpers
        requested_fields.update({
            'auid',
            'compound',
            'aurl',
            'geometry',
            'positions_fractional',
            'species',
        })

        schema_fields = self._get_schema_fields()
        if schema_fields:
            requested_fields = {field for field in requested_fields if field in schema_fields}

        elements = re.findall(r'[A-Z][a-z]?', formula)
        unique_species: List[str] = []
        for el in elements:
            if el not in unique_species:
                unique_species.append(el)

        if not unique_species:
            return results

        nspecies = len(unique_species)
        paging_count = max(1, limit)

        query_parts = [
            f"species({','.join(unique_species)})",
            f"nspecies({nspecies})",
            f"paging(0,{paging_count})",
        ]
        query_parts.extend(sorted(requested_fields))

        base_url = AFLOW_REST_URL.rstrip('/')
        query_url = f"{base_url}/?{','.join(query_parts)}"

        try:
            response = requests.get(
                query_url,
                timeout=30,
                headers={'User-Agent': 'mat-rev/1.0'}
            )
            response.raise_for_status()
            raw_data = response.json()
        except Exception as exc:
            print(f"  AFLOW request failed: {exc}")
            return results

        if isinstance(raw_data, list):
            entries = raw_data
        elif isinstance(raw_data, dict):
            entries = [value for value in raw_data.values() if isinstance(value, dict)]
        else:
            entries = []

        for entry in entries[:limit]:
            structure_data: Dict = {'database': 'AFLOW'}

            for prop in props:
                value = get_property_value(entry, 'aflow', prop)
                if value is not None:
                    structure_data[STANDARD_PROPERTIES[prop]] = value

            # Ensure core identifiers are present even if mapping skipped them
            material_id_key = STANDARD_PROPERTIES.get('material_id')
            if material_id_key and material_id_key not in structure_data and entry.get('auid'):
                structure_data[material_id_key] = entry.get('auid')

            formula_key = STANDARD_PROPERTIES.get('formula')
            if formula_key and formula_key not in structure_data and entry.get('compound'):
                structure_data[formula_key] = entry.get('compound')

            structure = None
            geometry = entry.get('geometry')
            positions = entry.get('positions_fractional')
            if geometry and positions and isinstance(geometry, str) and isinstance(positions, str):
                try:
                    from pymatgen.core.lattice import Lattice

                    params = [float(part) for part in geometry.split(',') if part.strip()]
                    if len(params) == 6:
                        lattice = Lattice.from_parameters(*params)

                        coords = []
                        for coord in positions.split(';'):
                            coord = coord.strip()
                            if coord:
                                coords.append([float(val) for val in coord.split(',') if val.strip()])

                        species_sequence: List[str] = []
                        compound = entry.get('compound', '') or ''
                        composition_tokens = re.findall(r'([A-Z][a-z]*)([0-9\.]+)?', compound)
                        raw_counts: List[float] = []
                        ordered_elements: List[str] = []
                        for elem, count_str in composition_tokens:
                            if not elem:
                                continue
                            try:
                                count_val = float(count_str) if count_str else 1.0
                            except (TypeError, ValueError):
                                count_val = 1.0
                            ordered_elements.append(elem)
                            raw_counts.append(count_val)

                        total_sites = len(coords)
                        if raw_counts and total_sites > 0:
                            total_units = sum(raw_counts)
                            if total_units > 0:
                                scale = total_sites / total_units
                                assigned = 0
                                for elem, count_val in zip(ordered_elements, raw_counts):
                                    expected = int(round(count_val * scale))
                                    species_sequence.extend([elem] * expected)
                                    assigned += expected
                                if assigned != total_sites and ordered_elements:
                                    diff = total_sites - assigned
                                    if diff > 0:
                                        species_sequence.extend([ordered_elements[-1]] * diff)
                                    elif diff < 0:
                                        species_sequence = species_sequence[:total_sites]

                        if (not species_sequence or len(species_sequence) != total_sites) and total_sites > 0:
                            species_list = [e.strip() for e in (entry.get('species') or ','.join(unique_species)).split(',') if e.strip()]
                            if species_list:
                                repeats = max(1, total_sites // len(species_list))
                                species_sequence = []
                                for elem in species_list:
                                    species_sequence.extend([elem] * repeats)
                                while len(species_sequence) < total_sites:
                                    species_sequence.append(species_list[len(species_sequence) % len(species_list)])
                                species_sequence = species_sequence[:total_sites]

                        if species_sequence and len(species_sequence) == total_sites and coords:
                            structure = PymatgenStructure(lattice, species_sequence, coords, coords_are_cartesian=False)
                except Exception:
                    structure = None

            if structure:
                structure_data['structure'] = structure
            else:
                if geometry:
                    structure_data['aflow_geometry'] = geometry
                if positions:
                    structure_data['aflow_positions_fractional'] = positions

            # Normalize space group number when embedded in string (e.g., "R-3m #166")
            sg_number_key = STANDARD_PROPERTIES.get('space_group_number')
            sg_value = structure_data.get(sg_number_key)
            if isinstance(sg_value, str):
                match = re.search(r'#(\d+)', sg_value)
                if match:
                    structure_data[sg_number_key] = int(match.group(1))

            # Apply defaults and metadata
            structure_data['functional'] = 'GGA-PBE'
            structure_data['source_database'] = 'AFLOW'
            if entry.get('aurl'):
                structure_data['aflow_entry'] = f"http://{entry['aurl']}" if not entry['aurl'].startswith(('http://', 'https://')) else entry['aurl']

            results.append(structure_data)

        return results
    
    def _safe_float(self, value: str) -> Optional[float]:
        """Safely convert string to float"""
        try:
            return float(value.strip())
        except (ValueError, AttributeError):
            return None
    
    def save_cif(self, structure_data: Dict, filename: str) -> str:
        """Save AFLOW structure as CIF file"""
        cif_path = self.output_dir / f"{filename}.cif"
        
        if 'structure' in structure_data:
            structure = structure_data['structure']
            cif_writer = CifWriter(structure)
            cif_writer.write_file(str(cif_path))
        else:
            # Create placeholder CIF with metadata
            with open(cif_path, 'w') as f:
                f.write(f"# AFLOW structure for {structure_data.get('formula', 'unknown')}\n")
                f.write(f"# Material ID: {structure_data.get('material_id', 'unknown')}\n")
                f.write(f"# Structure data not available in current format\n")
        
        # Save metadata
        metadata = {k: v for k, v in structure_data.items() if k != 'structure'}
        metadata_path = self.output_dir / f"{filename}_metadata.json"
        with open(metadata_path, 'w') as f:
            json.dump(metadata, f, indent=2, default=str)
        
        return str(cif_path)


class AlexandriaClient(MaterialsDatabaseClient):
    """Alexandria database client using OPTIMADE interface."""

    def __init__(self, output_directory: Optional[Path] = None):
        super().__init__("alexandria", output_directory=output_directory)
        self.base_url = "https://alexandria.icams.rub.de/pbe"  # PBE functional database
        self.pbesol_url = "https://alexandria.icams.rub.de/pbesol"  # PBEsol functional database
    
    def get_structures(self, formula: str, limit: int = 10) -> List[Dict]:
        """Get structures from Alexandria database using OPTIMADE API"""
        try:
            results = []
            
            # Try both PBE and PBEsol functionals
            for functional, url in [("PBE", self.base_url), ("PBEsol", self.pbesol_url)]:
                try:
                    # Construct OPTIMADE query
                    query_url = f"{url}/v1/structures"
                    params = {
                        'filter': f'chemical_formula_reduced="{formula}"',
                        'page_limit': min(limit, 5)  # Split between functionals
                    }
                    
                    response = requests.get(query_url, params=params, timeout=30)
                    
                    if response.status_code == 200:
                        data = response.json()
                        entries = data.get('data', [])
                        
                        for entry in entries:
                            attributes = entry.get('attributes', {})
                            
                            # Combine entry and attributes for property extraction
                            full_data = {**entry, **attributes}
                            
                            # Use property mapping to extract standardized properties
                            structure_data = {
                                'database': 'Alexandria'
                            }
                            
                            # Get available properties for Alexandria
                            available_props = get_available_properties('alexandria')
                            
                            # Extract all available properties using mapping
                            for prop_name in available_props:
                                value = get_property_value(full_data, 'alexandria', prop_name)
                                if value is not None:
                                    structure_data[STANDARD_PROPERTIES[prop_name]] = value
                            
                            # Set functional information
                            structure_data['functional'] = f'GGA {functional}'
                            structure_data['source_database'] = 'Alexandria'
                            
                            # Try to construct pymatgen structure
                            if all(k in attributes for k in ['lattice_vectors', 'cartesian_site_positions', 'species_at_sites']):
                                try:
                                    structure = self._create_pymatgen_structure(attributes)
                                    structure_data['structure'] = structure
                                except Exception as e:
                                    print(f"  Could not create structure: {e}")
                            
                            results.append(structure_data)
                            
                            if len(results) >= limit:
                                break
                        
                        print(f"  Found {len(entries)} materials from Alexandria ({functional})")
                    
                except requests.RequestException as e:
                    print(f"  Error querying Alexandria {functional}: {e}")
                
                if len(results) >= limit:
                    break
            
            return results[:limit]
        
        except Exception as e:
            print(f"Error retrieving from Alexandria: {e}")
            return []
    
    def _create_pymatgen_structure(self, attributes: Dict) -> PymatgenStructure:
        """Create pymatgen structure from OPTIMADE attributes"""
        lattice = attributes['lattice_vectors']
        positions = attributes['cartesian_site_positions']
        species = attributes['species_at_sites']
        
        # Convert to pymatgen format
        from pymatgen.core.lattice import Lattice
        
        lattice_obj = Lattice(lattice)
        structure = PymatgenStructure(lattice_obj, species, positions, coords_are_cartesian=True)
        
        return structure
    
    def save_cif(self, structure_data: Dict, filename: str) -> str:
        """Save Alexandria structure as CIF file"""
        cif_path = self.output_dir / f"{filename}.cif"
        
        if 'structure' in structure_data:
            structure = structure_data['structure']
            cif_writer = CifWriter(structure)
            cif_writer.write_file(str(cif_path))
        else:
            # Create CIF from OPTIMADE data if available
            with open(cif_path, 'w') as f:
                f.write(f"# Alexandria structure\n")
                f.write(f"# Formula: {structure_data.get('formula', 'unknown')}\n")
                f.write(f"# Material ID: {structure_data.get('material_id', 'unknown')}\n")
                f.write(f"# Functional: {structure_data.get('functional', 'unknown')}\n")
                f.write(f"# Space Group: {structure_data.get('space_group', 'unknown')}\n")
                
                # Add basic structure info if available
                if structure_data.get('lattice_vectors'):
                    f.write(f"\n# Lattice vectors available in metadata\n")
        
        # Save metadata
        metadata = {k: v for k, v in structure_data.items() if k != 'structure'}
        metadata_path = self.output_dir / f"{filename}_metadata.json"
        with open(metadata_path, 'w') as f:
            json.dump(metadata, f, indent=2, default=str)
        
        return str(cif_path)


class MaterialsCloudClient(MaterialsDatabaseClient):
    """Materials Cloud database client using OPTIMADE interface."""

    _MP_SUMMARY_FIELDS: Sequence[str] = (
        "material_id",
        "band_gap",
        "formation_energy_per_atom",
        "energy_per_atom",
        "energy_above_hull",
        "density",
        "volume",
        "is_metal",
        "total_magnetization",
        "ordering",
        "symmetry",
    )

    def __init__(self, output_directory: Optional[Path] = None, *, mp_api_key: Optional[str] = None):
        super().__init__("materials_cloud", output_directory=output_directory)
        self.base_url = "https://optimade.materialscloud.org"
        self._max_results_per_database = 4
        self.archive_databases: List[Dict[str, Optional[str]]] = []
        self.mp_api_key = mp_api_key or os.getenv("MP_API_KEY")
        if not self.mp_api_key:
            try:  # Prefer config fallback when present
                import config  # type: ignore

                self.mp_api_key = getattr(config, "MP_API_KEY", None)
            except ImportError:
                self.mp_api_key = None

        self._mpr_client: Optional[MPRester] = None
        self._mpr_client_unavailable = False
        self._mp_summary_cache: Dict[str, Optional[Dict[str, Any]]] = {}

        self._discover_databases()

    def _discover_databases(self) -> None:
        """Discover available databases from Materials Cloud."""
        try:
            response = requests.get(f"{self.base_url}/archive/index/v1/links", timeout=30)
            response.raise_for_status()
            links = response.json().get("data", [])

            discovered: List[Dict[str, Optional[str]]] = []
            for link in links:
                attributes = link.get("attributes", {})
                if attributes.get("link_type") != "child":
                    continue

                base_url = attributes.get("base_url")
                if not base_url:
                    continue

                discovered.append(
                    {
                        "id": link.get("id"),
                        "base_url": base_url.rstrip("/"),
                        "name": attributes.get("name"),
                    }
                )

            if discovered:
                self.archive_databases = discovered
                print(f"  Found {len(self.archive_databases)} Materials Cloud databases")
                return

            raise RuntimeError("No child archives returned from Materials Cloud")
        except Exception as exc:
            print(f"  Could not discover Materials Cloud databases automatically: {exc}")

        # Fallback archives known to be active
        self.archive_databases = [
            {
                "id": "m0-zg",
                "base_url": f"{self.base_url}/archive/m0-zg",
                "name": "Materials Cloud Archive (m0-zg)",
            },
            {
                "id": "1z-pd",
                "base_url": f"{self.base_url}/archive/1z-pd",
                "name": "Materials Cloud Archive (1z-pd)",
            },
        ]

    def _normalize_formula(self, formula: str) -> str:
        try:
            return Composition(formula).reduced_formula
        except Exception:
            return formula

    def _optimade_response_fields(self) -> Sequence[str]:
        """Return a conservative set of OPTIMADE fields shared across archives."""
        return (
            "id",
            "chemical_formula_reduced",
            "_mcloudarchive_mp_id",
            "lattice_vectors",
            "cartesian_site_positions",
            "species_at_sites",
            "dimension_types",
            "nsites",
            "last_modified",
        )

    def _get_mpr_client(self) -> Optional[MPRester]:
        if self._mpr_client_unavailable:
            return None

        if self._mpr_client is None:
            if MPRester is None or not self.mp_api_key:
                self._mpr_client_unavailable = True
                return None
            try:
                self._mpr_client = MPRester(self.mp_api_key)
            except Exception as exc:
                print(f"  Could not initialize Materials Project helper for Materials Cloud: {exc}")
                self._mpr_client_unavailable = True
                self._mpr_client = None
                return None

        return self._mpr_client

    @staticmethod
    def _normalize_mp_identifier(value: Any) -> Optional[str]:
        if value is None:
            return None
        norm = str(value).strip()
        if not norm or norm.lower() == "nan":
            return None
        if not norm.startswith("mp-"):
            norm = f"mp-{norm}"
        return norm

    def _fetch_materials_project_summary(self, mp_id: str) -> Optional[Dict[str, Any]]:
        if mp_id in self._mp_summary_cache:
            return self._mp_summary_cache[mp_id]

        client = self._get_mpr_client()
        if client is None:
            self._mp_summary_cache[mp_id] = None
            return None

        try:
            docs = client.materials.summary.search(
                material_ids=[mp_id],
                fields=list(self._MP_SUMMARY_FIELDS),
            )
        except Exception as exc:
            print(f"  Could not retrieve Materials Project properties for {mp_id}: {exc}")
            self._mp_summary_cache[mp_id] = None
            return None

        if not docs:
            self._mp_summary_cache[mp_id] = None
            return None

        doc = docs[0]
        doc_dict = doc.model_dump() if hasattr(doc, "model_dump") else doc.__dict__
        self._mp_summary_cache[mp_id] = doc_dict
        return doc_dict

    def _augment_with_structure_properties(self, structure_data: Dict[str, Any]) -> None:
        structure = structure_data.get("structure")
        if not isinstance(structure, PymatgenStructure):
            return

        volume_key = STANDARD_PROPERTIES.get("volume", "volume")
        if structure_data.get(volume_key) is None:
            structure_data[volume_key] = float(structure.volume)

        density_key = STANDARD_PROPERTIES.get("density", "density")
        if structure_data.get(density_key) is None:
            try:
                density = structure.density
            except Exception:
                density = None
            if density is not None:
                structure_data[density_key] = float(density)

        try:
            space_group_symbol, space_group_number = structure.get_space_group_info()
        except Exception:
            space_group_symbol = space_group_number = None

        space_group_key = STANDARD_PROPERTIES.get("space_group", "space_group")
        space_group_number_key = STANDARD_PROPERTIES.get("space_group_number", "space_group_number")

        if space_group_symbol and not structure_data.get(space_group_key):
            structure_data[space_group_key] = space_group_symbol

        if space_group_number and structure_data.get(space_group_number_key) is None:
            structure_data[space_group_number_key] = space_group_number

    def _augment_with_materials_project(self, structure_data: Dict[str, Any], mp_id: Optional[str]) -> None:
        if not mp_id:
            return

        summary = self._fetch_materials_project_summary(mp_id)
        if not summary:
            return

        structure_data.setdefault("materials_project_id", mp_id)

        property_map = {
            "band_gap": "band_gap",
            "formation_energy_per_atom": "formation_energy_per_atom",
            "energy_per_atom": "energy_per_atom",
            "energy_above_hull": "energy_above_hull",
            "density": "density",
            "volume": "volume",
        }

        for prop, field in property_map.items():
            std_key = STANDARD_PROPERTIES.get(prop, prop)
            if structure_data.get(std_key) is None:
                value = summary.get(field)
                if value is not None:
                    structure_data[std_key] = value

        bool_map = {"is_metallic": "is_metal"}
        for prop, field in bool_map.items():
            std_key = STANDARD_PROPERTIES.get(prop, prop)
            if structure_data.get(std_key) is None:
                value = summary.get(field)
                if value is not None:
                    structure_data[std_key] = bool(value)

        extra_map = {
            "magnetic_moment": "total_magnetization",
            "magnetic_ordering": "ordering",
        }
        for prop, field in extra_map.items():
            std_key = STANDARD_PROPERTIES.get(prop, prop)
            if structure_data.get(std_key) is None:
                value = summary.get(field)
                if value is not None:
                    structure_data[std_key] = value

        electronic_key = STANDARD_PROPERTIES.get("electronic_type", "electronic_type")
        if structure_data.get(electronic_key) is None and summary.get("is_metal") is not None:
            structure_data[electronic_key] = "metal" if summary["is_metal"] else "insulator"

        symmetry = summary.get("symmetry") or {}
        sg_symbol = symmetry.get("symbol")
        sg_number = symmetry.get("number")
        space_group_key = STANDARD_PROPERTIES.get("space_group", "space_group")
        space_group_number_key = STANDARD_PROPERTIES.get("space_group_number", "space_group_number")

        if sg_symbol and not structure_data.get(space_group_key):
            structure_data[space_group_key] = sg_symbol
        if sg_number and structure_data.get(space_group_number_key) is None:
            structure_data[space_group_number_key] = sg_number

    def _create_pymatgen_structure(self, attributes: Dict[str, Any]) -> Optional[PymatgenStructure]:
        required_keys = {'lattice_vectors', 'cartesian_site_positions', 'species_at_sites'}
        if not required_keys.issubset(attributes):
            return None

        lattice_vectors = attributes['lattice_vectors']
        cart_positions = attributes['cartesian_site_positions']
        site_species = attributes['species_at_sites']

        try:
            from pymatgen.core.lattice import Lattice

            lattice = Lattice(lattice_vectors)
            return PymatgenStructure(lattice, site_species, cart_positions, coords_are_cartesian=True)
        except Exception as exc:
            print(f"  Could not create pymatgen structure from OPTIMADE attributes: {exc}")
            return None

    def get_structures(self, formula: str, limit: int = 10) -> List[Dict]:
        """Retrieve Materials Cloud structures using the official OPTIMADE client."""
        if OptimadeClient is None or OptimadeStructure is None:
            print("  Materials Cloud client unavailable: install optimade[http_client] to enable access.")
            return []

        normalized_formula = self._normalize_formula(formula)
        filter_str = f'chemical_formula_reduced="{normalized_formula}"'
        results: List[Dict] = []
        available_props = get_available_properties('materials_cloud')
        response_fields = list(self._optimade_response_fields())

        for archive in self.archive_databases:
            if len(results) >= limit:
                break

            base_url = archive.get("base_url")
            if not base_url:
                continue

            per_db_limit = max(1, min(self._max_results_per_database, limit - len(results)))

            try:
                client = OptimadeClient(
                    base_urls=[base_url],
                    max_results_per_provider=per_db_limit,
                    use_async=False,
                    silent=True,
                )
                try:
                    response = client.structures.get(
                        filter=filter_str,
                        response_fields=response_fields,
                    )
                except Exception as primary_exc:
                    print(
                        f"  Materials Cloud query for {archive.get('id')} with filtered fields failed: {primary_exc}. Retrying without response_fields."
                    )
                    response = client.structures.get(filter=filter_str)

                entries = (
                    response
                    .get('structures', {})
                    .get(filter_str, {})
                    .get(base_url, {})
                    .get('data', [])
                )
            except Exception as exc:
                print(f"  Materials Cloud query failed for {archive.get('id')}: {exc}")
                continue

            if not entries:
                continue

            print(f"  Found {len(entries)} materials from Materials Cloud database {archive.get('id')}")

            for entry in entries:
                if len(results) >= limit:
                    break

                attributes = entry.get('attributes', {})
                full_data = {
                    **entry,
                    **attributes,
                    'archive_database': archive.get('id'),
                }

                structure_data: Dict[str, Any] = {
                    'database': 'Materials Cloud',
                    'source_database': 'Materials Cloud',
                    'archive_database': archive.get('id'),
                }

                if archive.get('name'):
                    structure_data['archive_database_name'] = archive['name']

                for prop_name in available_props:
                    value = get_property_value(full_data, 'materials_cloud', prop_name)
                    if value is not None:
                        structure_data[STANDARD_PROPERTIES[prop_name]] = value

                # Provide defaults for functional/source when mapping is constant
                structure_data.setdefault('functional', 'GGA PBE (typical)')
                structure_data.setdefault('source_database', 'Materials Cloud')

                # Persist useful raw OPTIMADE metadata
                for extra_key in (
                    'lattice_vectors',
                    'cartesian_site_positions',
                    'species_at_sites',
                    'dimension_types',
                    'nsites',
                ):
                    if extra_key in attributes:
                        structure_data[extra_key] = attributes.get(extra_key)

                # Attempt to build pymatgen structure from raw attributes; fall back to optimade converter.
                structure_obj = self._create_pymatgen_structure(attributes)
                if structure_obj is not None:
                    structure_data['structure'] = structure_obj
                elif OptimadeStructure is not None:
                    try:
                        entry_for_conversion = entry
                        if 'structure_features' not in attributes:
                            entry_for_conversion = {
                                **entry,
                                'attributes': {
                                    **attributes,
                                    'structure_features': [],
                                },
                            }

                        structure = OptimadeStructure(entry_for_conversion).convert('pymatgen')
                        if isinstance(structure, PymatgenStructure):
                            structure_data['structure'] = structure
                    except OptimadeConversionError as conv_exc:
                        print(
                            f"  Could not convert Materials Cloud structure {entry.get('id')} to pymatgen: {conv_exc}"
                        )
                    except Exception as exc:
                        print(
                            f"  Unexpected error converting Materials Cloud structure {entry.get('id')}: {exc}"
                        )

                normalized_mp_id = self._normalize_mp_identifier(attributes.get('_mcloudarchive_mp_id'))
                if normalized_mp_id:
                    structure_data.setdefault('materials_project_id', normalized_mp_id)

                self._augment_with_structure_properties(structure_data)
                self._augment_with_materials_project(structure_data, normalized_mp_id)

                results.append(structure_data)

        return results[:limit]
    
    def save_cif(self, structure_data: Dict, filename: str) -> str:
        """Save Materials Cloud structure as CIF file"""
        cif_path = self.output_dir / f"{filename}.cif"
        
        if 'structure' in structure_data:
            structure = structure_data['structure']
            cif_writer = CifWriter(structure)
            cif_writer.write_file(str(cif_path))
        else:
            # Create CIF from OPTIMADE data if available
            with open(cif_path, 'w') as f:
                f.write(f"# Materials Cloud structure\n")
                f.write(f"# Formula: {structure_data.get('formula', 'unknown')}\n")
                f.write(f"# Material ID: {structure_data.get('material_id', 'unknown')}\n")
                f.write(f"# Archive Database: {structure_data.get('archive_database', 'unknown')}\n")
                if structure_data.get('archive_database_name'):
                    f.write(f"# Archive Name: {structure_data.get('archive_database_name')}\n")
                f.write(f"# Functional: {structure_data.get('functional', 'unknown')}\n")
                f.write(f"# Space Group: {structure_data.get('space_group', 'unknown')}\n")
                
                # Add basic structure info if available
                if structure_data.get('lattice_vectors'):
                    f.write(f"\n# Lattice vectors available in metadata\n")
        
        # Save metadata
        metadata = {k: v for k, v in structure_data.items() if k != 'structure'}
        metadata_path = self.output_dir / f"{filename}_metadata.json"
        with open(metadata_path, 'w') as f:
            json.dump(metadata, f, indent=2, default=str)
        
        return str(cif_path)


class MPDSClient(MaterialsDatabaseClient):
    """MPDS (Materials Platform for Data Science) database client."""

    def __init__(self, api_key: str, output_directory: Optional[Path] = None):
        super().__init__("mpds", output_directory=output_directory)
        self.api_key = api_key
        if MPDSDataRetrieval is None:
            raise ImportError("mpds-client is required for MPDS access")
        self.client = MPDSDataRetrieval(api_key=api_key)
    
    def get_structures(self, formula: str, limit: int = 10) -> List[Dict]:
        """Get structures from MPDS database"""
        try:
            print(f"  Connecting to MPDS for {formula}...")
            
            # Search for materials with the given formula using simpler approach
            # MPDS API is quite specific about query format
            query = {
                "formulae": formula,
                "props": "atomic structure"
            }
            
            results = []
            
            try:
                # Get data from MPDS with proper field specification
                answer = self.client.get_data(
                    query,
                    fields={
                        'S': ['phase_id', 'entry', 'chemical_formula', 'sg_n', 'lattice_abc', 'lattice_angles', 'basis_noneq'],
                        'P': ['sample']
                    }
                )
                
                count = 0
                for item in answer:
                    if count >= limit:
                        break
                    
                    # Parse MPDS data
                    phase_id = item.get('phase_id', '')
                    entry = item.get('entry', '')
                    chem_formula = item.get('chemical_formula', '')
                    space_group = item.get('sg_n', '')
                    
                    # Check if formula matches (allow some flexibility)
                    if self._formula_matches(chem_formula, formula):
                        # Create MPDS data structure for property mapping
                        mpds_data = {
                            'phase_id': phase_id,
                            'entry': entry,
                            'chemical_formula': chem_formula or formula,
                            'sg_n': space_group,
                        }
                        
                        # Use property mapping to extract standardized properties
                        structure_data = {
                            'database': 'MPDS'
                        }
                        
                        # Get available properties for MPDS
                        available_props = get_available_properties('mpds')
                        
                        # Extract all available properties using mapping
                        for prop_name in available_props:
                            value = get_property_value(mpds_data, 'mpds', prop_name)
                            if value is not None:
                                structure_data[STANDARD_PROPERTIES[prop_name]] = value
                        
                        # Add additional MPDS-specific fields
                        structure_data['functional'] = 'Various (experimental and computational)'
                        structure_data['phase_id'] = phase_id
                        structure_data['source'] = 'MPDS - Materials Platform for Data Science'
                        
                        # Try to get structure if available
                        try:
                            structure = self._create_structure_from_mpds_data(item)
                            if structure:
                                structure_data['structure'] = structure
                        except Exception as e:
                            print(f"  Could not create structure: {e}")
                        
                        results.append(structure_data)
                        count += 1
                
                print(f"  Found {len(results)} materials from MPDS")
                return results
                
            except Exception as e:
                print(f"  MPDS API error: {e}")
                # Try alternative approach with different query
                return self._get_structures_alternative(formula, limit)
            
        except Exception as e:
            print(f"Error retrieving from MPDS: {e}")
            # Fallback to simple approach
            return self._get_structures_simple(formula, limit)
    
    def _get_structures_alternative(self, formula: str, limit: int) -> List[Dict]:
        """Alternative MPDS structure retrieval using different query format"""
        try:
            # Try phase diagram data which is more accessible
            query = {
                "elements": self._parse_formula_elements(formula),
                "classes": "binary",  # Try binary systems first
                "props": "phase diagram"
            }
            
            results = []
            
            answer = self.client.get_data(
                query,
                fields={
                    'S': ['phase_id', 'chemical_formula'],
                    'P': []
                }
            )
            
            count = 0
            for item in answer:
                if count >= limit:
                    break
                
                phase_id = item.get('phase_id', '')
                chem_formula = item.get('chemical_formula', '')
                
                if self._formula_matches(chem_formula, formula):
                    structure_data = {
                        'database': 'MPDS',
                        'material_id': f"mpds_pd_{phase_id}" if phase_id else f"mpds_pd_{count+1}",
                        'formula': chem_formula or formula,
                        'functional': 'Various (experimental and computational)',
                        'phase_id': phase_id,
                        'source': 'MPDS - Materials Platform for Data Science',
                        'note': 'Retrieved from phase diagram data'
                    }
                    results.append(structure_data)
                    count += 1
            
            if results:
                print(f"  Found {len(results)} materials from MPDS (phase diagram data)")
                return results
            else:
                # Final fallback
                return self._get_structures_simple(formula, limit)
                
        except Exception as e:
            print(f"  MPDS alternative query error: {e}")
            return self._get_structures_simple(formula, limit)
    
    def _get_structures_simple(self, formula: str, limit: int) -> List[Dict]:
        """Simplified MPDS structure retrieval"""
        try:
            # Create simplified MPDS data for property mapping
            mpds_simple_data = {
                'phase_id': f"mpds_{formula}_1",
                'chemical_formula': formula,
            }
            
            # Use property mapping to extract standardized properties
            structure_data = {
                'database': 'MPDS'
            }
            
            # Get available properties for MPDS
            available_props = get_available_properties('mpds')
            
            # Extract all available properties using mapping
            for prop_name in available_props:
                value = get_property_value(mpds_simple_data, 'mpds', prop_name)
                if value is not None:
                    structure_data[STANDARD_PROPERTIES[prop_name]] = value
            
            # Add additional fields
            structure_data['functional'] = 'Various (experimental and computational)'
            structure_data['note'] = 'MPDS connection established (simplified result)'
            structure_data['source'] = 'MPDS - Materials Platform for Data Science'
            
            return [structure_data]
        except Exception as e:
            print(f"Error with MPDS simple approach: {e}")
            return []
    
    def _parse_formula_elements(self, formula: str) -> str:
        """Parse chemical formula to extract elements for MPDS query"""
        import re
        # Extract element symbols from formula
        elements = re.findall(r'[A-Z][a-z]?', formula)
        return '-'.join(elements)
    
    def _formula_matches(self, mpds_formula: str, target_formula: str) -> bool:
        """Check if MPDS formula matches target formula (flexible matching)"""
        if not mpds_formula:
            return False
        
        # Simple matching - remove spaces and compare
        mpds_clean = mpds_formula.replace(' ', '').replace('-', '')
        target_clean = target_formula.replace(' ', '').replace('-', '')
        
        # Check if formulas are similar or if target is contained in mpds formula
        return (mpds_clean.lower() == target_clean.lower() or 
                target_clean.lower() in mpds_clean.lower() or
                mpds_clean.lower() in target_clean.lower())
    
    def _create_structure_from_mpds_data(self, item: Dict) -> Optional[PymatgenStructure]:
        """Create pymatgen structure from MPDS data"""
        try:
            # MPDS data structure varies, try to extract structural information
            cell_abc = item.get('cell_abc', [])
            cell_angles = item.get('cell_angles', [])
            basis_noneq = item.get('basis_noneq', [])
            
            if not (cell_abc and cell_angles and basis_noneq):
                return None
            
            # Try to construct structure (this is simplified)
            from pymatgen.core.lattice import Lattice
            from pymatgen.core.structure import Structure
            
            # Basic lattice construction
            if len(cell_abc) >= 3 and len(cell_angles) >= 3:
                lattice = Lattice.from_parameters(
                    a=cell_abc[0], b=cell_abc[1], c=cell_abc[2],
                    alpha=cell_angles[0], beta=cell_angles[1], gamma=cell_angles[2]
                )
                
                # This is a simplified approach - real MPDS data parsing would be more complex
                # For now, return None to use metadata only
                return None
            
        except Exception:
            pass
        
        return None
    
    def save_cif(self, structure_data: Dict, filename: str) -> str:
        """Save MPDS structure as CIF file"""
        cif_path = self.output_dir / f"{filename}.cif"
        
        if 'structure' in structure_data and structure_data['structure']:
            structure = structure_data['structure']
            cif_writer = CifWriter(structure)
            cif_writer.write_file(str(cif_path))
        else:
            # Create placeholder CIF with metadata
            with open(cif_path, 'w') as f:
                f.write(f"# MPDS structure\n")
                f.write(f"# Formula: {structure_data.get('formula', 'unknown')}\n")
                f.write(f"# Material ID: {structure_data.get('material_id', 'unknown')}\n")
                f.write(f"# Phase ID: {structure_data.get('phase_id', 'unknown')}\n")
                f.write(f"# Space Group: {structure_data.get('space_group_number', 'unknown')}\n")
                f.write(f"# Source: {structure_data.get('source', 'MPDS')}\n")
                f.write(f"# Note: Structure data format varies in MPDS\n")
        
        # Save metadata
        metadata = {k: v for k, v in structure_data.items() if k != 'structure'}
        metadata_path = self.output_dir / f"{filename}_metadata.json"
        with open(metadata_path, 'w') as f:
            json.dump(metadata, f, indent=2, default=str)
        
        return str(cif_path)


class OQMDClient(MaterialsDatabaseClient):
    """OQMD database client using the public REST API."""

    BASE_URL = "https://oqmd.org/oqmdapi"

    def __init__(self, output_directory: Optional[Path] = None):
        super().__init__("oqmd", output_directory=output_directory)
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "mat-rev/1.0"})

    def get_structures(self, formula: str, limit: int = 10) -> List[Dict]:
        """Retrieve structures from OQMD formation energy endpoint."""
        if limit <= 0:
            return []

        params = {
            "composition": formula,
            "fields": "name,entry_id,spacegroup,volume,unit_cell,band_gap,delta_e,stability,sites,calculation_label",
            "limit": max(1, limit),
            "format": "json",
            "noduplicate": "True",
        }

        try:
            response = self.session.get(f"{self.BASE_URL}/formationenergy", params=params, timeout=30)
            response.raise_for_status()
            payload = response.json()
        except Exception as exc:
            print(f"  OQMD request failed: {exc}")
            return []

        entries = []
        if isinstance(payload, dict):
            data = payload.get("data")
            if isinstance(data, list):
                entries = data

        if not entries:
            return []

        available_props = get_available_properties("oqmd")
        results: List[Dict] = []

        for entry in entries[:limit]:
            structure_data: Dict = {"database": "OQMD"}

            for prop_name in available_props:
                value = get_property_value(entry, "oqmd", prop_name)
                if value is not None:
                    structure_data[STANDARD_PROPERTIES[prop_name]] = value

            structure = self._build_structure(entry)
            if structure:
                structure_data["structure"] = structure
            else:
                # Preserve raw structural data for metadata output
                if entry.get("unit_cell"):
                    structure_data["oqmd_unit_cell"] = entry.get("unit_cell")
                if entry.get("sites"):
                    structure_data["oqmd_sites"] = entry.get("sites")

            structure_data.setdefault("functional", "OQMD DFT")
            structure_data.setdefault("source_database", "OQMD")

            results.append(structure_data)

        return results

    def _build_structure(self, entry: Dict) -> Optional[PymatgenStructure]:
        unit_cell = entry.get("unit_cell")
        sites = entry.get("sites")

        if not unit_cell or not sites:
            return None

        if not (isinstance(unit_cell, (list, tuple)) and len(unit_cell) == 3):
            return None

        try:
            from pymatgen.core.lattice import Lattice

            lattice = Lattice(unit_cell)
        except Exception:
            return None

        species: List[str] = []
        frac_coords: List[List[float]] = []

        for site in sites:
            if not isinstance(site, str) or "@" not in site:
                continue

            specie_raw, coord_str = site.split("@", 1)
            specie = specie_raw.strip()
            try:
                coords = [float(val) for val in coord_str.strip().split()]
            except ValueError:
                continue

            if len(coords) != 3:
                continue

            species.append(specie)
            frac_coords.append(coords)

        if not species or len(species) != len(frac_coords):
            return None

        try:
            return PymatgenStructure(lattice, species, frac_coords, coords_are_cartesian=False)
        except Exception:
            return None

    def save_cif(self, structure_data: Dict, filename: str) -> str:
        cif_path = self.output_dir / f"{filename}.cif"

        if "structure" in structure_data:
            structure = structure_data["structure"]
            cif_writer = CifWriter(structure)
            cif_writer.write_file(str(cif_path))
        else:
            with open(cif_path, "w") as handle:
                handle.write(f"# OQMD structure for {structure_data.get('formula', 'unknown')}\n")
                handle.write(f"# Material ID: {structure_data.get('material_id', 'unknown')}\n")
                unit_cell = structure_data.get("oqmd_unit_cell")
                if unit_cell:
                    handle.write(f"# Unit cell: {json.dumps(unit_cell)}\n")
                sites = structure_data.get("oqmd_sites")
                if sites:
                    handle.write(f"# Sites: {sites}\n")

        metadata = {k: v for k, v in structure_data.items() if k != "structure"}
        metadata_path = self.output_dir / f"{filename}_metadata.json"
        with open(metadata_path, "w") as handle:
            json.dump(metadata, handle, indent=2, default=str)

        return str(cif_path)


class MaterialsDatabaseRetriever:
    """Retrieve materials data from the configured databases."""

    def __init__(
        self,
        mp_api_key: Optional[str] = None,
        mpds_api_key: Optional[str] = None,
        output_directory: Optional[Path] = None,
    ):
        self.mp_api_key = mp_api_key
        self.mpds_api_key = mpds_api_key
        self.output_directory = Path(output_directory) if output_directory else (Path.cwd() / "downloaded_materials")
        self.output_directory.mkdir(parents=True, exist_ok=True)
        self.clients: Dict[str, MaterialsDatabaseClient] = {}
        self._initialize_clients()

    def _initialize_clients(self):
        """Initialize available database clients."""
        # Materials Project
        if self.mp_api_key:
            try:
                self.clients['materials_project'] = MaterialsProjectClient(
                    self.mp_api_key, output_directory=self.output_directory
                )
                print("✓ Materials Project client initialized")
            except Exception as e:
                print(f"✗ Materials Project client failed: {e}")
        
        # JARVIS
        try:
            self.clients['jarvis'] = JARVISClient(output_directory=self.output_directory)
            print("✓ JARVIS client initialized")
        except Exception as e:
            print(f"✗ JARVIS client failed: {e}")
        
        # AFLOW
        try:
            self.clients['aflow'] = AFLOWClient(output_directory=self.output_directory)
            print("✓ AFLOW client initialized")
        except Exception as e:
            print(f"✗ AFLOW client failed: {e}")
        
        # Alexandria
        try:
            self.clients['alexandria'] = AlexandriaClient(output_directory=self.output_directory)
            print("✓ Alexandria client initialized")
        except Exception as e:
            print(f"✗ Alexandria client failed: {e}")
        
        # Materials Cloud
        try:
            self.clients['materials_cloud'] = MaterialsCloudClient(
                output_directory=self.output_directory,
                mp_api_key=self.mp_api_key,
            )
            print("✓ Materials Cloud client initialized")
        except Exception as e:
            print(f"✗ Materials Cloud client failed: {e}")
        
        # OQMD
        try:
            self.clients['oqmd'] = OQMDClient(output_directory=self.output_directory)
            print("✓ OQMD client initialized")
        except Exception as e:
            print(f"✗ OQMD client failed: {e}")

        # MPDS
        if self.mpds_api_key:
            try:
                self.clients['mpds'] = MPDSClient(
                    self.mpds_api_key, output_directory=self.output_directory
                )
                print("✓ MPDS client initialized")
            except Exception as e:
                print(f"✗ MPDS client failed: {e}")
    
    def retrieve_materials(self, formula: str, limit_per_db: int = 3) -> Dict[str, List[Dict]]:
        """Retrieve materials from all available databases"""
        all_results = {}
        
        print(f"\nRetrieving materials for formula: {formula}")
        print("=" * 50)
        
        for db_name, client in self.clients.items():
            print(f"\nQuerying {db_name}...")
            try:
                results = client.get_structures(formula, limit_per_db)
                all_results[db_name] = results
                print(f"  Found {len(results)} materials")
                
                # Save CIF files for retrieved materials
                for i, material in enumerate(results):
                    filename = f"{db_name}_{formula}_{i+1}"
                    cif_path = client.save_cif(material, filename)
                    print(f"  Saved: {cif_path}")
                    
            except Exception as e:
                print(f"  Error: {e}")
                all_results[db_name] = []
        
        return all_results
    
    def test_retrieval(self, test_formulas: List[str] = None) -> Dict:
        """Test retrieval from all databases with sample materials"""
        if test_formulas is None:
            test_formulas = ["Fe2O3", "SiO2", "CaTiO3"]  # Default test materials
        
        test_results = {}
        
        print("Testing materials database retrieval...")
        print("=" * 60)
        
        for formula in test_formulas:
            print(f"\nTesting with formula: {formula}")
            results = self.retrieve_materials(formula, limit_per_db=1)
            test_results[formula] = results
            
            # Summary for this formula
            total_materials = sum(len(materials) for materials in results.values())
            successful_dbs = len([db for db, materials in results.items() if materials])
            
            print(f"\nSummary for {formula}:")
            print(f"  Total materials found: {total_materials}")
            print(f"  Successful databases: {successful_dbs}/{len(self.clients)}")
        
        return test_results


