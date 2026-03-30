"""
Tessellarium — Lean Generator Test

Tests Lean 4 code generation from design matrices.
All tests work offline — no Lean compilation.
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.lean_generator import (
    generate_covering_array_proof,
    generate_latin_square_proof,
    generate_bibd_proof,
)
from app.models import VerificationRequest


def test_covering_array_basic():
    """Generate Lean code for a simple 2-factor pairwise covering array."""
    print("Test: Covering array code generation (2 factors)")

    matrix = [
        {"temp": "t20", "lot": "lotA"},
        {"temp": "t20", "lot": "lotB"},
        {"temp": "t30", "lot": "lotA"},
        {"temp": "t30", "lot": "lotB"},
    ]

    code = generate_covering_array_proof(matrix, strength=2)

    assert "native_decide" in code, "Must use native_decide"
    assert "covering_array_verified" in code, "Must have theorem name"
    assert "matrix" in code.lower(), "Must define the matrix"
    assert "Fin 4" in code or "Fin {{ num_runs }}" not in code, "Must have concrete Fin"
    assert "pairCovered" in code, "Must have pair coverage check"
    assert "allPairsCovered" in code
    assert "isStrength2CoveringArray" in code
    print(f"   Generated {len(code)} chars of Lean code")
    print("   PASSED")


def test_covering_array_3_factors():
    """Generate Lean code for a 3-factor covering array."""
    print("Test: Covering array code generation (3 factors)")

    matrix = [
        {"temp": "t20", "lot": "lotA", "time": "t1h"},
        {"temp": "t20", "lot": "lotB", "time": "t2h"},
        {"temp": "t30", "lot": "lotA", "time": "t2h"},
        {"temp": "t30", "lot": "lotB", "time": "t1h"},
    ]

    code = generate_covering_array_proof(matrix, strength=2)

    assert "Fin 4" in code  # 4 runs
    assert "Fin 3" in code  # 3 factors
    assert "native_decide" in code
    # Should reference all 3 factors in numLevels
    assert "numLevels" in code
    print(f"   Generated {len(code)} chars of Lean code")
    print("   PASSED")


def test_covering_array_empty_matrix():
    """Empty matrix returns comment, not Lean code."""
    print("Test: Empty matrix handling")

    code = generate_covering_array_proof([], strength=2)

    assert "Empty matrix" in code
    assert "native_decide" not in code
    print("   PASSED")


def test_covering_array_level_indexing():
    """Level names are correctly mapped to Nat indices."""
    print("Test: Level indexing correctness")

    matrix = [
        {"temp": "t20", "lot": "lotA"},
        {"temp": "t30", "lot": "lotB"},
        {"temp": "t40", "lot": "lotC"},
    ]

    code = generate_covering_array_proof(matrix, strength=2)

    # Should have values 0, 1, 2 for both factors (3 levels each)
    assert "=> 0" in code
    assert "=> 1" in code
    assert "=> 2" in code
    print("   PASSED")


def test_latin_square_generation():
    """Generate Lean code for Latin square verification."""
    print("Test: Latin square code generation")

    matrix = [
        {"row": "r1", "col": "c1", "sym": "A"},
        {"row": "r1", "col": "c2", "sym": "B"},
        {"row": "r2", "col": "c1", "sym": "B"},
        {"row": "r2", "col": "c2", "sym": "A"},
    ]

    code = generate_latin_square_proof(matrix)

    assert "native_decide" in code
    assert "latin_square_verified" in code
    assert "isValidLatinSquare" in code
    print(f"   Generated {len(code)} chars of Lean code")
    print("   PASSED")


def test_latin_square_wrong_factors():
    """Latin square with != 3 factors returns comment."""
    print("Test: Latin square wrong factor count")

    matrix = [{"a": "1", "b": "2"}]
    code = generate_latin_square_proof(matrix)

    assert "requires exactly 3 factors" in code
    print("   PASSED")


def test_bibd_generation():
    """Generate BIBD placeholder."""
    print("Test: BIBD code generation (placeholder)")

    matrix = [{"block": "1", "treat": "A"}]
    code = generate_bibd_proof(matrix, lambda_val=1)

    assert "bibd_placeholder" in code or "trivial" in code
    print("   PASSED")


def test_covering_array_deterministic():
    """Same matrix produces identical Lean code."""
    print("Test: Deterministic code generation")

    matrix = [
        {"temp": "t20", "lot": "lotA"},
        {"temp": "t30", "lot": "lotB"},
    ]

    code1 = generate_covering_array_proof(matrix, strength=2)
    code2 = generate_covering_array_proof(matrix, strength=2)

    assert code1 == code2, "Code generation must be deterministic"
    print("   PASSED")


def test_verification_request_model():
    """VerificationRequest model validates correctly."""
    print("Test: VerificationRequest model")

    req = VerificationRequest(
        design_matrix=[
            {"temp": "t20", "lot": "lotA"},
            {"temp": "t30", "lot": "lotB"},
        ],
        design_family="covering_array",
        property_to_verify="pairwise_coverage",
        strength=2,
        timeout_seconds=30,
    )

    assert len(req.design_matrix) == 2
    assert req.design_family == "covering_array"
    assert req.strength == 2
    assert req.timeout_seconds == 30
    print("   PASSED")


def run_all_tests():
    print("=" * 70)
    print("TESSELLARIUM — Lean Generator Tests")
    print("=" * 70)
    print()

    test_covering_array_basic()
    test_covering_array_3_factors()
    test_covering_array_empty_matrix()
    test_covering_array_level_indexing()
    test_latin_square_generation()
    test_latin_square_wrong_factors()
    test_bibd_generation()
    test_covering_array_deterministic()
    test_verification_request_model()

    print()
    print("=" * 70)
    print("ALL TESTS PASSED ✅")
    print("=" * 70)


if __name__ == "__main__":
    run_all_tests()
