"""
Tessellarium — Lean Verification Service Models
"""

from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


class VerificationStatus(str, Enum):
    VERIFIED = "verified"
    FAILED = "failed"
    TIMEOUT = "timeout"
    NOT_ATTEMPTED = "not_attempted"


class VerificationRequest(BaseModel):
    """Request to verify a design matrix property."""
    design_matrix: list[dict[str, str]]
    design_family: str  # "covering_array", "latin_square", "bibd"
    property_to_verify: str  # "pairwise_coverage", "bijectivity", "balance"
    strength: int = 2  # for covering arrays
    lambda_val: int = 1  # for BIBD
    timeout_seconds: int = Field(default=30, ge=1, le=120)


class VerificationResponse(BaseModel):
    """Result of verification."""
    status: VerificationStatus
    property_verified: str
    proof_time_ms: int = 0
    details: Optional[str] = None
    counterexample: Optional[dict] = None
