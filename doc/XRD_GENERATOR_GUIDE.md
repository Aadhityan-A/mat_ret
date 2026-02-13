# XRD Generator Guide

## Overview

The XRD Generator computes powder X-ray diffraction patterns from crystal structures using `pymatgen` and provides peak finding with `scipy`.

Sources:

- CIF file (`.cif`)
- Current structure selected in the mat_ret main GUI

## Core Diffraction Model

Base reflections are computed using:

- `pymatgen.analysis.diffraction.xrd.XRDCalculator`

The generated reflections include:

- 2theta positions
- relative stick intensities
- `d_hkl` values
- HKL lists and multiplicities

## Radiation

You can use standard radiation labels supported by pymatgen (for example `CuKa`, `CuKa1`, `CuKa2`, `MoKa`) or a custom wavelength in Angstrom.

Default:

- `CuKa = 1.54184 A`

## Scan Range and Resolution

Pattern calculations use:

- `2theta_min` (deg)
- `2theta_max` (deg)
- `2theta_step` (deg)

A uniform 2theta grid is generated for profile output and peak detection.

## Peak Profile Models

### Stick

Ideal discrete Bragg sticks without broadening.

### Gaussian

Peak kernel:

- `G(dx) = exp(-0.5 * (dx / sigma)^2)`
- `sigma = FWHM / (2 * sqrt(2 * ln(2)))`

### Lorentzian

Peak kernel:

- `L(dx) = 1 / (1 + (dx / gamma)^2)`
- `gamma = FWHM / 2`

### Pseudo-Voigt

Mixture:

- `PV(dx) = (1 - eta) * G(dx) + eta * L(dx)`
- `eta` in `[0, 1]`

## Intensity Normalization

Profile and stick intensities are normalized to a maximum of `100` for display and export.

## Peak Finder

Detected on the broadened profile with `scipy.signal.find_peaks`.

Exposed controls:

- minimum height
- prominence
- minimum distance (deg)
- minimum width (deg)
- match tolerance (deg) to map detected profile peaks back to nearest theoretical stick

Matched peak annotations include:

- nearest stick position
- `d` spacing
- HKL labels

## Exports

From the GUI:

- Plot export: `PNG`, `SVG`, `PDF`
- Pattern CSV: `two_theta_deg, profile_intensity, stick_intensity`
- Peaks CSV:
  - `two_theta_deg`
  - `intensity`
  - `d_spacing_angstrom`
  - `hkls`
  - `matched_stick_two_theta_deg`

## Defaults

- Radiation: `CuKa`
- 2theta range: `5` to `90` deg
- Step: `0.02` deg
- Profile: `Pseudo-Voigt`
- FWHM: `0.15` deg
- Eta: `0.5`
- Peak finder: enabled

## Known Limitations

- This is a powder pattern model and does not include preferred orientation effects.
- No synthetic instrumental background/noise model is added in this version.
- Broadening uses constant FWHM across the scan range.
- Single active pattern per window (no multi-pattern overlay in this release).
