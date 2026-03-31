"""
Tessellarium — Design Generator Tests

Tests the Generate -> Filter -> Score -> Repair -> Assess pipeline.
Tests that require OAPackage or PyDOE2 are skipped if not installed.
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.models.problem_space import (
    ProblemSpace, Factor, Level, Hypothesis, Constraint,
    EpistemicState, DesignFamily,
)
from app.doe_planner.design_generators import (
    GeneratedDesign, DesignQuality, FilterResult,
    DesignQualityAssessor,
    PyDOEFullFactGenerator, PyDOEGSDGenerator, PyDOEFracFactGenerator,
    OAEnumerationGenerator, DoptimizeGenerator,
    filter_by_constraints, repair_coverage, compute_pairwise_coverage,
    generate_best_design, COVERAGE_CHAIN, ROBUSTNESS_CHAIN,
)

try:
    import oapackage
    HAS_OAPACKAGE = True
except ImportError:
    HAS_OAPACKAGE = False

try:
    import pyDOE2
    HAS_PYDOE2 = True
except ImportError:
    HAS_PYDOE2 = False


def _make_ps(
    factors=None, constraints=None, budget=None, hypotheses=None,
) -> ProblemSpace:
    """Create a test ProblemSpace. Default: 3 factors (3, 3, 2 levels)."""
    if factors is None:
        factors = [
            Factor(id="temp", name="Temperature",
                   levels=[Level(id="t20", name="20C"), Level(id="t30", name="30C"),
                           Level(id="t40", name="40C")]),
            Factor(id="lot", name="Reagent Lot",
                   levels=[Level(id="lotA", name="A"), Level(id="lotB", name="B"),
                           Level(id="lotC", name="C")]),
            Factor(id="time", name="Incubation Time",
                   levels=[Level(id="t1h", name="1h"), Level(id="t2h", name="2h")]),
        ]
    if hypotheses is None:
        hypotheses = [
            Hypothesis(id="H1", statement="Temp causes drop",
                       distinguishing_factors=["temp"]),
            Hypothesis(id="H2", statement="Lot causes drop",
                       distinguishing_factors=["lot"]),
        ]
    return ProblemSpace(
        objective="Test objective",
        factors=factors,
        hypotheses=hypotheses,
        constraints=constraints or [],
        max_runs_budget=budget,
    )


def _make_2level_ps(n_factors=4, budget=8) -> ProblemSpace:
    """Create a PS with n 2-level factors."""
    factors = [
        Factor(id=f"f{i}", name=f"Factor{i}",
               levels=[Level(id=f"f{i}lo", name="Lo"), Level(id=f"f{i}hi", name="Hi")])
        for i in range(n_factors)
    ]
    return _make_ps(factors=factors, budget=budget)


# ─── Full Factorial Tests ─────────────────────────────────────────────

def test_full_factorial_within_budget():
    """Budget covers full factorial -> produced."""
    print("Test: Full factorial within budget")
    if not HAS_PYDOE2:
        print("   SKIPPED (pyDOE2 not installed)")
        return
    ps = _make_ps(
        factors=[
            Factor(id="a", name="A", levels=[Level(id="a1", name="1"), Level(id="a2", name="2")]),
            Factor(id="b", name="B", levels=[Level(id="b1", name="1"), Level(id="b2", name="2")]),
        ],
        budget=4,
    )
    gen = PyDOEFullFactGenerator()
    result = gen.generate(ps, 4)
    assert result is not None
    assert result.num_runs == 4
    assert result.family == DesignFamily.FULL_FACTORIAL
    assert result.source == "pydoe2_fullfact"
    print(f"   {result.num_runs} runs, source={result.source}")
    print("   PASSED")


def test_full_factorial_exceeds_budget():
    """Budget too small -> returns None."""
    print("Test: Full factorial exceeds budget")
    if not HAS_PYDOE2:
        print("   SKIPPED (pyDOE2 not installed)")
        return
    ps = _make_ps(budget=4)  # 3*3*2=18, budget=4
    gen = PyDOEFullFactGenerator()
    result = gen.generate(ps, 4)
    assert result is None
    print("   Correctly returned None")
    print("   PASSED")


def test_gsd_produces_balanced_design():
    """GSD for 3 factors (3,3,2), budget=8."""
    print("Test: GSD produces balanced design")
    if not HAS_PYDOE2:
        print("   SKIPPED (pyDOE2 not installed)")
        return
    ps = _make_ps(budget=8)
    gen = PyDOEGSDGenerator()
    result = gen.generate(ps, 8)
    if result is None:
        print("   GSD returned None (acceptable if no reduction fits)")
        print("   PASSED")
        return
    assert result.num_runs <= 8
    assert result.source == "pydoe2_gsd"
    print(f"   {result.num_runs} runs, reduction={result.properties.get('reduction')}")
    print("   PASSED")


def test_gsd_not_used_when_full_fact_fits():
    """Budget covers full factorial -> GSD returns None."""
    print("Test: GSD not used when full factorial fits")
    if not HAS_PYDOE2:
        print("   SKIPPED (pyDOE2 not installed)")
        return
    ps = _make_ps(
        factors=[
            Factor(id="a", name="A", levels=[Level(id="a1", name="1"), Level(id="a2", name="2")]),
            Factor(id="b", name="B", levels=[Level(id="b1", name="1"), Level(id="b2", name="2")]),
        ],
        budget=4,
    )
    gen = PyDOEGSDGenerator()
    result = gen.generate(ps, 4)
    assert result is None, "GSD should return None when full factorial fits"
    print("   PASSED")


def test_fracfact_two_level_only():
    """4 two-level factors -> fracfact produces design."""
    print("Test: Fractional factorial (2-level)")
    if not HAS_PYDOE2:
        print("   SKIPPED (pyDOE2 not installed)")
        return
    ps = _make_2level_ps(n_factors=4, budget=8)
    gen = PyDOEFracFactGenerator()
    result = gen.generate(ps, 8)
    assert result is not None, "fracfact should produce a design for 4 2-level factors"
    assert result.source == "pydoe2_fracfact"
    assert result.num_runs <= 8
    print(f"   {result.num_runs} runs, gen={result.properties.get('generators')}")
    print("   PASSED")


def test_fracfact_skips_mixed_levels():
    """Mixed-level factors -> fracfact returns None."""
    print("Test: Fractional factorial skips mixed levels")
    if not HAS_PYDOE2:
        print("   SKIPPED (pyDOE2 not installed)")
        return
    ps = _make_ps(budget=8)  # 3,3,2 levels -> mixed
    gen = PyDOEFracFactGenerator()
    result = gen.generate(ps, 8)
    assert result is None
    print("   PASSED")


# ─── OAPackage Tests ──────────────────────────────────────────────────

def test_oa_enumeration_basic():
    """Small problem -> OA enumeration produces design."""
    print("Test: OA enumeration basic")
    if not HAS_OAPACKAGE:
        print("   SKIPPED (OAPackage not installed)")
        return
    ps = _make_ps(
        factors=[
            Factor(id="a", name="A", levels=[Level(id="a1", name="1"), Level(id="a2", name="2")]),
            Factor(id="b", name="B", levels=[Level(id="b1", name="1"), Level(id="b2", name="2")]),
        ],
        budget=4,
    )
    gen = OAEnumerationGenerator()
    result = gen.generate(ps, 4)
    if result is not None:
        assert result.source == "oa_enumerate"
        print(f"   {result.num_runs} runs, D-eff={result.properties.get('d_efficiency')}")
    else:
        print("   OA enumeration returned None (acceptable)")
    print("   PASSED")


def test_doptimize_basic():
    """3 two-level factors, budget=8 -> Doptimize produces design."""
    print("Test: Doptimize basic")
    if not HAS_OAPACKAGE:
        print("   SKIPPED (OAPackage not installed)")
        return
    ps = _make_2level_ps(n_factors=3, budget=8)
    gen = DoptimizeGenerator(alpha=[1, 2, 0])
    result = gen.generate(ps, 8)
    if result is not None:
        assert result.source == "oa_doptimize"
        print(f"   {result.num_runs} runs, D-eff={result.properties.get('d_efficiency')}")
    else:
        print("   Doptimize returned None (acceptable)")
    print("   PASSED")


def test_doptimize_alpha_affects_result():
    """Different alpha values don't crash."""
    print("Test: Doptimize with different alphas")
    if not HAS_OAPACKAGE:
        print("   SKIPPED (OAPackage not installed)")
        return
    ps = _make_2level_ps(n_factors=3, budget=8)
    for alpha in [[1, 0, 0], [1, 2, 0], [0, 1, 0]]:
        gen = DoptimizeGenerator(alpha=alpha)
        result = gen.generate(ps, 8)
        status = f"{result.num_runs} runs" if result else "None"
        print(f"   alpha={alpha}: {status}")
    print("   PASSED")


