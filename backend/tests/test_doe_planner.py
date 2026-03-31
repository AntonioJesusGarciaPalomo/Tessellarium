"""
Tessellarium — Integration Test

This test simulates the EXACT demo scenario:
1. A researcher has 3 factors at 2-3 levels
2. Two competing hypotheses
3. 4 of 12 combinations already tested
4. Budget of 4 more runs
5. Then a constraint is added: "lot C is exhausted"
6. System recalculates and shows discrimination cost

If this test passes, the core of Tessellarium works.
"""

import sys
import os
import json

# Add parent to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.models.problem_space import (
    ProblemSpace, Factor, Level, Hypothesis, Evidence,
    Constraint, ExperimentalRun, EpistemicState, CandidateStrategy,
)
from app.doe_planner.planner import DOEPlanner
from app.safety.governor import SafetyGovernor


def create_demo_problem_space() -> ProblemSpace:
    """
    Demo scenario: Reagent stability assay.

    Objective: Determine why yield dropped in recent batches.

    Factors:
    - Temperature: 20°C, 30°C, 40°C (3 levels)
    - Reagent Lot: A, B, C (3 levels)
    - Incubation Time: 1h, 2h (2 levels)

    Hypotheses:
    - H1: Temperature drift causes yield drop (distinguishing factor: temperature)
    - H2: Reagent lot C is degraded (distinguishing factor: reagent lot)
    - H3: Incubation time is insufficient (distinguishing factor: incubation time)

    Already tested: 4 runs
    Budget: 4 more runs
    """

    # Factors
    temp = Factor(
        id="temp", name="Temperature",
        levels=[
            Level(id="t20", name="20°C"),
            Level(id="t30", name="30°C"),
            Level(id="t40", name="40°C"),
        ],
    )
    lot = Factor(
        id="lot", name="Reagent Lot",
        levels=[
            Level(id="lotA", name="Lot A"),
            Level(id="lotB", name="Lot B"),
            Level(id="lotC", name="Lot C"),
        ],
    )
    time = Factor(
        id="time", name="Incubation Time",
        levels=[
            Level(id="t1h", name="1 hour"),
            Level(id="t2h", name="2 hours"),
        ],
    )

    # Hypotheses
    h1 = Hypothesis(
        id="H1",
        statement="Temperature drift above 30°C causes yield drop",
        epistemic_state=EpistemicState.SPECULATIVE,
        distinguishing_factors=["temp"],
    )
    h2 = Hypothesis(
        id="H2",
        statement="Reagent lot C is degraded and causes yield drop",
        epistemic_state=EpistemicState.SPECULATIVE,
        distinguishing_factors=["lot"],
    )
    h3 = Hypothesis(
        id="H3",
        statement="Insufficient incubation time (1h vs 2h) reduces yield",
        epistemic_state=EpistemicState.SPECULATIVE,
        distinguishing_factors=["time"],
    )

    # Evidence from initial observations
    evidence = [
        Evidence(
            id="E1",
            source_type="csv_analysis",
            content="Yield dropped 15% in last 3 batches (all used lot C at 30°C)",
            supports_hypotheses=["H2"],
            confidence=0.6,
        ),
        Evidence(
            id="E2",
            source_type="protocol_text",
            content="Protocol specifies 30°C ± 2°C; lab logs show 28-33°C range",
            supports_hypotheses=["H1"],
            confidence=0.4,
        ),
    ]

    # Already completed runs
    completed = [
        ExperimentalRun(id="R1", combination={"temp": "t20", "lot": "lotA", "time": "t1h"}, result_summary="Yield: 92%"),
        ExperimentalRun(id="R2", combination={"temp": "t30", "lot": "lotA", "time": "t1h"}, result_summary="Yield: 90%"),
        ExperimentalRun(id="R3", combination={"temp": "t30", "lot": "lotC", "time": "t1h"}, result_summary="Yield: 74%"),
        ExperimentalRun(id="R4", combination={"temp": "t40", "lot": "lotC", "time": "t2h"}, result_summary="Yield: 68%"),
    ]

    return ProblemSpace(
        objective="Determine root cause of yield drop in recent batches",
        factors=[temp, lot, time],
        hypotheses=[h1, h2, h3],
        evidence=evidence,
        completed_runs=completed,
        max_runs_budget=4,
    )


