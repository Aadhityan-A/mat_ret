from pathlib import Path

import numpy as np
import pytest
from pymatgen.core import Lattice, Structure
from pymatgen.io.cif import CifWriter

from mat_ret.xrd import (
    XRDConfig,
    export_xrd_pattern_csv,
    export_xrd_peaks_csv,
    generate_xrd_from_cif,
    generate_xrd_from_structure,
    list_supported_radiations,
)


@pytest.fixture()
def nacl_structure() -> Structure:
    """Simple NaCl rock-salt test structure."""
    return Structure(
        lattice=Lattice.cubic(5.64),
        species=["Na", "Cl"],
        coords=[[0.0, 0.0, 0.0], [0.5, 0.5, 0.5]],
    )


def test_supported_radiations_contains_cuka() -> None:
    radiations = list_supported_radiations()
    assert "CuKa" in radiations
    assert "CuKa1" in radiations


def test_generate_xrd_from_structure_returns_non_empty_pattern(nacl_structure: Structure) -> None:
    result = generate_xrd_from_structure(nacl_structure, config=XRDConfig())
    assert result.two_theta_stick.size > 0
    assert result.intensity_stick.size == result.two_theta_stick.size
    assert result.two_theta_profile.size > 0
    assert result.intensity_profile.size == result.two_theta_profile.size
    assert np.all(result.intensity_profile >= 0.0)
    assert np.max(result.intensity_profile) <= 100.0 + 1e-6
    assert len(result.peaks) > 0


def test_cif_and_structure_paths_match_stick_positions(
    nacl_structure: Structure,
    tmp_path: Path,
) -> None:
    cif_path = tmp_path / "nacl.cif"
    CifWriter(nacl_structure).write_file(str(cif_path))

    cfg = XRDConfig(profile="stick", peak_finder_enabled=False)
    from_structure = generate_xrd_from_structure(nacl_structure, config=cfg)
    from_cif = generate_xrd_from_cif(cif_path, config=cfg)

    assert from_structure.two_theta_stick.size == from_cif.two_theta_stick.size
    np.testing.assert_allclose(from_structure.two_theta_stick, from_cif.two_theta_stick, atol=1e-8)
    np.testing.assert_allclose(from_structure.intensity_stick, from_cif.intensity_stick, atol=1e-8)


def test_custom_wavelength_shifts_peak_positions(nacl_structure: Structure) -> None:
    cu_result = generate_xrd_from_structure(
        nacl_structure,
        config=XRDConfig(profile="stick", peak_finder_enabled=False, radiation="CuKa"),
    )
    short_lambda_result = generate_xrd_from_structure(
        nacl_structure,
        config=XRDConfig(
            profile="stick",
            peak_finder_enabled=False,
            radiation="CuKa",
            custom_wavelength=0.80000,
        ),
    )
    assert short_lambda_result.two_theta_stick[0] < cu_result.two_theta_stick[0]


@pytest.mark.parametrize("profile", ["stick", "gaussian", "lorentzian", "pseudo_voigt"])
def test_profile_models_produce_non_negative_patterns(
    nacl_structure: Structure,
    profile: str,
) -> None:
    cfg = XRDConfig(profile=profile, peak_finder_enabled=False)
    result = generate_xrd_from_structure(nacl_structure, config=cfg)
    assert np.all(result.intensity_profile >= 0.0)
    assert result.intensity_profile.size == result.two_theta_profile.size
    assert np.max(result.intensity_profile) <= 100.0 + 1e-6


def test_invalid_config_raises_clear_errors(nacl_structure: Structure) -> None:
    with pytest.raises(ValueError, match="two_theta_max"):
        generate_xrd_from_structure(
            nacl_structure,
            config=XRDConfig(two_theta_min=80.0, two_theta_max=20.0),
        )

    with pytest.raises(ValueError, match="two_theta_step"):
        generate_xrd_from_structure(
            nacl_structure,
            config=XRDConfig(two_theta_step=0.0),
        )

    with pytest.raises(ValueError, match="custom_wavelength"):
        generate_xrd_from_structure(
            nacl_structure,
            config=XRDConfig(custom_wavelength=-1.0),
        )

    with pytest.raises(ValueError, match="Unsupported radiation"):
        generate_xrd_from_structure(
            nacl_structure,
            config=XRDConfig(radiation="NotARealLine"),  # type: ignore[arg-type]
        )


def test_peak_finder_controls_peak_count(nacl_structure: Structure) -> None:
    default_result = generate_xrd_from_structure(
        nacl_structure,
        config=XRDConfig(profile="pseudo_voigt", peak_finder_enabled=True),
    )
    high_threshold_result = generate_xrd_from_structure(
        nacl_structure,
        config=XRDConfig(
            profile="pseudo_voigt",
            peak_finder_enabled=True,
            peak_min_height=101.0,
            peak_prominence=0.0,
        ),
    )
    disabled_result = generate_xrd_from_structure(
        nacl_structure,
        config=XRDConfig(profile="pseudo_voigt", peak_finder_enabled=False),
    )

    assert len(default_result.peaks) > 0
    assert len(high_threshold_result.peaks) == 0
    assert len(disabled_result.peaks) == 0


def test_csv_export_helpers_write_expected_headers(
    nacl_structure: Structure,
    tmp_path: Path,
) -> None:
    result = generate_xrd_from_structure(nacl_structure, config=XRDConfig())
    pattern_csv = tmp_path / "pattern.csv"
    peaks_csv = tmp_path / "peaks.csv"

    export_xrd_pattern_csv(result, pattern_csv)
    export_xrd_peaks_csv(result, peaks_csv)

    assert pattern_csv.exists()
    assert peaks_csv.exists()

    pattern_header = pattern_csv.read_text(encoding="utf-8").splitlines()[0]
    peaks_header = peaks_csv.read_text(encoding="utf-8").splitlines()[0]

    assert pattern_header == "two_theta_deg,profile_intensity,stick_intensity"
    assert peaks_header == "two_theta_deg,intensity,d_spacing_angstrom,hkls,matched_stick_two_theta_deg"
