"""
Tessellarium — Critic Agent Test

Tests the deterministic offline critique logic.
All tests work offline — no Azure OpenAI calls.
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.models.problem_space import (
    ProblemSpace, Factor, Level, Hypothesis, Evidence,
    Constraint, ExperimentCandidate, DesignMatrix,
    DiscriminationPair, CandidateStrategy, DesignFamily,
    EpistemicState,
)
from app.agents.critic_agent import CriticAgent


def _make_ps(**kwargs) -> ProblemSpace:
    """Create the demo ProblemSpace."""
    defaults = dict(
        objective="Determine root cause of yield drop",
        factors=[
            Factor(
                id="temp", name="Temperature",
                levels=[
                    Level(id="t20", name="20°C"),
                    Level(id="t30", name="30°C"),
                    Level(id="t40", name="40°C"),
                ],
            ),
            Factor(
                id="lot", name="Reagent Lot",
                levels=[
                    Level(id="lotA", name="Lot A"),
                    Level(id="lotB", name="Lot B"),
                    Level(id="lotC", name="Lot C", available=False),
                ],
            ),
        ],
        hypotheses=[
            Hypothesis(id="H1", statement="Temperature causes yield drop",
                       distinguishing_factors=["temp"]),
            Hypothesis(id="H2", statement="Lot C is degraded",
                       distinguishing_factors=["lot"]),
        ],
        constraints=[
            Constraint(
                id="C1", description="Lot C exhausted",
                constraint_type="material_unavailable",
                excluded_factor_id="lot", excluded_level_id="lotC",
            ),
        ],
        max_runs_budget=4,
    )
    defaults.update(kwargs)
    return ProblemSpace(**defaults)


def _make_agent() -> CriticAgent:
    return CriticAgent.__new__(CriticAgent)


def test_critique_has_all_sections():
    """Offline critique produces all 6 required sections."""
    print("Test: All 6 sections present")

    agent = _make_agent()
    ps = _make_ps()
    candidate = ExperimentCandidate(
        strategy=CandidateStrategy.MAX_DISCRIMINATION,
        design_matrix=DesignMatrix(
            rows=[
                {"temp": "t20", "lot": "lotA"},
                {"temp": "t30", "lot": "lotB"},
            ],
            num_runs=2,
            design_family=DesignFamily.COVERING_ARRAY,
        ),
        discrimination_pairs=[
            DiscriminationPair(
                hypothesis_a_id="H1", hypothesis_b_id="H2",
                discriminating_combinations=[{"temp": "t20", "lot": "lotB"}],
                discrimination_power=0.5,
            ),
        ],
        total_discrimination_score=0.5,
        justification="Test candidate.",
    )

    critique = agent.critique_offline(ps, candidate)

    assert "1. OBJECTIVE ALIGNMENT" in critique
    assert "2. CONSTRAINT SATISFACTION" in critique
    assert "3. CONFOUNDING RISK" in critique
    assert "4. COVERAGE GAPS" in critique
    assert "5. REDUNDANCY" in critique
    assert "6. WEAKEST LINK" in critique
    assert candidate.critique == critique
    print("   PASSED")


def test_constraint_violation_detected():
    """Critique detects excluded level in design matrix."""
    print("Test: Constraint violation detection")

    agent = _make_agent()
    ps = _make_ps()
    candidate = ExperimentCandidate(
        strategy=CandidateStrategy.MAX_COVERAGE,
        design_matrix=DesignMatrix(
            rows=[
                {"temp": "t20", "lot": "lotA"},
                {"temp": "t30", "lot": "lotC"},  # VIOLATION
            ],
            num_runs=2,
            design_family=DesignFamily.CUSTOM,
        ),
        discrimination_pairs=[],
        total_discrimination_score=0.0,
        justification="Test.",
    )

    critique = agent.critique_offline(ps, candidate)

    assert "excluded level" in critique.lower() or "lotC" in critique
    print("   PASSED")


def test_budget_violation_detected():
    """Critique detects runs exceeding budget."""
    print("Test: Budget violation detection")

    agent = _make_agent()
    ps = _make_ps(max_runs_budget=2)
    candidate = ExperimentCandidate(
        strategy=CandidateStrategy.MAX_DISCRIMINATION,
        design_matrix=DesignMatrix(
            rows=[
                {"temp": "t20", "lot": "lotA"},
                {"temp": "t30", "lot": "lotA"},
                {"temp": "t40", "lot": "lotB"},
            ],
            num_runs=3,
            design_family=DesignFamily.COVERING_ARRAY,
        ),
        discrimination_pairs=[],
        total_discrimination_score=0.0,
        justification="Test.",
    )

    critique = agent.critique_offline(ps, candidate)

    assert "budget" in critique.lower() or "3 runs" in critique
    print("   PASSED")


def test_confounding_detected():
    """Critique detects confounded factors."""
    print("Test: Confounding detection")

    agent = _make_agent()
    ps = _make_ps()
    # Factors always co-vary: temp and lot change in lockstep
    candidate = ExperimentCandidate(
        strategy=CandidateStrategy.MAX_DISCRIMINATION,
        design_matrix=DesignMatrix(
            rows=[
                {"temp": "t20", "lot": "lotA"},
                {"temp": "t30", "lot": "lotB"},
            ],
            num_runs=2,
            design_family=DesignFamily.COVERING_ARRAY,
        ),
        discrimination_pairs=[],
        total_discrimination_score=0.0,
        justification="Test.",
    )

    critique = agent.critique_offline(ps, candidate)

    assert "confound" in critique.lower()
    assert "Temperature" in critique or "Reagent" in critique
    print("   PASSED")


def test_no_confounding_when_independent():
    """No confounding when factors vary independently."""
    print("Test: No confounding for independent factors")

    agent = _make_agent()
    ps = _make_ps()
    candidate = ExperimentCandidate(
        strategy=CandidateStrategy.MAX_DISCRIMINATION,
        design_matrix=DesignMatrix(
            rows=[
                {"temp": "t20", "lot": "lotA"},
                {"temp": "t20", "lot": "lotB"},
                {"temp": "t30", "lot": "lotA"},
                {"temp": "t30", "lot": "lotB"},
            ],
            num_runs=4,
            design_family=DesignFamily.FULL_FACTORIAL,
        ),
        discrimination_pairs=[
            DiscriminationPair(
                hypothesis_a_id="H1", hypothesis_b_id="H2",
                discriminating_combinations=[{"temp": "t20", "lot": "lotB"}],
                discrimination_power=0.5,
            ),
        ],
        total_discrimination_score=0.5,
        justification="Full factorial.",
    )

    critique = agent.critique_offline(ps, candidate)

    assert "No issues identified" in critique.split("CONFOUNDING RISK:")[1].split("\n")[0]
    print("   PASSED")


def test_low_coverage_flagged():
    """Critique flags low discrimination power."""
    print("Test: Low coverage gap detection")

    agent = _make_agent()
    ps = _make_ps()
    candidate = ExperimentCandidate(
        strategy=CandidateStrategy.MAX_DISCRIMINATION,
        design_matrix=DesignMatrix(
            rows=[{"temp": "t20", "lot": "lotA"}],
            num_runs=1,
            design_family=DesignFamily.CUSTOM,
        ),
        discrimination_pairs=[
            DiscriminationPair(
                hypothesis_a_id="H1", hypothesis_b_id="H2",
                discriminating_combinations=[{"temp": "t20", "lot": "lotA"}],
                discrimination_power=0.1,
            ),
        ],
        total_discrimination_score=0.1,
        justification="Test.",
    )

    critique = agent.critique_offline(ps, candidate)

    assert "0.100" in critique or "H1 vs H2" in critique
    print("   PASSED")


def test_redundancy_detected():
    """Critique detects duplicate runs."""
    print("Test: Redundancy detection")

    agent = _make_agent()
    ps = _make_ps()
    candidate = ExperimentCandidate(
        strategy=CandidateStrategy.MAX_ROBUSTNESS,
        design_matrix=DesignMatrix(
            rows=[
                {"temp": "t20", "lot": "lotA"},
                {"temp": "t30", "lot": "lotB"},
                {"temp": "t20", "lot": "lotA"},  # DUPLICATE of run 1
            ],
            num_runs=3,
            design_family=DesignFamily.CUSTOM,
        ),
        discrimination_pairs=[],
        total_discrimination_score=0.0,
        justification="Test.",
    )

    critique = agent.critique_offline(ps, candidate)

    assert "identical" in critique.lower() or "Run 3" in critique
    print("   PASSED")


def test_weakest_link_identified():
    """Critique identifies the weakest hypothesis pair."""
    print("Test: Weakest link identification")

    agent = _make_agent()
    ps = _make_ps()
    candidate = ExperimentCandidate(
        strategy=CandidateStrategy.MAX_DISCRIMINATION,
        design_matrix=DesignMatrix(
            rows=[{"temp": "t20", "lot": "lotA"}],
            num_runs=1,
            design_family=DesignFamily.CUSTOM,
        ),
        discrimination_pairs=[
            DiscriminationPair(
                hypothesis_a_id="H1", hypothesis_b_id="H2",
                discriminating_combinations=[{"temp": "t20"}],
                discrimination_power=0.8,
            ),
            DiscriminationPair(
                hypothesis_a_id="H1", hypothesis_b_id="H3",
                discriminating_combinations=[],
                discrimination_power=0.1,
            ),
        ],
        total_discrimination_score=0.45,
        justification="Test.",
    )

    critique = agent.critique_offline(ps, candidate)

    assert "H1 vs H3" in critique
    assert "0.100" in critique
    assert "hardest to distinguish" in critique.lower()
    print("   PASSED")


def test_clean_design_no_issues():
    """Clean design should have No issues identified in most sections."""
    print("Test: Clean design — no false positives")

    agent = _make_agent()
    ps = _make_ps(constraints=[], max_runs_budget=10)
    candidate = ExperimentCandidate(
        strategy=CandidateStrategy.MAX_COVERAGE,
        design_matrix=DesignMatrix(
            rows=[
                {"temp": "t20", "lot": "lotA"},
                {"temp": "t20", "lot": "lotB"},
                {"temp": "t30", "lot": "lotA"},
                {"temp": "t30", "lot": "lotB"},
            ],
            num_runs=4,
            design_family=DesignFamily.FULL_FACTORIAL,
        ),
        discrimination_pairs=[
            DiscriminationPair(
                hypothesis_a_id="H1", hypothesis_b_id="H2",
                discriminating_combinations=[
                    {"temp": "t20", "lot": "lotB"},
                    {"temp": "t30", "lot": "lotB"},
                ],
                discrimination_power=0.5,
            ),
        ],
        total_discrimination_score=0.5,
        justification="Full factorial.",
    )

    critique = agent.critique_offline(ps, candidate)

    assert "CONSTRAINT SATISFACTION: No issues" in critique
    assert "CONFOUNDING RISK: No issues" in critique
    assert "REDUNDANCY: No issues" in critique
    print("   PASSED")


def test_user_message_building():
    """_build_user_message produces complete context for the LLM."""
    print("Test: User message building")

    agent = _make_agent()
    ps = _make_ps()
    candidate = ExperimentCandidate(
        strategy=CandidateStrategy.MAX_DISCRIMINATION,
        design_matrix=DesignMatrix(
            rows=[{"temp": "t20", "lot": "lotA"}],
            num_runs=1,
            design_family=DesignFamily.CUSTOM,
        ),
        discrimination_pairs=[],
        total_discrimination_score=0.0,
        justification="Test.",
    )

    msg = agent._build_user_message(ps, candidate)

    assert "OBJECTIVE" in msg
    assert "yield drop" in msg
    assert "FACTORS" in msg
    assert "Temperature" in msg
    assert "HYPOTHESES" in msg
    assert "H1" in msg
    assert "CONSTRAINTS" in msg
    assert "Lot C exhausted" in msg
    assert "BUDGET" in msg
    assert "CANDIDATE" in msg
    assert "max_discrimination" in msg
    print("   PASSED")


def run_all_tests():
    print("=" * 70)
    print("TESSELLARIUM — Critic Agent Tests")
    print("=" * 70)
    print()

    test_critique_has_all_sections()
    test_constraint_violation_detected()
    test_budget_violation_detected()
    test_confounding_detected()
    test_no_confounding_when_independent()
    test_low_coverage_flagged()
    test_redundancy_detected()
    test_weakest_link_identified()
    test_clean_design_no_issues()
    test_user_message_building()

    print()
    print("=" * 70)
    print("ALL TESTS PASSED ✅")
    print("=" * 70)


if __name__ == "__main__":
    run_all_tests()
