"""
Tessellarium — Core Data Models

The Problem Space is the central data structure of Tessellarium.
Everything flows through it:
- Content Understanding extracts INTO it
- Parser Agent structures it
- Safety Governor constrains it
- DOE Planner compiles FROM it
- Explainer Agent explains it
- Frontend renders it
"""

from __future__ import annotations
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field
from datetime import datetime, timezone
import uuid


# ─── Enums ───────────────────────────────────────────────────────────────────

class EpistemicState(str, Enum):
    SPECULATIVE = "speculative"
    SUPPORTED = "supported"
    CHALLENGED = "challenged"
    INCONCLUSIVE = "inconclusive"


class OperativeState(str, Enum):
    PROPOSED = "proposed"
    DESIGNED = "designed"
    IN_EXECUTION = "in_execution"
    ANALYZED = "analyzed"
    REPLICATED = "replicated"
    ARCHIVED = "archived"


class SafetyVerdict(str, Enum):
    ALLOW = "allow"
    DEGRADE = "degrade"
    BLOCK = "block"


class DesignFamily(str, Enum):
    FULL_FACTORIAL = "full_factorial"
    FRACTIONAL_FACTORIAL = "fractional_factorial"
    LATIN_SQUARE = "latin_square"
    BIBD = "bibd"
    ORTHOGONAL_ARRAY = "orthogonal_array"
    COVERING_ARRAY = "covering_array"
    CUSTOM = "custom"


class CandidateStrategy(str, Enum):
    MAX_DISCRIMINATION = "max_discrimination"
    MAX_ROBUSTNESS = "max_robustness"
    MAX_COVERAGE = "max_coverage"


class VerificationStatus(str, Enum):
    VERIFIED = "verified"
    FAILED = "failed"
    TIMEOUT = "timeout"
    NOT_ATTEMPTED = "not_attempted"


# ─── Factor & Level ──────────────────────────────────────────────────────────

