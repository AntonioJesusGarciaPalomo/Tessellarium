"""
Tessellarium — Lean 4 Formal Verification Service

Receives design matrices, generates Lean 4 proofs, compiles them,
and returns VERIFIED / FAILED / TIMEOUT / NOT_ATTEMPTED.
"""

from fastapi import FastAPI
from app.models import VerificationRequest, VerificationResponse
from app.verifier import verify

app = FastAPI(
    title="Tessellarium Lean Verify",
    version="0.1.0",
    description="Formal verification of combinatorial design properties.",
)


@app.get("/health")
async def health():
    return {"status": "ok", "service": "tess-lean-verify", "version": "0.1.0"}


@app.post("/verify", response_model=VerificationResponse)
async def verify_design(request: VerificationRequest):
    """
    Verify a design matrix property using Lean 4.

    Generates a .lean file, compiles it with lake build,
    and returns the verification result.
    """
    return await verify(request)