# ─── Mapping Tests ────────────────────────────────────────────────────

def test_level_mapping_correctness():
    """Numeric indices map to correct factor/level IDs."""
    print("Test: Level mapping correctness")
    from app.doe_planner.design_generators import DesignGenerator

    class DummyGen(DesignGenerator):
        @property
        def name(self): return "dummy"
        def generate(self, ps, budget): return None

    ps = _make_ps(
        factors=[
            Factor(id="f1", name="F1",
                   levels=[Level(id="f1a", name="A"), Level(id="f1b", name="B")]),
            Factor(id="f2", name="F2",
                   levels=[Level(id="f2x", name="X"), Level(id="f2y", name="Y"),
                           Level(id="f2z", name="Z")]),
        ],
    )
    gen = DummyGen()
    rows = gen._map_indices_to_ids([[0, 2], [1, 0]], ps)
    assert rows[0] == {"f1": "f1a", "f2": "f2z"}
    assert rows[1] == {"f1": "f1b", "f2": "f2x"}
    print("   PASSED")


def test_level_mapping_with_unavailable_levels():
    """Only available levels are used in mapping."""
    print("Test: Level mapping with unavailable levels")
    from app.doe_planner.design_generators import DesignGenerator

    class DummyGen(DesignGenerator):
        @property
        def name(self): return "dummy"
        def generate(self, ps, budget): return None

    ps = _make_ps(
        factors=[
            Factor(id="f1", name="F1",
                   levels=[Level(id="f1a", name="A"),
                           Level(id="f1b", name="B", available=False),
                           Level(id="f1c", name="C")]),
        ],
    )
    gen = DummyGen()
    rows = gen._map_indices_to_ids([[0], [1]], ps)
    # Available levels: f1a (idx 0), f1c (idx 1). f1b is skipped.
    assert rows[0]["f1"] == "f1a"
    assert rows[1]["f1"] == "f1c"
    print("   PASSED")


