"""
Property Mapping Configuration for Materials Databases

This module contains standardized property names and their database-specific field mappings.
Users can modify the STANDARD_PROPERTIES to change naming conventions across all databases.

The mapping system follows this structure:
- STANDARD_PROPERTIES: Defines the common property names we want to use
- DATABASE_PROPERTY_MAPPINGS: Maps each database's specific field names to our standard names
- get_property_value(): Helper function to extract property values using these mappings
"""

from typing import Dict, Any, Optional, List
import json

# =============================================================================
# STANDARD PROPERTY DEFINITIONS
# =============================================================================
# These are the standardized property names used throughout the application.
# Users can modify these names to change the naming convention across all databases.

STANDARD_PROPERTIES = {
    # Structural Properties
    'material_id': 'material_id',
    'formula': 'formula', 
    'space_group': 'space_group',
    'space_group_number': 'space_group_number',
    'density': 'density',
    'volume': 'volume',
    'lattice_parameters': 'lattice_parameters',
    'crystal_system': 'crystal_system',
    
    # Electronic Properties
    'band_gap': 'band_gap',
    'band_gap_direct': 'band_gap_direct',
    'band_gap_indirect': 'band_gap_indirect',
    'is_metallic': 'is_metallic',
    'electronic_type': 'electronic_type',
    
    # Energetic Properties
    'formation_energy': 'formation_energy',
    'formation_energy_per_atom': 'formation_energy_per_atom',
    'energy_per_atom': 'energy_per_atom',
    'total_energy': 'total_energy',
    'energy_above_hull': 'energy_above_hull',
    
    # Mechanical Properties
    'bulk_modulus': 'bulk_modulus',
    'shear_modulus': 'shear_modulus',
    'elastic_modulus': 'elastic_modulus',
    'poisson_ratio': 'poisson_ratio',
    'elastic_tensor': 'elastic_tensor',
    'hardness': 'hardness',
    
    # Thermal Properties
    'thermal_expansion': 'thermal_expansion',
    'thermal_conductivity': 'thermal_conductivity',
    'heat_capacity': 'heat_capacity',
    'debye_temperature': 'debye_temperature',
    
    # Magnetic Properties
    'magnetic_moment': 'magnetic_moment',
    'magnetic_ordering': 'magnetic_ordering',
    'is_magnetic': 'is_magnetic',
    
    # Optical Properties
    'refractive_index': 'refractive_index',
    'dielectric_constant': 'dielectric_constant',
    'optical_absorption': 'optical_absorption',
    
    # Computational Metadata
    'functional': 'functional',
    'calculation_method': 'calculation_method',
    'calculation_date': 'calculation_date',
    'source_database': 'source_database',
    'last_modified': 'last_modified',
    'entry_id': 'entry_id'
}

# =============================================================================
# DATABASE-SPECIFIC PROPERTY MAPPINGS
# =============================================================================
# These mappings translate database-specific field names to our standard property names.
# Add new mappings here when new properties are discovered from database documentation.

