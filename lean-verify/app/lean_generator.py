"""
Tessellarium — Lean 4 Code Generator

Generates .lean files from design matrices and verification properties.
Uses Jinja2 templates for the Lean code structure.
"""

import os
from pathlib import Path
from jinja2 import Environment, FileSystemLoader

TEMPLATE_DIR = Path(__file__).parent.parent / "lean_templates"

_env = Environment(
    loader=FileSystemLoader(str(TEMPLATE_DIR)),
    keep_trailing_newline=True,
)


def generate_covering_array_proof(
    matrix: list[dict[str, str]],
    strength: int = 2,
) -> str:
    """
    Generate Lean 4 code that verifies a matrix is a covering array
    of strength t: every t-column subset contains all value tuples.

    For strength=2 (pairwise): every pair of columns contains all
    combinations of their values.
    """
    if not matrix:
        return "-- Empty matrix, nothing to verify"

    # Extract factor IDs and unique levels per factor
    factor_ids = list(matrix[0].keys())
    factor_levels: dict[str, list[str]] = {}
    for fid in factor_ids:
        levels = sorted(set(row[fid] for row in matrix))
        factor_levels[fid] = levels

    num_runs = len(matrix)
    num_factors = len(factor_ids)

    # Build the matrix as numeric indices
    # Map each level to a Fin index
    level_to_idx: dict[str, dict[str, int]] = {}
    for fid in factor_ids:
        level_to_idx[fid] = {
            lvl: i for i, lvl in enumerate(factor_levels[fid])
        }

    numeric_matrix = []
    for row in matrix:
        numeric_row = []
        for fid in factor_ids:
            numeric_row.append(level_to_idx[fid][row[fid]])
        numeric_matrix.append(numeric_row)

    levels_per_factor = [len(factor_levels[fid]) for fid in factor_ids]

    template = _env.get_template("covering_array.lean.j2")
    return template.render(
        num_runs=num_runs,
        num_factors=num_factors,
        factor_ids=factor_ids,
        factor_levels=factor_levels,
        levels_per_factor=levels_per_factor,
        numeric_matrix=numeric_matrix,
        strength=strength,
        level_to_idx=level_to_idx,
    )


def generate_latin_square_proof(
    matrix: list[dict[str, str]],
) -> str:
    """
    Generate Lean 4 code that verifies a matrix is a valid Latin square:
    each symbol appears exactly once per row and once per column.

    Expects a matrix with 3 factors: row, column, symbol.
    """
    if not matrix or len(matrix[0]) != 3:
        return "-- Latin square requires exactly 3 factors"

    factor_ids = list(matrix[0].keys())
    n = len(matrix)

    # Build value-to-index maps for each factor
    value_maps: dict[str, dict[str, int]] = {}
    for fid in factor_ids:
        vals = sorted(set(row[fid] for row in matrix))
        value_maps[fid] = {v: i for i, v in enumerate(vals)}

    # Encode entries as (row_idx, col_idx, sym_idx) tuples
    entries = []
    for row in matrix:
        triple = tuple(value_maps[fid][row[fid]] for fid in factor_ids)
        entries.append(triple)

    entry_strs = [f"({a}, {b}, {c})" for a, b, c in entries]
    encoded = "[" + ", ".join(entry_strs) + "]"

    template = _env.get_template("latin_square.lean.j2")
    return template.render(
        encoded_entries=encoded,
        factor_ids=factor_ids,
        n=n,
    )


def generate_bibd_proof(
    matrix: list[dict[str, str]],
    lambda_val: int = 1,
) -> str:
    """
    Generate Lean 4 code that verifies a BIBD property:
    every pair of treatments appears together in exactly lambda blocks.
    """
    if not matrix:
        return "-- Empty matrix, nothing to verify"

    template = _env.get_template("bibd.lean.j2")
    return template.render(
        matrix=matrix,
        lambda_val=lambda_val,
    )