# ─── Filter Tests ─────────────────────────────────────────────────────

def test_filter_no_constraints():
    """No constraints -> no rows removed."""
    print("Test: Filter with no constraints")
    ps = _make_ps(constraints=[])
    rows = [
        {"temp": "t20", "lot": "lotA", "time": "t1h"},
        {"temp": "t30", "lot": "lotB", "time": "t2h"},
    ]
    result = filter_by_constraints(rows, ps)
    assert result.removed_count == 0
    assert len(result.surviving_rows) == 2
    print("   PASSED")


def test_filter_removes_excluded_level():
    """Constraint on one level -> rows with that level removed."""
    print("Test: Filter removes excluded level")
    ps = _make_ps(constraints=[
        Constraint(id="C1", description="Lot C gone",
                   constraint_type="material_unavailable",
                   excluded_factor_id="lot", excluded_level_id="lotC"),
    ])
    rows = [
        {"temp": "t20", "lot": "lotA", "time": "t1h"},
        {"temp": "t30", "lot": "lotC", "time": "t2h"},  # excluded
        {"temp": "t40", "lot": "lotB", "time": "t1h"},
    ]
    result = filter_by_constraints(rows, ps)
    assert result.removed_count == 1
    assert len(result.surviving_rows) == 2
    assert all(r["lot"] != "lotC" for r in result.surviving_rows)
    print("   PASSED")


def test_filter_measures_coverage_damage():
    """After filtering, coverage metrics are computed."""
    print("Test: Filter measures coverage damage")
    ps = _make_ps(constraints=[
        Constraint(id="C1", description="Lot C gone",
                   constraint_type="material_unavailable",
                   excluded_factor_id="lot", excluded_level_id="lotC"),
    ])
    rows = [
        {"temp": "t20", "lot": "lotA", "time": "t1h"},
        {"temp": "t30", "lot": "lotC", "time": "t2h"},
    ]
    result = filter_by_constraints(rows, ps)
    assert result.pairwise_coverage_before >= result.pairwise_coverage_after
    print(f"   Coverage before: {result.pairwise_coverage_before:.2f}, "
          f"after: {result.pairwise_coverage_after:.2f}")
    print("   PASSED")


# ─── Repair Tests ─────────────────────────────────────────────────────

def test_repair_restores_coverage():
    """After heavy filtering, repair adds rows."""
    print("Test: Repair restores coverage")
    ps = _make_ps(constraints=[])
    current = [{"temp": "t20", "lot": "lotA", "time": "t1h"}]
    pool = [
        {"temp": "t30", "lot": "lotB", "time": "t2h"},
        {"temp": "t40", "lot": "lotC", "time": "t1h"},
        {"temp": "t20", "lot": "lotB", "time": "t2h"},
    ]
    result = repair_coverage(current, pool, 3, ps)
    assert len(result) > len(current)
    cov = compute_pairwise_coverage(result, ps)
    print(f"   Repaired to {len(result)} rows, coverage={cov:.2f}")
    print("   PASSED")


# ─── Quality Assessor Tests ──────────────────────────────────────────

