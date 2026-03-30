"""
Tessellarium — Search Service Chunk Extraction Test

Tests the data transformation logic for extracting indexable chunks
from ProblemSpace, ExperimentCandidate, and DecisionCard objects.
All tests work offline — no Azure AI Search calls.
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.models.problem_space import (
    ProblemSpace, Factor, Level, Hypothesis, Evidence,
    Constraint, ExperimentalRun, ExperimentCandidate,
    DesignMatrix, DiscriminationPair, DecisionCard, ConstraintCost,
    EpistemicState, OperativeState, CandidateStrategy, DesignFamily,
)
from app.services.search_service import SearchService


def _make_service() -> SearchService:
    """Create a SearchService with fake credentials (no actual connection)."""
    return SearchService.__new__(SearchService)


def _make_problem_space() -> ProblemSpace:
    """Create the demo ProblemSpace for testing."""
    return ProblemSpace(
        id="test-session-001",
        objective="Determine root cause of yield drop in recent batches",
        protocol_filename="protocol-RSA-2026.pdf",
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
                    Level(id="lotC", name="Lot C"),
                ],
                is_safety_sensitive=True,
            ),
        ],
        hypotheses=[
            Hypothesis(
                id="H1",
                statement="Temperature drift above 30°C causes yield drop",
                epistemic_state=EpistemicState.SPECULATIVE,
                distinguishing_factors=["temp"],
            ),
            Hypothesis(
                id="H2",
                statement="Reagent lot C is degraded",
                epistemic_state=EpistemicState.SUPPORTED,
                distinguishing_factors=["lot"],
                evidence_ids=["E1"],
            ),
        ],
        evidence=[
            Evidence(
                id="E1",
                source_type="csv_analysis",
                content="Yield dropped 15% in last 3 batches (all used lot C at 30°C)",
                supports_hypotheses=["H2"],
                confidence=0.7,
                source_reference="results.csv:row42",
            ),
            Evidence(
                id="E2",
                source_type="protocol_text",
                content="Protocol specifies 30°C ± 2°C; lab logs show 28-33°C range",
                supports_hypotheses=["H1"],
                confidence=0.4,
            ),
        ],
        constraints=[
            Constraint(
                id="C1",
                description="Lot C is exhausted — no more reagent available",
                constraint_type="material_unavailable",
                excluded_factor_id="lot",
                excluded_level_id="lotC",
            ),
        ],
    )


def _make_candidate() -> ExperimentCandidate:
    """Create a sample ExperimentCandidate."""
    return ExperimentCandidate(
        id="cand-001",
        strategy=CandidateStrategy.MAX_DISCRIMINATION,
        design_matrix=DesignMatrix(
            rows=[
                {"temp": "t20", "lot": "lotA"},
                {"temp": "t30", "lot": "lotB"},
                {"temp": "t40", "lot": "lotA"},
                {"temp": "t20", "lot": "lotB"},
            ],
            num_runs=4,
            design_family=DesignFamily.COVERING_ARRAY,
        ),
        discrimination_pairs=[
            DiscriminationPair(
                hypothesis_a_id="H1",
                hypothesis_b_id="H2",
                discriminating_combinations=[{"temp": "t20", "lot": "lotB"}],
                discrimination_power=0.75,
            ),
        ],
        total_discrimination_score=0.75,
        justification="Selected 4 runs optimized for maximum discrimination across 1 hypothesis pair.",
        constraint_costs=[
            ConstraintCost(
                constraint_id="C1",
                constraint_description="Lot C is exhausted",
                affected_hypothesis_pairs=[],
            ),
        ],
    )


def _make_decision_card() -> DecisionCard:
    """Create a sample DecisionCard."""
    return DecisionCard(
        recommendation="Run candidate A (max discrimination, 4 runs)",
        why="This candidate maximizes discrimination between H1 and H2 within the 4-run budget",
        evidence_used=["E1: yield dropped 15%", "E2: temperature range 28-33°C"],
        assumptions=["Lot A and B are comparable in purity", "Temperature control is ±2°C"],
        counterevidence_or_limits=["Only 2 of 3 lots tested", "No replication"],
        what_would_change_mind="If lot B shows the same yield drop as lot C, H2 is weakened",
    )


def test_problem_space_chunk_extraction():
    """Extract chunks from a ProblemSpace and verify structure."""
    print("Test: ProblemSpace chunk extraction")

    service = _make_service()
    ps = _make_problem_space()
    chunks = service._extract_problem_space_chunks(ps)

    # Should have: 1 objective + 2 factors + 2 hypotheses + 2 evidence + 1 constraint = 8
    assert len(chunks) == 8, f"Expected 8 chunks, got {len(chunks)}"

    # All chunks should have required fields
    required_fields = {
        "id", "session_id", "source_type", "artifact_type",
        "title", "content", "citation_text", "created_at",
    }
    for chunk in chunks:
        missing = required_fields - set(chunk.keys())
        assert not missing, f"Chunk {chunk['id']} missing fields: {missing}"
        assert chunk["session_id"] == "test-session-001"

    print(f"   Extracted {len(chunks)} chunks")
    print("   PASSED")


def test_objective_chunk():
    """Objective chunk has correct content and citation."""
    print("Test: Objective chunk content")

    service = _make_service()
    ps = _make_problem_space()
    chunks = service._extract_problem_space_chunks(ps)

    obj_chunks = [c for c in chunks if c["artifact_type"] == "objective"]
    assert len(obj_chunks) == 1

    obj = obj_chunks[0]
    assert "yield drop" in obj["content"]
    assert obj["source_type"] == "protocol"
    assert "Objective:" in obj["citation_text"]
    assert "protocol-RSA-2026.pdf" in obj["citation_text"]
    assert len(obj["factor_ids"]) == 2
    assert len(obj["hypothesis_ids"]) == 2

    print("   PASSED")


def test_factor_chunks():
    """Factor chunks have level names and citation text."""
    print("Test: Factor chunk content")

    service = _make_service()
    ps = _make_problem_space()
    chunks = service._extract_problem_space_chunks(ps)

    factor_chunks = [c for c in chunks if c["artifact_type"] == "factor"]
    assert len(factor_chunks) == 2

    temp_chunk = next(c for c in factor_chunks if "Temperature" in c["title"])
    assert "20°C" in temp_chunk["content"]
    assert "30°C" in temp_chunk["content"]
    assert "40°C" in temp_chunk["content"]
    assert temp_chunk["factor_ids"] == ["temp"]
    assert "Temperature" in temp_chunk["citation_text"]
    assert "20°C, 30°C, 40°C" in temp_chunk["citation_text"]

    lot_chunk = next(c for c in factor_chunks if "Reagent" in c["title"])
    assert "Safety-sensitive: True" in lot_chunk["content"]

    print("   PASSED")


def test_hypothesis_chunks():
    """Hypothesis chunks include epistemic state and distinguishing factors."""
    print("Test: Hypothesis chunk content")

    service = _make_service()
    ps = _make_problem_space()
    chunks = service._extract_problem_space_chunks(ps)

    hyp_chunks = [c for c in chunks if c["artifact_type"] == "hypothesis"]
    assert len(hyp_chunks) == 2

    h1 = next(c for c in hyp_chunks if "H1" in c["content"])
    assert "speculative" in h1["content"]
    assert "Temperature" in h1["content"]
    assert h1["hypothesis_ids"] == ["H1"]
    assert "[speculative]" in h1["citation_text"]

    h2 = next(c for c in hyp_chunks if "H2" in c["content"])
    assert "supported" in h2["content"]

    print("   PASSED")


def test_evidence_chunks():
    """Evidence chunks have confidence and source references."""
    print("Test: Evidence chunk content")

    service = _make_service()
    ps = _make_problem_space()
    chunks = service._extract_problem_space_chunks(ps)

    ev_chunks = [c for c in chunks if c["source_type"] == "evidence"]
    assert len(ev_chunks) == 2

    e1 = next(c for c in ev_chunks if "E1" in c["id"])
    assert e1["confidence"] == 0.7
    assert e1["source_url"] == "results.csv:row42"
    assert "H2" in e1["hypothesis_ids"]
    assert "csv_analysis" in e1["artifact_type"]

    print("   PASSED")


def test_constraint_chunks():
    """Constraint chunks reference the excluded factor."""
    print("Test: Constraint chunk content")

    service = _make_service()
    ps = _make_problem_space()
    chunks = service._extract_problem_space_chunks(ps)

    con_chunks = [c for c in chunks if c["artifact_type"] == "constraint"]
    assert len(con_chunks) == 1

    c1 = con_chunks[0]
    assert "Lot C is exhausted" in c1["content"]
    assert c1["factor_ids"] == ["lot"]
    assert c1["constraint_ids"] == ["C1"]
    assert "material_unavailable" in c1["content"]

    print("   PASSED")


def test_compilation_chunk_extraction():
    """Extract chunks from an ExperimentCandidate."""
    print("Test: Compilation chunk extraction")

    service = _make_service()
    ps = _make_problem_space()
    candidate = _make_candidate()
    chunks = service._extract_compilation_chunks(ps, candidate)

    assert len(chunks) == 1
    chunk = chunks[0]

    assert chunk["source_type"] == "compilation"
    assert chunk["artifact_type"] == "max_discrimination"
    assert "4" in chunk["content"]  # num_runs
    assert "covering_array" in chunk["content"]
    assert "0.750" in chunk["content"]  # discrimination score
    assert "Lot C is exhausted" in chunk["content"]
    assert chunk["confidence"] == 0.75
    assert "DOE compilation" in chunk["citation_text"]

    print("   PASSED")


def test_decision_card_chunk_extraction():
    """Extract chunks from a DecisionCard."""
    print("Test: Decision card chunk extraction")

    service = _make_service()
    card = _make_decision_card()
    chunks = service._extract_decision_card_chunks("test-session-001", card)

    assert len(chunks) == 1
    chunk = chunks[0]

    assert chunk["source_type"] == "decision_card"
    assert "max discrimination" in chunk["content"]
    assert "E1: yield dropped" in chunk["content"]
    assert "lot B shows the same yield" in chunk["content"]
    assert "Decision card:" in chunk["citation_text"]
    assert chunk["confidence"] == 0.9

    print("   PASSED")


def test_empty_problem_space():
    """Empty ProblemSpace produces no chunks."""
    print("Test: Empty ProblemSpace")

    service = _make_service()
    ps = ProblemSpace()
    chunks = service._extract_problem_space_chunks(ps)

    assert len(chunks) == 0
    print("   PASSED")


def test_filter_building():
    """OData filter expressions from dict."""
    print("Test: Filter expression building")

    assert SearchService._build_filter({"source_type": "protocol"}) == "source_type eq 'protocol'"
    assert SearchService._build_filter({"session_id": "abc", "source_type": "evidence"}) == \
        "session_id eq 'abc' and source_type eq 'evidence'"

    collection_filter = SearchService._build_filter({"hypothesis_ids": ["H1", "H2"]})
    assert "hypothesis_ids/any" in collection_filter
    assert "H1" in collection_filter
    assert "H2" in collection_filter

    print("   PASSED")


def test_chunk_ids_are_deterministic():
    """Same ProblemSpace produces same chunk IDs (idempotent indexing)."""
    print("Test: Deterministic chunk IDs")

    service = _make_service()
    ps = _make_problem_space()
    chunks1 = service._extract_problem_space_chunks(ps)
    chunks2 = service._extract_problem_space_chunks(ps)

    ids1 = sorted(c["id"] for c in chunks1)
    ids2 = sorted(c["id"] for c in chunks2)
    assert ids1 == ids2, "Chunk IDs should be deterministic"

    print("   PASSED")


def run_all_tests():
    print("=" * 70)
    print("TESSELLARIUM — Search Service Chunk Extraction Tests")
    print("=" * 70)
    print()

    test_problem_space_chunk_extraction()
    test_objective_chunk()
    test_factor_chunks()
    test_hypothesis_chunks()
    test_evidence_chunks()
    test_constraint_chunks()
    test_compilation_chunk_extraction()
    test_decision_card_chunk_extraction()
    test_empty_problem_space()
    test_filter_building()
    test_chunk_ids_are_deterministic()

    print()
    print("=" * 70)
    print("ALL TESTS PASSED ✅")
    print("=" * 70)


if __name__ == "__main__":
    run_all_tests()
