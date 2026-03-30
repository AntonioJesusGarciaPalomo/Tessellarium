"""
Tessellarium — Explainer Agent Test

Tests offline Decision Card generation with mock grounding results.
All tests work offline — no Azure OpenAI or AI Search calls.
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.models.problem_space import (
    ProblemSpace, Factor, Level, Hypothesis, Evidence,
    Constraint, ExperimentCandidate, DesignMatrix,
    DiscriminationPair, DecisionCard, CandidateStrategy,
    DesignFamily, EpistemicState,
)
from app.agents.explainer_agent import ExplainerAgent


def _make_agent() -> ExplainerAgent:
    return ExplainerAgent.create_offline()


def _make_ps(**kwargs) -> ProblemSpace:
    defaults = dict(
        objective="Determine root cause of yield drop",
        factors=[
            Factor(
                id="temp", name="Temperature",
                levels=[
                    Level(id="t20", name="20°C"),
                    Level(id="t30", name="30°C"),
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
                       epistemic_state=EpistemicState.SUPPORTED,
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
        total_combinations=8,
    )
    defaults.update(kwargs)
    return ProblemSpace(**defaults)


def _make_candidate(**kwargs) -> ExperimentCandidate:
    defaults = dict(
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
        justification="Selected 2 runs for max discrimination.",
    )
    defaults.update(kwargs)
    return ExperimentCandidate(**defaults)


def _make_grounding() -> list[dict]:
    return [
        {
            "id": "ev-1",
            "content": "Yield dropped 15% in last 3 batches (all used lot C at 30°C)",
            "citation_text": "E1 [csv_analysis]: Yield dropped 15% — protocol-RSA.pdf",
            "source_type": "evidence",
            "confidence": 0.7,
            "score": 0.95,
        },
        {
            "id": "hyp-2",
            "content": "Hypothesis H2: Lot C is degraded [supported]",
            "citation_text": "H2: Lot C is degraded [supported] — protocol-RSA.pdf",
            "source_type": "protocol",
            "confidence": 0.8,
            "score": 0.88,
        },
    ]


def test_decision_card_structure():
    """Offline card has all 6 required fields."""
    print("Test: Decision card has all 6 fields")

    agent = _make_agent()
    ps = _make_ps()
    candidate = _make_candidate()
    grounding = _make_grounding()

    card = agent.explain_offline(ps, candidate, grounding)

    assert isinstance(card, DecisionCard)
    assert card.recommendation, "recommendation must not be empty"
    assert card.why, "why must not be empty"
    assert len(card.evidence_used) > 0, "must have evidence_used"
    assert len(card.assumptions) > 0, "must have assumptions"
    assert len(card.counterevidence_or_limits) > 0, "must have limits"
    assert card.what_would_change_mind, "must have what_would_change_mind"
    print("   PASSED")


def test_card_stored_on_candidate():
    """Decision card is stored in candidate.decision_card."""
    print("Test: Card stored on candidate")

    agent = _make_agent()
    ps = _make_ps()
    candidate = _make_candidate()
    card = agent.explain_offline(ps, candidate, _make_grounding())

    assert candidate.decision_card is card
    print("   PASSED")


def test_grounding_citations_present():
    """Evidence_used references grounding results."""
    print("Test: Grounding citations in evidence_used")

    agent = _make_agent()
    ps = _make_ps()
    candidate = _make_candidate()
    grounding = _make_grounding()

    card = agent.explain_offline(ps, candidate, grounding)

    assert any("[1]" in e for e in card.evidence_used)
    assert any("[2]" in e for e in card.evidence_used)
    assert any("evidence" in e.lower() or "csv" in e.lower()
               for e in card.evidence_used)
    print("   PASSED")


def test_citation_refs_in_why():
    """Why field cites evidence with [N] references."""
    print("Test: Citation references in why field")

    agent = _make_agent()
    ps = _make_ps()
    candidate = _make_candidate()
    grounding = _make_grounding()

    card = agent.explain_offline(ps, candidate, grounding)

    assert "[1]" in card.why or "[2]" in card.why, \
        f"Expected citation refs in why, got: {card.why}"
    print("   PASSED")


def test_no_grounding_fallback():
    """Without grounding results, card still generated with disclaimer."""
    print("Test: No grounding — fallback explanation")

    agent = _make_agent()
    ps = _make_ps()
    candidate = _make_candidate()

    card = agent.explain_offline(ps, candidate, grounding_results=[])

    assert card.recommendation
    assert card.why
    assert any("no grounding" in e.lower() or "design properties" in e.lower()
               for e in card.evidence_used)
    print("   PASSED")


def test_recommendation_mentions_strategy():
    """Recommendation includes the strategy and run count."""
    print("Test: Recommendation includes strategy info")

    agent = _make_agent()
    ps = _make_ps()
    candidate = _make_candidate()

    card = agent.explain_offline(ps, candidate, _make_grounding())

    assert "2" in card.recommendation  # num_runs
    assert "max_discrimination" in card.recommendation or "covering" in card.recommendation
    print("   PASSED")


def test_assumptions_include_constraints():
    """Assumptions reference unavailable levels."""
    print("Test: Assumptions reference constraints")

    agent = _make_agent()
    ps = _make_ps()
    candidate = _make_candidate()

    card = agent.explain_offline(ps, candidate, _make_grounding())

    assert any("Lot C" in a or "unavailable" in a for a in card.assumptions)
    assert any("budget" in a.lower() or "4 runs" in a for a in card.assumptions)
    print("   PASSED")


def test_weakest_pair_in_change_mind():
    """What_would_change_mind references the weakest hypothesis pair."""
    print("Test: Weakest pair in what_would_change_mind")

    agent = _make_agent()
    ps = _make_ps()
    candidate = _make_candidate()

    card = agent.explain_offline(ps, candidate, _make_grounding())

    assert "H1" in card.what_would_change_mind
    assert "H2" in card.what_would_change_mind
    print("   PASSED")


def test_critique_informs_limits():
    """Critic review feeds into counterevidence_or_limits."""
    print("Test: Critique informs limits")

    agent = _make_agent()
    ps = _make_ps()
    candidate = _make_candidate(
        critique="4. COVERAGE GAPS: H1 vs H2 power is only 0.500."
    )

    card = agent.explain_offline(ps, candidate, _make_grounding())

    assert any("COVERAGE" in l or "0.500" in l for l in card.counterevidence_or_limits)
    print("   PASSED")


def test_user_message_has_grounding_context():
    """User message includes GROUNDING CONTEXT section."""
    print("Test: User message includes grounding context")

    agent = _make_agent()
    ps = _make_ps()
    candidate = _make_candidate()
    grounding = _make_grounding()

    msg = agent._build_user_message(ps, candidate, grounding)

    assert "GROUNDING CONTEXT" in msg
    assert "[1]" in msg
    assert "[2]" in msg
    assert "Yield dropped 15%" in msg
    assert "OBJECTIVE" in msg
    assert "CANDIDATE" in msg
    print("   PASSED")


def test_user_message_no_grounding():
    """User message handles empty grounding gracefully."""
    print("Test: User message with no grounding")

    agent = _make_agent()
    ps = _make_ps()
    candidate = _make_candidate()

    msg = agent._build_user_message(ps, candidate, grounding_results=None)

    assert "GROUNDING CONTEXT" in msg
    assert "No grounding evidence" in msg
    print("   PASSED")


def test_build_decision_card_from_json():
    """_build_decision_card parses LLM JSON output."""
    print("Test: Build DecisionCard from JSON")

    parsed = {
        "recommendation": "Run 4 experiments",
        "why": "Based on evidence [1] and [2].",
        "evidence_used": ["[1] source A", "[2] source B"],
        "assumptions": ["assumption 1"],
        "counterevidence_or_limits": ["limit 1"],
        "what_would_change_mind": "If X changes.",
    }

    card = ExplainerAgent._build_decision_card(parsed)

    assert isinstance(card, DecisionCard)
    assert card.recommendation == "Run 4 experiments"
    assert "[1]" in card.why
    assert len(card.evidence_used) == 2
    print("   PASSED")


def run_all_tests():
    print("=" * 70)
    print("TESSELLARIUM — Explainer Agent Tests")
    print("=" * 70)
    print()

    test_decision_card_structure()
    test_card_stored_on_candidate()
    test_grounding_citations_present()
    test_citation_refs_in_why()
    test_no_grounding_fallback()
    test_recommendation_mentions_strategy()
    test_assumptions_include_constraints()
    test_weakest_pair_in_change_mind()
    test_critique_informs_limits()
    test_user_message_has_grounding_context()
    test_user_message_no_grounding()
    test_build_decision_card_from_json()

    print()
    print("=" * 70)
    print("ALL TESTS PASSED ✅")
    print("=" * 70)


if __name__ == "__main__":
    run_all_tests()
