"""
Tessellarium — Critic Agent

Reviews DOE Planner candidates and identifies weaknesses.
The Critic ONLY critiques. It does NOT propose alternatives.
It does NOT modify the design. It identifies problems.

This is a pure reasoning agent — no tools, no retrieval.
"""

import json
import os
from typing import Optional

from app.models.problem_space import (
    ProblemSpace, ExperimentCandidate,
)
from app.agents.foundry_client import AgentBase, get_foundry_client


CRITIC_SYSTEM_PROMPT = """You are the Critic Agent of Tessellarium, a decisive experiment compiler.

Your ONLY job is to identify weaknesses in a proposed experimental design.
You do NOT suggest alternatives. You do NOT modify the design.
You do NOT propose new experiments. You ONLY critique.

Given:
- The experimental objective
- The factors, levels, hypotheses, and constraints
- A candidate design (strategy, design matrix, discrimination pairs, justification)

Analyze and report:

1. OBJECTIVE ALIGNMENT: Does this design actually address the stated objective? Could a researcher run these experiments and answer the question?

2. CONSTRAINT SATISFACTION: Are all constraints respected? Check that excluded levels do not appear in the design matrix. Check that the number of runs does not exceed the budget.

3. CONFOUNDING RISK: Are there factors that always co-vary in the selected runs? If factor A and factor B always change together, their effects cannot be separated. List any confounded pairs.

4. COVERAGE GAPS: Which hypothesis pairs have low discrimination power in this design? What factor-level combinations are missing that would be informative?

5. REDUNDANCY: Are there runs in the matrix that provide no additional discrimination value beyond what other runs already provide? Identify any redundant runs.

6. WEAKEST LINK: What is the single weakest aspect of this design? What is the hypothesis pair that is hardest to distinguish with this design?

Return your critique as structured text with these 6 numbered sections.
Be specific — reference factor names, hypothesis IDs, and run numbers.
Be concise — each section should be 1-3 sentences.
If a section has no issues, say "No issues identified."

RULES:
- Do NOT suggest what to do instead. Only say what is wrong.
- Do NOT generate alternative designs.
- Do NOT change any aspect of the input.
- Be honest. If the design is solid, say so. Do not invent problems."""


