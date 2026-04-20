"""
Tessellarium — DOE Planner Utilities

Shared helpers used by both planner.py and design_generators.py.
Extracted here to break the circular import between those two modules.
"""


def combo_key(combo: dict[str, str]) -> str:
    """Deterministic string key for a factor-level combination dict."""
    return "|".join(f"{k}={v}" for k, v in sorted(combo.items()))