class Level(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    name: str
    value: Optional[str] = None
    available: bool = True


class Factor(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    name: str
    levels: list[Level]
    is_blocking_factor: bool = False
    is_safety_sensitive: bool = False


# ─── Hypothesis & Evidence ───────────────────────────────────────────────────

class Evidence(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    source_type: str  # "protocol_text", "csv_analysis", "image_observation"
    content: str
    supports_hypotheses: list[str] = []
    challenges_hypotheses: list[str] = []
    confidence: float = Field(ge=0.0, le=1.0, default=0.5)
    source_reference: Optional[str] = None


class Hypothesis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    statement: str
    epistemic_state: EpistemicState = EpistemicState.SPECULATIVE
    operative_state: OperativeState = OperativeState.PROPOSED
    evidence_ids: list[str] = []
    parent_id: Optional[str] = None
    distinguishing_factors: list[str] = []  # Factor IDs that differentiate this hypothesis


# ─── Constraints ─────────────────────────────────────────────────────────────

class Constraint(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    description: str
    constraint_type: str  # "material_unavailable", "safety_exclusion", "budget", "equipment"
    excluded_factor_id: Optional[str] = None
    excluded_level_id: Optional[str] = None
    excluded_combinations: list[dict[str, str]] = []
    is_safety_constraint: bool = False
    discrimination_cost: Optional[str] = None


# ─── Experimental Run ────────────────────────────────────────────────────────

class ExperimentalRun(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    combination: dict[str, str]  # {factor_id: level_id}
    result_summary: Optional[str] = None
    evidence_ids: list[str] = []


# ─── DOE Planner Output ─────────────────────────────────────────────────────

class DesignMatrix(BaseModel):
    rows: list[dict[str, str]]
    num_runs: int
    design_family: DesignFamily
    design_properties: dict = {}
    design_source: str = "greedy"
    d_efficiency: Optional[float] = None
    a_efficiency: Optional[float] = None
    gwlp: Optional[list[float]] = None
    design_rank: Optional[int] = None
    verification_status: VerificationStatus = VerificationStatus.NOT_ATTEMPTED
    verification_details: Optional[str] = None


class DiscriminationPair(BaseModel):
    hypothesis_a_id: str
    hypothesis_b_id: str
    discriminating_combinations: list[dict[str, str]]
    discrimination_power: float = Field(ge=0.0, le=1.0)


class DecisionCard(BaseModel):
    recommendation: str
    why: str
    evidence_used: list[str]
    assumptions: list[str]
    counterevidence_or_limits: list[str]
    what_would_change_mind: str


class AffectedPair(BaseModel):
    pair: str
    excluded_runs: int
    total_discriminating: int
    lost_fraction: float


class ConstraintCost(BaseModel):
    constraint_id: str
    constraint_description: str
    affected_hypothesis_pairs: list[AffectedPair] = []


class ExperimentCandidate(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    strategy: CandidateStrategy
    design_matrix: DesignMatrix
    discrimination_pairs: list[DiscriminationPair]
    total_discrimination_score: float
    justification: str
    constraint_costs: list[ConstraintCost] = []
    critique: Optional[str] = None
    decision_card: Optional[DecisionCard] = None


# ─── Coverage Map ────────────────────────────────────────────────────────────

class CoverageCell(BaseModel):
    combination: dict[str, str]
    is_tested: bool = False
    run_id: Optional[str] = None
    is_discriminative_for: list[str] = []  # ["H1-vs-H2", "H1-vs-H3"]
    is_excluded: bool = False
    exclusion_reason: Optional[str] = None


# ─── The Problem Space ───────────────────────────────────────────────────────

class ProblemSpace(BaseModel):
    """
    The complete experimental problem space.
    THE central artifact of Tessellarium.
    """
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    # Extracted from protocol
    objective: str = ""
    factors: list[Factor] = []
    hypotheses: list[Hypothesis] = []
    evidence: list[Evidence] = []
    constraints: list[Constraint] = []

    # Already done
    completed_runs: list[ExperimentalRun] = []

    # Coverage
    total_combinations: int = 0
    tested_combinations: int = 0
    coverage_map: list[CoverageCell] = []

    # DOE output
    candidates: list[ExperimentCandidate] = []

    # Safety
    safety_verdict: SafetyVerdict = SafetyVerdict.ALLOW
    safety_notes: list[str] = []

    # Budget
    max_runs_budget: Optional[int] = None

    # Source files
    protocol_filename: Optional[str] = None
    csv_filename: Optional[str] = None
    image_filename: Optional[str] = None

    def get_factor_by_id(self, factor_id: str) -> Optional[Factor]:
        return next((f for f in self.factors if f.id == factor_id), None)

    def get_hypothesis_by_id(self, h_id: str) -> Optional[Hypothesis]:
        return next((h for h in self.hypotheses if h.id == h_id), None)

    def get_available_levels(self, factor_id: str) -> list[Level]:
        factor = self.get_factor_by_id(factor_id)
        if not factor:
            return []
        return [lvl for lvl in factor.levels if lvl.available]

    def get_untested_combinations(self) -> list[dict[str, str]]:
        return [
            c.combination for c in self.coverage_map
            if not c.is_tested and not c.is_excluded
        ]

    def get_discriminative_untested(self) -> list[CoverageCell]:
        return [
            c for c in self.coverage_map
            if not c.is_tested and not c.is_excluded and len(c.is_discriminative_for) > 0
        ]


# ─── API Models ──────────────────────────────────────────────────────────────

class UploadResponse(BaseModel):
    session_id: str
    problem_space: ProblemSpace


class CompileRequest(BaseModel):
    session_id: str
    new_constraints: list[Constraint] = []
    updated_budget: Optional[int] = None


class CompileResponse(BaseModel):
    session_id: str
    problem_space: ProblemSpace
    candidates: list[ExperimentCandidate]
    safety_verdict: SafetyVerdict
    safety_notes: list[str]
