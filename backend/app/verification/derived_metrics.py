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

    Returns None if baseline is zero.
    """
    if baseline_val == 0.0:
        return None
    return ((target_val - baseline_val) / abs(baseline_val)) * 100.0


def calculate_proportion(
    part_val: float,
    whole_val: float,
) -> float | None:
    """Calculate (part / whole) * 100.

    Returns None if whole is zero.
    """
    if whole_val == 0.0:
        return None
    return (part_val / whole_val) * 100.0


def numbers_match(
    a: float | int | None,
    b: float | int | None,
    rel_tol: float = 0.01,
    abs_tol: float = 0.01,
) -> bool:
    """Deterministic comparison with tight, documented relative and absolute tolerances."""
    if a is None or b is None:
        return a is None and b is None

    fa, fb = float(a), float(b)
    if math.isnan(fa) or math.isnan(fb):
        return False
    if math.isinf(fa) or math.isinf(fb):
        return fa == fb

    return math.isclose(fa, fb, rel_tol=rel_tol, abs_tol=abs_tol)