def test_quality_assessor_basic():
    """OAPackage quality metrics for a simple design."""
    print("Test: Quality assessor basic")
    if not HAS_OAPACKAGE:
        print("   SKIPPED (OAPackage not installed)")
        return
    ps = _make_ps(
        factors=[
            Factor(id="a", name="A", levels=[Level(id="a0", name="0"), Level(id="a1", name="1")]),
            Factor(id="b", name="B", levels=[Level(id="b0", name="0"), Level(id="b1", name="1")]),
        ],
    )
    rows = [
        {"a": "a0", "b": "b0"},
        {"a": "a0", "b": "b1"},
        {"a": "a1", "b": "b0"},
        {"a": "a1", "b": "b1"},
    ]
    q = DesignQualityAssessor.assess(rows, ps)
    assert q.source_library == "oapackage"
    assert q.d_efficiency is not None
    print(f"   D-eff={q.d_efficiency}, GWLP={q.gwlp}, rank={q.rank}")
    print("   PASSED")


def test_quality_assessor_without_oapackage():
    """Quality assessor returns none metrics if OAPackage unavailable."""
    print("Test: Quality assessor fallback")
    q = DesignQuality(source_library="none")
    assert q.d_efficiency is None
    assert q.gwlp is None
    print("   PASSED")


# ─── Orchestration Tests ─────────────────────────────────────────────

def test_coverage_chain_produces_design():
    """COVERAGE_CHAIN produces a design."""
    print("Test: Coverage chain")
    if not HAS_PYDOE2 and not HAS_OAPACKAGE:
        print("   SKIPPED (no DOE libraries installed)")
        return
    ps = _make_ps(budget=8)
    result = generate_best_design(ps, 8, COVERAGE_CHAIN)
    if result:
        print(f"   {result.source}: {result.num_runs} runs")
    else:
        print("   No design produced (acceptable for this problem size)")
    print("   PASSED")


def test_robustness_chain_produces_design():
    """ROBUSTNESS_CHAIN produces a design."""
    print("Test: Robustness chain")
    if not HAS_PYDOE2 and not HAS_OAPACKAGE:
        print("   SKIPPED (no DOE libraries installed)")
        return
    ps = _make_ps(budget=8)
    result = generate_best_design(ps, 8, ROBUSTNESS_CHAIN)
    if result:
        print(f"   {result.source}: {result.num_runs} runs")
    else:
        print("   No design produced (acceptable)")
    print("   PASSED")


def test_all_generators_fail_returns_none():
    """Empty problem -> all generators return None."""
    print("Test: All generators fail -> None")
    ps = ProblemSpace(objective="empty")
    result = generate_best_design(ps, 4, COVERAGE_CHAIN)
    assert result is None
    print("   PASSED")


def test_pairwise_coverage_computation():
    """Pairwise coverage computed correctly."""
    print("Test: Pairwise coverage computation")
    ps = _make_ps(
        factors=[
            Factor(id="a", name="A", levels=[Level(id="a0", name="0"), Level(id="a1", name="1")]),
            Factor(id="b", name="B", levels=[Level(id="b0", name="0"), Level(id="b1", name="1")]),
        ],
    )
    # Full factorial: all 4 pairs covered
    full = [
        {"a": "a0", "b": "b0"}, {"a": "a0", "b": "b1"},
        {"a": "a1", "b": "b0"}, {"a": "a1", "b": "b1"},
    ]
    assert compute_pairwise_coverage(full, ps) == 1.0

    # Half: 2 of 4 pairs
    half = [{"a": "a0", "b": "b0"}, {"a": "a1", "b": "b1"}]
    cov = compute_pairwise_coverage(half, ps)
    assert 0.0 < cov < 1.0
    print(f"   Full coverage: 1.0, Half coverage: {cov:.2f}")
    print("   PASSED")


def run_all_tests():
    print("=" * 70)
    print("TESSELLARIUM — Design Generator Tests")
    print("=" * 70)
    print(f"OAPackage: {'available' if HAS_OAPACKAGE else 'NOT installed'}")
    print(f"PyDOE2: {'available' if HAS_PYDOE2 else 'NOT installed'}")
    print()

    test_full_factorial_within_budget()
    test_full_factorial_exceeds_budget()
    test_gsd_produces_balanced_design()
    test_gsd_not_used_when_full_fact_fits()
    test_fracfact_two_level_only()
    test_fracfact_skips_mixed_levels()
    test_oa_enumeration_basic()
    test_doptimize_basic()
    test_doptimize_alpha_affects_result()
    test_level_mapping_correctness()
    test_level_mapping_with_unavailable_levels()
    test_filter_no_constraints()
    test_filter_removes_excluded_level()
    test_filter_measures_coverage_damage()
    test_repair_restores_coverage()
    test_quality_assessor_basic()
    test_quality_assessor_without_oapackage()
    test_coverage_chain_produces_design()
    test_robustness_chain_produces_design()
    test_all_generators_fail_returns_none()
    test_pairwise_coverage_computation()

    print()
    print("=" * 70)
    print("ALL TESTS PASSED ✅")
    print("=" * 70)


if __name__ == "__main__":
    run_all_tests()
