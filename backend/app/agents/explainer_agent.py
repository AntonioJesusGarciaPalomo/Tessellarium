"""
Tessellarium — Explainer Agent

Generates six-field Decision Cards grounded in evidence from the
Semantic Citation Layer. Every claim MUST be cited.
"""

import json
import os
from typing import Optional

from app.models.problem_space import (
    ProblemSpace, ExperimentCandidate, DecisionCard,
)
from app.agents.foundry_client import AgentBase, get_foundry_client


EXPLAINER_SYSTEM_PROMPT = """You are the Explainer Agent of Tessellarium, a decisive experiment compiler.

Your ONLY job is to generate a structured Decision Card that explains WHY a specific experimental design was recommended. You translate deterministic compiler output into human-readable explanations.

You MUST ground every claim in evidence from the GROUNDING CONTEXT provided.
Cite evidence using numbered references [1], [2], etc.
Do NOT make claims without citation. If no relevant evidence is found, say "No grounding evidence available" and explain based on the design properties alone.

Return ONLY a valid JSON object with these 6 fields:

{
  "recommendation": "One-sentence summary of the recommended design",
  "why": "2-3 sentences explaining WHY this design was chosen, citing evidence as [1], [2], etc.",
  "evidence_used": ["[1] description of source", "[2] description of source"],
  "assumptions": ["assumption 1", "assumption 2"],
  "counterevidence_or_limits": ["limitation or counterevidence 1", "limitation 2"],
  "what_would_change_mind": "What new observation would change this recommendation"
}

RULES:
1. Be specific — reference factor names, hypothesis IDs, and actual numbers.
2. Every factual claim in "why" MUST have a citation [N] that maps to an entry in "evidence_used".
3. "evidence_used" entries must reference actual sources from the GROUNDING CONTEXT.
4. "assumptions" should list what must be true for this recommendation to hold.
5. "counterevidence_or_limits" should honestly state what challenges this design or what it cannot do.
6. "what_would_change_mind" should describe a concrete, testable observation.
7. Do NOT suggest alternative designs. Only explain this one.
8. Return ONLY the JSON object. No explanation, no markdown, no commentary."""