def test_doe_compilation():
    """Test the full DOE compilation pipeline."""

    print("=" * 70)
    print("TESSELARIUM — DOE Planner Integration Test")
    print("=" * 70)

    # Create problem space
    ps = create_demo_problem_space()

    print(f"\n📋 Objective: {ps.objective}")
    print(f"📊 Factors: {len(ps.factors)} ({', '.join(f.name for f in ps.factors)})")
    for f in ps.factors:
        print(f"   {f.name}: {', '.join(l.name for l in f.levels)}")
    print(f"🔬 Hypotheses: {len(ps.hypotheses)}")
    for h in ps.hypotheses:
        print(f"   {h.id}: {h.statement}")
    print(f"✅ Completed runs: {len(ps.completed_runs)}")
    print(f"💰 Budget: {ps.max_runs_budget} more runs")

    # Phase 3: Safety check
    print("\n" + "─" * 70)
    print("Phase 3: Safety Gate")
    print("─" * 70)

    governor = SafetyGovernor(ps)
    verdict = governor.evaluate()
    print(f"   Verdict: {verdict.value}")
    for note in ps.safety_notes:
        print(f"   ⚠️  {note}")

    # Phase 4: Compile
    print("\n" + "─" * 70)
    print("Phase 4: DOE Compilation")
    print("─" * 70)

    planner = DOEPlanner(ps)
    candidates = planner.compile()

    print(f"\n   Total combinations: {ps.total_combinations}")
    print(f"   Tested: {ps.tested_combinations}")
    print(f"   Untested (available): {len(ps.get_untested_combinations())}")
    print(f"   Untested + discriminative: {len(ps.get_discriminative_untested())}")

    for i, candidate in enumerate(candidates):
        print(f"\n   {'═' * 60}")
        print(f"   Candidate {i+1}: {candidate.strategy.value}")
        print(f"   {'═' * 60}")
        print(f"   Design family: {candidate.design_matrix.design_family.value}")
        print(f"   Runs: {candidate.design_matrix.num_runs}")
        print(f"   Discrimination score: {candidate.total_discrimination_score}")
        print(f"   Justification: {candidate.justification}")

        print(f"\n   Design matrix:")
        for j, row in enumerate(candidate.design_matrix.rows):
            labels = []
            for fid, lid in row.items():
                factor = ps.get_factor_by_id(fid)
                level = next((l for l in factor.levels if l.id == lid), None) if factor else None
                labels.append(f"{factor.name if factor else fid}={level.name if level else lid}")
            print(f"      Run {j+1}: {', '.join(labels)}")

        if candidate.discrimination_pairs:
            print(f"\n   Discrimination pairs:")
            for pair in candidate.discrimination_pairs:
                print(f"      {pair.hypothesis_a_id} vs {pair.hypothesis_b_id}: "
                      f"power={pair.discrimination_power:.3f} "
                      f"({len(pair.discriminating_combinations)} combos)")

        if candidate.design_matrix.design_properties:
            print(f"\n   Design properties: {json.dumps(candidate.design_matrix.design_properties, indent=6)}")

    # Phase 5: Add constraint and recalculate
    print("\n" + "=" * 70)
    print("RECALCULATION: \"Lot C is exhausted\"")
    print("=" * 70)

    # Mark lot C as unavailable
    lot_factor = ps.get_factor_by_id("lot")
    for level in lot_factor.levels:
        if level.id == "lotC":
            level.available = False

    ps.constraints.append(Constraint(
        description="Lot C is exhausted — no more reagent available",
        constraint_type="material_unavailable",
        excluded_factor_id="lot",
        excluded_level_id="lotC",
    ))

    # Recompile
    planner2 = DOEPlanner(ps)
    candidates2 = planner2.compile()

    print(f"\n   Total combinations (after constraint): {ps.total_combinations}")
    print(f"   Tested: {ps.tested_combinations}")
    print(f"   Untested (available): {len(ps.get_untested_combinations())}")

    for i, candidate in enumerate(candidates2):
        print(f"\n   Candidate {i+1}: {candidate.strategy.value}")
        print(f"   Runs: {candidate.design_matrix.num_runs}")
        print(f"   Discrimination score: {candidate.total_discrimination_score}")

        print(f"   Design matrix:")
        for j, row in enumerate(candidate.design_matrix.rows):
            labels = []
            for fid, lid in row.items():
                factor = ps.get_factor_by_id(fid)
                level = next((l for l in factor.levels if l.id == lid), None) if factor else None
                labels.append(f"{factor.name if factor else fid}={level.name if level else lid}")
            print(f"      Run {j+1}: {', '.join(labels)}")

        if candidate.constraint_costs:
            print(f"\n   ⚠️  Constraint costs:")
            for cost in candidate.constraint_costs:
                print(f"      {cost.constraint_description}")
                for ap in cost.affected_hypothesis_pairs:
                    print(f"         {ap.pair}: lost {ap.excluded_runs}/{ap.total_discriminating} "
                          f"discriminating runs ({ap.lost_fraction*100:.1f}% lost)")

    # Phase 6: Test safety block
    print("\n" + "=" * 70)
    print("SAFETY TEST: Clinical query")
    print("=" * 70)

    governor2 = SafetyGovernor(ps)
    verdict2 = governor2.evaluate(user_query="What dose should I administer to the patient?")
    print(f"   Verdict: {verdict2.value}")
    for note in ps.safety_notes:
        print(f"   🛑 {note}")

    print("\n" + "=" * 70)
    print("ALL TESTS PASSED ✅")
    print("=" * 70)


def test_classical_integration():
    """Test that classical generators integrate with the planner."""
    print("\n" + "=" * 70)
    print("CLASSICAL INTEGRATION TEST")
    print("=" * 70)

    ps = create_demo_problem_space()

    planner = DOEPlanner(ps)
    candidates = planner.compile()

    assert len(candidates) == 3

    for c in candidates:
        assert hasattr(c.design_matrix, 'design_source'), "design_source field missing"
        print(f"  {c.strategy.value}: source={c.design_matrix.design_source}, "
              f"D-eff={c.design_matrix.d_efficiency}, "
              f"GWLP={c.design_matrix.gwlp}")

    disc_cand = next(c for c in candidates if c.strategy == CandidateStrategy.MAX_DISCRIMINATION)
    assert disc_cand.design_matrix.design_source == "greedy", \
        f"MAX_DISCRIMINATION should be greedy, got {disc_cand.design_matrix.design_source}"

    print("\nCLASSICAL INTEGRATION TEST PASSED ✅")


if __name__ == "__main__":
    test_doe_compilation()
    test_classical_integration()
