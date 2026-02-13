"""Search query parsing and element-set helpers for mat_ret."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, List, Optional, Set
import re

from pymatgen.core.composition import Composition
from pymatgen.core.periodic_table import Element


CHEMSYS_SPLIT_RE = re.compile(r"[-,]+")
ELEMENT_TOKEN_RE = re.compile(r"^[A-Z][a-z]?$")


@dataclass(frozen=True)
class SearchQuery:
    """Normalized search query passed from GUI to worker/backend."""

    mode: str  # "formula" or "elements_all"
    formula: Optional[str]
    elements: List[str]
    display_text: str


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