class ExplainerAgent(AgentBase):
    """
    Generates grounded Decision Cards for DOE Planner candidates.
    Uses GPT-4o with evidence from the Semantic Citation Layer.

    Foundry agent name: tessellarium-explainer
    """

    def __init__(
        self,
        azure_endpoint: Optional[str] = None,
        api_key: Optional[str] = None,
        api_version: str = "2025-12-01-preview",
        model: str = "gpt-4o",
        foundry_client=None,
    ):
        super().__init__(
            model=model,
            foundry_client=foundry_client or get_foundry_client(),
            azure_endpoint=azure_endpoint,
            api_key=api_key,
            api_version=api_version,
        )

    async def explain(
        self,
        problem_space: ProblemSpace,
        candidate: ExperimentCandidate,
        grounding_results: Optional[list[dict]] = None,
    ) -> DecisionCard:
        """
        Generate a Decision Card for a candidate, grounded in search results.
        """
        user_message = self._build_user_message(
            problem_space, candidate, grounding_results,
        )

        raw_json = await self._call_llm(
            system_prompt=EXPLAINER_SYSTEM_PROMPT,
            user_message=user_message,
            temperature=0.2,
            max_tokens=2000,
            response_format={"type": "json_object"},
        )

        parsed = json.loads(raw_json)
        card = self._build_decision_card(parsed)
        candidate.decision_card = card
        return card

    @classmethod
    def create_offline(cls) -> "ExplainerAgent":
        """Create an instance for offline use (no LLM credentials needed)."""
        instance = cls.__new__(cls)
        instance.model = "offline"
        instance._foundry = None
        instance._direct_client = None
        return instance

    def explain_offline(
        self,
        problem_space: ProblemSpace,
        candidate: ExperimentCandidate,
        grounding_results: Optional[list[dict]] = None,
    ) -> DecisionCard:
        """
        Offline Decision Card generation — no LLM call.
        Builds a deterministic card from the candidate's properties
        and available grounding evidence.
        """
        grounding = grounding_results or []
        dm = candidate.design_matrix
        ps = problem_space

        # Build evidence_used from grounding results
        evidence_used = []
        for i, result in enumerate(grounding[:5], 1):
            source = result.get("source_type", "unknown")
            citation = result.get("citation_text", result.get("content", "")[:100])
            evidence_used.append(f"[{i}] {citation} (source: {source})")

        # Build citations string for the why field
        citation_refs = ""
        if evidence_used:
            refs = ", ".join(f"[{i}]" for i in range(1, len(evidence_used) + 1))
            citation_refs = f" Based on available evidence {refs}."

        # Gather factor names
        factor_names = ", ".join(f.name for f in ps.factors)

        # Gather discrimination info
        disc_info = ""
        if candidate.discrimination_pairs:
            pair_parts = []
            for pair in candidate.discrimination_pairs:
                pair_parts.append(
                    f"{pair.hypothesis_a_id} vs {pair.hypothesis_b_id} "
                    f"(power: {pair.discrimination_power:.3f})"
                )
            disc_info = f" Discrimination pairs: {'; '.join(pair_parts)}."

        # Gather constraint costs
        cost_info = ""
        if candidate.constraint_costs:
            cost_parts = []
            for cost in candidate.constraint_costs:
                desc = cost.constraint_description
                if desc:
                    cost_parts.append(desc)
            if cost_parts:
                cost_info = f" Active constraints: {'; '.join(cost_parts)}."

        # Build assumptions
        assumptions = []
        for f in ps.factors:
            unavailable = [l for l in f.levels if not l.available]
            if unavailable:
                assumptions.append(
                    f"Factor '{f.name}' levels "
                    f"{', '.join(l.name for l in unavailable)} "
                    f"remain unavailable"
                )
        if ps.max_runs_budget:
            assumptions.append(
                f"Budget of {ps.max_runs_budget} runs is a hard constraint"
            )
        if not assumptions:
            assumptions.append("All factor levels are available and accessible")

        # Build counterevidence/limits
        limits = []
        if candidate.critique:
            # Extract key issues from critique
            for line in candidate.critique.split("\n"):
                if "No issues" not in line and any(
                    kw in line for kw in ["COVERAGE", "CONFOUNDING", "WEAKEST", "violation"]
                ):
                    clean = line.strip().lstrip("0123456789. ")
                    if clean:
                        limits.append(clean[:200])
        if not limits:
            limits.append(
                f"Design covers {dm.num_runs} of "
                f"{ps.total_combinations or '?'} total combinations"
            )

        # Build what_would_change_mind
        weakest_pair = ""
        if candidate.discrimination_pairs:
            weakest = min(
                candidate.discrimination_pairs,
                key=lambda p: p.discrimination_power,
            )
            weakest_pair = (
                f"If additional evidence shows that "
                f"{weakest.hypothesis_a_id} and {weakest.hypothesis_b_id} "
                f"cannot be distinguished by the selected factor levels, "
                f"this design would need revision."
            )
        else:
            weakest_pair = (
                "If new hypotheses emerge that require different "
                "distinguishing factors, this design would need revision."
            )

        card = DecisionCard(
            recommendation=(
                f"Run {dm.num_runs} experiments using "
                f"{dm.design_family.value} design across {factor_names}, "
                f"optimized for {candidate.strategy.value}."
            ),
            why=(
                f"This {candidate.strategy.value} candidate selects "
                f"{dm.num_runs} runs from the {dm.design_family.value} family "
                f"with a discrimination score of "
                f"{candidate.total_discrimination_score:.3f}.{disc_info}"
                f"{cost_info}{citation_refs}"
            ),
            evidence_used=evidence_used if evidence_used else [
                "No grounding evidence available — explanation based on "
                "design properties only."
            ],
            assumptions=assumptions,
            counterevidence_or_limits=limits,
            what_would_change_mind=weakest_pair,
        )

        candidate.decision_card = card
        return card

    def _build_user_message(
        self,
        ps: ProblemSpace,
        candidate: ExperimentCandidate,
        grounding_results: Optional[list[dict]],
    ) -> str:
        """Assemble user message with grounding context."""
        parts = []

        # Grounding context FIRST — the most important part
        parts.append("=== GROUNDING CONTEXT ===")
        if grounding_results:
            for i, result in enumerate(grounding_results, 1):
                source = result.get("source_type", "unknown")
                citation = result.get("citation_text", "")
                content = result.get("content", "")
                parts.append(
                    f"[{i}] ({source}) {citation}\n    {content}"
                )
        else:
            parts.append(
                "(No grounding evidence available. Base your explanation "
                "on the design properties below.)"
            )
        parts.append("")

        # Problem Space context
        parts.append(f"=== OBJECTIVE ===\n{ps.objective}\n")

        parts.append("=== FACTORS ===")
        for f in ps.factors:
            levels = ", ".join(
                f"{l.name}{'*' if not l.available else ''}"
                for l in f.levels
            )
            parts.append(f"  {f.id}: {f.name} — [{levels}]")
        parts.append("")

        parts.append("=== HYPOTHESES ===")
        for h in ps.hypotheses:
            parts.append(
                f"  {h.id}: {h.statement} [{h.epistemic_state.value}]"
            )
        parts.append("")

        # Candidate details
        dm = candidate.design_matrix
        parts.append(
            f"=== CANDIDATE: {candidate.strategy.value} ===\n"
            f"Design family: {dm.design_family.value}\n"
            f"Runs: {dm.num_runs}\n"
            f"Discrimination score: {candidate.total_discrimination_score:.3f}\n"
            f"Justification: {candidate.justification}\n"
        )

        # Design matrix
        parts.append("Design matrix:")
        for i, row in enumerate(dm.rows):
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

        # Discrimination pairs
        if candidate.discrimination_pairs:
            parts.append("Discrimination pairs:")
            for pair in candidate.discrimination_pairs:
                parts.append(
                    f"  {pair.hypothesis_a_id} vs {pair.hypothesis_b_id}: "
                    f"power={pair.discrimination_power:.3f}"
                )
            parts.append("")

        # Constraint costs
        if candidate.constraint_costs:
            parts.append("Constraint costs:")
            for cost in candidate.constraint_costs:
                parts.append(f"  {cost.constraint_description}")
            parts.append("")

        # Critique (if available)
        if candidate.critique:
            parts.append(f"=== CRITIC REVIEW ===\n{candidate.critique}\n")

        return "\n".join(parts)

    @staticmethod
    def _build_decision_card(parsed: dict) -> DecisionCard:
        """Convert LLM JSON output to a DecisionCard."""
        return DecisionCard(
            recommendation=parsed.get("recommendation", ""),
            why=parsed.get("why", ""),
            evidence_used=parsed.get("evidence_used", []),
            assumptions=parsed.get("assumptions", []),
            counterevidence_or_limits=parsed.get("counterevidence_or_limits", []),
            what_would_change_mind=parsed.get("what_would_change_mind", ""),
        )


