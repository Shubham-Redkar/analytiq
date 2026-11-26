"""Deterministic mathematical calculations and numerical checks for claims."""

import math
from typing import Any


def safe_float(val: Any) -> float | None:
    """Convert value to float safely without throwing exceptions."""
    if val is None:
        return None
    if isinstance(val, (int, float)):
        if math.isnan(val) or math.isinf(val):
            return None
        return float(val)
    if isinstance(val, str):
        try:
            f = float(val.strip().replace(",", ""))
            if math.isnan(f) or math.isinf(f):
                return None
            return f
        except ValueError:
            return None
    return None


def calculate_difference(
    target_val: float,
    baseline_val: float,
    is_absolute: bool = False,
) -> float:
    """Calculate target_val - baseline_val or absolute difference."""
    diff = target_val - baseline_val
    return abs(diff) if is_absolute else diff


def calculate_percentage_change(
    baseline_val: float,
    target_val: float,
) -> float | None:
    """Calculate ((target - baseline) / baseline) * 100.

    Policy:
    - Positive baseline: ((target - baseline) / baseline) * 100.
    - Zero baseline: None (undefined).
    - Negative baseline: None by default (undefined in ordinary percentage change
      without explicit domain convention).
    """
    if baseline_val <= 0.0:
        return None
    return ((target_val - baseline_val) / baseline_val) * 100.0


def calculate_proportion(
    part_val: float,
    whole_val: float,
    as_percentage: bool = False,
) -> float | None:
    """Calculate part / whole or (part / whole) * 100 if as_percentage is True.

    Returns None if whole <= 0.
    """
    if whole_val <= 0.0:
        return None
    ratio = part_val / whole_val
    return (ratio * 100.0) if as_percentage else ratio


def numbers_match(
    a: Any,
    b: Any,
    rel_tol: float = 1e-9,
    abs_tol: float = 1e-8,
    display_places: int | None = None,
) -> bool:
    """Deterministic, type-aware numerical comparison policy.

    Rules:
    1. Booleans are rejected from numeric comparisons to prevent True == 1.
    2. Null/None equality is exact (None matches only None).
    3. Exact integers/counts are compared with 0 tolerance (exact equality).
    4. Floating-point comparisons use strict tolerances (rel_tol=1e-9, abs_tol=1e-8)
       unless explicit display rounding places are provided.
    5. NaN values never match. Infinite values match only identical signed infinity.
    """
    if a is None or b is None:
        return a is None and b is None

    # Disallow booleans from masquerading as integers/floats
    if isinstance(a, bool) or isinstance(b, bool):
        return isinstance(a, bool) and isinstance(b, bool) and a is b

    # If both are exact integers, enforce strict exact integer equality
    if isinstance(a, int) and isinstance(b, int):
        return a == b

    try:
        fa, fb = float(a), float(b)
    except (ValueError, TypeError):
        return False

    if math.isnan(fa) or math.isnan(fb):
        return False
    if math.isinf(fa) or math.isinf(fb):
        return fa == fb

    # Optional display-rounding check (e.g. 33.33% matches round(33.33333, 2))
    if display_places is not None:
        return round(fa, display_places) == round(fb, display_places)

    return math.isclose(fa, fb, rel_tol=rel_tol, abs_tol=abs_tol)
