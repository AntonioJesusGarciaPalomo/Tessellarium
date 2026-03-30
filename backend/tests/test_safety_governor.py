"""
Tessellarium — Safety Governor Test

Tests the deterministic regex-based safety checks WITHOUT the Content Safety API.
All tests work offline.
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.models.problem_space import (
    ProblemSpace, Factor, Level, Hypothesis, Evidence,
    Constraint, SafetyVerdict, EpistemicState,
)
from app.safety.governor import SafetyGovernor


def _make_ps(**kwargs) -> ProblemSpace:
    """Create a minimal ProblemSpace with optional overrides."""
    defaults = dict(
        objective="Determine root cause of yield drop",
        factors=[
            Factor(
                id="temp", name="Temperature",
                levels=[Level(id="t20", name="20°C"), Level(id="t30", name="30°C")],
            ),
        ],
        hypotheses=[
            Hypothesis(id="H1", statement="Temperature causes yield drop"),
        ],
    )
    defaults.update(kwargs)
    return ProblemSpace(**defaults)


def test_verdict_ordering():
    """SafetyVerdict comparison: BLOCK > DEGRADE > ALLOW."""
    print("Test: Verdict ordering")

    assert SafetyGovernor._max_verdict(SafetyVerdict.ALLOW, SafetyVerdict.ALLOW) == SafetyVerdict.ALLOW
    assert SafetyGovernor._max_verdict(SafetyVerdict.ALLOW, SafetyVerdict.DEGRADE) == SafetyVerdict.DEGRADE
    assert SafetyGovernor._max_verdict(SafetyVerdict.DEGRADE, SafetyVerdict.ALLOW) == SafetyVerdict.DEGRADE
    assert SafetyGovernor._max_verdict(SafetyVerdict.ALLOW, SafetyVerdict.BLOCK) == SafetyVerdict.BLOCK
    assert SafetyGovernor._max_verdict(SafetyVerdict.BLOCK, SafetyVerdict.ALLOW) == SafetyVerdict.BLOCK
    assert SafetyGovernor._max_verdict(SafetyVerdict.DEGRADE, SafetyVerdict.BLOCK) == SafetyVerdict.BLOCK
    assert SafetyGovernor._max_verdict(SafetyVerdict.BLOCK, SafetyVerdict.DEGRADE) == SafetyVerdict.BLOCK
    assert SafetyGovernor._max_verdict(SafetyVerdict.BLOCK, SafetyVerdict.BLOCK) == SafetyVerdict.BLOCK

    print("   PASSED")


def test_allow_safe_content():
    """Normal scientific content should be ALLOW."""
    print("Test: ALLOW for safe content")

    ps = _make_ps()
    governor = SafetyGovernor(ps)
    verdict = governor.evaluate()

    assert verdict == SafetyVerdict.ALLOW, f"Expected ALLOW, got {verdict.value}"
    assert len(ps.safety_notes) == 0
    print("   PASSED")


def test_allow_with_query():
    """Normal scientific query should be ALLOW."""
    print("Test: ALLOW with safe query")

    ps = _make_ps()
    governor = SafetyGovernor(ps)
    verdict = governor.evaluate(user_query="Which temperature gives the best yield?")

    assert verdict == SafetyVerdict.ALLOW, f"Expected ALLOW, got {verdict.value}"
    print("   PASSED")


def test_degrade_clinical_factor():
    """Factor with clinical terms → DEGRADE."""
    print("Test: DEGRADE for clinical factor")

    ps = _make_ps(
        factors=[
            Factor(
                id="dose", name="Drug dosage",
                levels=[
                    Level(id="d1", name="10mg"),
                    Level(id="d2", name="20mg"),
                ],
            ),
        ],
    )
    governor = SafetyGovernor(ps)
    verdict = governor.evaluate()

    assert verdict == SafetyVerdict.DEGRADE, f"Expected DEGRADE, got {verdict.value}"
    assert any("clinical" in note.lower() or "drug" in note.lower() for note in ps.safety_notes)
    assert ps.factors[0].is_safety_sensitive is True
    print("   PASSED")


def test_degrade_biohazard_factor():
    """Factor with bio-hazard terms → DEGRADE."""
    print("Test: DEGRADE for bio-hazard factor")

    ps = _make_ps(
        factors=[
            Factor(
                id="vec", name="Viral vector type",
                levels=[
                    Level(id="v1", name="AAV"),
                    Level(id="v2", name="Lentivirus"),
                ],
            ),
        ],
    )
    governor = SafetyGovernor(ps)
    verdict = governor.evaluate()

    assert verdict == SafetyVerdict.DEGRADE, f"Expected DEGRADE, got {verdict.value}"
    assert any("hazard" in note.lower() or "biological" in note.lower() for note in ps.safety_notes)
    print("   PASSED")


def test_degrade_clinical_hypothesis():
    """Hypothesis with clinical content → DEGRADE."""
    print("Test: DEGRADE for clinical hypothesis")

    ps = _make_ps(
        hypotheses=[
            Hypothesis(
                id="H1",
                statement="The patient's prognosis improves with the new treatment plan",
                epistemic_state=EpistemicState.SPECULATIVE,
            ),
        ],
    )
    governor = SafetyGovernor(ps)
    verdict = governor.evaluate()

    assert verdict == SafetyVerdict.DEGRADE, f"Expected DEGRADE, got {verdict.value}"
    assert any("clinical" in note.lower() for note in ps.safety_notes)
    print("   PASSED")


def test_degrade_clinical_query():
    """Query with clinical terms (but not advisory) → DEGRADE."""
    print("Test: DEGRADE for clinical query")

    ps = _make_ps()
    governor = SafetyGovernor(ps)
    verdict = governor.evaluate(user_query="What is the patient's prognosis?")

    assert verdict == SafetyVerdict.DEGRADE, f"Expected DEGRADE, got {verdict.value}"
    assert any("clinical" in note.lower() for note in ps.safety_notes)
    print("   PASSED")


def test_block_advisory_query():
    """Query requesting clinical advice → BLOCK."""
    print("Test: BLOCK for advisory query")

    ps = _make_ps()
    governor = SafetyGovernor(ps)
    verdict = governor.evaluate(user_query="What dose should I administer to the patient?")

    assert verdict == SafetyVerdict.BLOCK, f"Expected BLOCK, got {verdict.value}"
    assert any("advice" in note.lower() or "recommendation" in note.lower() for note in ps.safety_notes)
    print("   PASSED")


def test_block_advisory_objective():
    """Objective with advisory language → BLOCK."""
    print("Test: BLOCK for advisory objective")

    ps = _make_ps(
        objective="Recommend taking this medication for the patient"
    )
    governor = SafetyGovernor(ps)
    verdict = governor.evaluate()

    assert verdict == SafetyVerdict.BLOCK, f"Expected BLOCK, got {verdict.value}"
    assert any("objective" in note.lower() for note in ps.safety_notes)
    print("   PASSED")


def test_degrade_adds_constraint():
    """DEGRADE should add a safety constraint to the ProblemSpace."""
    print("Test: DEGRADE adds safety constraint")

    ps = _make_ps(
        factors=[
            Factor(
                id="med", name="Medication type",
                levels=[
                    Level(id="m1", name="Aspirin"),
                    Level(id="m2", name="Ibuprofen"),
                ],
            ),
        ],
    )
    initial_constraints = len(ps.constraints)
    governor = SafetyGovernor(ps)
    verdict = governor.evaluate()

    assert verdict == SafetyVerdict.DEGRADE
    assert len(ps.constraints) > initial_constraints, "Should have added a safety constraint"
    safety_constraints = [c for c in ps.constraints if c.is_safety_constraint]
    assert len(safety_constraints) > 0, "Should have at least one safety constraint"
    print("   PASSED")


def test_no_api_still_works():
    """Without Content Safety service, regex-only mode works fine."""
    print("Test: No API — regex-only mode")

    ps = _make_ps()
    governor = SafetyGovernor(ps, content_safety_service=None)
    verdict = governor.evaluate()

    assert verdict == SafetyVerdict.ALLOW
    print("   PASSED")


def test_block_overrides_degrade():
    """If both DEGRADE and BLOCK triggers are present, BLOCK wins."""
    print("Test: BLOCK overrides DEGRADE")

    ps = _make_ps(
        factors=[
            Factor(
                id="dose", name="Drug dosage",
                levels=[Level(id="d1", name="10mg"), Level(id="d2", name="20mg")],
            ),
        ],
    )
    governor = SafetyGovernor(ps)
    # Factor triggers DEGRADE, query triggers BLOCK
    verdict = governor.evaluate(user_query="What dose should I administer to the patient?")

    assert verdict == SafetyVerdict.BLOCK, f"Expected BLOCK, got {verdict.value}"
    print("   PASSED")


def test_degradation_report():
    """get_degradation_report() returns structured information."""
    print("Test: Degradation report")

    ps = _make_ps(
        factors=[
            Factor(
                id="med", name="Medication type",
                levels=[Level(id="m1", name="Aspirin"), Level(id="m2", name="Ibuprofen")],
            ),
        ],
    )
    governor = SafetyGovernor(ps)
    governor.evaluate()

    report = governor.get_degradation_report()
    assert report["verdict"] == "degrade"
    assert len(report["excluded_factors"]) > 0
    assert len(report["notes"]) > 0
    assert "excluded" in report["message"].lower() or "safety" in report["message"].lower()
    print("   PASSED")


def run_all_tests():
    print("=" * 70)
    print("TESSELLARIUM — Safety Governor Tests")
    print("=" * 70)
    print()

    test_verdict_ordering()
    test_allow_safe_content()
    test_allow_with_query()
    test_degrade_clinical_factor()
    test_degrade_biohazard_factor()
    test_degrade_clinical_hypothesis()
    test_degrade_clinical_query()
    test_block_advisory_query()
    test_block_advisory_objective()
    test_degrade_adds_constraint()
    test_no_api_still_works()
    test_block_overrides_degrade()
    test_degradation_report()

    print()
    print("=" * 70)
    print("ALL TESTS PASSED ✅")
    print("=" * 70)


if __name__ == "__main__":
    run_all_tests()
