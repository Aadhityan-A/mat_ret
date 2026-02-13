"""X-ray diffraction utilities for mat_ret."""

from __future__ import annotations

import csv
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional, Sequence, Union

import numpy as np
from pymatgen.analysis.diffraction.xrd import WAVELENGTHS, XRDCalculator
from pymatgen.core.structure import Structure
from pymatgen.io.cif import CifParser
from scipy.signal import find_peaks

ProfileModel = Literal["stick", "gaussian", "lorentzian", "pseudo_voigt"]
PathLike = Union[str, Path]


@dataclass
class XRDConfig:
    """Configuration for XRD generation and analysis."""

    radiation: str = "CuKa"
    custom_wavelength: Optional[float] = None
    two_theta_min: float = 5.0
    two_theta_max: float = 90.0
    two_theta_step: float = 0.02
    profile: ProfileModel = "pseudo_voigt"
    fwhm: float = 0.15
    eta: float = 0.5
    peak_finder_enabled: bool = True
    peak_min_height: float = 5.0
    peak_prominence: float = 2.0
    peak_distance: float = 0.10
    peak_width: float = 0.0
    peak_match_tolerance: float = 0.25
    symprec: float = 0.0


@dataclass
class XRDPeak:
    """Detected profile peak with optional theoretical reflection match."""

    two_theta: float
    intensity: float
    d_spacing: Optional[float] = None
    hkls: str = ""
    matched_stick_two_theta: Optional[float] = None


@dataclass
class XRDResult:
    """Calculated XRD pattern and optional peak analysis."""

    config: XRDConfig
    source: str
    radiation: str
    wavelength: float
    two_theta_stick: np.ndarray
    intensity_stick: np.ndarray
    d_spacings_stick: List[Optional[float]]
    hkls_stick: List[str]
    two_theta_profile: np.ndarray
    intensity_profile: np.ndarray
    intensity_stick_profile: np.ndarray
    peaks: List[XRDPeak] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


def list_supported_radiations() -> List[str]:
    """Return supported XRD radiation labels from pymatgen."""
    return sorted(list(XRDCalculator.AVAILABLE_RADIATION))


def generate_xrd_from_cif(cif_path: PathLike, config: Optional[XRDConfig] = None) -> XRDResult:
    """Generate XRD result from a CIF file path."""
    path = Path(cif_path).expanduser()
    if not path.exists():
        raise FileNotFoundError(f"CIF file does not exist: {path}")
    if not path.is_file():
        raise ValueError(f"Expected a CIF file path, got directory: {path}")

    parser = CifParser(str(path))
    structures = parser.parse_structures(primitive=False)
    if not structures:
        raise ValueError(f"No structures parsed from CIF file: {path}")

    result = generate_xrd_from_structure(structures[0], config=config)
    result.source = str(path)
    result.metadata["source_type"] = "cif"
    result.metadata["cif_path"] = str(path)
    return result


def generate_xrd_from_structure(
    structure: Structure,
    config: Optional[XRDConfig] = None,
) -> XRDResult:
    """Generate XRD result from a pymatgen Structure."""
    if not isinstance(structure, Structure):
        raise TypeError("structure must be a pymatgen.core.structure.Structure")

    cfg = config if config is not None else XRDConfig()
    _validate_config(cfg)
    wavelength_value = _resolve_wavelength(cfg)
    calculator_input: Union[str, float] = (
        float(cfg.custom_wavelength) if cfg.custom_wavelength is not None else cfg.radiation
    )

    calculator = XRDCalculator(wavelength=calculator_input, symprec=cfg.symprec)
    pattern = calculator.get_pattern(
        structure,
        two_theta_range=(cfg.two_theta_min, cfg.two_theta_max),
    )

    stick_two_theta = np.asarray(pattern.x, dtype=float)
    stick_intensity = _normalize_to_100(np.asarray(pattern.y, dtype=float))
    d_spacings = [float(value) if value is not None else None for value in pattern.d_hkls]
    hkl_strings = [_format_hkls(entry) for entry in pattern.hkls]

    profile_two_theta = _make_two_theta_grid(cfg)
    stick_profile = _stick_to_grid(profile_two_theta, stick_two_theta, stick_intensity)
    profile_intensity = _build_profile(profile_two_theta, stick_two_theta, stick_intensity, cfg)
    profile_intensity = _normalize_to_100(profile_intensity)

    peaks = _find_profile_peaks(
        profile_two_theta=profile_two_theta,
        profile_intensity=profile_intensity,
        stick_two_theta=stick_two_theta,
        d_spacings=d_spacings,
        hkl_strings=hkl_strings,
        cfg=cfg,
    )

    return XRDResult(
        config=cfg,
        source="structure",
        radiation=cfg.radiation if cfg.custom_wavelength is None else "custom",
        wavelength=wavelength_value,
        two_theta_stick=stick_two_theta,
        intensity_stick=stick_intensity,
        d_spacings_stick=d_spacings,
        hkls_stick=hkl_strings,
        two_theta_profile=profile_two_theta,
        intensity_profile=profile_intensity,
        intensity_stick_profile=stick_profile,
        peaks=peaks,
        metadata={
            "formula": structure.composition.reduced_formula,
            "num_sites": len(structure),
            "num_reflections": int(stick_two_theta.size),
            "profile_model": cfg.profile,
        },
    )