class CriticAgent(AgentBase):
    """
    Reviews DOE Planner candidates for weaknesses.
    Uses GPT-4o-mini for analytical critique. No tools.

    Foundry agent name: tessellarium-critic
    """

    def __init__(
        self,
        azure_endpoint: Optional[str] = None,
        api_key: Optional[str] = None,
        api_version: str = "2025-12-01-preview",
        model: str = "gpt-4o-mini",
        foundry_client=None,
    ):
        super().__init__(
            model=model,
            foundry_client=foundry_client or get_foundry_client(),
            azure_endpoint=azure_endpoint,
            api_key=api_key,
            api_version=api_version,
        )

    async def critique(
        self,
        problem_space: ProblemSpace,
        candidate: ExperimentCandidate,
    ) -> str:
        """
        Critique a single candidate design.
        Returns a structured critique string stored in candidate.critique.
        """
        user_message = self._build_user_message(problem_space, candidate)

        critique_text = await self._call_llm(
            system_prompt=CRITIC_SYSTEM_PROMPT,
            user_message=user_message,
            temperature=0.3,
            max_tokens=1500,
        )

        candidate.critique = critique_text
        return critique_text

    def critique_sync(
        self,
        problem_space: ProblemSpace,
        candidate: ExperimentCandidate,
    ) -> str:
        """Synchronous version for testing (direct mode only)."""
        user_message = self._build_user_message(problem_space, candidate)

        critique_text = self._call_llm_sync(
            system_prompt=CRITIC_SYSTEM_PROMPT,
            user_message=user_message,
            temperature=0.3,
            max_tokens=1500,
        )

        candidate.critique = critique_text
        return critique_text

    @classmethod
    def create_offline(cls) -> "CriticAgent":
        """Create an instance for offline use (no LLM credentials needed)."""
        instance = cls.__new__(cls)
        instance.model = "offline"
        instance._foundry = None
        instance._direct_client = None
        return instance

    def critique_offline(
        self,
        problem_space: ProblemSpace,
        candidate: ExperimentCandidate,
    ) -> str:
        """
        Offline deterministic critique — no LLM call.
        Performs the same structural checks programmatically.
        Used for testing and as a baseline.
        """
        sections = []

        # 1. Objective alignment
        if problem_space.objective:
            sections.append(
                f"1. OBJECTIVE ALIGNMENT: The design proposes "
                f"{candidate.design_matrix.num_runs} runs using "
                f"{candidate.strategy.value} strategy to address: "
                f"\"{problem_space.objective}\". "
                f"{'Alignment appears reasonable.' if candidate.total_discrimination_score > 0 else 'No discrimination — design may not address the objective.'}"
            )
        else:
            sections.append(
                "1. OBJECTIVE ALIGNMENT: No objective stated. "
                "Cannot assess alignment."
            )

        # 2. Constraint satisfaction
        constraint_issues = self._check_constraints(problem_space, candidate)
        if constraint_issues:
            sections.append(
                f"2. CONSTRAINT SATISFACTION: {'; '.join(constraint_issues)}"
            )
        else:
            sections.append(
                "2. CONSTRAINT SATISFACTION: No issues identified."
            )

        # 3. Confounding risk
        confounded = self._check_confounding(problem_space, candidate)
        if confounded:
            sections.append(
                f"3. CONFOUNDING RISK: {'; '.join(confounded)}"
            )
        else:
            sections.append(
                "3. CONFOUNDING RISK: No issues identified."
            )

        # 4. Coverage gaps
        gaps = self._check_coverage_gaps(problem_space, candidate)
        if gaps:
            sections.append(f"4. COVERAGE GAPS: {'; '.join(gaps)}")
        else:
            sections.append("4. COVERAGE GAPS: No issues identified.")

        # 5. Redundancy
        redundant = self._check_redundancy(candidate)
        if redundant:
            sections.append(f"5. REDUNDANCY: {'; '.join(redundant)}")
        else:
            sections.append("5. REDUNDANCY: No issues identified.")

        # 6. Weakest link
        weakest = self._find_weakest_link(candidate)
        sections.append(f"6. WEAKEST LINK: {weakest}")

        critique_text = "\n\n".join(sections)
        candidate.critique = critique_text
        return critique_text

    def _build_user_message(
        self,
        ps: ProblemSpace,
        candidate: ExperimentCandidate,
    ) -> str:
        """Assemble the user message for the LLM."""
        parts = []

        parts.append(f"=== OBJECTIVE ===\n{ps.objective}\n")

        parts.append("=== FACTORS ===")
        for f in ps.factors:
            levels = ", ".join(
                f"{l.name}{'*' if not l.available else ''}"
                for l in f.levels
            )
            parts.append(f"  {f.id}: {f.name} — levels: [{levels}]")
        parts.append("")

        parts.append("=== HYPOTHESES ===")
        for h in ps.hypotheses:
            parts.append(
                f"  {h.id}: {h.statement} "
                f"[{h.epistemic_state.value}] "
                f"distinguishing factors: {h.distinguishing_factors}"
            )
        parts.append("")

        parts.append("=== CONSTRAINTS ===")
        if ps.constraints:
            for c in ps.constraints:
                parts.append(f"  {c.id}: {c.description} (type: {c.constraint_type})")
        else:
            parts.append("  (none)")
        parts.append("")

        parts.append(f"=== BUDGET ===\nMax runs: {ps.max_runs_budget or 'unlimited'}\n")

        parts.append(
            f"=== CANDIDATE: {candidate.strategy.value} ===\n"
            f"Design family: {candidate.design_matrix.design_family.value}\n"
            f"Runs: {candidate.design_matrix.num_runs}\n"
            f"Discrimination score: {candidate.total_discrimination_score}\n"
            f"Justification: {candidate.justification}\n"
        )

        parts.append("Design matrix:")
        for i, row in enumerate(candidate.design_matrix.rows):
            labels = []
            for fid, lid in row.items():
                factor = ps.get_factor_by_id(fid)
                level = None
                if factor:
                    level = next(
                        (l for l in factor.levels if l.id == lid), None
                    )
                labels.append(
                    f"{factor.name if factor else fid}="
                    f"{level.name if level else lid}"
                )
            parts.append(f"  Run {i+1}: {', '.join(labels)}")
        parts.append("")

        if candidate.discrimination_pairs:
            parts.append("Discrimination pairs:")
            for pair in candidate.discrimination_pairs:
                parts.append(
                    f"  {pair.hypothesis_a_id} vs {pair.hypothesis_b_id}: "
                    f"power={pair.discrimination_power:.3f} "
                    f"({len(pair.discriminating_combinations)} combos)"
                )

        return "\n".join(parts)

    # ─── Deterministic checks ────────────────────────────────────────

    @staticmethod
    def _check_constraints(
        ps: ProblemSpace, candidate: ExperimentCandidate,
    ) -> list[str]:
        """Check if all constraints are satisfied."""
        issues = []

        # Budget check
        budget = ps.max_runs_budget
        if budget and candidate.design_matrix.num_runs > budget:
            issues.append(
                f"Design has {candidate.design_matrix.num_runs} runs "
                f"but budget allows only {budget}"
            )

        # Excluded level check
        for constraint in ps.constraints:
            if constraint.excluded_factor_id and constraint.excluded_level_id:
                fid = constraint.excluded_factor_id
                lid = constraint.excluded_level_id
                for i, row in enumerate(candidate.design_matrix.rows):
                    if row.get(fid) == lid:
                        issues.append(
                            f"Run {i+1} uses excluded level "
                            f"{fid}={lid} ({constraint.description})"
                        )
        return issues

    @staticmethod
    def _check_confounding(
        ps: ProblemSpace, candidate: ExperimentCandidate,
    ) -> list[str]:
        """Check for factors that always co-vary."""
        issues = []
        rows = candidate.design_matrix.rows
        if len(rows) < 2:
            return issues

        factor_ids = list(rows[0].keys()) if rows else []
        for i, f1 in enumerate(factor_ids):
            for f2 in factor_ids[i + 1:]:
                # Check if f1 and f2 always change together
                pairs = set()
                for row in rows:
                    pairs.add((row.get(f1), row.get(f2)))
                # If the number of unique pairs equals the number of
                # unique values for each factor, they're confounded
                f1_vals = {row.get(f1) for row in rows}
                f2_vals = {row.get(f2) for row in rows}
                if (
                    len(f1_vals) > 1
                    and len(f2_vals) > 1
                    and len(pairs) == len(f1_vals)
                    and len(pairs) == len(f2_vals)
                ):
                    f1_name = f1
                    f2_name = f2
                    for f in ps.factors:
                        if f.id == f1:
                            f1_name = f.name
                        if f.id == f2:
                            f2_name = f.name
                    issues.append(
                        f"Factors {f1_name} and {f2_name} are confounded "
                        f"(always co-vary across {len(rows)} runs)"
                    )
        return issues

    @staticmethod
    def _check_coverage_gaps(
        ps: ProblemSpace, candidate: ExperimentCandidate,
    ) -> list[str]:
        """Check for hypothesis pairs with low discrimination."""
        issues = []
        for pair in candidate.discrimination_pairs:
            if pair.discrimination_power < 0.3:
                issues.append(
                    f"{pair.hypothesis_a_id} vs {pair.hypothesis_b_id}: "
                    f"discrimination power is only {pair.discrimination_power:.3f} "
                    f"({len(pair.discriminating_combinations)} discriminating combos)"
                )
        if not candidate.discrimination_pairs and len(ps.hypotheses) >= 2:
            issues.append(
                "No discrimination pairs — this design cannot distinguish "
                "between any hypotheses"
            )
        return issues

    @staticmethod
    def _check_redundancy(candidate: ExperimentCandidate) -> list[str]:
        """Check for duplicate runs in the design matrix."""
        issues = []
        seen = {}
        for i, row in enumerate(candidate.design_matrix.rows):
            key = tuple(sorted(row.items()))
            if key in seen:
                issues.append(
                    f"Run {i+1} is identical to run {seen[key]+1}"
                )
            else:
                seen[key] = i
        return issues

    @staticmethod
    def _find_weakest_link(candidate: ExperimentCandidate) -> str:
        """Find the weakest hypothesis pair."""
        if not candidate.discrimination_pairs:
            return "No discrimination pairs in this design."

        weakest = min(
            candidate.discrimination_pairs,
            key=lambda p: p.discrimination_power,
        )
        return (
            f"Weakest pair: {weakest.hypothesis_a_id} vs "
            f"{weakest.hypothesis_b_id} with discrimination power "
            f"{weakest.discrimination_power:.3f} "
            f"({len(weakest.discriminating_combinations)} combos). "
            f"This pair is hardest to distinguish."
        )


