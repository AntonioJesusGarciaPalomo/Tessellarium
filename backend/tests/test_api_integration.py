"""
Tessellarium — API Integration Test

Tests the FastAPI endpoints end-to-end using TestClient.
All tests work offline — uses in-memory session storage.
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from fastapi.testclient import TestClient
from main import app
from app.models.problem_space import (
    ProblemSpace, Factor, Level, Hypothesis, EpistemicState,
)


client = TestClient(app)


def test_health():
    """Health endpoint returns OK."""
    print("Test: GET /health")
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["app"] == "Tessellarium"
    print("   PASSED")


def test_set_and_get_session():
    """POST /api/problem-space/{id} then GET /api/session/{id}."""
    print("Test: Set and get session")

    ps = ProblemSpace(
        id="test-api-001",
        objective="Test objective",
        factors=[
            Factor(
                id="f1", name="Factor 1",
                levels=[Level(id="f1l1", name="Low"), Level(id="f1l2", name="High")],
            ),
        ],
        hypotheses=[
            Hypothesis(id="H1", statement="Test hypothesis",
                       distinguishing_factors=["f1"]),
            Hypothesis(id="H2", statement="Alternative",
                       distinguishing_factors=["f1"]),
        ],
        max_runs_budget=4,
    )

    response = client.post(
        "/api/problem-space/test-api-001",
        json=ps.model_dump(mode="json"),
    )
    assert response.status_code == 200

    response = client.get("/api/session/test-api-001")
    assert response.status_code == 200
    data = response.json()
    assert data["objective"] == "Test objective"
    assert len(data["factors"]) == 1
    print("   PASSED")


def test_compile():
    """POST /api/compile produces 3 candidates."""
    print("Test: Compile endpoint")

    ps = ProblemSpace(
        id="test-api-compile",
        objective="Determine root cause of yield drop",
        factors=[
            Factor(id="temp", name="Temperature",
                   levels=[Level(id="t20", name="20C"), Level(id="t30", name="30C")]),
            Factor(id="lot", name="Reagent Lot",
                   levels=[Level(id="lotA", name="Lot A"), Level(id="lotB", name="Lot B")]),
        ],
        hypotheses=[
            Hypothesis(id="H1", statement="Temperature causes yield drop",
                       distinguishing_factors=["temp"]),
            Hypothesis(id="H2", statement="Lot causes yield drop",
                       distinguishing_factors=["lot"]),
        ],
        max_runs_budget=3,
    )

    client.post("/api/problem-space/test-api-compile", json=ps.model_dump(mode="json"))

    response = client.post("/api/compile", json={"session_id": "test-api-compile"})
    assert response.status_code == 200
    data = response.json()
    assert data["safety_verdict"] == "allow"
    assert len(data["candidates"]) == 3

    for c in data["candidates"]:
        assert c["design_matrix"]["num_runs"] > 0
        assert c["strategy"] in ("max_discrimination", "max_robustness", "max_coverage")

    print("   PASSED")


def test_compile_not_found():
    """POST /api/compile with invalid session returns 404."""
    print("Test: Compile with invalid session")
    response = client.post("/api/compile", json={"session_id": "nonexistent"})
    assert response.status_code == 404
    print("   PASSED")


def test_add_constraint_and_recompile():
    """POST /api/constrain/{id} recalculates."""
    print("Test: Add constraint and recompile")

    ps = ProblemSpace(
        id="test-api-constrain",
        objective="Test constraint",
        factors=[
            Factor(id="temp", name="Temperature",
                   levels=[Level(id="t20", name="20C"), Level(id="t30", name="30C"), Level(id="t40", name="40C")]),
            Factor(id="lot", name="Reagent Lot",
                   levels=[Level(id="lotA", name="A"), Level(id="lotB", name="B"), Level(id="lotC", name="C")]),
        ],
        hypotheses=[
            Hypothesis(id="H1", statement="Temp issue", distinguishing_factors=["temp"]),
            Hypothesis(id="H2", statement="Lot issue", distinguishing_factors=["lot"]),
        ],
        max_runs_budget=4,
    )

    client.post("/api/problem-space/test-api-constrain", json=ps.model_dump(mode="json"))

    r1 = client.post("/api/compile", json={"session_id": "test-api-constrain"})
    assert r1.status_code == 200
    total_before = r1.json()["problem_space"]["total_combinations"]

    r2 = client.post("/api/constrain/test-api-constrain", json={
        "description": "Lot C exhausted",
        "constraint_type": "material_unavailable",
        "excluded_factor_id": "lot",
        "excluded_level_id": "lotC",
    })
    assert r2.status_code == 200
    total_after = r2.json()["problem_space"]["total_combinations"]

    assert total_after < total_before, f"{total_after} < {total_before}"
    print(f"   Before: {total_before}, After: {total_after}")
    print("   PASSED")


def test_sessions_list():
    """GET /api/sessions returns saved sessions."""
    print("Test: List sessions")
    response = client.get("/api/sessions")
    assert response.status_code == 200
    assert isinstance(response.json(), list)
    print("   PASSED")


def run_all_tests():
    print("=" * 70)
    print("TESSELLARIUM — API Integration Tests")
    print("=" * 70)
    print()

    test_health()
    test_set_and_get_session()
    test_compile()
    test_compile_not_found()
    test_add_constraint_and_recompile()
    test_sessions_list()

    print()
    print("=" * 70)
    print("ALL TESTS PASSED ✅")
    print("=" * 70)


if __name__ == "__main__":
    run_all_tests()