def export_xrd_pattern_csv(result: XRDResult, filepath: PathLike) -> Path:
    """Export the generated profile and stick intensity traces to CSV."""
    path = Path(filepath).expanduser()
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["two_theta_deg", "profile_intensity", "stick_intensity"])
        for x_val, y_profile, y_stick in zip(
            result.two_theta_profile,
            result.intensity_profile,
            result.intensity_stick_profile,
        ):
            writer.writerow([f"{float(x_val):.6f}", f"{float(y_profile):.6f}", f"{float(y_stick):.6f}"])
    return path


def export_xrd_peaks_csv(result: XRDResult, filepath: PathLike) -> Path:
    """Export detected peak list to CSV."""
    path = Path(filepath).expanduser()
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "two_theta_deg",
                "intensity",
                "d_spacing_angstrom",
                "hkls",
                "matched_stick_two_theta_deg",
            ]
        )
        for peak in result.peaks:
            writer.writerow(
                [
                    f"{peak.two_theta:.6f}",
                    f"{peak.intensity:.6f}",
                    "" if peak.d_spacing is None else f"{peak.d_spacing:.6f}",
                    peak.hkls,
                    "" if peak.matched_stick_two_theta is None else f"{peak.matched_stick_two_theta:.6f}",
                ]
            )
    return path


def _validate_config(config: XRDConfig) -> None:
    if config.custom_wavelength is None and config.radiation not in XRDCalculator.AVAILABLE_RADIATION:
        raise ValueError(
            f"Unsupported radiation '{config.radiation}'. "
            f"Choose one of: {', '.join(list_supported_radiations())}"
        )
    if config.custom_wavelength is not None and config.custom_wavelength <= 0:
        raise ValueError("custom_wavelength must be > 0 Angstrom")
    if config.two_theta_min < 0:
        raise ValueError("two_theta_min must be >= 0")
    if config.two_theta_max <= config.two_theta_min:
        raise ValueError("two_theta_max must be greater than two_theta_min")
    if config.two_theta_step <= 0:
        raise ValueError("two_theta_step must be > 0")
    if config.profile not in ("stick", "gaussian", "lorentzian", "pseudo_voigt"):
        raise ValueError("profile must be one of: stick, gaussian, lorentzian, pseudo_voigt")
    if config.profile != "stick" and config.fwhm <= 0:
        raise ValueError("fwhm must be > 0 for broadened profiles")
    if not 0.0 <= config.eta <= 1.0:
        raise ValueError("eta must be between 0 and 1")
    if config.peak_min_height < 0:
        raise ValueError("peak_min_height must be >= 0")
    if config.peak_prominence < 0:
        raise ValueError("peak_prominence must be >= 0")
    if config.peak_distance < 0:
        raise ValueError("peak_distance must be >= 0")
    if config.peak_width < 0:
        raise ValueError("peak_width must be >= 0")
    if config.peak_match_tolerance < 0:
        raise ValueError("peak_match_tolerance must be >= 0")
    if config.symprec < 0:
        raise ValueError("symprec must be >= 0")


def _resolve_wavelength(config: XRDConfig) -> float:
    if config.custom_wavelength is not None:
        return float(config.custom_wavelength)
    return float(WAVELENGTHS[config.radiation])


def _make_two_theta_grid(config: XRDConfig) -> np.ndarray:
    upper = config.two_theta_max + (0.5 * config.two_theta_step)
    grid = np.arange(config.two_theta_min, upper, config.two_theta_step, dtype=float)
    if grid.size == 0:
        return np.array([config.two_theta_min], dtype=float)
    return grid


