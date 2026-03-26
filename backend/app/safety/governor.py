"""
Tessellarium — Safety Governor

Deterministic policy engine. No LLM calls.
Takes Content Safety signals + domain rules → outputs constraints for DOE Planner.

The key insight: safety is NOT a filter on the output.
Safety is a CONSTRAINT on the input to the compiler.
Dangerous regions are excluded from the search space BEFORE compilation.
"""

import re
from typing import Optional

from app.models.problem_space import (
    ProblemSpace, Constraint, SafetyVerdict, Factor, Hypothesis,
)


# ─── Domain-specific safety patterns ────────────────────────────────────────

CLINICAL_PATTERNS = [
    r"\b(diagnos|prescri|dosag|dosing|patient|treatment\s+plan)\b",
    r"\b(administer|inject|infuse|transfuse)\b",
    r"\b(clinical\s+trial|phase\s+[I1-3]|human\s+subject)\b",
    r"\b(drug|medication|therapeutic|pharmacol)\b",
    r"\b(symptom|prognosis|pathology|etiology)\b",
]

BIO_HAZARD_PATTERNS = [
    r"\b(biosafety\s+level|BSL-[2-4]|containment)\b",
    r"\b(pathogen|infectious|contagious|virulent)\b",
    r"\b(toxin|carcinogen|mutagen|teratogen)\b",
    r"\b(gene\s+edit|CRISPR|gene\s+therapy|viral\s+vector)\b",
    r"\b(radioactiv|ionizing|irradiat)\b",
]

DISALLOWED_ADVISORY_PATTERNS = [
    r"\b(should\s+I|recommend|advise|suggest)\s+(tak|us|administer|prescri)",
    r"\b(what\s+(dose|amount|concentration))\s+(should|would|to\s+give)\b",
    r"\b(is\s+it\s+safe\s+to|can\s+I\s+safely)\b",
]


