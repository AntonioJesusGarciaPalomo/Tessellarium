"""
Tessellarium — Parser Agent

Takes raw text from protocols, CSV analysis, and image observations,
and structures them into a ProblemSpace JSON.

This is the ONLY place where the LLM interprets experimental content.
The LLM never generates the experimental design — that's the DOE Planner's job.
The Parser Agent's sole responsibility is: unstructured → structured.
"""

import json
import os
from typing import Optional

from app.models.problem_space import (
    ProblemSpace, Factor, Level, Hypothesis, Evidence,
    ExperimentalRun, Constraint, EpistemicState, OperativeState,
)
from app.agents.foundry_client import AgentBase, get_foundry_client


PARSER_SYSTEM_PROMPT = """You are the Parser Agent of Tessellarium, a decisive experiment compiler.

Your ONLY job is to extract structured experimental information from raw text.
You do NOT suggest experiments. You do NOT give advice. You do NOT interpret results.
You ONLY extract and structure.

Given raw input (protocol text, CSV analysis, image observations, or any combination),
extract the following and return ONLY valid JSON with no markdown formatting:

{
  "objective": "The stated experimental objective in one sentence",
  "factors": [
    {
      "name": "Factor name",
      "levels": [
        {"name": "Level name", "value": "Optional numeric/coded value", "available": true}
      ],
      "is_blocking_factor": false,
      "is_safety_sensitive": false
    }
  ],
  "hypotheses": [
    {
      "statement": "Clear hypothesis statement",
      "epistemic_state": "speculative|supported|challenged|inconclusive",
      "operative_state": "proposed|designed|in_execution|analyzed|replicated|archived",
      "distinguishing_factors": ["factor_name_1"],
      "evidence_ids": []
    }
  ],
  "evidence": [
    {
      "source_type": "protocol_text|csv_analysis|image_observation",
      "content": "What was observed or stated",
      "supports_hypotheses": ["H1"],
      "challenges_hypotheses": [],
      "confidence": 0.0 to 1.0
    }
  ],
  "constraints": [
    {
      "description": "What is constrained and why",
      "constraint_type": "material_unavailable|safety_exclusion|budget|equipment|time",
      "excluded_factor_id": null,
      "excluded_level_id": null,
      "is_safety_constraint": false
    }
  ],
  "completed_runs": [
    {
      "combination": {"factor_name": "level_name"},
      "result_summary": "Brief result"
    }
  ],
  "max_runs_budget": null
}

RULES:
1. Extract ONLY what is explicitly stated or directly implied in the input.
2. Do NOT invent hypotheses that aren't mentioned or implied.
3. Do NOT infer results that aren't in the data.
4. If the input mentions competing explanations, extract them as separate hypotheses.
5. For each hypothesis, identify which factors would distinguish it from others (distinguishing_factors).
6. Mark evidence as supporting or challenging specific hypotheses based on what the text says.
7. If a material, reagent, or resource is mentioned as unavailable or depleted, add it as a constraint.
8. If safety concerns are mentioned (biological hazards, clinical applications, toxic materials), mark relevant factors as is_safety_sensitive: true.
9. Set epistemic_state based on the evidence: "speculative" if no evidence, "supported" if evidence in favor, "challenged" if evidence against, "inconclusive" if mixed.
10. Use factor NAMES (not IDs) in completed_runs combinations and distinguishing_factors — the system will resolve IDs later.
11. Assign hypothesis labels as H1, H2, H3, etc. in the order they appear.
12. Return ONLY the JSON object. No explanation, no markdown, no commentary."""