# ─── Standalone test ─────────────────────────────────────────────────────────

def test_explainer_offline():
    """
    Test the Explainer Agent WITHOUT calling Azure OpenAI.
    Uses mock grounding results and the offline explain method.
    """
    from app.models.problem_space import (
        Factor, Level, Hypothesis, Evidence, Constraint,
        EpistemicState, DesignMatrix, DiscriminationPair,
        CandidateStrategy, DesignFamily,
    )

    print("=" * 70)
    print("TESSELLARIUM — Explainer Agent Offline Test")
    print("=" * 70)

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
        ],
        hypotheses=[
            Hypothesis(
                id="H1", statement="Temperature drift causes yield drop",
                epistemic_state=EpistemicState.SPECULATIVE,
                distinguishing_factors=["temp"],
            ),
            Hypothesis(
                id="H2", statement="Lot C is degraded",
                epistemic_state=EpistemicState.SUPPORTED,
                distinguishing_factors=["lot"],
            ),
        ],
        constraints=[
            Constraint(
                id="C1", description="Lot C exhausted",
                constraint_type="material_unavailable",
                excluded_factor_id="lot", excluded_level_id="lotC",
            ),
        ],
        max_runs_budget=4,
        total_combinations=12,
    )

    candidate = ExperimentCandidate(
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
                hypothesis_a_id="H1", hypothesis_b_id="H2",
                discriminating_combinations=[
                    {"temp": "t20", "lot": "lotB"},
                    {"temp": "t30", "lot": "lotB"},
                ],
                discrimination_power=0.5,
            ),
        ],
        total_discrimination_score=0.5,
        justification="Selected 4 runs for max discrimination.",
        critique="4. COVERAGE GAPS: H1 vs H2 power is 0.500 — moderate.",
    )

    # Mock grounding results from SearchService
    mock_grounding = [
        {
            "id": "test-001-evidence-E1",
            "content": "Yield dropped 15% in last 3 batches (all used lot C at 30°C)",
            "citation_text": "E1 [csv_analysis]: Yield dropped 15% in last 3 batches — protocol-RSA-2026.pdf",
            "source_type": "evidence",
            "confidence": 0.7,
            "score": 0.95,
        },
        {
            "id": "test-001-hypothesis-H2",
            "content": "Hypothesis H2: Lot C is degraded. State: supported.",
            "citation_text": "H2: Lot C is degraded [supported] — protocol-RSA-2026.pdf",
            "source_type": "protocol",
            "confidence": 0.8,
            "score": 0.88,
        },
        {
            "id": "test-001-constraint-C1",
            "content": "Lot C exhausted. Type: material_unavailable.",
            "citation_text": "Constraint C1: Lot C exhausted — protocol-RSA-2026.pdf",
            "source_type": "protocol",
            "confidence": 1.0,
            "score": 0.82,
        },
    ]

    # Run offline explanation
    agent = ExplainerAgent.__new__(ExplainerAgent)
    card = agent.explain_offline(ps, candidate, mock_grounding)

    print(f"\n📋 Recommendation: {card.recommendation}")
    print(f"\n📝 Why: {card.why}")
    print(f"\n📄 Evidence used:")
    for e in card.evidence_used:
        print(f"   {e}")
    print(f"\n⚠️  Assumptions:")
    for a in card.assumptions:
        print(f"   - {a}")
    print(f"\n🔍 Limits:")
    for l in card.counterevidence_or_limits:
        print(f"   - {l}")
    print(f"\n🔄 What would change mind: {card.what_would_change_mind}")

    # Verify structure
    assert card.recommendation, "recommendation must not be empty"
    assert card.why, "why must not be empty"
    assert len(card.evidence_used) > 0, "must have evidence"
    assert len(card.assumptions) > 0, "must have assumptions"
    assert len(card.counterevidence_or_limits) > 0, "must have limits"
    assert card.what_would_change_mind, "must have change condition"
    assert candidate.decision_card is card

    # Verify grounding citations are present
    assert "[1]" in card.why or "[1]" in card.evidence_used[0]
    assert "evidence" in card.evidence_used[0].lower() or "csv" in card.evidence_used[0].lower()

    print(f"\n{'=' * 70}")
    print("EXPLAINER AGENT OFFLINE TEST PASSED ✅")
    print("=" * 70)


if __name__ == "__main__":
    test_explainer_offline()
