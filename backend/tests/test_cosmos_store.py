"""
Tessellarium — Cosmos Store Serialization Test

Tests ProblemSpace serialization roundtrip: model_dump → model_validate.
Works offline without Cosmos DB — validates that the data model survives
JSON serialization as it would through Cosmos DB storage.
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.models.problem_space import (
    ProblemSpace, Factor, Level, Hypothesis, Evidence,
    Constraint, ExperimentalRun, EpistemicState, OperativeState,
    SafetyVerdict,
)


def test_serialization_roundtrip():
    """Create a rich ProblemSpace, serialize, deserialize, assert equality."""

    print("=" * 70)
    print("TESSELLARIUM — Cosmos Store Serialization Test")
    print("=" * 70)

    # Build a ProblemSpace with all field types populated
    ps = ProblemSpace(
        id="test-session-001",
        objective="Determine root cause of yield drop",
        factors=[
            Factor(
                id="temp", name="Temperature",
                levels=[
                    Level(id="t20", name="20°C", value="20"),
                    Level(id="t30", name="30°C", value="30"),
                    Level(id="t40", name="40°C", value="40"),
                ],
            ),
            Factor(
                id="lot", name="Reagent Lot",
                levels=[
                    Level(id="lotA", name="Lot A"),
                    Level(id="lotB", name="Lot B"),
                    Level(id="lotC", name="Lot C", available=False),
                ],
                is_safety_sensitive=True,
            ),
        ],
        hypotheses=[
            Hypothesis(
                id="H1",
                statement="Temperature drift causes yield drop",
                epistemic_state=EpistemicState.SUPPORTED,
                operative_state=OperativeState.DESIGNED,
                distinguishing_factors=["temp"],
                evidence_ids=["E1"],
            ),
            Hypothesis(
                id="H2",
                statement="Lot C is degraded",
                epistemic_state=EpistemicState.SPECULATIVE,
                distinguishing_factors=["lot"],
            ),
        ],
        evidence=[
            Evidence(
                id="E1",
                source_type="csv_analysis",
                content="Yield dropped 15% in last 3 batches",
                supports_hypotheses=["H1"],
                challenges_hypotheses=["H2"],
                confidence=0.7,
                source_reference="results.csv:row42",
            ),
        ],
        constraints=[
            Constraint(
                id="C1",
                description="Lot C is exhausted",
                constraint_type="material_unavailable",
                excluded_factor_id="lot",
                excluded_level_id="lotC",
                is_safety_constraint=False,
            ),
        ],
        completed_runs=[
            ExperimentalRun(
                id="R1",
                combination={"temp": "t20", "lot": "lotA"},
                result_summary="Yield: 92%",
                evidence_ids=["E1"],
            ),
        ],
        max_runs_budget=4,
        safety_verdict=SafetyVerdict.DEGRADE,
        safety_notes=["Factor 'Reagent Lot' flagged for review"],
        protocol_filename="protocol.pdf",
        csv_filename="results.csv",
    )

    # Phase 1: Serialize with mode="json" (as CosmosStore does)
    print("\n1. Serializing ProblemSpace with model_dump(mode='json')...")
    doc = ps.model_dump(mode="json")
    doc["id"] = ps.id  # Cosmos requires top-level 'id'

    assert isinstance(doc, dict), "model_dump should return a dict"
    assert doc["id"] == "test-session-001"
    assert isinstance(doc["created_at"], str), "datetime should serialize to string"
    assert isinstance(doc["updated_at"], str), "datetime should serialize to string"
    print(f"   Serialized to dict with {len(doc)} top-level keys")
    print(f"   created_at type: {type(doc['created_at']).__name__} = {doc['created_at']}")

    # Phase 2: Deserialize back to ProblemSpace
    print("\n2. Deserializing back with ProblemSpace.model_validate()...")
    ps2 = ProblemSpace.model_validate(doc)
    print(f"   Deserialized ProblemSpace id={ps2.id}")

    # Phase 3: Assert structural equality
    print("\n3. Asserting structural equality...")

    assert ps2.id == ps.id, f"id mismatch: {ps2.id} != {ps.id}"
    assert ps2.objective == ps.objective
    assert len(ps2.factors) == len(ps.factors), "factors count mismatch"
    assert len(ps2.hypotheses) == len(ps.hypotheses), "hypotheses count mismatch"
    assert len(ps2.evidence) == len(ps.evidence), "evidence count mismatch"
    assert len(ps2.constraints) == len(ps.constraints), "constraints count mismatch"
    assert len(ps2.completed_runs) == len(ps.completed_runs), "completed_runs count mismatch"

    # Check factors deeply
    for i, (f1, f2) in enumerate(zip(ps.factors, ps2.factors)):
        assert f1.id == f2.id, f"factor[{i}].id mismatch"
        assert f1.name == f2.name, f"factor[{i}].name mismatch"
        assert len(f1.levels) == len(f2.levels), f"factor[{i}].levels count mismatch"
        assert f1.is_safety_sensitive == f2.is_safety_sensitive
        for j, (l1, l2) in enumerate(zip(f1.levels, f2.levels)):
            assert l1.id == l2.id, f"factor[{i}].level[{j}].id mismatch"
            assert l1.name == l2.name
            assert l1.value == l2.value
            assert l1.available == l2.available
    print("   Factors: OK")

    # Check hypotheses deeply
    for i, (h1, h2) in enumerate(zip(ps.hypotheses, ps2.hypotheses)):
        assert h1.id == h2.id
        assert h1.statement == h2.statement
        assert h1.epistemic_state == h2.epistemic_state
        assert h1.operative_state == h2.operative_state
        assert h1.distinguishing_factors == h2.distinguishing_factors
        assert h1.evidence_ids == h2.evidence_ids
    print("   Hypotheses: OK")

    # Check evidence
    for i, (e1, e2) in enumerate(zip(ps.evidence, ps2.evidence)):
        assert e1.id == e2.id
        assert e1.source_type == e2.source_type
        assert e1.content == e2.content
        assert e1.supports_hypotheses == e2.supports_hypotheses
        assert e1.challenges_hypotheses == e2.challenges_hypotheses
        assert e1.confidence == e2.confidence
        assert e1.source_reference == e2.source_reference
    print("   Evidence: OK")

    # Check constraints
    for i, (c1, c2) in enumerate(zip(ps.constraints, ps2.constraints)):
        assert c1.id == c2.id
        assert c1.description == c2.description
        assert c1.constraint_type == c2.constraint_type
        assert c1.excluded_factor_id == c2.excluded_factor_id
        assert c1.excluded_level_id == c2.excluded_level_id
        assert c1.is_safety_constraint == c2.is_safety_constraint
    print("   Constraints: OK")

    # Check completed runs
    for i, (r1, r2) in enumerate(zip(ps.completed_runs, ps2.completed_runs)):
        assert r1.id == r2.id
        assert r1.combination == r2.combination
        assert r1.result_summary == r2.result_summary
        assert r1.evidence_ids == r2.evidence_ids
    print("   Completed runs: OK")

    # Check scalar fields
    assert ps2.max_runs_budget == ps.max_runs_budget
    assert ps2.safety_verdict == ps.safety_verdict
    assert ps2.safety_notes == ps.safety_notes
    assert ps2.protocol_filename == ps.protocol_filename
    assert ps2.csv_filename == ps.csv_filename
    print("   Scalar fields: OK")

    # Check datetime roundtrip
    assert ps2.created_at == ps.created_at, "created_at datetime mismatch after roundtrip"
    assert ps2.updated_at == ps.updated_at, "updated_at datetime mismatch after roundtrip"
    print("   Datetimes: OK")

    # Phase 4: Verify model_dump → model_dump idempotency
    print("\n4. Verifying double-roundtrip idempotency...")
    doc2 = ps2.model_dump(mode="json")
    doc2["id"] = ps2.id
    ps3 = ProblemSpace.model_validate(doc2)
    assert ps3.id == ps.id
    assert len(ps3.factors) == len(ps.factors)
    assert len(ps3.hypotheses) == len(ps.hypotheses)
    print("   Double roundtrip: OK")

    print("\n" + "=" * 70)
    print("ALL TESTS PASSED ✅")
    print("=" * 70)


if __name__ == "__main__":
    test_serialization_roundtrip()
