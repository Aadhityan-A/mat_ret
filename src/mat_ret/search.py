"""Search query parsing and element-set helpers for mat_ret."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Set
import re

from pymatgen.core.composition import Composition
from pymatgen.core.periodic_table import Element


CHEMSYS_SPLIT_RE = re.compile(r"[-,]+")
ELEMENT_TOKEN_RE = re.compile(r"^[A-Z][a-z]?$")

CRYSTAL_SYSTEMS = (
    "cubic",
    "hexagonal",
    "trigonal",
    "tetragonal",
    "orthorhombic",
    "monoclinic",
    "triclinic",
)


@dataclass(frozen=True)
class SearchQuery:
    """Normalized search query passed from GUI to worker/backend."""

    mode: str  # "formula" or "elements_all"
    formula: Optional[str]
    elements: List[str]
    display_text: str


@dataclass
class SearchFilters:
    """Search filters that can be applied across databases.

    Databases that support server-side filters will translate these into native
    query parameters.  Others fall back to post-fetch filtering via
    :func:`apply_post_filters`.
    """

    # Electronic
    band_gap_min: Optional[float] = None
    band_gap_max: Optional[float] = None
    is_metal: Optional[bool] = None  # None = any, True = metals only, False = non-metals

    # Energetic
    formation_energy_min: Optional[float] = None
    formation_energy_max: Optional[float] = None
    energy_above_hull_max: Optional[float] = None
    is_stable: Optional[bool] = None  # True → energy_above_hull == 0

    # Structural
    density_min: Optional[float] = None
    density_max: Optional[float] = None
    volume_min: Optional[float] = None
    volume_max: Optional[float] = None
    space_group_number: Optional[int] = None
    crystal_system: Optional[str] = None
    num_elements_min: Optional[int] = None
    num_elements_max: Optional[int] = None
    num_sites_min: Optional[int] = None
    num_sites_max: Optional[int] = None

    # Mechanical
    bulk_modulus_min: Optional[float] = None
    bulk_modulus_max: Optional[float] = None
    shear_modulus_min: Optional[float] = None
    shear_modulus_max: Optional[float] = None

    # Magnetic
    magnetic_ordering: Optional[str] = None
    total_magnetization_min: Optional[float] = None
    total_magnetization_max: Optional[float] = None

    # Other
    exclude_theoretical: bool = False

    def has_any_filter(self) -> bool:
        """Return ``True`` if at least one filter is set."""
        for attr_name in (
            "band_gap_min", "band_gap_max", "is_metal",
            "formation_energy_min", "formation_energy_max",
            "energy_above_hull_max", "is_stable",
            "density_min", "density_max", "volume_min", "volume_max",
            "space_group_number", "crystal_system",
            "num_elements_min", "num_elements_max",
            "num_sites_min", "num_sites_max",
            "bulk_modulus_min", "bulk_modulus_max",
            "shear_modulus_min", "shear_modulus_max",
            "magnetic_ordering",
            "total_magnetization_min", "total_magnetization_max",
        ):
            if getattr(self, attr_name) is not None:
                return True
        return self.exclude_theoretical

    def active_filter_count(self) -> int:
        """Return the number of active (non-default) filters."""
        count = 0
        for attr_name in (
            "band_gap_min", "band_gap_max", "is_metal",
            "formation_energy_min", "formation_energy_max",
            "energy_above_hull_max", "is_stable",
            "density_min", "density_max", "volume_min", "volume_max",
            "space_group_number", "crystal_system",
            "num_elements_min", "num_elements_max",
            "num_sites_min", "num_sites_max",
            "bulk_modulus_min", "bulk_modulus_max",
            "shear_modulus_min", "shear_modulus_max",
            "magnetic_ordering",
            "total_magnetization_min", "total_magnetization_max",
        ):
            if getattr(self, attr_name) is not None:
                count += 1
        if self.exclude_theoretical:
            count += 1
        return count


def normalize_elements(elements: Iterable[str]) -> List[str]:
    """Validate and de-duplicate element symbols preserving first-seen order."""
    normalized: List[str] = []
    seen: Set[str] = set()

    for raw in elements:
        token = str(raw or "").strip()
        if not token:
            continue
        token = token[0].upper() + token[1:].lower()
        if not ELEMENT_TOKEN_RE.match(token):
            raise ValueError(f"Invalid element symbol '{raw}'")
        try:
            Element(token)
        except Exception as exc:
            raise ValueError(f"Invalid element symbol '{raw}'") from exc

        if token not in seen:
            seen.add(token)
            normalized.append(token)

    if not normalized:
        raise ValueError("Please select at least one valid element")

    return normalized


def format_chemsys(elements: Iterable[str]) -> str:
    """Format an element set into canonical chemsys text (e.g., Fe-O)."""
    return "-".join(normalize_elements(elements))


def parse_search_text(text: str) -> SearchQuery:
    """Parse user text into either formula or element-set query mode."""
    query_text = (text or "").strip()
    if not query_text:
        raise ValueError("Please enter a composition formula or element system (e.g., Fe2O3 or Fe-O)")

    if "-" in query_text or "," in query_text:
        raw_tokens = [tok.strip() for tok in CHEMSYS_SPLIT_RE.split(query_text) if tok.strip()]
        if not raw_tokens:
            raise ValueError("Please enter at least one element symbol")

        try:
            elements = normalize_elements(raw_tokens)
        except ValueError as exc:
            raise ValueError(f"Invalid element system: {exc}") from exc

        return SearchQuery(
            mode="elements_all",
            formula=None,
            elements=elements,
            display_text="-".join(elements),
        )

    try:
        reduced_formula = Composition(query_text).reduced_formula
    except Exception as exc:
        raise ValueError(f"Invalid formula: {exc}") from exc

    return SearchQuery(
        mode="formula",
        formula=reduced_formula,
        elements=[],
        display_text=reduced_formula,
    )


def _extract_symbols_from_formula(formula: str) -> Set[str]:
    try:
        return {el.symbol for el in Composition(formula).elements}
    except Exception:
        return set(re.findall(r"[A-Z][a-z]?", formula or ""))


def contains_all_elements(formula_or_structure: Any, required_elements: Iterable[str]) -> bool:
    """Return True when all required elements are present in the input formula/structure."""
    required_raw = [str(value or "").strip() for value in required_elements]
    required_raw = [value for value in required_raw if value]
    if not required_raw:
        return True

    if formula_or_structure is None:
        return False

    required = set(normalize_elements(required_raw))

    present: Set[str]

    if isinstance(formula_or_structure, str):
        present = _extract_symbols_from_formula(formula_or_structure)
    elif hasattr(formula_or_structure, "composition"):
        try:
            present = {el.symbol for el in formula_or_structure.composition.elements}
        except Exception:
            present = set()
    else:
        present = _extract_symbols_from_formula(str(formula_or_structure))

    return required.issubset(present)


# ---------------------------------------------------------------------------
# Post-fetch filtering
# ---------------------------------------------------------------------------

def _safe_float(value: Any) -> Optional[float]:
    """Coerce *value* to float if possible; return ``None`` otherwise."""
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def apply_post_filters(
    results: List[Dict[str, Any]],
    filters: Optional[SearchFilters],
    std_properties: Optional[Dict[str, str]] = None,
) -> List[Dict[str, Any]]:
    """Apply *filters* on already-fetched result dicts.

    Each result dict is expected to use **standardized** property keys (the
    *values* of ``STANDARD_PROPERTIES``).  Pass the ``STANDARD_PROPERTIES``
    mapping as *std_properties* so this function can resolve the key names;
    if ``None`` it assumes identity mapping (key == value).
    """
    if filters is None or not filters.has_any_filter():
        return results

    sp = std_properties or {}

    def _key(prop: str) -> str:
        return sp.get(prop, prop)

    filtered: List[Dict[str, Any]] = []
    for mat in results:
        # -- Electronic --
        if filters.band_gap_min is not None:
            val = _safe_float(mat.get(_key("band_gap")))
            if val is None or val < filters.band_gap_min:
                continue
        if filters.band_gap_max is not None:
            val = _safe_float(mat.get(_key("band_gap")))
            if val is None or val > filters.band_gap_max:
                continue
        if filters.is_metal is True:
            val = mat.get(_key("is_metallic"))
            if val is None:
                bg = _safe_float(mat.get(_key("band_gap")))
                if bg is None or bg > 0:
                    continue
            elif not val:
                continue
        elif filters.is_metal is False:
            val = mat.get(_key("is_metallic"))
            if val is None:
                bg = _safe_float(mat.get(_key("band_gap")))
                if bg is not None and bg == 0:
                    continue
            elif val:
                continue

        # -- Energetic --
        if filters.formation_energy_min is not None:
            val = _safe_float(mat.get(_key("formation_energy_per_atom")))
            if val is None or val < filters.formation_energy_min:
                continue
        if filters.formation_energy_max is not None:
            val = _safe_float(mat.get(_key("formation_energy_per_atom")))
            if val is None or val > filters.formation_energy_max:
                continue
        if filters.energy_above_hull_max is not None:
            val = _safe_float(mat.get(_key("energy_above_hull")))
            if val is None or val > filters.energy_above_hull_max:
                continue
        if filters.is_stable is True:
            val = _safe_float(mat.get(_key("energy_above_hull")))
            if val is None or val > 0:
                continue

        # -- Structural --
        if filters.density_min is not None:
            val = _safe_float(mat.get(_key("density")))
            if val is None or val < filters.density_min:
                continue
        if filters.density_max is not None:
            val = _safe_float(mat.get(_key("density")))
            if val is None or val > filters.density_max:
                continue
        if filters.volume_min is not None:
            val = _safe_float(mat.get(_key("volume")))
            if val is None or val < filters.volume_min:
                continue
        if filters.volume_max is not None:
            val = _safe_float(mat.get(_key("volume")))
            if val is None or val > filters.volume_max:
                continue
        if filters.space_group_number is not None:
            val = mat.get(_key("space_group_number"))
            try:
                if int(val) != filters.space_group_number:
                    continue
            except (TypeError, ValueError):
                continue
        if filters.crystal_system is not None:
            val = mat.get(_key("crystal_system"))
            if val is None or str(val).lower() != filters.crystal_system.lower():
                continue
        if filters.num_elements_min is not None or filters.num_elements_max is not None:
            formula_str = mat.get(_key("formula"), "")
            try:
                nel = len(Composition(formula_str).elements)
            except Exception:
                nel = None
            if nel is None:
                continue
            if filters.num_elements_min is not None and nel < filters.num_elements_min:
                continue
            if filters.num_elements_max is not None and nel > filters.num_elements_max:
                continue
        if filters.num_sites_min is not None or filters.num_sites_max is not None:
            nsites = mat.get("num_sites") or mat.get("nsites")
            if nsites is None:
                structure = mat.get("structure")
                nsites = len(structure) if structure is not None and hasattr(structure, "__len__") else None
            if nsites is None:
                continue
            nsites = int(nsites)
            if filters.num_sites_min is not None and nsites < filters.num_sites_min:
                continue
            if filters.num_sites_max is not None and nsites > filters.num_sites_max:
                continue

        # -- Mechanical --
        if filters.bulk_modulus_min is not None:
            val = _safe_float(mat.get(_key("bulk_modulus")))
            if val is None or val < filters.bulk_modulus_min:
                continue
        if filters.bulk_modulus_max is not None:
            val = _safe_float(mat.get(_key("bulk_modulus")))
            if val is None or val > filters.bulk_modulus_max:
                continue
        if filters.shear_modulus_min is not None:
            val = _safe_float(mat.get(_key("shear_modulus")))
            if val is None or val < filters.shear_modulus_min:
                continue
        if filters.shear_modulus_max is not None:
            val = _safe_float(mat.get(_key("shear_modulus")))
            if val is None or val > filters.shear_modulus_max:
                continue

        # -- Magnetic --
        if filters.magnetic_ordering is not None:
            val = mat.get(_key("magnetic_ordering"))
            if val is None or str(val).lower() != filters.magnetic_ordering.lower():
                continue
        if filters.total_magnetization_min is not None:
            val = _safe_float(mat.get(_key("magnetic_moment")) or mat.get("total_magnetization"))
            if val is None or val < filters.total_magnetization_min:
                continue
        if filters.total_magnetization_max is not None:
            val = _safe_float(mat.get(_key("magnetic_moment")) or mat.get("total_magnetization"))
            if val is None or val > filters.total_magnetization_max:
                continue

        filtered.append(mat)

    return filtered