def _normalize_to_100(values: np.ndarray) -> np.ndarray:
    clipped = np.clip(np.asarray(values, dtype=float), 0.0, None)
    if clipped.size == 0:
        return clipped
    max_val = float(np.max(clipped))
    if max_val <= 0:
        return clipped
    return (clipped / max_val) * 100.0


def _stick_to_grid(grid: np.ndarray, stick_x: np.ndarray, stick_y: np.ndarray) -> np.ndarray:
    result = np.zeros_like(grid, dtype=float)
    if stick_x.size == 0 or grid.size == 0:
        return result
    nearest = np.abs(grid[np.newaxis, :] - stick_x[:, np.newaxis]).argmin(axis=1)
    for peak_idx, grid_idx in enumerate(nearest):
        result[grid_idx] = max(result[grid_idx], float(stick_y[peak_idx]))
    return result


def _build_profile(
    grid: np.ndarray,
    stick_x: np.ndarray,
    stick_y: np.ndarray,
    config: XRDConfig,
) -> np.ndarray:
    if grid.size == 0:
        return np.array([], dtype=float)
    if stick_x.size == 0:
        return np.zeros_like(grid, dtype=float)
    if config.profile == "stick":
        return _stick_to_grid(grid, stick_x, stick_y)

    delta = grid[np.newaxis, :] - stick_x[:, np.newaxis]
    sigma = config.fwhm / (2.0 * math.sqrt(2.0 * math.log(2.0)))
    gamma = config.fwhm / 2.0

    if config.profile == "gaussian":
        kernel = np.exp(-0.5 * (delta / sigma) ** 2)
    elif config.profile == "lorentzian":
        kernel = 1.0 / (1.0 + (delta / gamma) ** 2)
    else:
        gaussian = np.exp(-0.5 * (delta / sigma) ** 2)
        lorentz = 1.0 / (1.0 + (delta / gamma) ** 2)
        kernel = (1.0 - config.eta) * gaussian + config.eta * lorentz

    return np.sum(stick_y[:, np.newaxis] * kernel, axis=0)


def _find_profile_peaks(
    profile_two_theta: np.ndarray,
    profile_intensity: np.ndarray,
    stick_two_theta: np.ndarray,
    d_spacings: Sequence[Optional[float]],
    hkl_strings: Sequence[str],
    cfg: XRDConfig,
) -> List[XRDPeak]:
    if not cfg.peak_finder_enabled or profile_two_theta.size == 0:
        return []
    if np.max(profile_intensity) <= 0:
        return []

    distance_samples: Optional[int] = None
    if cfg.peak_distance > 0:
        distance_samples = max(int(round(cfg.peak_distance / cfg.two_theta_step)), 1)

    width_samples: Optional[float] = None
    if cfg.peak_width > 0:
        width_samples = max(cfg.peak_width / cfg.two_theta_step, 1.0)

    peak_indices, _ = find_peaks(
        profile_intensity,
        height=cfg.peak_min_height,
        prominence=cfg.peak_prominence,
        distance=distance_samples,
        width=width_samples,
    )
    if peak_indices.size == 0:
        return []

    peaks: List[XRDPeak] = []
    for idx in peak_indices.tolist():
        x_val = float(profile_two_theta[idx])
        y_val = float(profile_intensity[idx])
        d_spacing: Optional[float] = None
        hkls = ""
        matched_stick: Optional[float] = None

        if stick_two_theta.size > 0:
            nearest = int(np.argmin(np.abs(stick_two_theta - x_val)))
            nearest_x = float(stick_two_theta[nearest])
            if abs(nearest_x - x_val) <= cfg.peak_match_tolerance:
                matched_stick = nearest_x
                d_spacing = d_spacings[nearest] if nearest < len(d_spacings) else None
                hkls = hkl_strings[nearest] if nearest < len(hkl_strings) else ""

        peaks.append(
            XRDPeak(
                two_theta=x_val,
                intensity=y_val,
                d_spacing=d_spacing,
                hkls=hkls,
                matched_stick_two_theta=matched_stick,
            )
        )

    return peaks


def _format_hkls(hkl_group: Any) -> str:
    if not hkl_group:
        return ""

    labels: List[str] = []
    for item in hkl_group:
        hkl = item.get("hkl")
        multiplicity = item.get("multiplicity")
        if hkl is None:
            continue
        hkl_label = f"({hkl[0]} {hkl[1]} {hkl[2]})"
        if multiplicity is not None:
            labels.append(f"{hkl_label} x{multiplicity}")
        else:
            labels.append(hkl_label)

    return ", ".join(labels)