class SafetyGovernor:
    """
    Analyzes the ProblemSpace and user queries for safety concerns.
    Converts concerns into constraints for the DOE Planner.

    Three decisions:
    - ALLOW: compile normally
    - DEGRADE: exclude sensitive region, recalculate, show cost
    - BLOCK: return evidence summary only + require human review
    """

    def __init__(self, problem_space: ProblemSpace):
        self.ps = problem_space
        self.notes: list[str] = []

    def evaluate(self, user_query: Optional[str] = None) -> SafetyVerdict:
        """
        Run all safety checks. Returns verdict and modifies ProblemSpace
        by adding safety constraints when degrading.
        """
        self.notes = []
        verdict = SafetyVerdict.ALLOW

        # Check 1: Scan factors for safety-sensitive domains
        factor_verdict = self._check_factors()
        if factor_verdict.value > verdict.value:
            verdict = factor_verdict

        # Check 2: Scan hypotheses for clinical/bio content
        hypothesis_verdict = self._check_hypotheses()
        if hypothesis_verdict.value > verdict.value:
            verdict = hypothesis_verdict

        # Check 3: Scan user query for disallowed advisory patterns
        if user_query:
            query_verdict = self._check_query(user_query)
            if query_verdict.value > verdict.value:
                verdict = query_verdict

        # Check 4: Scan protocol objective
        objective_verdict = self._check_objective()
        if objective_verdict.value > verdict.value:
            verdict = objective_verdict

        self.ps.safety_verdict = verdict
        self.ps.safety_notes = self.notes

        return verdict

    def _check_factors(self) -> SafetyVerdict:
        """Check if any factors are in safety-sensitive domains."""
        verdict = SafetyVerdict.ALLOW

        for factor in self.ps.factors:
            factor_text = f"{factor.name} {' '.join(l.name for l in factor.levels)}"

            if self._matches_patterns(factor_text, CLINICAL_PATTERNS):
                factor.is_safety_sensitive = True
                self.notes.append(
                    f"Factor '{factor.name}' involves clinical domain. "
                    f"Excluding from experimental space — system will not "
                    f"recommend clinical interventions."
                )
                # DEGRADE: add constraint to exclude this factor
                self.ps.constraints.append(Constraint(
                    description=f"Safety exclusion: factor '{factor.name}' is in clinical domain",
                    constraint_type="safety_exclusion",
                    excluded_factor_id=factor.id,
                    is_safety_constraint=True,
                ))
                verdict = SafetyVerdict.DEGRADE

            if self._matches_patterns(factor_text, BIO_HAZARD_PATTERNS):
                factor.is_safety_sensitive = True
                self.notes.append(
                    f"Factor '{factor.name}' involves biological hazards. "
                    f"Requires documented safety controls before inclusion."
                )
                # Only degrade, don't block — researcher may have controls
                if verdict == SafetyVerdict.ALLOW:
                    verdict = SafetyVerdict.DEGRADE

        return verdict

    def _check_hypotheses(self) -> SafetyVerdict:
        """Check if hypotheses involve clinical decision-making."""
        verdict = SafetyVerdict.ALLOW

        for hypothesis in self.ps.hypotheses:
            if self._matches_patterns(hypothesis.statement, CLINICAL_PATTERNS):
                self.notes.append(
                    f"Hypothesis '{hypothesis.statement[:80]}...' involves "
                    f"clinical content. System will provide evidence summary "
                    f"only, not actionable recommendations."
                )
                if self._matches_patterns(
                    hypothesis.statement, DISALLOWED_ADVISORY_PATTERNS
                ):
                    verdict = SafetyVerdict.BLOCK
                elif verdict == SafetyVerdict.ALLOW:
                    verdict = SafetyVerdict.DEGRADE

        return verdict

    def _check_query(self, query: str) -> SafetyVerdict:
        """Check user's natural language query for disallowed patterns."""
        if self._matches_patterns(query, DISALLOWED_ADVISORY_PATTERNS):
            self.notes.append(
                "Query contains a request for clinical/therapeutic advice. "
                "Tessellarium cannot provide actionable medical recommendations. "
                "Returning evidence summary with mandatory human review."
            )
            return SafetyVerdict.BLOCK

        if self._matches_patterns(query, CLINICAL_PATTERNS):
            self.notes.append(
                "Query involves clinical domain. "
                "Recommendations will exclude clinical factors and show "
                "what discrimination capability is lost."
            )
            return SafetyVerdict.DEGRADE

        if self._matches_patterns(query, BIO_HAZARD_PATTERNS):
            self.notes.append(
                "Query involves biological hazards. "
                "Ensure appropriate biosafety controls are documented."
            )
            return SafetyVerdict.DEGRADE

        return SafetyVerdict.ALLOW

    def _check_objective(self) -> SafetyVerdict:
        """Check the experimental objective."""
        obj = self.ps.objective
        if not obj:
            return SafetyVerdict.ALLOW

        if self._matches_patterns(obj, DISALLOWED_ADVISORY_PATTERNS):
            self.notes.append(
                "Experimental objective contains advisory language. "
                "Tessellarium designs experiments, it does not advise "
                "on clinical interventions."
            )
            return SafetyVerdict.BLOCK

        return SafetyVerdict.ALLOW

    @staticmethod
    def _matches_patterns(text: str, patterns: list[str]) -> bool:
        """Check if text matches any of the given regex patterns."""
        text_lower = text.lower()
        return any(re.search(p, text_lower) for p in patterns)

    def get_degradation_report(self) -> dict:
        """
        When verdict is DEGRADE, report what was excluded and what
        discrimination is lost. Called AFTER DOE Planner runs.
        """
        excluded_factors = [
            f for f in self.ps.factors if f.is_safety_sensitive
        ]
        safety_constraints = [
            c for c in self.ps.constraints if c.is_safety_constraint
        ]

        return {
            "verdict": self.ps.safety_verdict.value,
            "excluded_factors": [
                {"id": f.id, "name": f.name} for f in excluded_factors
            ],
            "safety_constraints": [
                {"description": c.description} for c in safety_constraints
            ],
            "notes": self.notes,
            "message": (
                "Some experimental regions have been excluded for safety. "
                "The DOE Planner compiled the best plan within safe boundaries. "
                "Constraint costs show what discrimination was lost."
                if self.ps.safety_verdict == SafetyVerdict.DEGRADE
                else "Query blocked. Evidence summary provided for human review."
                if self.ps.safety_verdict == SafetyVerdict.BLOCK
                else "All clear."
            ),
        }