DATABASE_PROPERTY_MAPPINGS = {
    'materials_project': {
        # Standard MP API fields (as of 2025)
        'material_id': 'material_id',
        'formula': 'formula_pretty',
        'space_group': 'symmetry.symbol',
        'space_group_number': 'symmetry.number',
        'density': 'density',
        'volume': 'volume',
        'crystal_system': 'symmetry.crystal_system',
        'band_gap': 'band_gap',
        'formation_energy_per_atom': 'formation_energy_per_atom',
        'energy_per_atom': 'energy_per_atom',
        'energy_above_hull': 'energy_above_hull',
        'is_metallic': 'is_metal',
        'bulk_modulus': 'elasticity.K_VRH',
        'shear_modulus': 'elasticity.G_VRH',
        'elastic_tensor': 'elasticity.elastic_tensor',
        'poisson_ratio': 'elasticity.poisson',
        'magnetic_moment': 'total_magnetization',
        'magnetic_ordering': 'ordering',
        'dielectric_constant': 'dielec.total',
        'functional': 'theoretical',  # MP uses GGA-PBE
        'source_database': 'Materials Project'
    },
    
    'jarvis': {
        # JARVIS-DFT database fields
        'material_id': 'jid',
        'formula': 'formula',
        'space_group': 'spg_symbol',
        'space_group_number': 'spg_number',
        'density': 'density',
        'volume': 'volume',
        'formation_energy_per_atom': 'formation_energy_peratom',
        'energy_per_atom': 'energy_per_atom',
        'band_gap': 'optb88vdw_bandgap',
        'band_gap_direct': 'optb88vdw_bandgap_direct',
        'band_gap_indirect': 'optb88vdw_bandgap_indirect',
        'bulk_modulus': 'bulk_modulus_kv',
        'shear_modulus': 'shear_modulus_gv',
        'elastic_tensor': 'elastic_tensor',
        'magnetic_moment': 'magmom_oszicar',
        'thermal_expansion': 'avg_thermal_expansion',
        'refractive_index': 'refractive_index',
        'dielectric_constant': 'epsilon_x',
        'functional': 'OptB88vdW/TBmBJ',
        'source_database': 'JARVIS'
    },
    
    'aflow': {
        # AFLOW database fields (based on documentation)
        'material_id': 'auid',  # AFLOW Unique Identifier
        'formula': 'compound',
        'space_group': 'spacegroup_orig',
        'space_group_number': 'sg',
        'density': 'density',
        'volume': 'volume_cell',
        'formation_energy_per_atom': 'enthalpy_formation_atom',
        'energy_per_atom': 'enthalpy_atom',
        'band_gap': 'Egap',
        'band_gap_direct': 'Egap_fit',
        'bulk_modulus': 'bulk_modulus_voigt',
        'shear_modulus': 'shear_modulus_voigt',
        'elastic_tensor': 'elastic_constants',
        'poisson_ratio': 'poisson_ratio_voigt',
        'hardness': 'hardness_chen',
        'thermal_expansion': 'thermal_expansion',
        'functional': 'GGA-PBE',
        'source_database': 'AFLOW'
    },
    
    'alexandria': {
        # Alexandria database fields (OPTIMADE interface with _alexandria_ prefix)
        'material_id': 'id',  # Standard OPTIMADE field
        'formula': 'chemical_formula_reduced',  # Standard OPTIMADE field
        'lattice_parameters': 'lattice_vectors',  # Standard OPTIMADE field
        'formation_energy_per_atom': '_alexandria_formation_energy_per_atom',  # Alexandria-specific field
        'band_gap': '_alexandria_band_gap',  # Alexandria-specific field
        'band_gap_direct': '_alexandria_band_gap_direct',  # Alexandria-specific field
        'total_energy': '_alexandria_energy',  # Alexandria-specific field
        'energy_per_atom': '_alexandria_energy_corrected',  # Alexandria-specific field
        'functional': '_alexandria_xc_functional',  # Alexandria-specific field
        'source_database': 'Alexandria',  # Hardcoded value
        'last_modified': 'last_modified'  # Standard OPTIMADE field
    },
    
    'materials_cloud': {
        # Materials Cloud (OPTIMADE interface)
        'material_id': 'id',
        'formula': 'chemical_formula_reduced',
        'space_group': 'space_group_symbol_hermann_mauguin',
        'space_group_number': 'space_group_it_number',
        'lattice_parameters': 'lattice_vectors',
        'last_modified': 'last_modified'
    },
    
    'mpds': {
        # MPDS database fields
        'material_id': 'phase_id',
        'formula': 'chemical_formula',
        'space_group': 'sg_symbol',
        'space_group_number': 'sg_n',
        'density': 'density',
        'lattice_parameters': 'cell_abc',
        'formation_energy': 'formation_energy',
        'band_gap': 'band_gap',
        'bulk_modulus': 'bulk_modulus',
        'thermal_expansion': 'thermal_expansion',
        'thermal_conductivity': 'thermal_conductivity',
        'magnetic_moment': 'magnetic_moment',
        'hardness': 'hardness',
        'functional': 'Various',
        'source_database': 'MPDS',
        'entry_id': 'entry'
    },

    'oqmd': {
        # OQMD RESTful API fields
        'material_id': 'entry_id',
        'entry_id': 'entry_id',
        'formula': 'name',
        'space_group': 'spacegroup',
        'volume': 'volume',
        'lattice_parameters': 'unit_cell',
        'formation_energy_per_atom': 'delta_e',
        'energy_above_hull': 'stability',
        'band_gap': 'band_gap',
        'functional': 'calculation_label',
        'source_database': 'OQMD'
    }
}

# =============================================================================
# PROPERTY UNITS MAPPING
# =============================================================================
# Standardized units for each property type

PROPERTY_UNITS = {
    'density': 'g/cm³',
    'volume': 'Ų',
    'band_gap': 'eV',
    'band_gap_direct': 'eV',
    'band_gap_indirect': 'eV',
    'formation_energy': 'eV',
    'formation_energy_per_atom': 'eV/atom',
    'energy_per_atom': 'eV/atom',
    'total_energy': 'eV',
    'energy_above_hull': 'eV/atom',
    'bulk_modulus': 'GPa',
    'shear_modulus': 'GPa',
    'elastic_modulus': 'GPa',
    'poisson_ratio': 'dimensionless',
    'elastic_tensor': 'GPa',
    'thermal_expansion': '10⁻⁶/K',
    'thermal_conductivity': 'W/m·K',
    'heat_capacity': 'J/mol·K',
    'debye_temperature': 'K',
    'magnetic_moment': 'μ_B',
    'hardness': 'GPa',
    'refractive_index': 'dimensionless',
    'dielectric_constant': 'dimensionless',
    'optical_absorption': 'cm⁻¹',
    'space_group_number': 'dimensionless',
    'lattice_parameters': 'Å',
    'crystal_system': 'categorical',
    'is_metallic': 'boolean',
    'electronic_type': 'categorical',
    'magnetic_ordering': 'categorical',
    'is_magnetic': 'boolean',
    'calculation_method': 'text',
    'calculation_date': 'date',
    'last_modified': 'date',
    'entry_id': 'text'
}

# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def get_property_value(data: Dict[str, Any], database: str, property_name: str) -> Any:
    """
    Extract a property value from database-specific data using standardized property names.
    
    Args:
        data: Dictionary containing the raw data from the database
        database: Name of the source database
        property_name: Standardized property name (from STANDARD_PROPERTIES)
        
    Returns:
        The property value if found, None otherwise
    """
    if database not in DATABASE_PROPERTY_MAPPINGS:
        return None
        
    if property_name not in STANDARD_PROPERTIES:
        return None
        
    db_mappings = DATABASE_PROPERTY_MAPPINGS[database]
    if property_name not in db_mappings:
        return None
        
    field_path = db_mappings[property_name]
    
    # Handle nested field paths (e.g., 'results.material.density')
    if '.' in field_path:
        value = data
        for key in field_path.split('.'):
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                return None
        return value
    else:
        # Handle simple field names
        return data.get(field_path, None)

def get_available_properties(database: str) -> List[str]:
    """
    Get list of available standardized properties for a specific database.
    
    Args:
        database: Name of the database
        
    Returns:
        List of available standardized property names
    """
    if database not in DATABASE_PROPERTY_MAPPINGS:
        return []
    
    return list(DATABASE_PROPERTY_MAPPINGS[database].keys())

def get_all_databases() -> List[str]:
    """Get list of all supported databases."""
    return list(DATABASE_PROPERTY_MAPPINGS.keys())

def get_property_info(property_name: str) -> Dict[str, Any]:
    """
    Get comprehensive information about a standardized property.
    
    Args:
        property_name: Standardized property name
        
    Returns:
        Dictionary with property information including units and availability
    """
    if property_name not in STANDARD_PROPERTIES:
        return {}
    
    info = {
        'standard_name': STANDARD_PROPERTIES[property_name],
        'unit': PROPERTY_UNITS.get(property_name, 'dimensionless'),
        'available_in_databases': []
    }
    
    for db_name, mappings in DATABASE_PROPERTY_MAPPINGS.items():
        if property_name in mappings:
            info['available_in_databases'].append(db_name)
    
    return info

def standardize_properties(data: Dict[str, Any], database: str) -> Dict[str, Any]:
    """
    Convert database-specific property names to standardized names.
    
    Args:
        data: Raw data from database
        database: Source database name
        
    Returns:
        Dictionary with standardized property names
    """
    standardized = {}
    
    for std_name in STANDARD_PROPERTIES:
        value = get_property_value(data, database, std_name)
        if value is not None:
            standardized[STANDARD_PROPERTIES[std_name]] = value
    
    return standardized

def export_property_mappings(filepath: str = 'property_mappings.json'):
    """
    Export the complete property mapping configuration to a JSON file.
    
    Args:
        filepath: Path to save the JSON file
    """
    export_data = {
        'standard_properties': STANDARD_PROPERTIES,
        'database_mappings': DATABASE_PROPERTY_MAPPINGS,
        'property_units': PROPERTY_UNITS,
        'metadata': {
            'description': 'Materials database property mapping configuration',
            'supported_databases': get_all_databases(),
            'total_properties': len(STANDARD_PROPERTIES)
        }
    }
    
    with open(filepath, 'w') as f:
        json.dump(export_data, f, indent=2)
    
    print(f"Property mappings exported to {filepath}")

# =============================================================================
# TESTING AND VALIDATION FUNCTIONS
# =============================================================================

def validate_property_mappings():
    """
    Validate that all property mappings are consistent and complete.
    """
    issues = []
    
    # Check for orphaned mappings (database fields not in standard properties)
    for db_name, mappings in DATABASE_PROPERTY_MAPPINGS.items():
        for property_name in mappings:
            if property_name not in STANDARD_PROPERTIES:
                issues.append(f"Database '{db_name}' has mapping for undefined property '{property_name}'")
    
    # Check for missing units
    for prop_name in STANDARD_PROPERTIES:
        if prop_name not in PROPERTY_UNITS and prop_name not in ['material_id', 'formula', 'space_group', 'functional', 'source_database']:
            issues.append(f"Property '{prop_name}' missing unit definition")
    
    if issues:
        print("Property mapping validation issues found:")
        for issue in issues:
            print(f"  - {issue}")
    else:
        print("✓ Property mappings validation passed")
    
    return len(issues) == 0

if __name__ == "__main__":
    # Run validation and export mappings when script is executed directly
    print("Materials Database Property Mapping Configuration")
    print("=" * 50)
    
    print(f"Supported databases: {', '.join(get_all_databases())}")
    print(f"Standard properties defined: {len(STANDARD_PROPERTIES)}")
    
    # Validate mappings
    validate_property_mappings()
    
    # Export mappings
    export_property_mappings()
    
    # Show sample property info
    print("\nSample property information:")
    for prop in ['band_gap', 'formation_energy_per_atom', 'bulk_modulus']:
        info = get_property_info(prop)
        print(f"  {prop}: {info}")