# ─── Standalone test ─────────────────────────────────────────────────────────

def test_critic_offline():
    """
    Test the Critic Agent WITHOUT calling Azure OpenAI.
    Uses the deterministic offline critique method.
    """
    from app.models.problem_space import (
        Factor, Level, Hypothesis, Evidence, Constraint,
        ExperimentalRun, EpistemicState, DesignMatrix,
        DiscriminationPair, CandidateStrategy, DesignFamily,
    )

    print("=" * 70)
    print("TESSELLARIUM — Critic Agent Offline Test")
    print("=" * 70)

    # Build a problem space
    ps = ProblemSpace(
        objective="Determine root cause of yield drop in recent batches",
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
            Factor(
                id="time", name="Incubation Time",
                levels=[
                    Level(id="t1h", name="1 hour"),
                    Level(id="t2h", name="2 hours"),
                ],
            ),
        ],
        hypotheses=[
            Hypothesis(
                id="H1",
                statement="Temperature drift causes yield drop",
                epistemic_state=EpistemicState.SPECULATIVE,
                distinguishing_factors=["temp"],
            ),
            Hypothesis(
                id="H2",
                statement="Reagent lot C is degraded",
                epistemic_state=EpistemicState.SUPPORTED,
                distinguishing_factors=["lot"],
            ),
            Hypothesis(
                id="H3",
                statement="Incubation time insufficient",
                epistemic_state=EpistemicState.SPECULATIVE,
                distinguishing_factors=["time"],
            ),
        ],
        constraints=[
            Constraint(
                id="C1",
                description="Lot C exhausted",
                constraint_type="material_unavailable",
                excluded_factor_id="lot",
                excluded_level_id="lotC",
            ),
        ],
        max_runs_budget=4,
    )

    # Build a candidate
    candidate = ExperimentCandidate(
        id="cand-test",
        strategy=CandidateStrategy.MAX_DISCRIMINATION,
        design_matrix=DesignMatrix(
            rows=[
                {"temp": "t20", "lot": "lotA", "time": "t1h"},
                {"temp": "t30", "lot": "lotB", "time": "t2h"},
                {"temp": "t40", "lot": "lotA", "time": "t1h"},
                {"temp": "t20", "lot": "lotB", "time": "t2h"},
            ],
            num_runs=4,
            design_family=DesignFamily.COVERING_ARRAY,
        ),
        discrimination_pairs=[
            DiscriminationPair(
                hypothesis_a_id="H1",
                hypothesis_b_id="H2",
                discriminating_combinations=[
                    {"temp": "t20", "lot": "lotB", "time": "t2h"},
                    {"temp": "t30", "lot": "lotB", "time": "t2h"},
                ],
                discrimination_power=0.5,
            ),
            DiscriminationPair(
                hypothesis_a_id="H1",
                hypothesis_b_id="H3",
                discriminating_combinations=[
                    {"temp": "t40", "lot": "lotA", "time": "t1h"},
                ],
                discrimination_power=0.25,
            ),
            DiscriminationPair(
                hypothesis_a_id="H2",
                hypothesis_b_id="H3",
                discriminating_combinations=[
                    {"temp": "t20", "lot": "lotA", "time": "t1h"},
                    {"temp": "t20", "lot": "lotB", "time": "t2h"},
                ],
                discrimination_power=0.5,
            ),
        ],
        total_discrimination_score=0.417,
        justification="Selected 4 runs optimized for maximum discrimination.",
    )

    # Run offline critique
    agent = CriticAgent.__new__(CriticAgent)
    critique = agent.critique_offline(ps, candidate)

    print(f"\n{critique}")

    # Verify critique was stored
    assert candidate.critique is not None, "Critique should be stored"
    assert "OBJECTIVE ALIGNMENT" in critique
    assert "CONSTRAINT SATISFACTION" in critique
    assert "CONFOUNDING RISK" in critique
    assert "COVERAGE GAPS" in critique
    assert "REDUNDANCY" in critique
    assert "WEAKEST LINK" in critique

    # Test with a constraint violation
    print("\n" + "─" * 70)
    print("Test: Constraint violation detection")
    bad_candidate = ExperimentCandidate(
        id="cand-bad",
        strategy=CandidateStrategy.MAX_COVERAGE,
        design_matrix=DesignMatrix(
            rows=[
                {"temp": "t20", "lot": "lotA", "time": "t1h"},
                {"temp": "t30", "lot": "lotC", "time": "t2h"},  # VIOLATION
            ],
            num_runs=2,
            design_family=DesignFamily.CUSTOM,
        ),
        discrimination_pairs=[],
        total_discrimination_score=0.0,
        justification="Test candidate.",
    )

    bad_critique = agent.critique_offline(ps, bad_candidate)
    print(f"\n{bad_critique}")
    assert "excluded level" in bad_critique.lower() or "lotC" in bad_critique

    print(f"\n{'=' * 70}")
    print("CRITIC AGENT OFFLINE TEST PASSED ✅")
    print("=" * 70)


if __name__ == "__main__":
    test_critic_offline()