class ParserAgent(AgentBase):
    """
    Structures raw experimental input into a ProblemSpace.
    Uses Azure OpenAI GPT-4o for interpretation.

    Foundry agent name: tessellarium-parser
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

    async def parse(
        self,
        protocol_text: Optional[str] = None,
        csv_analysis: Optional[str] = None,
        image_observations: Optional[str] = None,
        user_context: Optional[str] = None,
        max_runs_budget: Optional[int] = None,
    ) -> ProblemSpace:
        """
        Parse raw inputs into a structured ProblemSpace.

        Args:
            protocol_text: Extracted text from the protocol PDF
            csv_analysis: Summary of CSV analysis from Code Interpreter
            image_observations: Observations from GPT-4o vision
            user_context: Additional context from the researcher
            max_runs_budget: Maximum number of experimental runs allowed

        Returns:
            A structured ProblemSpace ready for the DOE Planner
        """
        # Build the user message from available inputs
        user_message = self._build_user_message(
            protocol_text, csv_analysis, image_observations,
            user_context, max_runs_budget,
        )

        # Call GPT-4o (via Foundry or direct)
        raw_json = await self._call_llm(
            system_prompt=PARSER_SYSTEM_PROMPT,
            user_message=user_message,
            temperature=0.1,
            max_tokens=4000,
            response_format={"type": "json_object"},
        )

        parsed = json.loads(raw_json)
        problem_space = self._build_problem_space(parsed, max_runs_budget)

        return problem_space

    def parse_sync(
        self,
        protocol_text: Optional[str] = None,
        csv_analysis: Optional[str] = None,
        image_observations: Optional[str] = None,
        user_context: Optional[str] = None,
        max_runs_budget: Optional[int] = None,
    ) -> ProblemSpace:
        """Synchronous version for testing (direct mode only)."""
        user_message = self._build_user_message(
            protocol_text, csv_analysis, image_observations,
            user_context, max_runs_budget,
        )

        raw_json = self._call_llm_sync(
            system_prompt=PARSER_SYSTEM_PROMPT,
            user_message=user_message,
            temperature=0.1,
            max_tokens=4000,
            response_format={"type": "json_object"},
        )

        parsed = json.loads(raw_json)
        return self._build_problem_space(parsed, max_runs_budget)

    def _build_user_message(
        self,
        protocol_text: Optional[str],
        csv_analysis: Optional[str],
        image_observations: Optional[str],
        user_context: Optional[str],
        max_runs_budget: Optional[int],
    ) -> str:
        """Assemble the user message from available inputs."""
        parts = []

        if protocol_text:
            parts.append(
                f"=== EXPERIMENTAL PROTOCOL ===\n{protocol_text}\n"
            )

        if csv_analysis:
            parts.append(
                f"=== CSV DATA ANALYSIS ===\n{csv_analysis}\n"
            )

        if image_observations:
            parts.append(
                f"=== IMAGE OBSERVATIONS ===\n{image_observations}\n"
            )

        if user_context:
            parts.append(
                f"=== RESEARCHER'S ADDITIONAL CONTEXT ===\n{user_context}\n"
            )

        if max_runs_budget:
            parts.append(
                f"=== BUDGET CONSTRAINT ===\n"
                f"Maximum number of additional experimental runs: {max_runs_budget}\n"
            )

        if not parts:
            raise ValueError("At least one input (protocol, CSV, image, or context) is required")

        return "\n".join(parts)

    def _build_problem_space(
        self,
        parsed: dict,
        max_runs_budget: Optional[int],
    ) -> ProblemSpace:
        """
        Convert the LLM's JSON output to a proper ProblemSpace with
        consistent IDs and cross-references.
        """
        # Build factors with stable IDs
        factors = []
        factor_name_to_id = {}
        level_name_to_id = {}  # (factor_name, level_name) → level_id

        for i, f_data in enumerate(parsed.get("factors", [])):
            factor_id = f"F{i+1}"
            factor_name = f_data["name"]
            factor_name_to_id[factor_name] = factor_id

            levels = []
            for j, l_data in enumerate(f_data.get("levels", [])):
                level_id = f"F{i+1}L{j+1}"
                level_name = l_data["name"] if isinstance(l_data, dict) else str(l_data)
                level_name_to_id[(factor_name, level_name)] = level_id

                levels.append(Level(
                    id=level_id,
                    name=level_name,
                    value=l_data.get("value") if isinstance(l_data, dict) else None,
                    available=l_data.get("available", True) if isinstance(l_data, dict) else True,
                ))

            factors.append(Factor(
                id=factor_id,
                name=factor_name,
                levels=levels,
                is_blocking_factor=f_data.get("is_blocking_factor", False),
                is_safety_sensitive=f_data.get("is_safety_sensitive", False),
            ))

        # Build hypotheses with stable IDs
        hypotheses = []
        hypothesis_label_to_id = {}

        for i, h_data in enumerate(parsed.get("hypotheses", [])):
            h_id = f"H{i+1}"
            hypothesis_label_to_id[f"H{i+1}"] = h_id
            # Also map by statement prefix for evidence linking
            hypothesis_label_to_id[h_data.get("statement", "")[:40]] = h_id

            # Resolve distinguishing factor names to IDs
            dist_factors = []
            for fname in h_data.get("distinguishing_factors", []):
                if fname in factor_name_to_id:
                    dist_factors.append(factor_name_to_id[fname])
                else:
                    # Try partial match
                    for key, fid in factor_name_to_id.items():
                        if fname.lower() in key.lower() or key.lower() in fname.lower():
                            dist_factors.append(fid)
                            break

            hypotheses.append(Hypothesis(
                id=h_id,
                statement=h_data.get("statement", ""),
                epistemic_state=EpistemicState(
                    h_data.get("epistemic_state", "speculative")
                ),
                operative_state=OperativeState(
                    h_data.get("operative_state", "proposed")
                ),
                distinguishing_factors=dist_factors,
            ))

        # Build evidence with stable IDs and resolved hypothesis references
        evidence_list = []
        for i, e_data in enumerate(parsed.get("evidence", [])):
            e_id = f"E{i+1}"

            supports = self._resolve_hypothesis_refs(
                e_data.get("supports_hypotheses", []),
                hypothesis_label_to_id,
            )
            challenges = self._resolve_hypothesis_refs(
                e_data.get("challenges_hypotheses", []),
                hypothesis_label_to_id,
            )

            evidence_list.append(Evidence(
                id=e_id,
                source_type=e_data.get("source_type", "protocol_text"),
                content=e_data.get("content", ""),
                supports_hypotheses=supports,
                challenges_hypotheses=challenges,
                confidence=float(e_data.get("confidence", 0.5)),
            ))

            # Link evidence back to hypotheses
            for h_id in supports + challenges:
                for h in hypotheses:
                    if h.id == h_id and e_id not in h.evidence_ids:
                        h.evidence_ids.append(e_id)

        # Build constraints
        constraints = []
        for i, c_data in enumerate(parsed.get("constraints", [])):
            excluded_factor_id = None
            excluded_level_id = None

            # Resolve factor/level names to IDs
            if c_data.get("excluded_factor_id"):
                fname = c_data["excluded_factor_id"]
                excluded_factor_id = factor_name_to_id.get(fname, fname)

            if c_data.get("excluded_level_id"):
                lname = c_data["excluded_level_id"]
                # Try to find the level ID
                for (fn, ln), lid in level_name_to_id.items():
                    if ln == lname or lname in ln:
                        excluded_level_id = lid
                        if not excluded_factor_id:
                            excluded_factor_id = factor_name_to_id.get(fn)
                        break

            constraints.append(Constraint(
                id=f"C{i+1}",
                description=c_data.get("description", ""),
                constraint_type=c_data.get("constraint_type", "equipment"),
                excluded_factor_id=excluded_factor_id,
                excluded_level_id=excluded_level_id,
                is_safety_constraint=c_data.get("is_safety_constraint", False),
            ))

        # Build completed runs
        completed_runs = []
        for i, r_data in enumerate(parsed.get("completed_runs", [])):
            combo = {}
            raw_combo = r_data.get("combination", {})
            for fname, lname in raw_combo.items():
                fid = factor_name_to_id.get(fname, fname)
                lid = level_name_to_id.get((fname, lname))
                if lid is None:
                    # Try partial match
                    for (fn, ln), l_id in level_name_to_id.items():
                        if fn == fname and (lname in ln or ln in lname):
                            lid = l_id
                            break
                if lid is None:
                    lid = lname  # Fallback to raw name
                combo[fid] = lid

            completed_runs.append(ExperimentalRun(
                id=f"R{i+1}",
                combination=combo,
                result_summary=r_data.get("result_summary"),
            ))

        # Assemble ProblemSpace
        ps = ProblemSpace(
            objective=parsed.get("objective", ""),
            factors=factors,
            hypotheses=hypotheses,
            evidence=evidence_list,
            constraints=constraints,
            completed_runs=completed_runs,
            max_runs_budget=max_runs_budget or parsed.get("max_runs_budget"),
        )

        return ps

    @staticmethod
    def _resolve_hypothesis_refs(
        refs: list[str],
        label_to_id: dict[str, str],
    ) -> list[str]:
        """Resolve hypothesis labels (H1, H2) to internal IDs."""
        resolved = []
        for ref in refs:
            ref_clean = ref.strip()
            if ref_clean in label_to_id:
                resolved.append(label_to_id[ref_clean])
            else:
                # Try as-is (might already be an ID)
                resolved.append(ref_clean)
        return resolved


# ─── Standalone test ─────────────────────────────────────────────────────────

def test_parser_offline():
    """
    Test the Parser Agent WITHOUT calling Azure OpenAI.
    Simulates what the LLM would return and tests the structuring logic.
    """
    print("=" * 70)
    print("TESSELLARIUM — Parser Agent Offline Test")
    print("=" * 70)

    # Simulated LLM output (what GPT-4o would return)
    simulated_llm_output = {
        "objective": "Determine root cause of yield drop in recent batches",
        "factors": [
            {
                "name": "Temperature",
                "levels": [
                    {"name": "20°C", "value": "20", "available": True},
                    {"name": "30°C", "value": "30", "available": True},
                    {"name": "40°C", "value": "40", "available": True},
                ],
                "is_blocking_factor": False,
                "is_safety_sensitive": False,
            },
            {
                "name": "Reagent Lot",
                "levels": [
                    {"name": "Lot A", "available": True},
                    {"name": "Lot B", "available": True},
                    {"name": "Lot C", "available": True},
                ],
                "is_blocking_factor": False,
                "is_safety_sensitive": False,
            },
            {
                "name": "Incubation Time",
                "levels": [
                    {"name": "1 hour", "value": "1", "available": True},
                    {"name": "2 hours", "value": "2", "available": True},
                ],
                "is_blocking_factor": False,
                "is_safety_sensitive": False,
            },
        ],
        "hypotheses": [
            {
                "statement": "Temperature drift above 30°C causes yield drop",
                "epistemic_state": "speculative",
                "operative_state": "proposed",
                "distinguishing_factors": ["Temperature"],
            },
            {
                "statement": "Reagent lot C is degraded and causes yield drop",
                "epistemic_state": "supported",
                "operative_state": "proposed",
                "distinguishing_factors": ["Reagent Lot"],
            },
            {
                "statement": "Insufficient incubation time reduces yield",
                "epistemic_state": "speculative",
                "operative_state": "proposed",
                "distinguishing_factors": ["Incubation Time"],
            },
        ],
        "evidence": [
            {
                "source_type": "csv_analysis",
                "content": "Yield dropped 15% in last 3 batches, all used lot C at 30°C",
                "supports_hypotheses": ["H2"],
                "challenges_hypotheses": [],
                "confidence": 0.6,
            },
            {
                "source_type": "protocol_text",
                "content": "Protocol specifies 30°C ± 2°C; lab logs show 28-33°C range",
                "supports_hypotheses": ["H1"],
                "challenges_hypotheses": [],
                "confidence": 0.4,
            },
            {
                "source_type": "image_observation",
                "content": "Gel image shows weaker bands in lanes 3-5 (lot C samples)",
                "supports_hypotheses": ["H2"],
                "challenges_hypotheses": [],
                "confidence": 0.7,
            },
        ],
        "constraints": [],
        "completed_runs": [
            {"combination": {"Temperature": "20°C", "Reagent Lot": "Lot A", "Incubation Time": "1 hour"}, "result_summary": "Yield: 92%"},
            {"combination": {"Temperature": "30°C", "Reagent Lot": "Lot A", "Incubation Time": "1 hour"}, "result_summary": "Yield: 90%"},
            {"combination": {"Temperature": "30°C", "Reagent Lot": "Lot C", "Incubation Time": "1 hour"}, "result_summary": "Yield: 74%"},
            {"combination": {"Temperature": "40°C", "Reagent Lot": "Lot C", "Incubation Time": "2 hours"}, "result_summary": "Yield: 68%"},
        ],
        "max_runs_budget": 4,
    }

    # Test the structuring logic (no LLM call)
    agent = ParserAgent.__new__(ParserAgent)
    ps = agent._build_problem_space(simulated_llm_output, max_runs_budget=4)

    print(f"\n📋 Objective: {ps.objective}")
    print(f"\n📊 Factors ({len(ps.factors)}):")
    for f in ps.factors:
        print(f"   {f.id}: {f.name}")
        for l in f.levels:
            print(f"      {l.id}: {l.name} (available: {l.available})")

    print(f"\n🔬 Hypotheses ({len(ps.hypotheses)}):")
    for h in ps.hypotheses:
        print(f"   {h.id}: {h.statement}")
        print(f"      State: {h.epistemic_state.value} / {h.operative_state.value}")
        print(f"      Distinguishing factors: {h.distinguishing_factors}")
        print(f"      Evidence: {h.evidence_ids}")

    print(f"\n📄 Evidence ({len(ps.evidence)}):")
    for e in ps.evidence:
        print(f"   {e.id} [{e.source_type}]: {e.content[:60]}...")
        print(f"      Supports: {e.supports_hypotheses}, Challenges: {e.challenges_hypotheses}")

    print(f"\n✅ Completed runs ({len(ps.completed_runs)}):")
    for r in ps.completed_runs:
        print(f"   {r.id}: {r.combination} → {r.result_summary}")

    print(f"\n💰 Budget: {ps.max_runs_budget}")

    # Verify the structured output works with DOE Planner
    from app.doe_planner.planner import DOEPlanner
    planner = DOEPlanner(ps)
    candidates = planner.compile()

    print(f"\n{'─' * 70}")
    print(f"DOE Planner compiled {len(candidates)} candidates from Parser output:")
    for c in candidates:
        print(f"   {c.strategy.value}: {c.design_matrix.num_runs} runs, "
              f"score={c.total_discrimination_score}")

    print(f"\n{'=' * 70}")
    print("PARSER → PLANNER PIPELINE TEST PASSED ✅")
    print("=" * 70)


if __name__ == "__main__":
    test_parser_offline()
